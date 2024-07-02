import concurrent.futures
import io
import json
import os
import random
import zipfile

import requests
from google.cloud import storage

from . import KintoClient, retry_timeout


SERVER = os.getenv("SERVER")
REQUESTS_PARALLEL_COUNT = int(os.getenv("REQUESTS_PARALLEL_COUNT", "4"))
BUNDLE_MAX_SIZE_BYTES = int(os.getenv("BUNDLE_MAX_SIZE_BYTES", "20_000_000"))
BUILD_ALL = os.getenv("BUILD_ALL", "0") in "1yY"
STORAGE_BUCKET_NAME = os.getenv("STORAGE_BUCKET_NAME", "rs-attachments")
DESTINATION_FOLDER = os.getenv("DESTINATION_FOLDER", "bundles")
SKIP_UPLOAD = os.getenv("SKIP_UPLOAD", "0") in "1yY"


def call_parallel(func, args_list):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=REQUESTS_PARALLEL_COUNT) as executor:
        futures = [executor.submit(func, *args) for args in args_list]
        results = [future.result() for future in futures]
    return results


def fetch_all_changesets(client):
    random_cache_bust = random.randint(999999000000, 999999999999)
    monitor_changeset = client.get_changeset("monitor", "changes", random_cache_bust)
    print("%s collections" % len(monitor_changeset["changes"]))

    args_list = [
        (c["bucket"], c["collection"], c["last_modified"]) for c in monitor_changeset["changes"]
    ]
    all_changesets = call_parallel(
        lambda bid, cid, ts: client.get_changeset(bid, cid, ts), args_list
    )
    return [
        {"bucket": bid, **changeset} for (bid, _, _), changeset in zip(args_list, all_changesets)
    ]


@retry_timeout
def fetch_attachment(url):
    print("Fetch %r" % url)
    resp = requests.get(url)
    return resp.content


def write_zip(output_path, content):
    parent_folder = os.path.dirname(output_path)
    os.makedirs(parent_folder, exist_ok=True)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, filecontent in content:
            zip_file.writestr(filename, filecontent)
    with open(output_path, "wb") as f:
        f.write(zip_buffer.getvalue())
    print("Wrote %r" % output_path)


def sync_cloud_storage(folder):
    # Ensure you have set the GOOGLE_APPLICATION_CREDENTIALS environment variable
    # to the path of your Google Cloud service account key file before running this script.
    client = storage.Client()
    bucket = client.bucket(STORAGE_BUCKET_NAME)
    local_files = set()
    for root, _, files in os.walk(folder):
        for file in files:
            local_file_path = os.path.join(root, file)
            remote_file_path = os.path.join(folder, file)

            blob = bucket.blob(remote_file_path)
            blob.upload_from_filename(local_file_path)
            print(f"Uploaded {local_file_path} to gs://{STORAGE_BUCKET_NAME}/{remote_file_path}")
            local_files.add(remote_file_path)

    blobs = bucket.list_blobs(prefix=folder)
    for blob in blobs:
        if blob.name not in local_files:
            blob.delete()
            print(f"Deleted gs://{STORAGE_BUCKET_NAME}/{blob.name}")


def build_bundles(event, context):
    rs_server = event.get("server") or SERVER

    client = KintoClient(server_url=rs_server)

    all_changesets = fetch_all_changesets(client)
    write_zip(
        f"{DESTINATION_FOLDER}/changesets.zip",
        [
            ("{bucket}--{metadata[id]}.json".format(**changeset), json.dumps(changeset))
            for changeset in all_changesets
        ],
    )

    base_url = client.server_info()["capabilities"]["attachments"]["base_url"]

    for changeset in all_changesets:
        if not BUILD_ALL and not changeset["metadata"].get("attachment", {}).get("bundle", False):
            # Bundling not enabled.
            continue

        # Skip bundle if no attachments found.
        bid = changeset["bucket"]
        cid = changeset["metadata"]["id"]
        records = [r for r in changeset["changes"] if "attachment" in r]
        if not records:
            print("%s/%s has no attachments" % (bid, cid))
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
        all_attachments = call_parallel(fetch_attachment, args_list)
        write_zip(
            f"{DESTINATION_FOLDER}/{bid}--{cid}.zip",
            [(f'{record["id"]}.meta.json', json.dumps(record)) for record in records]
            + [(record["id"], attachment) for record, attachment in zip(records, all_attachments)],
        )

    if not SKIP_UPLOAD:
        sync_cloud_storage(DESTINATION_FOLDER)
