import concurrent.futures
import os

import backoff
import kinto_http
import requests
from requests.adapters import TimeoutSauce


PARALLEL_REQUESTS = int(os.getenv("PARALLEL_REQUESTS", 4))
REQUESTS_TIMEOUT_SECONDS = float(os.getenv("REQUESTS_TIMEOUT_SECONDS", 2))
REQUESTS_NB_RETRIES = int(os.getenv("REQUESTS_NB_RETRIES", 4))

retry_timeout = backoff.on_exception(
    backoff.expo,
    (requests.exceptions.Timeout, requests.exceptions.ConnectionError),
    max_tries=REQUESTS_NB_RETRIES,
)


class CustomTimeout(TimeoutSauce):
    def __init__(self, *args, **kwargs):
        if kwargs["connect"] is None:
            kwargs["connect"] = REQUESTS_TIMEOUT_SECONDS
        if kwargs["read"] is None:
            kwargs["read"] = REQUESTS_TIMEOUT_SECONDS
        super().__init__(*args, **kwargs)


requests.adapters.TimeoutSauce = CustomTimeout


class KintoClient(kinto_http.Client):
    """
    This Kinto client will retry the requests if they fail for timeout, and
    if the server replies with a 5XX.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("retry", REQUESTS_NB_RETRIES)
        super().__init__(*args, **kwargs)

    @retry_timeout
    def server_info(self, *args, **kwargs):
        return super().server_info(*args, **kwargs)

    @retry_timeout
    def get_collection(self, *args, **kwargs):
        return super().get_collection(*args, **kwargs)

    @retry_timeout
    def get_records(self, *args, **kwargs):
        return super().get_records(*args, **kwargs)

    @retry_timeout
    def get_records_timestamp(self, *args, **kwargs):
        return super().get_records_timestamp(*args, **kwargs)

    @retry_timeout
    def get_changeset(self, bid, cid, expected):
        url = f"{self.session.server_url}/buckets/{bid}/collections/{cid}/changeset?_expected={expected}"
        resp = requests.get(url)
        resp.raise_for_status()
        changeset = resp.json()
        return changeset


def records_equal(a, b):
    """Compare records, ignoring timestamps."""
    ignored_fields = ("last_modified", "schema")
    ra = {k: v for k, v in a.items() if k not in ignored_fields}
    rb = {k: v for k, v in b.items() if k not in ignored_fields}
    return ra == rb


def call_parallel(func, args_list, max_workers=PARALLEL_REQUESTS):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(func, *args) for args in args_list]
        results = [future.result() for future in futures]
    return results
