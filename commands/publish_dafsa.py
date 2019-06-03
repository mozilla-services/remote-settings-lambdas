import requests
from requests.exceptions import HTTPError
import tempfile
import subprocess
from kinto_http import Client

COMMIT_HASH_URL = "https://api.github.com/repos/publicsuffix/list/commits/master"

LIST_URL = (
    "https://raw.githubusercontent.com/publicsuffix/list/master/public_suffix_list.dat"
)

MAKE_DAFSA_PY = "https://raw.githubusercontent.com/arpit73/temp_dafsa_testing_repo/master/publishing/make_dafsa.py"
PREPARE_TLDS_PY = "https://raw.githubusercontent.com/arpit73/temp_dafsa_testing_repo/master/publishing/prepare_tlds.py"


SERVER = "https://kinto.dev.mozaws.net/v1"
CREDENTIALS = ("arpit73", "s3cr3t")  # (username, password)


def get_latest_hash(url):
    try:
        response = requests.get(url)
        return response.json()["sha"]
    except HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")
    else:
        print("Fetching Failed")


# can be replaced with requests later to avoid extra dependency
def download_resources(*urls, **kwargs):
    for url in urls:
        file_location = kwargs["directory"] + "/" + url.split("/")[-1]
        print(file_location)
        try:
            response = requests.get(url, stream=True)
            with open(file_location, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                    else:
                        print("Error!!!")
        except HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
        except Exception as err:
            print(f"Other error occurred: {err}")


# TODO
def check_last_stored_hash():
    return True


def publish_dafsa(server, credentials, commit_hash):

    bucket_id = "firefox-core-network-dns"
    collection_id = "public-suffix-list"
    record_id = "latest-commit-hash"

    client = Client(server_url=SERVER, auth=credentials)
    client.create_bucket(id=bucket_id)
    client.create_collection(id=collection_id, bucket=bucket_id)

    client.create_record(
        id=record_id,
        data={"latest-commit-hash": commit_hash},
        collection=collection_id,
        bucket=bucket_id,
    )


with tempfile.TemporaryDirectory() as tmp:
    # print(tmp)
    download_resources(LIST_URL, MAKE_DAFSA_PY, PREPARE_TLDS_PY, directory=tmp)
    """
       prepare_tlds.py is called with the two arguments the location
       of the downloaded public suffix list and the name of the output file
    """
    subprocess.run(
        [
            "python3",
            f"{tmp}/prepare_tlds.py",
            f"{tmp}/public_suffix_list.dat",
            f"{tmp}/etld_data.inc",
        ]
    )
    subprocess.run(["ls",tmp])
    latest_hash = get_latest_hash(COMMIT_HASH_URL)
    # publish_dafsa(SERVER, CREDENTIALS, latest_hash)

