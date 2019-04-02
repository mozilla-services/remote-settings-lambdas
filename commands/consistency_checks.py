import concurrent
import copy
import os

from kinto_http import BearerTokenAuth

from . import PARALLEL_REQUESTS, KintoClient as Client


def records_equal(a, b):
    """Compare records, ignoring timestamps."""
    ignored_fields = ("last_modified", "schema")
    ra = {k: v for k, v in a.items() if k not in ignored_fields}
    rb = {k: v for k, v in b.items() if k not in ignored_fields}
    return ra == rb


def compare_collections(a, b):
    """Compare two lists of records. Returns empty list if equal."""
    b_by_id = {r["id"]: r for r in b}
    diff = []
    for ra in a:
        rb = b_by_id.pop(ra["id"], None)
        if rb is None:
            diff.append(ra)
        elif not records_equal(ra, rb):
            diff.append(ra)
    diff.extend(b_by_id.values())
    return diff


def fetch_signed_resources(server_url, auth):
    # List signed collection using capabilities.
    client = Client(
        server_url=server_url, auth=auth, bucket="monitor", collection="changes"
    )
    info = client.server_info()
    try:
        resources = info["capabilities"]["signer"]["resources"]
    except KeyError:
        raise ValueError("No signer capabilities found. Run on *writer* server!")

    # Build the list of signed collections, source -> preview -> destination
    # For most cases, configuration of signed resources is specified by bucket and
    # does not contain any collection information.
    resources_by_bid = {}
    resources_by_cid = {}
    preview_buckets = set()
    for resource in resources:
        if resource["source"]["collection"] is not None:
            resources_by_cid[
                (
                    resource["destination"]["bucket"],
                    resource["destination"]["collection"],
                )
            ] = resource
        else:
            resources_by_bid[resource["destination"]["bucket"]] = resource
        if "preview" in resource:
            preview_buckets.add(resource["preview"]["bucket"])

    print("Read collection list from {}".format(client.get_endpoint("collection")))
    resources = []
    monitored = client.get_records(_sort="bucket,collection")
    for entry in monitored:
        bid = entry["bucket"]
        cid = entry["collection"]

        # Skip preview collections entries
        if bid in preview_buckets:
            continue

        if (bid, cid) in resources_by_cid:
            r = resources_by_cid[(bid, cid)]
        elif bid in resources_by_bid:
            r = copy.deepcopy(resources_by_bid[bid])
            r["source"]["collection"] = r["destination"]["collection"] = cid
            if "preview" in r:
                r["preview"]["collection"] = cid
        else:
            raise ValueError(f"Unknown signed collection {bid}/{cid}")
        resources.append(r)

    return resources


def consistency_checks(event, context, **kwargs):
    """Check the collections content and status consistency.
    """
    server_url = event.get("server") or os.getenv("SERVER")
    auth = event.get("auth") or os.getenv("AUTH")
    if auth:
        auth = tuple(auth.split(":", 1)) if ":" in auth else BearerTokenAuth(auth)

    def _has_inconsistencies(server_url, auth, r):
        client = Client(server_url=server_url, auth=auth)

        source_metadata = client.get_collection(
            bucket=r["source"]["bucket"], id=r["source"]["collection"]
        )["data"]
        status = source_metadata["status"]

        identifier = "{bucket}/{collection}".format(**r["destination"])

        # Collection status is reset on any modification, so if status is ``to-review``,
        # then records in the source should be exactly the same as the records in the preview
        if status == "to-review":
            source_records = client.get_records(**r["source"])
            preview_records = client.get_records(**r["preview"])
            diff = compare_collections(source_records, preview_records)
            if diff:
                return identifier, diff

        # And if status is ``signed``, then records in the source and preview should
        # all be the same as those in the destination.
        elif status == "signed" or status is None:
            source_records = client.get_records(**r["source"])
            dest_records = client.get_records(**r["destination"])
            if "preview" in r:
                # If preview is enabled, then compare source/preview and preview/dest
                preview_records = client.get_records(**r["preview"])
                diff_source = compare_collections(source_records, preview_records)
                diff_preview = compare_collections(preview_records, dest_records)
            else:
                # Otherwise, just compare source/dest
                diff_source = compare_collections(source_records, dest_records)
                diff_preview = []
            # If difference detected, report it!
            if diff_source or diff_preview:
                return identifier, diff_source + diff_preview

        else:
            # And if status is ``work-in-progress``, we can't really check anything.
            # Source can differ from preview, and preview can differ from destination
            # if a review request was previously rejected.
            print(f"{identifier} SKIP ({status})")
            return identifier, None

        print(f"{identifier} OK")
        return identifier, None

    resources = fetch_signed_resources(server_url, auth)
    results = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=PARALLEL_REQUESTS
    ) as executor:
        futures = [
            executor.submit(_has_inconsistencies, server_url, auth, r)
            for r in resources
        ]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    inconsistent = [identifier for identifier, diff in results if diff]
    if inconsistent:
        raise ValueError(
            "Inconsistencies detected on {}".format(", ".join(inconsistent))
        )
