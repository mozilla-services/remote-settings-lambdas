import base64
import concurrent.futures
import cryptography
import hashlib
import time
from datetime import datetime

import cryptography.x509
import ecdsa
import requests
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.x509.oid import NameOID
from kinto_signer.serializer import canonical_json

from . import PARALLEL_REQUESTS, KintoClient as Client


class ValidationError(Exception):
    pass


def unpem(pem):
    # Join lines and strip -----BEGIN/END PUBLIC KEY----- header/footer
    return b"".join(
        [l.strip() for l in pem.split(b"\n") if l and not l.startswith(b"-----")]
    )


def timestamp_to_date(timestamp_milliseconds):
    timestamp_seconds = int(timestamp_milliseconds) / 1000
    return datetime.utcfromtimestamp(timestamp_seconds).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def download_collection_data(server_url, collection):
    client = Client(
        server_url=server_url,
        bucket=collection["bucket"],
        collection=collection["collection"],
    )
    endpoint = client.get_endpoint("collection")
    # Collection metadata with cache busting
    metadata = client.get_collection(_expected=collection["last_modified"])["data"]
    # Download records with cache busting
    records = client.get_records(
        _sort="-last_modified", _expected=collection["last_modified"]
    )
    timestamp = client.get_records_timestamp()
    return (collection, endpoint, metadata, records, timestamp)


def validate_signature(event, context, **kwargs):
    """Validate the signature of each collection.
    """
    server_url = event["server"]
    bucket = event.get("bucket", "monitor")
    collection = event.get("collection", "changes")
    client = Client(server_url=server_url, bucket=bucket, collection=collection)
    print("Read collection list from {}".format(client.get_endpoint("collection")))

    error_messages = []

    checked_certificates = {}

    collections = client.get_records()

    # Grab server data in parallel.
    start_time = time.time()
    collections_data = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=PARALLEL_REQUESTS
    ) as executor:
        futures = [
            executor.submit(download_collection_data, server_url, c)
            for c in collections
        ]
        for future in concurrent.futures.as_completed(futures):
            collections_data.append(future.result())
    elapsed_time = time.time() - start_time
    print(f"Downloaded all data in {elapsed_time:.2f}s")

    for i, (collection, endpoint, metadata, records, timestamp) in enumerate(
        collections_data
    ):
        start_time = time.time()

        message = "{:02d}/{:02d} {}:  ".format(i + 1, len(collections), endpoint)

        # 1. Serialize
        serialized = canonical_json(records, timestamp)
        data = b"Content-Signature:\x00" + serialized.encode("utf-8")

        # 2. Grab the signature
        try:
            signature = metadata["signature"]
        except KeyError:
            # Destination has no signature attribute.
            # Be smart and check if it was just configured.
            # See https://github.com/mozilla-services/remote-settings-lambdas/issues/31
            client = Client(
                server_url=server_url,
                bucket=collection["bucket"],
                collection=collection["collection"],
            )
            with_tombstones = client.get_records(_since=1)
            if len(with_tombstones) == 0:
                # It never contained records. Let's assume it is newly configured.
                message += "SKIP"
                print(message)
                continue
            # Some records and empty signature? It will fail below.
            signature = {}

        try:
            # 3. Verify the signature with the public key
            pubkey = signature["public_key"].encode("utf-8")
            verifier = ecdsa.VerifyingKey.from_pem(pubkey)
            signature_bytes = base64.urlsafe_b64decode(signature["signature"])
            verified = verifier.verify(signature_bytes, data, hashfunc=hashlib.sha384)
            assert verified, "Signature verification failed"

            # 4. Verify that the x5u certificate is valid (ie. that signature was well refreshed)
            x5u = signature["x5u"]
            if x5u not in checked_certificates:
                resp = requests.get(signature["x5u"])
                cert_pem = resp.text.encode("utf-8")
                cert = cryptography.x509.load_pem_x509_certificate(
                    cert_pem, crypto_default_backend()
                )
                assert (
                    cert.not_valid_before < datetime.now()
                ), "certificate not yet valid"
                assert cert.not_valid_after > datetime.now(), "certificate expired"
                subject = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[
                    0
                ].value
                # eg. ``onecrl.content-signature.mozilla.org``, or
                # ``pinning-preload.content-signature.mozilla.org``
                assert subject.endswith(
                    ".content-signature.mozilla.org"
                ), "invalid subject name"
                checked_certificates[x5u] = cert

            # 5. Check that public key matches the certificate one.
            cert = checked_certificates[x5u]
            cert_pubkey_pem = cert.public_key().public_bytes(
                crypto_serialization.Encoding.PEM,
                crypto_serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            assert (
                unpem(cert_pubkey_pem) == pubkey
            ), "signature public key does not match certificate"

            elapsed_time = time.time() - start_time
            message += f"OK ({elapsed_time:.2f}s)"
            print(message)
        except Exception:
            message += "⚠ BAD Signature ⚠"
            print(message)

            # Gather details for the global exception that will be raised.
            signed_on = metadata["last_modified"]
            signed_on_date = timestamp_to_date(signed_on)
            timestamp_date = timestamp_to_date(timestamp)
            error_message = (
                "Signature verification failed on {endpoint}\n"
                " - Signed on: {signed_on} ({signed_on_date})\n"
                " - Records timestamp: {timestamp} ({timestamp_date})"
            ).format(**locals())
            error_messages.append(error_message)

    # Make the lambda to fail in case an exception occured
    if len(error_messages) > 0:
        raise ValidationError("\n" + "\n\n".join(error_messages))
