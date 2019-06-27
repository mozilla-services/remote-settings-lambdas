import os
import tempfile
import unittest
from unittest import mock

import requests
import responses
from kinto_http import Client, KintoException


from commands.publish_dafsa import (
    get_latest_hash,
    download_resources,
    prepare_dafsa,
    remote_settings_publish,
    publish_dafsa,
    PREPARE_TLDS_PY,
    MAKE_DAFSA_PY,
    LIST_URL,
    BUCKET_ID,
    COLLECTION_ID,
    RECORD_ID,
    COMMIT_HASH_URL,
)


class TestUtilMethods(unittest.TestCase):
    def test_get_latest_hash(self):
        self.assertEqual(len(get_latest_hash(COMMIT_HASH_URL)), 40)
        self.assertRaises(
            requests.exceptions.HTTPError, get_latest_hash(COMMIT_HASH_URL + "c")
        )

    def test_download_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            download_resources(tmp, PREPARE_TLDS_PY, MAKE_DAFSA_PY, LIST_URL)
            self.assertEqual(
                sorted(os.listdir(tmp)),
                sorted(["public_suffix_list.dat", "prepare_tlds.py", "make_dafsa.py"]),
            )
            self.assertRaises(
                requests.exceptions.HTTPError,
                download_resources(tmp, PREPARE_TLDS_PY + "c"),
            )


class TestPrepareDafsa(unittest.TestCase):
    def test_prepare_dafsa(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_binary_path = prepare_dafsa(tmp)
            self.assertIn(os.path.basename(output_binary_path), os.listdir(tmp))
            self.assertGreater(os.path.getsize(output_binary_path), 0)

    def test_exception_is_raise_when_process_returns_non_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("subprocess.Popen") as mocked:
                mocked.return_value.returncode = 1
                with self.assertRaises(Exception) as cm:
                    prepare_dafsa(tmp)
                    self.assertIn("DAFSA Build Failed", str(cm.exception))


class TestRemoteSettingsPublish(unittest.TestCase):
    @responses.activate
    def test_remote_settings_publish(self):
        server = "https://kinto.dev.mozaws.net/v1"
        record_uri = f"{server}/buckets/main-workspace/collections/public-suffix-list/records/tld-dafsa"  # noqa
        attachment_uri = f"{record_uri}/attachment"

        responses.add(
            responses.PUT,
            f"{server}/accounts/arpit73",
            adding_headers={"Content-Type": "application/json"},
            data='{"data": {"password": "pAsSwErD"}}',
        )
        client = Client(
            server_url=server,
            auth=("arpit73", "pAsSwErD"),
            bucket=BUCKET_ID,
            collection=COLLECTION_ID,
        )
        self.assertEqual(
            client.get_endpoint("record", id=RECORD_ID),
            "/buckets/dafsa-bucket/collections/public-suffix-list/records/tld-dafsa",
        )

        responses.add(
            responses.POST,
            attachment_uri,
            adding_headers={"Content-Type": "multipart/form-data"},
            files={"attachment": ("dafsa.bin", b"some binary data")},
            data='{"commit_hash": "abc"}',
        )
        responses.add(
            responses.PATCH,
            record_uri,
            adding_headers={"Content-Type": "application/json"},
            data='{"data": {"status": "to-review"}}',
        )

        with tempfile.TemporaryDirectory() as tmp:
            with open(f"{tmp}/dafsa.bin", "wb") as f:
                f.write(b"some binary data")
            remote_settings_publish(client, "abc", f"{tmp}/dafsa.bin")


class TestPublishDafsa(unittest.TestCase):
    def setUp(self):
        self.event = {
            "server": "https://kinto.dev.mozaws.net/v1",
            "auth": "arpit73:pAsSwErD",
        }
        self.record_uri = f"{{{event.get('server')}/buckets/main-workspace/collections/public-suffix-list/records/tld-dafsa}}"  # noqa

        mocked = mock.patch("commands.publish_dafsa.prepare_dafsa")
        self.addCleanup(mocked.stop)
        self.mocked_prepare = mocked.start()

        mocked = mock.patch("commands.publish_dafsa.remote_settings_publish")
        self.addCleanup(mocked.stop)
        self.mocked_publish = mocked.start()

    @responses.activate
    def test_prepare_and_publish_are_not_called_when_hash_matches(self):
        responses.add(responses.GET, COMMIT_HASH_URL, json=[{"sha": "abc"}])
        responses.add(
            responses.PUT,
            f"{{{self.event.get('server')}/accounts/arpit73}}",
            adding_headers={"Content-Type": "application/json"},
            data='{"data": {"password": "pAsSwErD"}}',
        )
        responses.add(
            responses.GET, self.record_uri, json={"data": {"commit-hash": "abc"}}
        )

        publish_dafsa(self.event, context=None)

        self.assertFalse(self.mocked_prepare.called)
        self.assertFalse(self.mocked_publish.called)

    @responses.activate
    def test_KintoException_raised_when_fetching_failed(self):
        responses.add(responses.GET, COMMIT_HASH_URL, json=[{"sha": "abc"}])
        responses.add(
            responses.PUT,
            f"{{{self.event.get('server')}/accounts/arpit73}}",
            adding_headers={"Content-Type": "application/json"},
            data='{"data": {"password": "pAsSwErD"}}',
        )
        responses.add(
            responses.GET, self.record_uri, json={"data": {"commit-hash": "abc"}}
        )

        with self.assertRaises(
            KintoException, publish_dafsa(self.event, context=None)
        ) as e:
            self.assertEqual(e.response, None) or self.assertNotEqual(
                e.response.status_code, 404
            )

