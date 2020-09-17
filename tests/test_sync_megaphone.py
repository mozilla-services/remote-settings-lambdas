import unittest

import responses


from commands.sync_megaphone import sync_megaphone


class TestSyncMegaphone(unittest.TestCase):
    server = "https://fake-server.net/v1"
    megaphone_url = "https://megaphone.tld/v1"
    megaphone_auth = "bearer-token"
    broadcast_id = "remote-settings/monitor_changes"

    def setUp(self):
        self.source_monitor_changes_uri = (
            f"{self.server}/buckets/monitor/collections/changes/records"
        )
        self.megaphone_broadcasts_uri = f"{self.megaphone_url}/broadcasts"
        self.megaphone_broadcast_uri = (
            f"{self.megaphone_url}/broadcasts/{self.broadcast_id}"
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
        responses.add(
            responses.GET,
            self.megaphone_broadcasts_uri,
            json={
                "code": 200,
                "broadcasts": {
                    "remote-settings/monitor_changes": '"7"',
                    "test/broadcast2": "v0",
                },
            },
        )

        sync_megaphone(
            event={
                "server": self.server,
                "megaphone_url": self.megaphone_url,
                "megaphone_auth": self.megaphone_auth,
            },
            context=None,
        )

        # No PUT on Megaphone API was sent.
        assert len(responses.calls) == 2
        assert responses.calls[0].request.method == "GET"
        assert responses.calls[1].request.method == "GET"

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
            responses.GET,
            self.megaphone_broadcasts_uri,
            json={
                "code": 200,
                "broadcasts": {
                    "remote-settings/monitor_changes": '"5"',
                    "test/broadcast2": "v0",
                },
            },
        )
        responses.add(
            responses.PUT,
            self.megaphone_broadcast_uri,
        )

        sync_megaphone(
            event={
                "server": self.server,
                "megaphone_url": self.megaphone_url,
                "megaphone_auth": self.megaphone_auth,
            },
            context=None,
        )

        assert len(responses.calls) == 3
        assert responses.calls[0].request.method == "GET"
        assert responses.calls[1].request.method == "GET"
        assert responses.calls[2].request.body == '"10"'
        assert (
            responses.calls[2].request.headers["authorization"] == "Bearer bearer-token"
        )
