from __future__ import print_function
import base64
import functools
import hashlib
import multiprocessing
import os
import requests
import shutil
import sys
import time
from datetime import datetime
from tempfile import mkdtemp

import boto3
import boto3.session
import cryptography
import cryptography.x509
import ecdsa
from amo2kinto.generator import main as generator_main
from botocore.exceptions import ClientError
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.x509.oid import NameOID
from kinto_http import Client, KintoException
from kinto_signer.serializer import canonical_json


def unpem(pem):
    # Join lines and strip -----BEGIN/END PUBLIC KEY----- header/footer
    return b"".join([l.strip() for l in pem.split(b"\n")
                     if l and not l.startswith(b"-----")])


class ValidationError(Exception):
    pass


class RefreshError(Exception):
    pass


def download_collection_data(server_url, collection):
    client = Client(server_url=server_url,
                    bucket=collection['bucket'],
                    collection=collection['collection'])
    endpoint = client.get_endpoint('collection')
    # Collection metadata
    metadata = client.get_collection()['data']
    # Download records with cache busting
    records = client.get_records(_sort='-last_modified',
                                 _expected=collection["last_modified"])
    timestamp = client.get_records_timestamp()
    return (collection, endpoint, metadata, records, timestamp)


def validate_signature(event, context):
    server_url = event['server']
    bucket = event.get('bucket', "monitor")
    collection = event.get('collection', "changes")
    client = Client(server_url=server_url,
                    bucket=bucket,
                    collection=collection)
    print('Read collection list from {}'.format(client.get_endpoint('collection')))

    error_messages = []

    checked_certificates = {}

    collections = client.get_records()

    # Grab server data in parallel.
    start_time = time.time()
    pool = multiprocessing.Pool(processes=3)
    collections_data = pool.map(functools.partial(download_collection_data, server_url), collections)
    pool.close()
    pool.join()
    elapsed_time = time.time() - start_time
    print(f"Downloaded all data in {elapsed_time:.2f}s")

    for i, (collection, endpoint, metadata, records, timestamp) in enumerate(collections_data):
        start_time = time.time()

        message = "{:02d}/{:02d} {}:  ".format(i + 1, len(collections), endpoint)

        # 1. Serialize
        serialized = canonical_json(records, timestamp)
        data = b'Content-Signature:\x00' + serialized.encode('utf-8')

        # 2. Grab the signature
        try:
            signature = metadata['signature']
        except KeyError:
            # Destination has no signature attribute.
            # Be smart and check if it was just configured.
            # See https://github.com/mozilla-services/remote-settings-lambdas/issues/31
            client = Client(server_url=server_url,
                            bucket=collection['bucket'],
                            collection=collection['collection'])
            with_tombstones = client.get_records(_since=1)
            if len(with_tombstones) == 0:
                # It never contained records. Let's assume it is newly configured.
                message += 'SKIP'
                print(message)
                continue
            # Some records and empty signature? It will fail below.
            signature = {}

        try:
            # 3. Verify the signature with the public key
            pubkey = signature['public_key'].encode('utf-8')
            verifier = ecdsa.VerifyingKey.from_pem(pubkey)
            signature_bytes = base64.urlsafe_b64decode(signature['signature'])
            verified = verifier.verify(signature_bytes, data, hashfunc=hashlib.sha384)
            assert verified, "Signature verification failed"

            # 4. Verify that the x5u certificate is valid (ie. that signature was well refreshed)
            x5u = signature['x5u']
            if x5u not in checked_certificates:
                resp = requests.get(signature['x5u'])
                cert_pem = resp.text.encode('utf-8')
                cert = cryptography.x509.load_pem_x509_certificate(cert_pem, crypto_default_backend())
                assert cert.not_valid_before < datetime.now(), "certificate not yet valid"
                assert cert.not_valid_after > datetime.now(), "certificate expired"
                subject = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
                # eg. onecrl.content-signature.mozilla.org, pinning-preload.content-signature.mozilla.org
                assert subject.endswith('.content-signature.mozilla.org'), "invalid subject name"
                checked_certificates[x5u] = cert

            # 5. Check that public key matches the certificate one.
            cert = checked_certificates[x5u]
            cert_pubkey_pem = cert.public_key().public_bytes(crypto_serialization.Encoding.PEM,
                                                             crypto_serialization.PublicFormat.SubjectPublicKeyInfo)
            assert unpem(cert_pubkey_pem) == pubkey, "signature public key does not match certificate"

            elapsed_time = time.time() - start_time
            message += f'OK ({elapsed_time:.2f}s)'
            print(message)
        except Exception as e:
            message += '⚠ BAD Signature ⚠'
            print(message)

            # Gather details for the global exception that will be raised.
            signed_on = metadata['last_modified']
            signed_on_date = timestamp_to_date(signed_on)
            timestamp_date = timestamp_to_date(timestamp)
            error_message = (
                'Signature verification failed on {endpoint}\n'
                ' - Signed on: {signed_on} ({signed_on_date})\n'
                ' - Records timestamp: {timestamp} ({timestamp_date})'
            ).format(**locals())
            error_messages.append(error_message)

    # Make the lambda to fail in case an exception occured
    if len(error_messages) > 0:
        raise ValidationError("\n" + "\n\n".join(error_messages))


def validate_changes_collection(event, context):
    # 1. Grab the changes collection
    server_url = event['server']
    bucket = event.get('bucket', "monitor")
    collection = event.get('collection', "changes")
    client = Client(server_url=server_url,
                    bucket=bucket,
                    collection=collection)
    print('Looking at %s: ' % client.get_endpoint('collection'))

    collections = client.get_records()
    # 2. For each collection there, validate the ETag
    everything_ok = True
    for collection in collections:
        bid = collection["bucket"]
        cid = collection["collection"]
        last_modified = collection["last_modified"]
        etag = client.get_records_timestamp(bucket=bid, collection=cid)
        if str(etag) == str(last_modified):
            print("Etag OK for {}/{} : {}".format(bid, cid, etag))
        else:
            everything_ok = False
            print("Etag NOT OK for {}/{} : {} != {}".format(bid, cid, last_modified, etag))

    if not everything_ok:
        raise ValueError("One of the collection did not validate.")


def copy_records(event, context):
    """
    Note: This lambda is not safe if other user can interact with the destination
    collection.
    """
    source_server_url = event['server']
    source_auth = tuple(os.getenv("COPY_RECORDS_AUTH").split(':', 1))
    source_bucket = os.env['COPY_RECORDS_SOURCE_BUCKET']
    source_collection = os.env['COPY_RECORDS_DEST_COLLECTION']

    dest_server_url = os.getenv('COPY_RECORDS_DEST_SERVER', source_server_url)
    dest_auth = tuple(os.getenv("COPY_RECORDS_DEST_AUTH").split(':', 1), source_auth)
    dest_bucket = os.getenv('COPY_RECORDS_DEST_BUCKET', source_bucket)
    dest_collection = os.getenv('COPY_RECORDS_DEST_COLLECTION', source_collection)

    if source_bucket == dest_bucket and source_collection == dest_collection:
        raise ValueError("Cannot copy records: destination is identical to source")

    source_client = Client(server_url=source_server_url,
                           bucket=source_bucket,
                           collection=source_collection,
                           auth=source_auth)
    dest_client = Client(server_url=dest_server_url,
                         bucket=dest_bucket,
                         collection=dest_collection,
                         auth=dest_auth)

    source_timestamp = source_client.get_records_timestamp()
    dest_timestamp = dest_client.get_records_timestamp()
    if source_timestamp == dest_timestamp:
        print("Records are in sync. Nothing to do.")

    source_records = source_client.get_records()
    dest_records_by_id = {r["id"]: r for r in dest_client.get_records()}

    with dest_client.batch() as dest_batch:
        # Create or update the destination records.
        for r in source_records:
            dest_record = dest_records_by_id.pop(r["id"], None)
            if dest_record is None or r["last_modified"] > dest_record["last_modified"]:
                dest_batch.update_record(data=r)
        # Delete the records missing from source.
        for r in dest_records_by_id.values():
            dest_batch.delete_record(id=r["id"])

    ops_count = len(dest_batch.results())

    # If destination has signing, request review or auto-approve changes.
    server_info = dest_client.get_server_info()
    signer_config = server_info["capabilities"].get("signer", {})
    signed_dest = [r for r in signer_config.get("resources", [])
                   if r["source"]["bucket"] == dest_bucket and
                   (r["source"]["collection"] is None or
                    r["source"]["collection"] == dest_collection)]

    if len(signed_dest) == 0:
        print(f"Done. {ops_count} changes copied.")
        return

    has_autoapproval = (
        not signed_dest[0].get("to-review-enabled", signer_config["to-review-enabled"]) and
        not signed_dest[0].get("group_check-enabled", signer_config["group_check-enabled"])
    )
    if has_autoapproval:
        # Approve the changes.
        dest_client.patch_collection(data={"status": "to-sign"})
        print(f"Done. {ops_count} changes published and signed.")
    else:
        # Request review.
        dest_client.patch_collection(data={"status": "to-review"})
        print(f"Done. Requested review for {ops_count} changes.")


def timestamp_to_date(timestamp_milliseconds):
    timestamp_seconds = int(timestamp_milliseconds) / 1000
    return datetime.utcfromtimestamp(timestamp_seconds).strftime('%Y-%m-%d %H:%M:%S UTC')


def get_signed_source(server_info, change):
    # Small helper to identify the source collection from a potential
    # signing destination collection, like those mentioned in the changes endpoint
    # (eg. blocklists/plugins -> staging/plugins).
    signed_resources = server_info['capabilities']['signer']['resources']
    for r in signed_resources:
        match_destination = (r['destination']['bucket'] == change['bucket']
                             and (r['destination']['collection'] is None or
                                  r['destination']['collection'] == change['collection']))
        if match_destination:
            return {
                'bucket': r['source']['bucket'],
                # Per-bucket configuration.
                'collection': r['source']['collection'] or change['collection'],
            }


def refresh_signature(event, context):
    server_url = event['server']
    auth = tuple(os.getenv("REFRESH_SIGNATURE_AUTH").split(':', 1))

    # Look at the collections in the changes endpoint.
    bucket = event.get('bucket', "monitor")
    collection = event.get('collection', "changes")
    client = Client(server_url=server_url,
                    bucket=bucket,
                    collection=collection)
    print('Looking at %s: ' % client.get_endpoint('collection'))
    changes = client.get_records()

    # Look at the signer configuration on the server.
    server_info = client.server_info()

    # Check if the refresh feature is available.
    has_resign_feature = server_info["capabilities"]["signer"]["version"] > "3.3.0"

    errors = []

    for change in changes:
        # 0. Figure out which was the source collection of this signed collection.
        source = get_signed_source(server_info, change)
        if source is None:
            # Skip if change is no kinto-signer destination (eg. review collection)
            continue

        client = Client(server_url=server_url,
                        bucket=source['bucket'],
                        collection=source['collection'],
                        auth=auth)

        try:
            print('Looking at %s:' % client.get_endpoint('collection'), end=' ')

            # 1. Grab collection information
            collection_metadata = client.get_collection()['data']
            last_modified = collection_metadata['last_modified']
            status = collection_metadata.get('status')

            if has_resign_feature:
                # 2. Refresh!
                print('Refresh signature: ', end='')
                new_metadata = client.patch_collection(data={'status': 'to-resign'})
                last_modified = new_metadata['data']['last_modified']

            else:
                # 2. Can only refresh if current status is "signed"
                if status == 'signed':
                    print('Refresh signature: ', end='')
                    new_metadata = client.patch_collection(data={'status': 'to-sign'})
                    last_modified = new_metadata['data']['last_modified']

            # 3. Display the status of the collection
            print('status=', status, 'at', timestamp_to_date(last_modified), '(', last_modified, ')')

        except KintoException as e:
            print(e)
            errors.append(e)

    if len(errors) > 0:
        error_messages = [str(e) for e in errors]
        raise RefreshError("\n" + "\n\n".join(error_messages))


BLOCKPAGES_ARGS = ['server', 'bucket', 'addons-collection', 'plugins-collection']


def blockpages_generator(event, context):
    """Event will contain the blockpages_generator parameters:
         - server: The kinto server to read data from.
                   (i.e: https://kinto-writer.services.mozilla.com/)
         - aws_region: S3 bucket AWS Region.
         - bucket_name: S3 bucket name.
         - bucket: The readonly public and signed bucket.
         - addons-collection: The add-ons collection name.
         - plugins-collection: The plugin collection name.
    """

    args = []
    kwargs = {}

    for key, value in event.items():
        if key in BLOCKPAGES_ARGS:
            args.append('--' + key)
            args.append(value)
        elif key.lower() in ('aws_region', 'bucket_name'):
            kwargs[key.lower()] = value

    # In lambda we can only write in the temporary filesystem.
    target_dir = mkdtemp()
    args.append('--target-dir')
    args.append(target_dir)

    print("Blocked pages generator args", args)
    generator_main(args)
    print("Send results to s3", args)
    sync_to_s3(target_dir, **kwargs)
    print("Clean-up")
    shutil.rmtree(target_dir)


AWS_REGION = "eu-central-1"
BUCKET_NAME = "amo-blocked-pages"


def sync_to_s3(target_dir, aws_region=AWS_REGION, bucket_name=BUCKET_NAME):
    if not os.path.isdir(target_dir):
        raise ValueError('target_dir %r not found.' % target_dir)

    s3 = boto3.resource('s3', region_name=aws_region)
    try:
        s3.create_bucket(Bucket=bucket_name,
                         CreateBucketConfiguration={'LocationConstraint': aws_region})
    except ClientError:
        pass

    for filename in os.listdir(target_dir):
        print('Uploading %s to Amazon S3 bucket %s' % (filename, bucket_name))
        s3.Object(bucket_name, filename).put(Body=open(os.path.join(target_dir, filename), 'rb'),
                                             ContentType='text/html')

        print('File uploaded to https://s3.%s.amazonaws.com/%s/%s' % (
            aws_region, bucket_name, filename))


if __name__ == "__main__":
    # Run the function specified in CLI arg.
    #
    # $ AUTH=user:pass python aws_lambda.py refresh_signature
    #
    event = {'server': os.getenv('SERVER', 'http://localhost:8888/v1')}
    context = None
    try:
        function = globals()[sys.argv[1]]
    except KeyError as e:
        print("Unknown function %s" % e)
        sys.exit(1)

    function(event, context)
