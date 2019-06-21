import unittest
import tempfile
import os
import subprocess
import json

import requests
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
        self.assertRaises(HTTPError, get_latest_hash(COMMIT_HASH_URL + "c"))

    @responses.activate
    def test_make_dafsa_and_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            download_resources(tmp, PREPARE_TLDS_PY, MAKE_DAFSA_PY, LIST_URL)
            self.assertEqual(
                sorted(os.listdir(tmp)),
                sorted(["public_suffix_list.dat", "prepare_tlds.py", "make_dafsa.py"]),
            )

            output_binary_name = "dafsa.bin"
            output_binary_path = os.path.join(tmp, output_binary_name)
            prepare_tlds_py_path = os.path.join(tmp, "prepare_tlds.py")
            raw_psl_path = os.path.join(tmp, PSL_FILENAME)

            command = f"python3 {prepare_tlds_py_path} {raw_psl_path} --bin > {output_binary_path}"
            run = subprocess.Popen(
                command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            run.wait()

            self.assertEqual(run.returncode, 0)
            self.assertGreater(os.path.getsize(output_binary_path), 0)

            # responses.add(
            #     responses.GET,
            #     "https://kinto.dev.mozaws.net/v1",
            #     json={"error": "not found"},
            #     status=200,
            # )
            # client = Client(
            #     server_url="https://kinto.dev.mozaws.net/v1",
            #     auth=("user", "password"),
            #     bucket="test-bucket",
            #     collection="test-collection",
            # )

            # mimetype = "application/octet-stream"
            # filecontent = open(output_binary_path, "rb").read()
            # record_uri = client.get_endpoint("record", id="text-record")
            # attachment_uri = f"{record_uri}/attachment"
            # multipart = [("attachment", (output_binary_name, filecontent, mimetype))]
            # commit_hash = json.dumps(
            #     {"commit-hash": "cf23df2207d99a74fbe169e3eba035e633b65d94"}
            # )
            # client.session.request(
            #     method="post",
            #     data=commit_hash,
            #     endpoint=attachment_uri,
            #     files=multipart,
            # )


if __name__ == "__main__":
    unittest.main()
