import os
import shutil
from tempfile import mkdtemp

import boto3
import boto3.session
from amo2kinto.generator import main as generator_main
from botocore.exceptions import ClientError


AWS_REGION = "eu-central-1"
BUCKET_NAME = "amo-blocked-pages"
BLOCKPAGES_ARGS = ["server", "bucket", "addons-collection", "plugins-collection"]


def blockpages_generator(event, context, **kwargs):
    """Generate the blocklist HTML pages and upload them to S3.
    """
    args = []
    kwargs = {}

    for key, value in event.items():
        env_value = os.getenv(key.upper().replace("-", "_"))
        if env_value:
            value = env_value
        if key in BLOCKPAGES_ARGS:
            args.append("--" + key)
            args.append(value)
        elif key.lower() in ("aws_region", "bucket_name"):
            kwargs[key.lower()] = value

    # In lambda we can only write in the temporary filesystem.
    target_dir = mkdtemp()
    args.append("--target-dir")
    args.append(target_dir)

    print("Blocked pages generator args", args)
    generator_main(args)
    print("Send results to s3", args)
    sync_to_s3(target_dir, **kwargs)
    print("Clean-up")
    shutil.rmtree(target_dir)


def sync_to_s3(target_dir, aws_region=AWS_REGION, bucket_name=BUCKET_NAME):
    if not os.path.isdir(target_dir):
        raise ValueError("target_dir %r not found." % target_dir)

    s3 = boto3.resource("s3", region_name=aws_region)
    try:
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": aws_region},
        )
    except ClientError:
        pass

    for filename in os.listdir(target_dir):
        print("Uploading %s to Amazon S3 bucket %s" % (filename, bucket_name))
        s3.Object(bucket_name, filename).put(
            Body=open(os.path.join(target_dir, filename), "rb"), ContentType="text/html"
        )

        print(
            "File uploaded to https://s3.%s.amazonaws.com/%s/%s"
            % (aws_region, bucket_name, filename)
        )
