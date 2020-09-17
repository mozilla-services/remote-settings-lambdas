# Remote Settings Lambdas

A collection of scripts related to the Remote Settings service.

## Sentry

All commands use Sentry to report any unexpected errors. The `SENTRY_DSN`
environment variable is not required but is recommended.

## Commands

Each command can be run, either with Python:

```
$ python aws_lambda.py validate_signature
```

or via the Docker container:

```
$ docker run remote-settings-lambdas validate_signature
```


### refresh_signature

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``REFRESH_SIGNATURE_AUTH``: credentials, either ``user:pass`` or ``{access-token}`` (default: ``None``)
- ``REQUESTS_TIMEOUT_SECONDS``: Connection/Read timeout in seconds (default: ``2``)
- ``REQUESTS_NB_RETRIES``: Number of retries before failing (default: ``4``)

Example:

```
$ REFRESH_SIGNATURE_AUTH=reviewer:pass  python aws_lambda.py refresh_signature

Looking at /buckets/monitor/collections/changes:
Looking at /buckets/source/collections/source: to-review at 2018-03-05 13:56:08 UTC ( 1520258168885 )
Looking at /buckets/staging/collections/addons: Trigger new signature: signed at 2018-03-05 13:57:31 UTC ( 1520258251343 )
Looking at /buckets/staging/collections/certificates: Trigger new signature: signed at 2018-03-05 13:57:31 UTC ( 1520258251441 )
Looking at /buckets/staging/collections/plugins: Trigger new signature: signed at 2018-03-05 13:57:31 UTC ( 1520258251547 )
Looking at /buckets/staging/collections/gfx: Trigger new signature: signed at 2018-03-05 13:57:31 UTC ( 1520258251640 )

```


### backport_records

Backport the changes from one collection to another. This is useful if the new collection (*source*) has become the source of truth,
but there are still clients pulling data from the old collection (*destination*).

> Note: This lambda is not safe if other users can interact with the destination collection.

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``BACKPORT_RECORDS_SOURCE_AUTH``: authentication for source collection
- ``BACKPORT_RECORDS_DEST_AUTH``: authentication for destination collection (default: same as source)
- ``BACKPORT_RECORDS_SOURCE_BUCKET``: bucket id to read records from
- ``BACKPORT_RECORDS_SOURCE_COLLECTION``: collection id to read records from
- ``BACKPORT_RECORDS_SOURCE_FILTERS``: optional filters when backporting records as JSON format (default: none, eg. ``"{"min_age": 42}"``)
- ``BACKPORT_RECORDS_DEST_BUCKET``: bucket id to copy records to (default: same as source bucket)
- ``BACKPORT_RECORDS_DEST_COLLECTION``:collection id to copy records to (default: same as source collection)
- ``REQUESTS_TIMEOUT_SECONDS``: Connection/Read timeout in seconds (default: ``2``)
- ``REQUESTS_NB_RETRIES``: Number of retries before failing (default: ``4``)
- ``SAFE_HEADERS``: Add concurrency control headers to update requests (default: ``true``)

Example:

```
$ BACKPORT_RECORDS_SOURCE_AUTH=user:pass BACKPORT_RECORDS_SOURCE_BUCKET=blocklists BACKPORT_RECORDS_SOURCE_COLLECTION=certificates BACKPORT_RECORDS_DEST_BUCKET=security-state BACKPORT_RECORDS_DEST_COLLECTION=onecrl  python3 aws_lambda.py backport_records

Batch #0: PUT /buckets/security-state/collections/onecrl/records/003234b2-f425-eae6-9596-040747dab2b9 - 201
Batch #1: PUT /buckets/security-state/collections/onecrl/records/00ac492e-04f7-ee6d-5fd2-bb12b97a4b7f - 201
Batch #2: DELETE /buckets/security-state/collections/onecrl/records/23 - 200
Done. 3 changes applied.

```

```
$ BACKPORT_RECORDS_SOURCE_AUTH=user:pass BACKPORT_RECORDS_SOURCE_BUCKET=blocklists BACKPORT_RECORDS_SOURCE_COLLECTION=certificates BACKPORT_RECORDS_DEST_BUCKET=security-state BACKPORT_RECORDS_DEST_COLLECTION=onecrl  python3 aws_lambda.py backport_records

Records are in sync. Nothing to do.

```


### blockpages_generator

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``BUCKET``: Kinto blocklists bucket (default: ``blocklists``)
- ``ADDONS_COLLECTIONS``: Addons blocklist (default: ``addons``)
- ``PLUGINS_COLLECTIONS``: Addons blocklist (default: ``plugins``)
- ``AWS_REGION``: AWS S3 region (default: ``eu-central-1``)
- ``BUCKET_NAME``: AWS bucket name (default: ``amo-blocked-pages``)
- ``REQUESTS_TIMEOUT_SECONDS``: Connection/Read timeout in seconds (default: ``2``)
- ``REQUESTS_NB_RETRIES``: Number of retries before failing (default: ``4``)


### publish_dafsa

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``AUTH``: authentication to edit the ``public-suffix-list`` collection


### sync_megaphone

Send the current version of Remote Settings data to the Push server.

Does nothing if versions are in sync.

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``MEGAPHONE_HOST``: Push service host (eg.: ``push.services.mozilla.com``)
- ``MEGAPHONE_AUTH``: Push service bearer token
- ``BROADCASTER_ID``: Push broadcaster ID (default.: ``remote-settings``)
- ``CHANNEL_ID``: Push channel ID (default.: ``monitor_changes``)

Example:

```
$ SERVER=https://settings.prod.mozaws.net/v1 MEGAPHONE_HOST="push.services.mozilla.com" MEGAPHONE_AUTH="a-b-c" python aws_lambda.py sync_megaphone
```


## Test locally

```
$ make virtualenv
$ source .venv/bin/activate

$ SERVER=https://firefox.settings.services.mozilla.com/v1/  python aws_lambda.py validate_signature
```

### Local Kinto server

Best way to obtain a local setup that looks like a writable Remote Settings instance is to follow [this tutorial](https://remote-settings.readthedocs.io/en/latest/tutorial-local-server.html)

It is possible to initialize the server with some fake data, like for the Kinto Dist smoke tests:

```
$ bash /path/to/kinto-dist/tests/smoke-test.sh
```

## Releasing

- `git tag vX.Y.Z`
- `git push origin master; git push --tags origin`
- `make zip`
- Go to releases page on Github and create a release for x.y.z
- Attach the `remote-settings-lambdas-x.y.z.zip` file
- [Click here][bugzilla-stage-link] to open a ticket to get it deployed to stage and [here][bugzilla-prod-link] to prod


[bugzilla-stage-link]: https://bugzilla.mozilla.org/enter_bug.cgi?comment=Please%20upgrade%20the%20lambda%20functions%20to%20use%20the%20last%20release%20of%20remote-settings-lambdas.%0D%0A%0D%0A%5BInsert%20a%20short%20description%20of%20the%20changes%20here.%5D%0D%0A%0D%0Ahttps%3A%2F%2Fgithub.com%2Fmozilla-services%2Fremote-settings-lambdas%2Freleases%2Ftag%2FX.Y.Z%0D%0A%0D%0AThanks%21&component=Operations%3A%20Storage&product=Cloud%20Services&qa_contact=chartjes%40mozilla.com&short_desc=Please%20deploy%20remote-settings-lambdas-X.Y.Z%20lambda%20function%20to%20STAGE

[bugzilla-prod-link]: https://bugzilla.mozilla.org/enter_bug.cgi?comment=Please%20upgrade%20the%20lambda%20functions%20to%20use%20the%20last%20release%20of%20remote-settings-lambdas.%0D%0A%0D%0A%5BInsert%20a%20short%20description%20of%20the%20changes%20here.%5D%0D%0A%0D%0Ahttps%3A%2F%2Fgithub.com%2Fmozilla-services%2Fremote-settings-lambdas%2Freleases%2Ftag%2FX.Y.Z%0D%0A%0D%0AThanks%21&component=Operations%3A%20Storage&product=Cloud%20Services&qa_contact=chartjes%40mozilla.com&short_desc=Please%20deploy%20remote-settings-lambdas-X.Y.Z%20lambda%20function%20to%20PROD
