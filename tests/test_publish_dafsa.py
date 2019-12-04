import os
import tempfile
import unittest
from unittest import mock

import requests
import responses
from kinto_http import Client


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
    BUCKET_ID_PREVIEW,
    COLLECTION_ID,
    RECORD_ID,
    COMMIT_HASH_URL,
)


class TestsGetLatestHash(unittest.TestCase):
    @responses.activate
    def test_get_latest_hash_returns_sha1_hash(self):
        responses.add(responses.GET, COMMIT_HASH_URL, json=[{"sha": "hash"}])
        latest_hash = get_latest_hash(COMMIT_HASH_URL)
        self.assertEqual(latest_hash, "hash")

    @responses.activate
    def test_HTTPError_raised_when_404(self):
        responses.add(
            responses.GET, COMMIT_HASH_URL, json={"error": "not found"}, status=404
        )
        with self.assertRaises(requests.exceptions.HTTPError) as e:
            get_latest_hash(COMMIT_HASH_URL)
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
    def test_stored_hash_fetched_successfully(self):
        responses.add(
            responses.GET,
            self.record_uri,
            json={"data": {"commit-hash": "fake-commit-hash"}},
        )
        stored_hash = get_stored_hash(self.client)
        self.assertEqual(stored_hash, "fake-commit-hash")

    @responses.activate
    def test_returns_none_when_no_record_found(self):
        responses.add(
            responses.GET, self.record_uri, json={"error": "not found"}, status=404
        )
        self.assertIsNone(get_stored_hash(self.client))


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


class TestRemoteSettingsPublish(unittest.TestCase):
    def setUp(self):
        server = "https://fake-server.net/v1"
        auth = ("arpit73", "pAsSwErD")
        self.client = Client(
            server_url=server, auth=auth, bucket=BUCKET_ID, collection=COLLECTION_ID
        )
        record_uri = server + self.client.get_endpoint(
            "record", id=RECORD_ID, bucket=BUCKET_ID, collection=COLLECTION_ID
        )
        self.collection_uri = server + self.client.get_endpoint(
            "collection", bucket=BUCKET_ID, collection=COLLECTION_ID
        )
        self.attachment_uri = f"{record_uri}/attachment"

    @responses.activate
    def test_record_was_posted(self):
        responses.add(
            responses.POST,
            self.attachment_uri,
            json={"data": {"commit-hash": "fake-commit-hash"}},
        )
        responses.add(
            responses.PATCH, self.collection_uri, json={"data": {"status": "to-review"}}
        )

        with tempfile.TemporaryDirectory() as tmp:
            dafsa_filename = f"{tmp}/dafsa.bin"
            with open(dafsa_filename, "wb") as f:
                f.write(b"some binary data")
            remote_settings_publish(self.client, "fake-commit-hash", dafsa_filename)

            self.assertEqual(len(responses.calls), 2)

            self.assertEqual(responses.calls[0].request.url, self.attachment_uri)
            self.assertEqual(responses.calls[0].request.method, "POST")

            self.assertEqual(responses.calls[1].request.url, self.collection_uri)
            self.assertEqual(responses.calls[1].request.method, "PATCH")


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
        self.record_uri_preview = self.event.get("server") + client.get_endpoint(
            "record", id=RECORD_ID, bucket=BUCKET_ID_PREVIEW, collection=COLLECTION_ID
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
    def test_prepare_and_publish_not_called_when_pending_review(self):
        responses.add(
            responses.GET, COMMIT_HASH_URL, json=[{"sha": "fake-commit-hash"}]
        )
        responses.add(
            responses.GET,
            self.record_uri,
            json={"data": {"commit-hash": "different-fake-commit-hash"}},
        )
        responses.add(
            responses.GET,
            self.record_uri_preview,
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
        responses.add(
            responses.GET,
            self.record_uri_preview,
            json={"data": {"commit-hash": "different-fake-commit-hash"}},
        )

        publish_dafsa(self.event, context=None)

        self.assertTrue(self.mocked_prepare.called)
        self.assertTrue(self.mocked_publish.called)
