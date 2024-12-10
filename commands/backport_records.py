import json
import os

from decouple import config
from kinto_http.utils import collection_diff

from . import KintoClient as Client


def backport_records(event, context, **kwargs):
    """Backport records creations, updates and deletions from one collection to another."""
    server_url = event["server"]
    source_auth = (
        event.get("backport_records_source_auth") or os.environ["BACKPORT_RECORDS_SOURCE_AUTH"]
    )
    source_bucket = (
        event.get("backport_records_source_bucket") or os.environ["BACKPORT_RECORDS_SOURCE_BUCKET"]
    )
    source_collection = (
        event.get("backport_records_source_collection")
        or os.environ["BACKPORT_RECORDS_SOURCE_COLLECTION"]
    )
    source_filters_json = event.get("backport_records_source_filters") or os.getenv(
        "BACKPORT_RECORDS_SOURCE_FILTERS", ""
    )
    source_filters = json.loads(source_filters_json or "{}")

    dest_auth = event.get(
        "backport_records_dest_auth",
        os.getenv("BACKPORT_RECORDS_DEST_AUTH", source_auth),
    )
    dest_bucket = event.get(
        "backport_records_dest_bucket",
        os.getenv("BACKPORT_RECORDS_DEST_BUCKET", source_bucket),
    )
    dest_collection = event.get(
        "backport_records_dest_collection",
        os.getenv("BACKPORT_RECORDS_DEST_COLLECTION", source_collection),
    )
    safe_headers = event.get("safe_headers", config("SAFE_HEADERS", default=False, cast=bool))

    if source_bucket == dest_bucket and source_collection == dest_collection:
        raise ValueError("Cannot copy records: destination is identical to source")

    source_client = Client(
        server_url=server_url,
        bucket=source_bucket,
        collection=source_collection,
        auth=source_auth,
    )
    dest_client = Client(
        server_url=server_url,
        bucket=dest_bucket,
        collection=dest_collection,
        auth=dest_auth,
    )

    source_records = source_client.get_records(**source_filters)
    dest_records = dest_client.get_records()
    to_create, to_update, to_delete = collection_diff(source_records, dest_records)

    is_behind = to_create or to_update or to_delete
    has_pending_changes = is_behind
    if not is_behind:
        # When this lambda is ran with a signed collection as
        # its destination, the destination collection is in the
        # workspace bucket, and will have a status field among
        # its metadata.
        data = dest_client.get_collection()["data"]
        has_pending_changes = data.get("status") != "signed"

    if not (is_behind or has_pending_changes):
        print("Records are in sync. Nothing to do.")
        return

    with dest_client.batch() as dest_batch:
        for r in to_create:
            dest_batch.create_record(data=r)
        for old, new in to_update:
            # Add some concurrency control headers (make sure the
            # destination record wasn't changed since we read it).
            if_match = old["last_modified"] if safe_headers else None
            dest_batch.update_record(data=new, if_match=if_match)
        for r in to_delete:
            dest_batch.delete_record(id=r["id"])

    ops_count = len(dest_batch.results())

    # If destination has signing, request review or auto-approve changes.
    server_info = dest_client.server_info()
    signer_config = server_info["capabilities"].get("signer", {})
    signer_resources = signer_config.get("resources", [])
    # Check destination collection config (sign-off required etc.)
    signed_dest = [
        r
        for r in signer_resources
        if r["source"]["bucket"] == dest_bucket and r["source"]["collection"] == dest_collection
    ]
    if len(signed_dest) == 0:
        # Not explicitly configured. Check if configured at bucket level?
        signed_dest = [
            r
            for r in signer_resources
            if r["source"]["bucket"] == dest_bucket and r["source"]["collection"] is None
        ]
    # Destination has no signature enabled. Nothing to do.
    if len(signed_dest) == 0:
        print(f"Done. {ops_count} changes applied.")
        return

    has_autoapproval = not signed_dest[0].get(
        "to_review_enabled", signer_config["to_review_enabled"]
    )
    if has_autoapproval:
        # Approve the changes.
        dest_client.approve_changes()
        print(f"Done. {ops_count} changes applied and signed.")
    else:
        # Request review.
        dest_client.request_review(message="r?")
        print(f"Done. Requested review for {ops_count} changes.")
