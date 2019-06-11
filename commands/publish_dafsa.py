import os
import json
import tempfile
import subprocess
import requests
from requests.exceptions import HTTPError

from kinto_http import Client, KintoException


PSL_FILENAME = "public_suffix_list.dat"

COMMIT_HASH_URL = (
    f"https://api.github.com/repos/publicsuffix/list/commits?path={PSL_FILENAME}"
)
LIST_URL = f"https://raw.githubusercontent.com/publicsuffix/list/master/{PSL_FILENAME}"

MAKE_DAFSA_PY = "https://raw.githubusercontent.com/arpit73/temp_dafsa_testing_repo/master/publishing/make_dafsa.py"
PREPARE_TLDS_PY = "https://raw.githubusercontent.com/arpit73/temp_dafsa_testing_repo/master/publishing/prepare_tlds.py"

BUCKET_ID = "firefox-core-network-dns"
COLLECTION_ID = "public-suffix-list"
RECORD_ID = "latest-commit-hash"


def get_latest_hash():
    response = requests.get(COMMIT_HASH_URL)
    response.raise_for_status()
    return response.json()[0]["sha"]


def download_resources(directory, *urls):
    for url in urls:
        # file_location is found by appending the file_name(at the end of url string) to temp directory
        file_name = os.path.basename(url)
        file_location = os.path.join(directory, file_name)
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(file_location, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                try:
                    f.write(chunk)
                except IOError as e:
                    raise Exception(f"IO Error Occurred: {e}")


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
            raise Exception("DAFSA Build Failed !!!")

        subprocess.run(["ls", tmp])

        # Upload the attachment
        mimetype = "application/octet-stream"
        filecontent = open(output_binary_path, "rb").read()
        record_uri = client.get_endpoint("record", id=RECORD_ID)
        attachment_uri = f"{record_uri}/attachment"
        multipart = [("attachment", (output_binary_name, filecontent, mimetype))]
        commit_hash = json.dumps({"commit-hash": latest_hash})

        body, _ = client.session.request(
            method="post", data=commit_hash, endpoint=attachment_uri, files=multipart
        )


def publish_dafsa(event):

    SERVER = event["server"] or os.getenv("PUBLISH_DAFSA_SERVER")
    AUTH = event.get("publish_dafsa_auth") or os.getenv("PUBLISH_DAFSA_AUTH")
    # Auth format assumed to be "Username:Password"
    if AUTH:        
        AUTH = tuple(AUTH.split(":", 1))
    
    latest_hash = get_latest_hash()

    client = Client(
        server_url=SERVER, auth=AUTH, bucket=BUCKET_ID, collection=COLLECTION_ID
    )

    record = {}
    try:
        record = client.get_record(id=RECORD_ID)
    except KintoException as e:
        if not e.response or e.response.status != 404:
            raise KintoException(f"Record fetching failed: {e}")

    if record["data"]["commit-hash"] != latest_hash:
        make_dafsa_and_publish(client, latest_hash)

