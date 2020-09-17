import json
import unittest
from contextlib import asynccontextmanager
from unittest import mock

import responses


from commands.sync_megaphone import sync_megaphone, Megaphone


class TestSyncMegaphone(unittest.TestCase):
    server = "https://fake-server.net/v1"
    megaphone_host = "megaphone.tld"
    megaphone_auth = "bearer-token"
    broadcast_id = "remote-settings/monitor_changes"

    def setUp(self):
        self.source_monitor_changes_uri = (
            f"{self.server}/buckets/monitor/collections/changes/records"
        )
        self.megaphone_api_uri = (
            f"https://{self.megaphone_host}/v1/broadcasts/{self.broadcast_id}"
        )

    @responses.activate
    def test_does_nothing_if_up_to_date(self):
        responses.add(
            responses.GET,
            self.source_monitor_changes_uri,
            json={
                "data": [
                    {
                        "id": "a",
                        "bucket": "main-preview",
                        "collection": "cid",
                        "last_modified": 10,
                    },
                    {
                        "id": "b",
                        "bucket": "main",
                        "collection": "cid",
                        "last_modified": 7,
                    },
                ]
            },
        )
        patch = mock.patch("commands.sync_megaphone.Megaphone.get_version")
        patched = patch.start()
        self.addCleanup(patch.stop)
        patched.return_value = "7"

        sync_megaphone(
            event={
                "server": self.server,
                "megaphone_host": self.megaphone_host,
                "megaphone_auth": self.megaphone_auth,
            },
            context=None,
        )

        # No PUT on Megaphone API was sent.
        assert len(responses.calls) == 1

    @responses.activate
    def test_sends_version_if_differs(self):
        responses.add(
            responses.GET,
            self.source_monitor_changes_uri,
            json={
                "data": [
                    {
                        "id": "a",
                        "bucket": "main",
                        "collection": "cid",
                        "last_modified": 10,
                    },
                ]
            },
        )
        responses.add(
            responses.PUT,
            self.megaphone_api_uri,
        )
        patch = mock.patch("commands.sync_megaphone.Megaphone.get_version")
        patched = patch.start()
        self.addCleanup(patch.stop)
        patched.return_value = "5"

        sync_megaphone(
            event={
                "server": self.server,
                "megaphone_host": self.megaphone_host,
                "megaphone_auth": self.megaphone_auth,
            },
            context=None,
        )

        assert len(responses.calls) == 2
        assert responses.calls[1].request.method == "PUT"
        assert responses.calls[1].request.body == "10"

    def test_get_push_timestamp(self):
        class FakeConnection:
            async def send(self, value):
                self.sent = value

            async def recv(self):
                return json.dumps(
                    {"broadcasts": {TestSyncMegaphone.broadcast_id: '"42"'}}
                )

        fake_connection = FakeConnection()

        @asynccontextmanager
        async def fake_connect(url):
            yield fake_connection

        with mock.patch("commands.sync_megaphone.websockets") as mocked:
            mocked.connect = fake_connect

            megaphone = Megaphone(
                self.megaphone_host, self.megaphone_auth, self.broadcast_id
            )
            result = megaphone.get_version()

        assert json.loads(fake_connection.sent) == {
            "messageType": "hello",
            "broadcasts": {self.broadcast_id: "v0"},
            "use_webpush": True,
        }
        assert result == "42"
