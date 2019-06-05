import requests
from requests.exceptions import HTTPError
import tempfile
import subprocess
from kinto_http import Client, KintoException
import sys

COMMIT_HASH_URL = "https://api.github.com/repos/publicsuffix/list/commits/master"

LIST_URL = (
    "https://raw.githubusercontent.com/publicsuffix/list/master/public_suffix_list.dat"
)

MAKE_DAFSA_PY = "https://raw.githubusercontent.com/arpit73/temp_dafsa_testing_repo/master/publishing/make_dafsa.py"
PREPARE_TLDS_PY = "https://raw.githubusercontent.com/arpit73/temp_dafsa_testing_repo/master/publishing/prepare_tlds.py"


SERVER = "https://kinto.dev.mozaws.net/v1"
CREDENTIALS = ("arpit73", "s3cr3t")  # (username, password)

BUCKET_ID = "firefox-core-network-dns"
COLLECTION_ID = "public-suffix-list"
RECORD_ID = "latest-commit-hash"


def handle_request_errors(func):
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
        except Exception as err:
            print(f"Other error occurred: {err}")
        else:
            print("Fetching Failed")

    return inner


@handle_request_errors
def get_latest_hash(url):
    response = requests.get(url)
    return response.json()["sha"]


@handle_request_errors
def download_resources(*urls, **kwargs):
    for url in urls:
        # file_location is found by appending the file_name(at the end of url string) to temp directory
        file_location = kwargs["directory"] + "/" + url.split("/")[-1]
        print(file_location)
        response = requests.get(url, stream=True)
        with open(file_location, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                else:
                    print("Error!!!")


def record_exists(record):
    # will check if a valid record exists already a and return true if so
    pass


def make_dafsa_and_publish(client, latest_hash):
    with tempfile.TemporaryDirectory() as tmp:
        download_resources(LIST_URL, MAKE_DAFSA_PY, PREPARE_TLDS_PY, directory=tmp)
        """
        prepare_tlds.py is called with the two arguments the location of 
        the downloaded public suffix list and the name of the output file
        """
        subprocess.run(
            [
                "python3",
                f"{tmp}/prepare_tlds.py",
                f"{tmp}/public_suffix_list.dat",
                f"{tmp}/etld_data.inc",
            ]
        )
        subprocess.run(["ls", tmp])
        client.update_record(
            id=RECORD_ID,
            data={"latest-commit-hash": latest_hash},
            collection=COLLECTION_ID,
            bucket=BUCKET_ID,
        )


def publish_dafsa():
    client = Client(server_url=SERVER, auth=CREDENTIALS)
    latest_hash = get_latest_hash(COMMIT_HASH_URL)
    record = client.get_record(id=RECORD_ID, bucket=BUCKET_ID, collection=COLLECTION_ID)
    if record_exists(record):
        if record["data"]["latest-commit-hash"] == latest_hash:
            return 0
        else:
            make_dafsa_and_publish(client, latest_hash)
    else:
        make_dafsa_and_publish(client, latest_hash)
