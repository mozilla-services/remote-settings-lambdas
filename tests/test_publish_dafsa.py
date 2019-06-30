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
    get_stored_hash,
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


class TestsGetLatestHash(unittest.TestCase):
    def test_get_latest_hash_returns_sha1_hash(self):
        size_latest_hash = len(get_latest_hash(COMMIT_HASH_URL))
        self.assertEqual(size_latest_hash, 40)

    @responses.activate
    def test_HTTPError_raised_when_404(self):
        responses.add(
            responses.GET, COMMIT_HASH_URL, json={"error": "not found"}, status=404
        )
        with self.assertRaises(requests.exceptions.HTTPError) as e:
            latest_hash = get_latest_hash(COMMIT_HASH_URL)  # noqa
            self.assertEqual(e.status_code, 404)


class TestDownloadResources(unittest.TestCase):
    def test_all_files_downloaded_with_correct_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            download_resources(tmp, PREPARE_TLDS_PY, MAKE_DAFSA_PY, LIST_URL)
            self.assertEqual(
                sorted(os.listdir(tmp)),
                sorted(["public_suffix_list.dat", "prepare_tlds.py", "make_dafsa.py"]),
            )

    @responses.activate
    def test_HTTPError_raised_when_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            responses.add(
                responses.GET, PREPARE_TLDS_PY, json={"error": "not found"}, status=404
            )
            with self.assertRaises(requests.exceptions.HTTPError) as e:
                download_resources(tmp, PREPARE_TLDS_PY)
                self.assertEqual(e.status_code, 404)


class TestGetStoredHash(unittest.TestCase):
    def setUp(self):
        server = "https://fake-server.net/v1"
        auth = ("arpit73", "pAsSwErD")
        self.client = Client(
            server_url=server, auth=auth, bucket=BUCKET_ID, collection=COLLECTION_ID
        )
        self.record_uri = server + self.client.get_endpoint(
            "record", id=RECORD_ID, bucket=BUCKET_ID, collection=COLLECTION_ID
        )

    @responses.activate
    def test_KintoException_raised_when_stored_hash_fetching_failed(self):
        responses.add(
            responses.GET, self.record_uri, json={"error": "not found"}, status=404
        )
        with self.assertRaises(KintoException) as e:
            stored_hash = get_stored_hash(self.client)  # noqa
            self.assertEqual(e.status_code, 404)


class TestPrepareDafsa(unittest.TestCase):
    def test_file_is_created_in_output_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_binary_path = prepare_dafsa(tmp)
            self.assertIn(os.path.basename(output_binary_path), os.listdir(tmp))
            self.assertGreater(os.path.getsize(output_binary_path), 0)

    def test_exception_is_raised_when_process_returns_non_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("subprocess.Popen") as mocked:
                mocked.return_value.returncode = 1
                with self.assertRaises(Exception) as e:
                    prepare_dafsa(tmp)
                    self.assertIn("DAFSA Build Failed", str(e.exception))


# class TestRemoteSettingsPublish(unittest.TestCase):
#     @responses.activate
#     def test_remote_settings_publish(self):
#         server = "https://fake-server.net.net/v1"
#         record_uri = f"{server}/buckets/main-workspace/collections/public-suffix-list/records/tld-dafsa"  # noqa
#         attachment_uri = f"{record_uri}/attachment"

#         client = Client(
#             server_url=server,
#             auth=("arpit73", "pAsSwErD"),
#             bucket=BUCKET_ID,
#             collection=COLLECTION_ID,
#         )

#         responses.add(
#             responses.POST,
#             attachment_uri,
#             files={"attachment": ("dafsa.bin", b"some binary data")},
#             json='{"commit_hash": "abc"}',
#         )
#         responses.add(
#             responses.PATCH, record_uri, json='{"data": {"status": "to-review"}}'
#         )

#         with tempfile.TemporaryDirectory() as tmp:
#             with open(f"{tmp}/dafsa.bin", "wb") as f:
#                 f.write(b"some binary data")
#             remote_settings_publish(client, "abc", f"{tmp}/dafsa.bin")


class TestPublishDafsa(unittest.TestCase):
    def setUp(self):
        self.event = {
            "server": "https://fake-server.net/v1",
            "auth": "arpit73:pAsSwErD",
        }
        client = Client(
            server_url=self.event.get("server"),
            auth=("arpit73", "pAsSwErD"),
            bucket=BUCKET_ID,
            collection=COLLECTION_ID,
        )
        self.record_uri = self.event.get("server") + client.get_endpoint(
            "record", id=RECORD_ID, bucket=BUCKET_ID, collection=COLLECTION_ID
        )

        mocked = mock.patch("commands.publish_dafsa.prepare_dafsa")
        self.addCleanup(mocked.stop)
        self.mocked_prepare = mocked.start()

        mocked = mock.patch("commands.publish_dafsa.remote_settings_publish")
        self.addCleanup(mocked.stop)
        self.mocked_publish = mocked.start()

    @responses.activate
    def test_prepare_and_publish_are_not_called_when_hashes_matches(self):
        responses.add(
            responses.GET, COMMIT_HASH_URL, json=[{"sha": "fake-commit-hash"}]
        )
        responses.add(
            responses.GET,
            self.record_uri,
            json={"data": {"commit-hash": "fake-commit-hash"}},
        )

        publish_dafsa(self.event, context=None)

        self.assertFalse(self.mocked_prepare.called)
        self.assertFalse(self.mocked_publish.called)

    @responses.activate
    def test_prepare_and_publish_are_called_when_hashes_do_not_match(self):
        responses.add(
            responses.GET, COMMIT_HASH_URL, json=[{"sha": "fake-commit-hash"}]
        )
        responses.add(
            responses.GET,
            self.record_uri,
            json={"data": {"commit-hash": "different-fake-commit-hash"}},
        )

        publish_dafsa(self.event, context=None)

        self.assertTrue(self.mocked_prepare.called)
        self.assertTrue(self.mocked_publish.called)
