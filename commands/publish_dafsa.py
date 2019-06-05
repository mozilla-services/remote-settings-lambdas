import requests
from requests.exceptions import HTTPError
import tempfile
import subprocess
from kinto_http import Client, KintoException
import mimetypes
import os

COMMIT_HASH_URL = "https://api.github.com/repos/publicsuffix/list/commits/master"

LIST_URL = (
    "https://raw.githubusercontent.com/publicsuffix/list/master/public_suffix_list.dat"
)

MAKE_DAFSA_PY = "https://raw.githubusercontent.com/arpit73/temp_dafsa_testing_repo/master/publishing/make_dafsa.py"
PREPARE_TLDS_PY = "https://raw.githubusercontent.com/arpit73/temp_dafsa_testing_repo/master/publishing/prepare_tlds.py"


SERVER = "https://kinto.dev.mozaws.net/v1"
CREDENTIALS = (os.getenv("USERNAME"), os.getenv("PASSWORD"))  # (username, password)

BUCKET_ID = "test-firefox-core-network-dns"
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
    modified_files = response.json()["files"]
    for f in modified_files:
        if f["filename"] == "public_suffix_list.dat":
            return response.json()["sha"]
    return ""


@handle_request_errors
def download_resources(directory, *urls):
    for url in urls:
        # file_location is found by appending the file_name(at the end of url string) to temp directory
        file_name = os.path.basename(url)
        file_location = os.path.join(directory, file_name)
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
    return False


def make_dafsa_and_publish(client, latest_hash):
    with tempfile.TemporaryDirectory() as tmp:
        download_resources(tmp, LIST_URL, MAKE_DAFSA_PY, PREPARE_TLDS_PY)
        """
        prepare_tlds.py is called with the two arguments the location of 
        the downloaded public suffix list and the name of the output file
        """
        prepare_tlds_py_path = os.path.join(tmp, "prepare_tlds.py")
        raw_psl_path = os.path.join(tmp, "public_suffix_list.dat")
        output_binary_path = os.path.join(tmp, "etld_data.json")

        subprocess.run(
            ["python3", prepare_tlds_py_path, raw_psl_path, output_binary_path]
        )

        subprocess.run(["ls", tmp])

        # Upload the record
        client.update_record(
            id=RECORD_ID,
            data={"latest-commit-hash": latest_hash},
            collection=COLLECTION_ID,
            bucket=BUCKET_ID,
        )

        # Upload the attachment
        mimetype, _ = mimetypes.guess_type(output_binary_path)
        filename = os.path.basename(output_binary_path)
        filecontent = open(output_binary_path, "rb").read()
        record_uri = client.get_endpoint(
            "record", id=RECORD_ID, bucket=BUCKET_ID, collection=COLLECTION_ID
        )
        attachment_uri = f"{record_uri}/attachment"
        multipart = [("attachment", (filename, filecontent, mimetype))]
        try:
            body, _ = client.session.request(
                method="post", endpoint=attachment_uri, files=multipart
            )
        except KintoException as e:
            print(output_binary_path, "error during upload.", e)
        else:
            print(body)


def publish_dafsa():
    client = Client(server_url=SERVER, auth=CREDENTIALS)
    latest_hash = get_latest_hash()
    try:
        record = client.get_record(
            id=RECORD_ID, bucket=BUCKET_ID, collection=COLLECTION_ID
        )
    except KintoException as e:
        print(e)
    if record_exists(record) and (record["data"]["latest-commit-hash"] == latest_hash):
        return 0
    else:
        make_dafsa_and_publish(client, latest_hash)


publish_dafsa()
