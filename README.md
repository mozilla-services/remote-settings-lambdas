# Remote Settings Lambdas

A collection of scripts related to the Remote Settings service.

## Commands

Each command can be run, either with Python:

```
$ python aws_lambda.py validate_signature
```

or via the Docker container:

```
$ docker run remote-settings-lambdas validate_signature
```

### validate_signature

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)

Example:

```
$ SERVER=https://firefox.settings.services.mozilla.com/v1/  python aws_lambda.py validate_signature
Read collection list from /buckets/monitor/collections/changes
01/17 /buckets/blocklists/collections/addons:  OK
02/17 /buckets/blocklists-preview/collections/addons:  OK
03/17 /buckets/blocklists/collections/certificates:  OK
04/17 /buckets/blocklists-preview/collections/certificates:  OK
05/17 /buckets/blocklists/collections/plugins:  OK
06/17 /buckets/blocklists-preview/collections/plugins:  OK
07/17 /buckets/security-state-preview/collections/intermediates:  SKIP
08/17 /buckets/security-state/collections/intermediates:  SKIP
09/17 /buckets/blocklists-preview/collections/gfx:  OK
10/17 /buckets/blocklists/collections/qa:  OK
11/17 /buckets/fingerprinting-defenses/collections/fonts:  OK
12/17 /buckets/fingerprinting-defenses-preview/collections/fonts:  OK
13/17 /buckets/focus-preview/collections/experiments:  SKIP
14/17 /buckets/pinning-preview/collections/pins:  SKIP
15/17 /buckets/focus/collections/experiments:  SKIP
16/17 /buckets/pinning/collections/pins:  OK
17/17 /buckets/blocklists/collections/gfx:  OK

```


### refresh_signature

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``REFRESH_SIGNATURE_AUTH``: credentials, either ``user:pass`` or ``{access-token}`` (default: ``None``)

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


### consistency_checks

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``AUTH``: credentials, either ``user:pass`` or ``{access-token}`` (default: ``None``)

Example:

```
$ AUTH=XYPJTNBCDE-lVna SERVER=https://settings-writer.stage.mozaws.net/v1 python aws_lambda.py consistency_checks

Read collection list from /buckets/monitor/collections/changes
blocklists/certificates OK
blocklists/gfx OK
blocklists/addons OK
blocklists/plugins OK
main/cfr OK
main/chinarepack-newtab-configuration OK
main/chinarepack-newtab-topsites OK
main/fxmonitor-breaches SKIP (work-in-progress)
main/fenix-experiments OK
main/fftv-experiments OK
main/lite-experiments SKIP (work-in-progress)
main/language-dictionaries OK
main/normandy-recipes OK
main/onboarding OK
main/rocket-prefs SKIP (work-in-progress)
main/personality-provider-models OK
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
- ``BACKPORT_RECORDS_DEST_BUCKET``: bucket id to copy records to (default: same as source bucket)
- ``BACKPORT_RECORDS_DEST_COLLECTION``:collection id to copy records to (default: same as source collection)

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

### validate_changes_collection

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``BUCKET``: monitor changes bucket (default: ``monitor``)
- ``COLLECTION``: monitor changes collection (default: ``changes``)


### blockpages_generator

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``BUCKET``: Kinto blocklists bucket (default: ``blocklists``)
- ``ADDONS_COLLECTIONS``: Addons blocklist (default: ``addons``)
- ``PLUGINS_COLLECTIONS``: Addons blocklist (default: ``plugins``)
- ``AWS_REGION``: AWS S3 region (default: ``eu-central-1``)
- ``BUCKET_NAME``: AWS bucket name (default: ``amo-blocked-pages``)


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

