import json
import os
import subprocess
import tempfile

import requests
from kinto_http import Client, KintoException


PSL_FILENAME = "public_suffix_list.dat"

COMMIT_HASH_URL = (
    f"https://api.github.com/repos/publicsuffix/list/commits?path={PSL_FILENAME}"
)
LIST_URL = f"https://raw.githubusercontent.com/publicsuffix/list/master/{PSL_FILENAME}"

MAKE_DAFSA_PY = "https://hg.mozilla.org/mozilla-central/raw-file/27de3a352a395fd4fac5964d1027a3144e28224b/xpcom/ds/tools/make_dafsa.py"  # noqa
PREPARE_TLDS_PY = "https://hg.mozilla.org/mozilla-central/raw-file/822cb68b6ab75c96d7e36aa1f7fffda122d41f0c/netwerk/dns/prepare_tlds.py"  # noqa

BUCKET_ID = os.getenv("BUCKET_ID", "main-workspace")
BUCKET_ID_PREVIEW = "main-preview"
COLLECTION_ID = "public-suffix-list"
RECORD_ID = "tld-dafsa"


def get_latest_hash(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()[0]["sha"]


def download_resources(directory, *urls):
    for url in urls:
        file_name = os.path.basename(url)
        file_location = os.path.join(directory, file_name)
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(file_location, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)


def get_stored_hash(client, bucket=None):
    record = {}
    try:
        record = client.get_record(id=RECORD_ID, bucket=bucket)
    except KintoException as e:
        if e.response is None or e.response.status_code != 404:
            raise

    return record.get("data", {}).get("commit-hash")


def prepare_dafsa(directory):
    download_resources(directory, LIST_URL, MAKE_DAFSA_PY, PREPARE_TLDS_PY)
    """
    prepare_tlds.py is called with the three arguments the location of
    the downloaded public suffix list, the name of the output file and
    the '--bin' flag to create a binary file
    """
    output_binary_name = "dafsa.bin"
    output_binary_path = os.path.join(directory, output_binary_name)
    prepare_tlds_py_path = os.path.join(directory, "prepare_tlds.py")
    raw_psl_path = os.path.join(directory, PSL_FILENAME)
    # Make the DAFSA
    command = (
        f"python3 {prepare_tlds_py_path} {raw_psl_path} --bin > {output_binary_path}"
    )
    run = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    run.wait()
    if run.returncode != 0:
        raise Exception("DAFSA Build Failed !!!")

    return output_binary_path


def remote_settings_publish(client, latest_hash, binary_path):
    # Upload the attachment
    binary_name = os.path.basename(binary_path)
    mimetype = "application/octet-stream"
    filecontent = open(binary_path, "rb").read()
    record_uri = client.get_endpoint("record", id=RECORD_ID)
    attachment_uri = f"{record_uri}/attachment"
    multipart = [("attachment", (binary_name, filecontent, mimetype))]
    commit_hash = json.dumps({"commit-hash": latest_hash})
    client.session.request(
        method="post", data=commit_hash, endpoint=attachment_uri, files=multipart
    )
    # Requesting the new record for review
    client.patch_collection(data={"status": "to-review"})


def publish_dafsa(event, context):
    """Publish the Public Suffix List from https://publicsuffix.org"""
    server = event.get("server") or os.getenv("SERVER")
    auth = event.get("auth") or os.getenv("AUTH")
    # Auth format assumed to be "Username:Password"
    if auth:
        auth = tuple(auth.split(":", 1))

    client = Client(
        server_url=server, auth=auth, bucket=BUCKET_ID, collection=COLLECTION_ID
    )

    latest_hash = get_latest_hash(COMMIT_HASH_URL)
    stored_hash = get_stored_hash(client)

    already_published = stored_hash == latest_hash
    if not already_published:
        stored_hash_preview = get_stored_hash(client, bucket=BUCKET_ID_PREVIEW)
        already_published = stored_hash_preview == latest_hash

    if not already_published:
        with tempfile.TemporaryDirectory() as tmp:
            output_binary_path = prepare_dafsa(tmp)
            remote_settings_publish(client, latest_hash, output_binary_path)
