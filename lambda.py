from __future__ import print_function
from datetime import datetime
import codecs
import json
import os
import tempfile
from functools import partial

import boto3
import boto3.session
from botocore.exceptions import ClientError

from tempfile import mkdtemp

from amo2kinto.generator import main as generator_main
from amo2kinto.importer import main as importer_main
from amo2kinto.kinto import update_schema_if_mandatory
from amo2kinto.verifier import main as verifier

from kinto_http import Client
from kinto_signer.serializer import canonical_json
from kinto_signer.hasher import compute_hash
from kinto_signer.signer.local_ecdsa import ECDSASigner


JSON2KINTO_ARGS = ['server', 'auth', 'editor-auth', 'reviewer-auth',
                   'addons-server', 'schema-file', 'no-schema',
                   'certificates-bucket', 'certificates-collection',
                   'gfx-bucket', 'gfx-collection',
                   'addons-bucket', 'addons-collection',
                   'plugins-bucket', 'plugins-collection',
                   'certificates', 'gfx', 'addons', 'plugins']

JSON2KINTO_ENV_VARIABLES = {'JSON2KINTO_AUTH': '--auth',
                            'JSON2KINTO_EDITOR_AUTH': '--editor-auth',
                            'JSON2KINTO_REVIEWER_AUTH': '--reviewer-auth'}


def json2kinto(event, context):
    """Event will contain the json2kinto parameters:
         - server: The kinto server to write data to.
                   (i.e: https://kinto-writer.services.mozilla.com/)
         - amo-server: The amo server to read blocklists data from.
                       (i.e: https://addons.mozilla.org/)
         - schema: The JSON schema collection file to read schema from.
                   (i.e: schemas.json)
    """

    args = {}

    # Upgrade by reading some ENV variables
    for key, arg in JSON2KINTO_ENV_VARIABLES.items():
        value = os.getenv(key)
        if value is not None:
            args[arg] = value

    # Deduplicate keys that might also be present in the event.
    for key, value in event.items():
        if key in JSON2KINTO_ARGS:
            args['--%s' % key] = value

    # Convert the dict as a list of argv
    flatten_args = sum(args.items(), ())

    # Remove password from there when writting the args.
    print("importer args", list(reduce(lambda x, y: x + y,
                                       [x for x in args.items()
                                        if x[0] not in JSON2KINTO_ENV_VARIABLES.values()])))
    importer_main(flatten_args)


def xmlverifier(event, context):
    """xmlverifier takes local and remote parameter and validate that both
    are equals.

    """
    print("verifier args", event)
    response = verifier([event['local'], event['remote']])
    if response:
        raise Exception("There is a difference between: %r and %r" % (
            event['local'], event['remote']))


DEFAULT_COLLECTIONS = [
    {'bucket': 'blocklists',
     'collection': 'certificates'},
    {'bucket': 'blocklists',
     'collection': 'addons'},
    {'bucket': 'blocklists',
     'collection': 'plugins'},
    {'bucket': 'blocklists',
     'collection': 'gfx'},
    {'bucket': 'pinning',
     'collection': 'pins'}
]


def validate_signature(event, context):
    server_url = event['server']
    collections = event.get('collections', DEFAULT_COLLECTIONS)

    for collection in collections:
        client = Client(server_url=server_url,
                        bucket=collection['bucket'],
                        collection=collection['collection'])
        print('Looking at %s: ' % client.get_endpoint('collection'), end='')

        # 1. Grab collection information
        dest_col = client.get_collection()

        # 2. Grab records
        records = client.get_records(_sort='-last_modified')
        timestamp = client.get_records_timestamp()

        # 3. Serialize
        serialized = canonical_json(records, timestamp)

        # 4. Compute hash
        computed_hash = compute_hash(serialized)

        # 5. Grab the signature
        signature = dest_col['data']['signature']

        # 6. Grab the public key
        try:
            f = tempfile.NamedTemporaryFile(delete=False)
            f.write(signature['public_key'])
            f.close()

            # 7. Verify the signature matches the hash
            signer = ECDSASigner(public_key=f.name)
            signer.verify(serialized, signature)
            print('Signature OK')
        except Exception:
            print('Signature KO. Computed hash: `{}`'.format(computed_hash))
            raise
        finally:
            os.unlink(f.name)


def timestamp_to_date(timestamp_milliseconds):
    timestamp_seconds = int(timestamp_milliseconds) / 1000
    return datetime.utcfromtimestamp(timestamp_seconds).strftime('%Y-%m-%d %H:%M:%S UTC')


def refresh_signature(event, context):
    server_url = event['server']
    collections = event.get('collections', DEFAULT_COLLECTIONS)
    auth = tuple(os.getenv("REFRESH_SIGNATURE_AUTH").split(':', 1))

    for collection in collections:
        client = Client(server_url=server_url,
                        bucket=collection['bucket'],
                        collection=collection['collection'],
                        auth=auth)
        print('Looking at %s:' % client.get_endpoint('collection'), end=' ')

        # 1. Grab collection information
        collection_metadata = client.get_collection()['data']
        last_modified = collection_metadata['last_modified']

        # 2. If status is signed
        if collection_metadata['status'] == 'signed':

            # 2.1. Trigger a signature
            print('Trigger new signature: ', end='')
            new_metadata = client.patch_collection(data={'status': 'to-sign'})
            last_modified = new_metadata['data']['last_modified']

        # 3. Display the status of the collection
        print(collection_metadata['status'],
              'at', timestamp_to_date(last_modified), '(', last_modified, ')')


SCHEMA_COLLECTIONS = [
    {'bucket': 'staging',
     'collection': 'certificates'},
    {'bucket': 'staging',
     'collection': 'addons'},
    {'bucket': 'staging',
     'collection': 'plugins'},
    {'bucket': 'staging',
     'collection': 'gfx'}
]


def schema_updater(event, context):
    """Event will contain the json2kinto parameters:
         - server: The kinto server to write data to.
                   (i.e: https://kinto-writer.services.mozilla.com/)
    """
    server_url = event['server']
    auth = tuple(os.getenv('AUTH').split(':', 1))

    collections = event.get('collections', SCHEMA_COLLECTIONS)

    # Open the file
    with codecs.open("schemas.json", 'r', encoding='utf-8') as f:
        schemas = json.load(f)['collections']

    # Check all collections
    for collection in collections:
        client = Client(server_url=server_url,
                        bucket=collection['bucket'],
                        collection=collection['collection'],
                        auth=auth)
        print('Checking at %s: ' % client.get_endpoint('collection'), end='')

        # 1. Grab collection information
        dest_col = client.get_collection()

        # 2. Collection schema
        collection_type = collection['collection']
        config = schemas[collection_type]['config']

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
