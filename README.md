# amo2kinto Lambda

Use this script to generate a zip for Amazon Lambda:

    make clean virtualenv zip upload-to-s3

Or if you want to build it on a Lambda instance:

    make remote-zip

You must run this script on a linux x86_64 arch, the same as Amazon Lambda.

This now requires Python 3.6


## Test locally

For example, run [kinto-dist](https://github.com/Kinto/kinto-dist/) locally (see README).

Initialize the server with the Kinto Dist smoke tests:

```
$ bash /path/to/kinto-dist/tests/smoke-test.sh
```

### Validate signatures

```
$ AUTH=user:pass  python aws_lambda.py validate_signature

Looking at /buckets/monitor/collections/changes:
Looking at /buckets/destination/collections/destination: Signature OK
Looking at /buckets/blocklists/collections/addons: Signature OK
Looking at /buckets/blocklists-preview/collections/addons: Signature OK
Looking at /buckets/blocklists/collections/certificates: Signature OK
Looking at /buckets/blocklists-preview/collections/certificates: Signature OK
Looking at /buckets/blocklists/collections/plugins: Signature OK
Looking at /buckets/blocklists-preview/collections/plugins: Signature OK
Looking at /buckets/blocklists/collections/gfx: Signature OK
Looking at /buckets/blocklists-preview/collections/gfx: Signature OK

```

### Refresh signatures

```
$ REFRESH_SIGNATURE_AUTH=reviewer:pass  python aws_lambda.py refresh_signature

Looking at /buckets/monitor/collections/changes:
Looking at /buckets/source/collections/source: to-review at 2018-03-05 13:56:08 UTC ( 1520258168885 )
Looking at /buckets/staging/collections/addons: Trigger new signature: signed at 2018-03-05 13:57:31 UTC ( 1520258251343 )
Looking at /buckets/staging/collections/certificates: Trigger new signature: signed at 2018-03-05 13:57:31 UTC ( 1520258251441 )
Looking at /buckets/staging/collections/plugins: Trigger new signature: signed at 2018-03-05 13:57:31 UTC ( 1520258251547 )
Looking at /buckets/staging/collections/gfx: Trigger new signature: signed at 2018-03-05 13:57:31 UTC ( 1520258251640 )

```

### Update schemas

```
$ AUTH=user:pass  python aws_lambda.py schema_updater

Checking at /buckets/staging/collections/addons: OK
Checking at /buckets/staging/collections/certificates: OK
Checking at /buckets/staging/collections/gfx: OK
Checking at /buckets/staging/collections/plugins: OK
```
