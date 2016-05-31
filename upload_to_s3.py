from __future__ import print_function
import sys

import boto
import boto.s3
from boto.s3.key import Key

BUCKET_NAME = "amo2kinto"
FILENAME = "ami-built-lambda.zip"

conn = boto.connect_s3()

bucket = conn.create_bucket(BUCKET_NAME,
                            location=boto.s3.connection.Location.DEFAULT)


print('Uploading %s to Amazon S3 bucket %s' % (FILENAME, BUCKET_NAME))


def percent_cb(complete, total):
    sys.stdout.write('.')
    sys.stdout.flush()

k = Key(bucket)
k.key = 'lambda.zip'
k.set_contents_from_filename(FILENAME, cb=percent_cb, num_cb=10)
