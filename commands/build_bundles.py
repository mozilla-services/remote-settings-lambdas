import io
import concurrent.futures
import json
import os
import random
import zipfile

import requests


from . import KintoClient, retry_timeout


SERVER = os.getenv("SERVER")
REQUESTS_PARALLEL_COUNT = int(os.getenv("REQUESTS_PARALLEL_COUNT", "4"))
BUNDLE_MAX_SIZE_BYTES = int(os.getenv("BUNDLE_MAX_SIZE_BYTES", "20_000_000"))


def call_parallel(func, args_list):
    results = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=REQUESTS_PARALLEL_COUNT
    ) as executor:
        futures = [executor.submit(func, *args) for args in args_list]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
    return results


@retry_timeout
def fetch_attachment(url):
    print("Fetch %r" % url)
    resp = requests.get(url)
    return resp.content


def write_zip(output_path, content):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, filecontent in content:
            zip_file.writestr(filename, filecontent)
    with open(output_path, "wb") as f:
        f.write(zip_buffer.getvalue())
    print("Wrote %r" % output_path)


def build_bundles(event, context):
    rs_server = event.get("server") or SERVER

    client = KintoClient(server_url=rs_server)

    # List server collections
    random_cache_bust = random.randint(999999000000, 999999999999)
    monitor_changeset = client.get_changeset("monitor", "changes", random_cache_bust)
    main_collections = [
        (c["bucket"], c["collection"], c["last_modified"])
        for c in monitor_changeset["changes"]
    ]
    print("%s collections" % len(main_collections))

    # Fetch all collections changesets and build "collections.zip"
    all_changesets = call_parallel(
        lambda bid, cid, ts: client.get_changeset(bid, cid, ts), main_collections
    )
    bid_cid_ts_changesets = list(zip(main_collections, all_changesets))
    write_zip(
        "collections.zip",
        [
            (f"{bid}--{cid}.json", json.dumps(changeset))
            for (bid, cid, _), changeset in bid_cid_ts_changesets
        ],
    )

    base_url = client.server_info()["capabilities"]["attachments"]["base_url"]

    for (bid, cid, _), changeset in bid_cid_ts_changesets:
        # TODO: only build bundles for opted in collections.
        # Either copy 'attachment' field into main bucket collections attributes on approve,
        # or look-up signer resources to pick main-workspace collection from main collection.

        # Fetch all attachments and build "{bid}--{cid}.zip"
        records = [r for r in changeset["changes"] if "attachment" in r]
        if not records:
            print("%s/%s has no attachments" % (bid, cid))
            continue
        print("%s/%s: %s records with attachments" % (bid, cid, len(records)))

        total_size_bytes = sum(r["attachment"]["size"] for r in records)
        if total_size_bytes > BUNDLE_MAX_SIZE_BYTES:
            print("Bundle would be too big. Skip.")
            continue
        print("Attachments total size %sB" % total_size_bytes)

        call_args = [(f'{base_url}{r["attachment"]["location"]}',) for r in records]
        all_attachments = call_parallel(fetch_attachment, call_args)
        write_zip(
            f"{bid}--{cid}.zip",
            [(f'{record["id"]}.meta.json', json.dumps(record)) for record in records]
            + [
                (record["id"], attachment)
                for record, attachment in zip(records, all_attachments)
            ],
        )

    # TODO: send build zip files to Cloud Storage
