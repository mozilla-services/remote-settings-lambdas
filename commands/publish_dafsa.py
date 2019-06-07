import requests
import tempfile
from requests.exceptions import HTTPError

import os
import subprocess
from kinto_http import Client, KintoException

import json

COMMIT_HASH_URL = (
    "https://api.github.com/repos/publicsuffix/list/commits?path=public_suffix_list.dat"
)

LIST_URL = (
    "https://raw.githubusercontent.com/publicsuffix/list/master/public_suffix_list.dat"
)

MAKE_DAFSA_PY = "https://raw.githubusercontent.com/arpit73/temp_dafsa_testing_repo/master/publishing/make_dafsa.py"
PREPARE_TLDS_PY = "https://raw.githubusercontent.com/arpit73/temp_dafsa_testing_repo/master/publishing/prepare_tlds.py"


SERVER = "https://kinto.dev.mozaws.net/v1"
CREDENTIALS = (os.getenv("USERNAME"), os.getenv("PASSWORD"))  # (username, password)

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
def get_latest_hash():
    response = requests.get(COMMIT_HASH_URL)
    response.raise_for_status()
    return response.json()[0]["sha"]


@handle_request_errors
def download_resources(directory, *urls):
    for url in urls:
        # file_location is found by appending the file_name(at the end of url string) to temp directory
        file_name = os.path.basename(url)
        file_location = os.path.join(directory, file_name)
        print(file_location)
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(file_location, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                else:
                    print("Error!!!")


def make_dafsa_and_publish(client, latest_hash):
    with tempfile.TemporaryDirectory() as tmp:
        download_resources(tmp, LIST_URL, MAKE_DAFSA_PY, PREPARE_TLDS_PY)
        """
        prepare_tlds.py is called with the two arguments the location of 
        the downloaded public suffix list and the name of the output file
        """
        output_binary_name = "etld_data.json"

        prepare_tlds_py_path = os.path.join(tmp, "prepare_tlds.py")
        raw_psl_path = os.path.join(tmp, "public_suffix_list.dat")
        output_binary_path = os.path.join(tmp, output_binary_name)

        # Make the DAFSA
        run = subprocess.run(
            ["python3", prepare_tlds_py_path, raw_psl_path, output_binary_path]
        )
        if run.returncode != 0:
            print("DAFSA Build Failed !!!")
            return 1

        subprocess.run(["ls", tmp])

        # Upload the attachment
        mimetype = "application/octet-stream"
        filename = output_binary_name
        filecontent = open(output_binary_path, "rb").read()
        record_uri = client.get_endpoint("record", id=RECORD_ID)
        attachment_uri = f"{record_uri}/attachment"
        multipart = [("attachment", (filename, filecontent, mimetype))]
        commit_hash = json.dumps({"commit-hash": latest_hash})

        body, _ = client.session.request(
            method="post", data=commit_hash, endpoint=attachment_uri, files=multipart
        )
        print(body)


def publish_dafsa():
    client = Client(
        server_url=SERVER, auth=CREDENTIALS, bucket=BUCKET_ID, collection=COLLECTION_ID
    )
    latest_hash = get_latest_hash()
    # try:
    record = client.get_record(id=RECORD_ID)
    print(record)
    # except KintoException as e:
    #     print(e)

    # if record["data"]["latest-commit-hash"] == latest_hash:
    #     return 1
    # else:
    make_dafsa_and_publish(client, latest_hash)


publish_dafsa()
