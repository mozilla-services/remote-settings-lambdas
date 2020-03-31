import json
import unittest

import responses


from commands.backport_records import backport_records


class TestRecordsFilter(unittest.TestCase):
    server = "https://fake-server.net/v1"
    auth = ("foo", "bar")
    source_bid = "main"
    source_cid = "one"
    dest_bid = "main-workspace"
    dest_cid = "other"

    def setUp(self):
        self.source_collection_uri = (
            f"{self.server}/buckets/{self.source_bid}/collections/{self.source_cid}"
        )
        self.source_records_uri = f"{self.source_collection_uri}/records"

        self.dest_collection_uri = (
            f"{self.server}/buckets/{self.dest_bid}/collections/{self.dest_cid}"
        )
        self.dest_records_uri = f"{self.dest_collection_uri}/records"

    @responses.activate
    def test_missing_records_are_backported(self):
        responses.add(
            responses.GET,
            self.server + "/",
            json={
                "settings": {"batch_max_requests": 10},
                "capabilities": {"signer": {"resources": []}},
            },
        )
        responses.add(
            responses.GET,
            self.source_records_uri,
            json={
                "data": [
                    {"id": "a", "age": 22, "last_modified": 1},
                    {"id": "b", "age": 30, "last_modified": 10},
                ]
            },
        )
        responses.add(
            responses.GET,
            self.dest_records_uri,
            json={"data": [{"id": "a", "age": 22, "last_modified": 2}]},
        )
        responses.add(responses.POST, self.server + "/batch", json={"responses": []})

        backport_records(
            event={
                "server": self.server,
                "backport_records_source_auth": self.auth,
                "backport_records_source_bucket": self.source_bid,
                "backport_records_source_collection": self.source_cid,
                "backport_records_source_filters": '{"min_age": 20}',
                "backport_records_dest_bucket": self.dest_bid,
                "backport_records_dest_collection": self.dest_cid,
            },
            context=None,
        )

        assert responses.calls[0].request.method == "GET"
        assert responses.calls[0].request.url.endswith("?min_age=20")

        assert responses.calls[1].request.method == "GET"
        assert responses.calls[2].request.method == "GET"

        assert responses.calls[3].request.method == "POST"
        posted_records = json.loads(responses.calls[3].request.body)
        assert posted_records["requests"] == [
            {
                "body": {"data": {"age": 30, "id": "b", "last_modified": 10}},
                "headers": {"If-None-Match": "*"},
                "method": "PUT",
                "path": "/buckets/main-workspace/collections/other/records/b",
            }
        ]

    @responses.activate
    def test_outdated_records_are_overwritten(self):
        responses.add(
            responses.GET,
            self.server + "/",
            json={
                "settings": {"batch_max_requests": 10},
                "capabilities": {"signer": {"resources": []}},
            },
        )
        responses.add(responses.HEAD, self.source_records_uri, headers={"ETag": '"42"'})
        responses.add(
            responses.GET,
            self.source_records_uri,
            json={"data": [{"id": "a", "age": 22, "last_modified": 2}]},
        )
        responses.add(responses.HEAD, self.dest_records_uri, headers={"ETag": '"41"'})
        responses.add(
            responses.GET,
            self.dest_records_uri,
            json={"data": [{"id": "a", "age": 20, "last_modified": 1}]},
        )
        responses.add(responses.POST, self.server + "/batch", json={"responses": []})

        backport_records(
            event={
                "server": self.server,
                "backport_records_source_auth": self.auth,
                "backport_records_source_bucket": self.source_bid,
                "backport_records_source_collection": self.source_cid,
                "backport_records_dest_bucket": self.dest_bid,
                "backport_records_dest_collection": self.dest_cid,
            },
            context=None,
        )

        assert responses.calls[3].request.method == "POST"
        posted_records = json.loads(responses.calls[3].request.body)
        assert posted_records["requests"] == [
            {
                "body": {"data": {"age": 22, "id": "a"}},
                "headers": {"If-Match": '"1"'},
                "method": "PUT",
                "path": "/buckets/main-workspace/collections/other/records/a",
            }
        ]
