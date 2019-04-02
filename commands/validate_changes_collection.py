import os

from . import KintoClient as Client


def validate_changes_collection(event, context, **kwargs):
    """Validate the entries of the monitor endpoint.
    """
    # 1. Grab the changes collection
    server_url = event["server"]
    bucket = event.get("bucket", os.getenv("BUCKET", "monitor"))
    collection = event.get("collection", os.getenv("COLLECTION", "changes"))

    client = Client(server_url=server_url, bucket=bucket, collection=collection)
    print("Looking at %s: " % client.get_endpoint("collection"))

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
            print(
                "Etag NOT OK for {}/{} : {} != {}".format(bid, cid, last_modified, etag)
            )

    if not everything_ok:
        raise ValueError("One of the collection did not validate.")
