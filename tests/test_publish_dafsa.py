import unittest
import tempfile
import os
import subprocess

import responses
from requests import HTTPError
from kinto_http import Client


from commands.publish_dafsa import (
    get_latest_hash,
    download_resources,
    PSL_FILENAME,
    PREPARE_TLDS_PY,
    MAKE_DAFSA_PY,
    LIST_URL,
    COMMIT_HASH_URL,
)


class TestDafsaPublishingMethods(unittest.TestCase):
    def test_get_latest_hash(self):
        self.assertEqual(len(get_latest_hash(COMMIT_HASH_URL)), 40)
        # self.assertRaises(HTTPError, get_latest_hash(COMMIT_HASH_URL + "c"))

    @responses.activate
    def test_make_dafsa_and_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            download_resources(tmp, PREPARE_TLDS_PY, MAKE_DAFSA_PY, LIST_URL)
            self.assertEqual(
                sorted(os.listdir(tmp)),
                sorted(["public_suffix_list.dat", "prepare_tlds.py", "make_dafsa.py"]),
            )

            output_binary_name = "etld_data.json"
            output_binary_path = os.path.join(tmp, output_binary_name)
            prepare_tlds_py_path = os.path.join(tmp, "prepare_tlds.py")
            raw_psl_path = os.path.join(tmp, PSL_FILENAME)

            run = subprocess.run(
                [
                    "python3",
                    prepare_tlds_py_path,
                    raw_psl_path,
                    output_binary_path,
                    "--bin",
                ]
            )
            self.assertEqual(run.returncode, 0)
            self.assertGreater(os.path.getsize(output_binary_path), 0)
