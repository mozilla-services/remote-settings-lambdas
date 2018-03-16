from __future__ import print_function
import base64
import codecs
import hashlib
import json
import operator
import os
import sys
import time
import uuid
from datetime import datetime
from tempfile import mkdtemp

import boto3
import boto3.session
import ecdsa
from amo2kinto.generator import main as generator_main
from amo2kinto.kinto import update_schema_if_mandatory
from botocore.exceptions import ClientError
from kinto_http import Client


def canonical_json(records, last_modified):
    records = (r for r in records if not r.get('deleted', False))
    records = sorted(records, key=operator.itemgetter('id'))
    payload = {'data': records, 'last_modified': '%s' % last_modified}
    return json.dumps(payload, sort_keys=True, separators=(',', ':'))


class ValidationError(Exception):
    pass


def validate_signature(event, context):
    server_url = event['server']
    bucket = event.get('bucket', "monitor")
    collection = event.get('collection', "changes")
    client = Client(server_url=server_url,
                    bucket=bucket,
                    collection=collection)
    print('Read collection list from {}'.format(client.get_endpoint('collection')))

    collections = client.get_records()

    error_messages = []

    for i, collection in enumerate(collections):
        client = Client(server_url=server_url,
                        bucket=collection['bucket'],
                        collection=collection['collection'])

        endpoint = client.get_endpoint('collection')
        message = "{:02d}/{:02d} {}:  ".format(i + 1, len(collections), endpoint)

        # 1. Grab collection information
        dest_col = client.get_collection()['data']
        signed_on = dest_col['last_modified']

        # 2. Grab records
        records = client.get_records(_sort='-last_modified')
        timestamp = client.get_records_timestamp()

        # 3. Serialize
        serialized = canonical_json(records, timestamp)

        # 4. Grab the signature
        try:
            signature = dest_col['signature']
        except KeyError:
            # Destination has no signature attribute.
            # Be smart and check if it was just configured.
            # See https://github.com/mozilla-services/amo2kinto-lambda/issues/31
            with_tombstones = client.get_records(_since=1)
            if len(with_tombstones) == 0:
                # It never contained records. Let's assume it is newly configured.
                message += 'SKIP'
                print(message)
                continue
            # Some records and empty signature? It will fail below.
            signature = {}

        # 5. Grab the public key
        try:
            pubkey = signature['public_key'].encode('utf-8')
            data = b'Content-Signature:\x00' + serialized.encode('utf-8')
            verifier = ecdsa.VerifyingKey.from_pem(pubkey)
            signature = base64.urlsafe_b64decode(signature['signature'])
            verified = verifier.verify(signature, data, hashfunc=hashlib.sha384)
            assert verified == True, "Signature verification failed"

            message += 'OK'
            print(message)
        except Exception as e:
            message += '⚠ BAD Signature ⚠'
            print(message)

            # Gather details for the global exception that will be raised.
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
        print('Looking at %s:' % client.get_endpoint('collection'), end=' ')

        # 1. Grab collection information
        collection_metadata = client.get_collection()['data']
        last_modified = collection_metadata['last_modified']

        # 2. If status is signed
        status = collection_metadata.get('status')
        if status == 'signed':

            # 2.1. Trigger a signature
            print('Trigger new signature: ', end='')
            new_metadata = client.patch_collection(data={'status': 'to-sign'})
            last_modified = new_metadata['data']['last_modified']

        # 3. Display the status of the collection
        print('status=', status, 'at', timestamp_to_date(last_modified), '(', last_modified, ')')


def schema_updater(event, context):
    """Event will contain the json2kinto parameters:
         - server: The kinto server to write data to.
                   (i.e: https://kinto-writer.services.mozilla.com/)
    """
    server_url = event['server']
    auth = tuple(os.getenv('AUTH').split(':', 1))

    # AMO schemas are all in the staging bucket.
    # See https://github.com/mozilla-services/cloudops-deployment/blob/dc72e8241f5f721e49c054c8726a4fc4a7089b61/projects/kinto-lambda/ansible/playbooks/schema_updater_lambda.yml#L16-L20
    bucket = event.get('bucket', 'staging')

    # Open the file
    with codecs.open('schemas.json', 'r', encoding='utf-8') as f:
        schemas = json.load(f)['collections']

    # Use the collections mentioned in the schemas file.
    for cid, schema in schemas.items():
        if not schema.get('synced'):
            continue

        client = Client(server_url=server_url,
                        bucket=bucket,
                        collection=cid,
                        auth=auth)
        print('Checking at %s: ' % client.get_endpoint('collection'), end='')

        # 1. Grab collection information
        dest_col = client.get_collection()

        # 2. Collection schema
        config = schema['config']
        update_schema_if_mandatory(dest_col, config, client.patch_collection)
        print('OK')


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


def invalidate_cache(event, context):
    distribution_id = event['distribution_id']

    timestamp = int(time.mktime(time.gmtime()))
    # Create a boto client
    client = boto3.client('cloudfront')
    client.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': ['/v1/*']
            },
            'CallerReference': '{}-{}'.format(timestamp, uuid.uuid4())
        })


if __name__ == "__main__":
    # Run the function specified in CLI arg.
    #
    # $ AUTH=user:pass  python aws_lambda.py schema_updater
    # Checking at /buckets/staging/collections/addons: OK
    # Checking at /buckets/staging/collections/certificates: OK
    # Checking at /buckets/staging/collections/gfx: OK
    # Checking at /buckets/staging/collections/plugins: OK
    #
    event = {'server': os.getenv('SERVER', 'http://localhost:8888/v1')}
    context = None
    try:
        function = globals()[sys.argv[1]]
    except KeyError as e:
        print("Unknown function %s" % e)
        sys.exit(1)

    function(event, context)
