import json
import unittest
from datetime import datetime, timezone
from unittest import mock

import responses

from commands.refresh_signature import refresh_signature


class TestSignatureRefresh(unittest.TestCase):
    server = "https://fake-server.net/v1"
    auth = ("foo", "bar")

    # def setUp(self):
    #     self.source_collection_uri = (
    #         f"{self.server}/buckets/{self.source_bid}/collections/{self.source_cid}"
    #     )
    #     self.source_records_uri = f"{self.source_collection_uri}/records"

    #     self.dest_collection_uri = (
    #         f"{self.server}/buckets/{self.dest_bid}/collections/{self.dest_cid}"
    #     )
    #     self.dest_records_uri = f"{self.dest_collection_uri}/records"

    @responses.activate
    def test_skip_recently_signed(self):
        responses.add(
            responses.GET,
            self.server + "/",
            json={
                "settings": {"batch_max_requests": 10},
                "capabilities": {
                    "signer": {
                        "resources": [
                            {
                                "source": {
                                    "bucket": "main-workspace",
                                    "collection": None,
                                },
                                "destination": {"bucket": "main", "collection": None},
                            }
                        ]
                    }
                },
            },
        )

        responses.add(
            responses.GET,
            self.server + "/buckets/monitor/collections/changes/records",
            json={
                "data": [
                    {"id": "a", "bucket": "main", "collection": "search-config"},
                    {"id": "b", "bucket": "main", "collection": "top-sites"},
                ]
            },
        )

        for cid, date in [
            ("search-config", "2019-01-11T15:11:07.807323+00:00"),
            ("top-sites", "2019-01-18T15:11:07.807323+00:00"),
        ]:
            responses.add(
                responses.GET,
                self.server + "/buckets/main-workspace/collections/" + cid,
                json={
                    "data": {"last_modified": 42, "last_signature_date": date},
                },
            )
            responses.add(
                responses.PATCH,
                self.server + "/buckets/main-workspace/collections/" + cid,
                json={
                    "data": {
                        "last_modified": 43,
                    }
                },
            )

        patch = mock.patch("commands.refresh_signature.utcnow")
        self.addCleanup(patch.stop)
        mocked = patch.start()

        mocked.return_value = datetime(2019, 1, 20).replace(tzinfo=timezone.utc)

        refresh_signature(
            event={
                "server": self.server,
            },
            context=None,
        )

        patch_requests = [r for r in responses.calls if r.request.method == "PATCH"]

        assert len(patch_requests) == 1
