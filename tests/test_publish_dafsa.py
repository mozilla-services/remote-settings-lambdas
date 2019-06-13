import unittest
import tempfile
import os

from requests import HTTPError

from commands.publish_dafsa import (
    get_latest_hash,
    download_resources,
    PREPARE_TLDS_PY,
    MAKE_DAFSA_PY,
    LIST_URL,
    COMMIT_HASH_URL,
)  # noqa


class TestDafsaPublishingMethods(unittest.TestCase):
    def test_get_latest_hash(self):
        self.assertEqual(len(get_latest_hash(COMMIT_HASH_URL)), 40)
        self.assertRaises(HTTPError, get_latest_hash(COMMIT_HASH_URL + "c"))

    def test_download_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            download_resources(tmp, PREPARE_TLDS_PY, MAKE_DAFSA_PY, LIST_URL)
            self.assertEqual(len(os.listdir(tmp)), 3)
            self.assertEqual(
                sorted(os.listdir(tmp)),
                sorted(["public_suffix_list.dat", "prepare_tlds.py", "make_dafsa.py"]),
            )
            self.assertRaises(
                HTTPError,
                download_resources(
                    tmp, PREPARE_TLDS_PY + "c", MAKE_DAFSA_PY + "c", LIST_URL + "c"
                ),
            )


if __name__ == "__main__":
    unittest.main()
