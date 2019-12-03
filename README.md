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

### validate_signature

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``REQUESTS_TIMEOUT_SECONDS``: Connection/Read timeout in seconds (default: ``2``)
- ``REQUESTS_NB_RETRIES``: Number of retries before failing (default: ``4``)

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


### consistency_checks

Environment config:

- ``SERVER``: server URL (default: ``http://localhost:8888/v1``)
- ``AUTH``: credentials, either ``user:pass`` or ``{access-token}`` (default: ``None``)
- ``PARALLEL_REQUESTS``: Number of parallel requests (default: ``4``)
- ``REQUESTS_TIMEOUT_SECONDS``: Connection/Read timeout in seconds (default: ``2``)
- ``REQUESTS_NB_RETRIES``: Number of retries before failing (default: ``4``)

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
- ``BACKPORT_RECORDS_SOURCE_FILTERS``: optional filters when backporting records as JSON format (default: none, eg. ``"{"min_age": 42}"``)
- ``BACKPORT_RECORDS_DEST_BUCKET``: bucket id to copy records to (default: same as source bucket)
- ``BACKPORT_RECORDS_DEST_COLLECTION``:collection id to copy records to (default: same as source collection)
- ``REQUESTS_TIMEOUT_SECONDS``: Connection/Read timeout in seconds (default: ``2``)
- ``REQUESTS_NB_RETRIES``: Number of retries before failing (default: ``4``)

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
- ``PARALLEL_REQUESTS``: Number of parallel requests (default: ``4``)
- ``REQUESTS_TIMEOUT_SECONDS``: Connection/Read timeout in seconds (default: ``2``)
- ``REQUESTS_NB_RETRIES``: Number of retries before failing (default: ``4``)


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

### uptake_health

Environment config:

- `REDASH_API_KEY`: For Redash (no default, must be set)
- `REDASH_API_QUERY_URL`: Restful JSON URL for Redash (see code for default)
- `REDASH_TIMEOUT_SECONDS`: How many seconds to wait for Redash (see code for default)
- `EXCLUDE_SOURCES`: Comma separated list of sources to ignore (see code for default)
- `MIN_TOTAL_ENTRIES`: Integer of the minimum entries to even try (see code for default)
- `DEFAULT_ERROR_THRESHOLD_PERCENT`: Floating point number for default threshold (see code for default)
- `REQUESTS_TIMEOUT_SECONDS`: Connection/Read timeout in seconds (default: ``2``)
- `REQUESTS_NB_RETRIES`: Number of retries before failing (default: ``4``)

Example:

```
$ REDASH_API_KEY=xxxxx python3 aws_lambda.py uptake_health

📅 From 2019-03-12 00:00:00 to 2019-03-12 23:59:59
blocklists/addons                        (good: 1,027,245 bad:    11,081)               1.07%
blocklists/plugins                       (good:   943,780 bad:     6,149)               0.65%
main/fxmonitor-breaches                  (good:   840,611 bad:     1,878)               0.22%
main/onboarding                          (good:   887,404 bad:        38)               0.00%
main/sites-classification                (good:   887,525 bad:        60)               0.01%
main/tippytop                            (good:   828,329 bad:   132,338)              13.78%
settings-changes-monitoring              (good: 3,314,418 bad:    57,722)               1.71%

1 settings have a bad ratio over threshold.

main/tippytop
	network_error    13.32% (127,922)
	sync_error       0.42% (4,036)
	sign_retry_error 0.02% (222)
	unknown_error    0.01% (122)
	sign_error       0.00% (36)

```

The objective of this script is to check in on the collected uptake from Telemetry
with respect to Remote Settings. Essentially, across all statuses that we worry
about, we use this script to check that the amount of bad statuses don't exceed
a threshold.

The ultimately use case for this script is to run it periodically and use it to
trigger alerts/notifications that the Product Delivery team can take heed of.

#### Architectural Overview

This is stateless script, written in Python, meant to be executed roughly once a day.
It queries [Redash](https://sql.telemetry.mozilla.org) for
a Redash query's data that is pre-emptively run every 24 hours.
The data it analyses is a
list of everything stored in "Remote Content" along with a count of
every possible status (e.g. `up_to_date`, `network_error`, etc.)
The script sums the "good" statuses and compares it against the "bad" statuses and
if that ratio (expressed as a percentage) is over a certain threshold it alerts
by sending an event to Sentry which notifies the team by email.

> Note: *bad* statuses are the ones ending with `_error` (eg. `sync_error`,
> `network_error`, ...)

#### Historical Strategy

As of Firefox Nightly 67, Firefox clients that use Remote Settings only
send Telemetry pings in daily batches.
I.e. it's _not_ real-time. The "uptake histogram" is buffered in
the browser and will send periodically instead of as soon as possible. In Firefox
Nightly (67 at the time of writing),
[we are switching to real-time Telemetry Events](https://bugzilla.mozilla.org/show_bug.cgi?id=1517469).

On the Telemetry backend we're still consuming the older uptake histogram but once,
the population using the new Telemetry Events is large enough,
we will switch the Redash query (where appropriate) and still use
this script to worry about the percentage thresholds.
And the strategy for notifications should hopefully not change. There is no plan
to rush this change since we'll still be doing "legacy" histogram telemetry
_and_ the new telemetry events so we can let it mature a bit before changing
the source of data.

Although we will eventually switch to real-time Telemetry Events, nothing changes in
terms of the surface API but the underlying data is more up-to-date and the response
time of reacting to failure spikes is faster.

It is worth noting that as underlying tools change, we might decommission this
solution and use something native to the Telemetry analysis tools that achives
the same goal.


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
