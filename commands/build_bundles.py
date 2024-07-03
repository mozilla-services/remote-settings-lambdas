"""
This command will create Zip files in order to bundle all collections data,
and all attachments of collections that have the `attachment.bundle` flag in
their metadata.
It then uploads these zip files to Google Cloud Storage.
"""

import io
import json
import os
import random
import zipfile
from email.utils import parsedate_to_datetime

import requests
from google.cloud import storage

from . import KintoClient, call_parallel, retry_timeout


SERVER = os.getenv("SERVER")
REQUESTS_PARALLEL_COUNT = int(os.getenv("REQUESTS_PARALLEL_COUNT", "8"))
BUNDLE_MAX_SIZE_BYTES = int(os.getenv("BUNDLE_MAX_SIZE_BYTES", "20_000_000"))
STORAGE_BUCKET_NAME = os.getenv("STORAGE_BUCKET_NAME", "remote-settings-nonprod-stage-attachments")
DESTINATION_FOLDER = os.getenv("DESTINATION_FOLDER", "bundles")
# Flags for local development
BUILD_ALL = os.getenv("BUILD_ALL", "0") in "1yY"
SKIP_UPLOAD = os.getenv("SKIP_UPLOAD", "0") in "1yY"


def fetch_all_changesets(client):
    """
    Return the `/changeset` responses for all collections listed
    in the `monitor/changes` endpoint.
    The result contains the metadata and all the records of all collections
    for both preview and main buckets.
    """
    random_cache_bust = random.randint(999999000000, 999999999999)
    monitor_changeset = client.get_changeset("monitor", "changes", random_cache_bust)
    print("%s collections" % len(monitor_changeset["changes"]))

    args_list = [
        (c["bucket"], c["collection"], c["last_modified"]) for c in monitor_changeset["changes"]
    ]
    all_changesets = call_parallel(
        lambda bid, cid, ts: client.get_changeset(bid, cid, ts), args_list, REQUESTS_PARALLEL_COUNT
    )
    return [
        {"bucket": bid, **changeset} for (bid, _, _), changeset in zip(args_list, all_changesets)
    ]


@retry_timeout
def get_modified_timestamp(url):
    """
    Return URL modified date as epoch millisecond.
    """
    resp = requests.get(url)
    if not resp.ok:
        return None
    dts = resp.headers["Last-Modified"]
    dt = parsedate_to_datetime(dts)
    epoch_msec = int(dt.timestamp() * 1000)
    return epoch_msec


@retry_timeout
def fetch_attachment(url):
    print("Fetch %r" % url)
    resp = requests.get(url)
    return resp.content


def write_zip(output_path: str, content: list[tuple[str, bytes]]):
    """
    Write a Zip at the specified `output_path` location with the specified `content`.
    The content is specified as a list of file names and their binary content.
    """
    parent_folder = os.path.dirname(output_path)
    os.makedirs(parent_folder, exist_ok=True)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, filecontent in content:
            zip_file.writestr(filename, filecontent)
    with open(output_path, "wb") as f:
        f.write(zip_buffer.getvalue())
    print("Wrote %r" % output_path)


def sync_cloud_storage(
    storage_bucket: str, remote_folder: str, to_upload: list[str], to_delete: list[str]
):
    """
    Upload the specified `to_upload` filenames, and delete the specified `to_delete` filenames
    from the `remote_folder` of the `storage_bucket`.
    """
    # Ensure you have set the GOOGLE_APPLICATION_CREDENTIALS environment variable
    # to the path of your Google Cloud service account key file before running this script.
    client = storage.Client()
    bucket = client.bucket(storage_bucket)
    for filename in to_upload:
        remote_file_path = os.path.join(remote_folder, filename)
        blob = bucket.blob(remote_file_path)
        blob.upload_from_filename(filename)
        print(f"Uploaded {filename} to gs://{storage_bucket}/{remote_file_path}")

    to_delete = {os.path.join(remote_folder, f) for f in to_delete}
    blobs = bucket.list_blobs(prefix=remote_folder)
    for blob in blobs:
        if blob.name in to_delete:
            blob.delete()
            print(f"Deleted gs://{storage_bucket}/{blob.name}")


def build_bundles(event, context):
    """
    Main command entry point that:
    - fetches all collections changesets
    - builds a `changesets.zip`
    - fetches attachments of all collections with bundle flag
    - builds `{bid}--{cid}.zip` for each of them
    - send the bundles to the Cloud storage bucket
    """
    rs_server = event.get("server") or SERVER

    client = KintoClient(server_url=rs_server)

    base_url = client.server_info()["capabilities"]["attachments"]["base_url"]

    existing_bundle_timestamp = get_modified_timestamp(
        f"{base_url}{DESTINATION_FOLDER}/changesets.zip"
    )
    if existing_bundle_timestamp is None:
        print("No previous bundle found")  # Should only happen once.
        existing_bundle_timestamp = -1

    all_changesets = fetch_all_changesets(client)
    highest_timestamp = max(c["timestamp"] for c in all_changesets)

    if existing_bundle_timestamp >= highest_timestamp:
        print("Existing bundle up-to-date. Nothing to do.")
        return

    bundles_to_upload = []
    bundles_to_delete = []

    write_zip(
        "changesets.zip",
        [
            ("{bucket}--{metadata[id]}.json".format(**changeset), json.dumps(changeset))
            for changeset in all_changesets
        ],
    )
    bundles_to_upload.append("changesets.zip")

    for changeset in all_changesets:
        bid = changeset["bucket"]
        cid = changeset["metadata"]["id"]
        should_bundle = changeset["metadata"].get("attachment", {}).get("bundle", False)
        attachments_bundle_filename = f"{bid}--{cid}.zip"

        if not should_bundle:
            bundles_to_delete.append(attachments_bundle_filename)
            if not BUILD_ALL:
                continue

        if not BUILD_ALL and changeset["timestamp"] < existing_bundle_timestamp:
            # Collection hasn't changed since last bundling.
            continue

        # Skip bundle if no attachments found.
        records = [r for r in changeset["changes"] if "attachment" in r]
        if not records:
            print("%s/%s has no attachments" % (bid, cid))
            bundles_to_delete.append(attachments_bundle_filename)
            continue

        print("%s/%s: %s records with attachments" % (bid, cid, len(records)))

        # Skip bundle if total size is too big.
        total_size_bytes = sum(r["attachment"]["size"] for r in records)
        total_size_mb = total_size_bytes / 1024 / 1024
        if total_size_bytes > BUNDLE_MAX_SIZE_BYTES:
            print(f"Bundle would be too big ({total_size_mb:.2f}MB). Skip.")
            continue
        print(f"Attachments total size {total_size_mb:.2f}MB")

        # Fetch all attachments and build "{bid}--{cid}.zip"
        args_list = [(f'{base_url}{r["attachment"]["location"]}',) for r in records]
        all_attachments = call_parallel(fetch_attachment, args_list, REQUESTS_PARALLEL_COUNT)
        write_zip(
            attachments_bundle_filename,
            [(f'{record["id"]}.meta.json', json.dumps(record)) for record in records]
            + [(record["id"], attachment) for record, attachment in zip(records, all_attachments)],
        )
        bundles_to_upload.append(attachments_bundle_filename)

    if not SKIP_UPLOAD:
        sync_cloud_storage(
            STORAGE_BUCKET_NAME, DESTINATION_FOLDER, bundles_to_upload, bundles_to_delete
        )
