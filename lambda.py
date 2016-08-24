from __future__ import print_function
import os

import boto3
import boto3.session
from botocore.exceptions import ClientError

from tempfile import mkdtemp

from amo2kinto.generator import main as generator_main
from amo2kinto.importer import main as importer_main
from amo2kinto.verifier import main as verifier


JSON2KINTO_ARGS = ['server', 'auth', 'addons-server', 'schema-file', 'no-schema',
                   'certificates-bucket', 'certificates-collection',
                   'gfx-bucket', 'gfx-collection',
                   'addons-bucket', 'addons-collection',
                   'plugins-bucket', 'plugins-collection',
                   'certificates', 'gfx', 'addons', 'plugins']


def json2kinto(event, context):
    """Event will contain the json2kinto parameters:
         - server: The kinto server to write data to.
                   (i.e: https://kinto-writer.services.mozilla.com/)
         - amo-server: The amo server to read blocklists data from.
                       (i.e: https://addons.mozilla.org/)
         - schema: The JSON schema collection file to read schema from.
                   (i.e: schemas.json)
    """

    args = []

    for key, value in event.items():
        if key in JSON2KINTO_ARGS:
            args.append('--' + key)
            args.append(value)

    print("importer args", args)
    importer_main(args)


def xmlverifier(event, context):
    """xmlverifier takes local and remote parameter and validate that both
    are equals.

    """
    print("verifier args", event)
    response = verifier([event['local'], event['remote']])
    if response:
        raise Exception("There is a difference between: %r and %r" % (
            event['local'], event['remote']))


BLOCKPAGES_ARGS = ['server', 'bucket', 'addons-collection', 'plugins-collection']


def blockpages_generator(event, context):
    """Event will contain the blockpages_generator parameters:
         - server: The kinto server to write data to.
                   (i.e: https://kinto-writer.services.mozilla.com/)
         - s3bucket: S3 bucket to sync the files too.
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
        s3.Object(bucket_name, filename).put(Body=open(os.path.join(target_dir, filename), 'rb'))

        print('File uploaded to https://s3.%s.amazonaws.com/%s/%s' % (
            aws_region, bucket_name, filename))
