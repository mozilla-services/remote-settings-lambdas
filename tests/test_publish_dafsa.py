import unittest
import tempfile
import os
import json

import requests
import responses
from requests import HTTPError
from kinto_http import Client


from commands.publish_dafsa import (
    get_latest_hash,
    download_resources,
    prepare_dafsa,
    remote_settings_publish,
    publish_dafsa,
    PSL_FILENAME,
    PREPARE_TLDS_PY,
    MAKE_DAFSA_PY,
    LIST_URL,
    COMMIT_HASH_URL,
)


class TestUtilMethods(unittest.TestCase):
    def test_get_latest_hash(self):
        self.assertEqual(len(get_latest_hash(COMMIT_HASH_URL)), 40)
        self.assertRaises(HTTPError, get_latest_hash(COMMIT_HASH_URL + "c"))

    def test_download_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            download_resources(tmp, PREPARE_TLDS_PY, MAKE_DAFSA_PY, LIST_URL)
            self.assertEqual(
                sorted(os.listdir(tmp)),
                sorted(["public_suffix_list.dat", "prepare_tlds.py", "make_dafsa.py"]),
            )
            self.assertRaises(HTTPError, download_resources(tmp, PREPARE_TLDS_PY + "c"))


class TestDafsaCreationPublishingMethods(unittest.TestCase):
    def test_prepare_dafsa(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_binary_path = prepare_dafsa(tmp)
            self.assertIn(os.path.basename(output_binary_path), os.listdir(tmp))
            self.assertGreater(os.path.getsize(output_binary_path), 0)

    @responses.activate
    def test_remote_settings_publish(self):
        responses.add(responses.GET, json)


if __name__ == "__main__":
    unittest.main()
