import requests
from requests.exceptions import HTTPError
import wget
import tempfile
import subprocess

COMMIT_HASH_URL = "https://api.github.com/repos/publicsuffix/list/commits/master"
LIST_URL = (
    "https://raw.githubusercontent.com/publicsuffix/list/master/public_suffix_list.dat"
)
MAKE_DAFSA_PY = "https://raw.githubusercontent.com/arpit73/temp_dafsa_testing_repo/master/publishing/make_dafsa.py"
PREPARE_TLDS_PY = "https://raw.githubusercontent.com/arpit73/temp_dafsa_testing_repo/master/publishing/prepare_tlds.py"

DAFSA_OUTPUT = "./etld_data.inc"


def get_latest_hash(url):
    try:
        response = requests.get(url)
        return response.json()["sha"]
    except HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")
    else:
        print("Failed")


# can be replaced with requests later to avoid extra dependency
def download_resources(*urls, **kwargs):
    for url in urls:
        wget.download(url, out=kwargs["directory"])


# TODO
def check_last_stored_hash():
    pass


latest_hash = get_latest_hash(COMMIT_HASH_URL)


with tempfile.TemporaryDirectory() as tmp:
    # print(tmp)
    download_resources(LIST_URL, MAKE_DAFSA_PY, PREPARE_TLDS_PY, directory=tmp)
    """
       prepare_tlds.py is called with the two arguments the location 
       of the downloaded psl and the name of the output file
    """
    subprocess.run(
        [
            "python3",
            f"{tmp}/prepare_tlds.py",
            f"{tmp}/public_suffix_list.dat",
            f"{tmp}/etld_data.inc",
        ]
    )
    # import prepare_tlds
    # prepare_tlds.main(DAFSA_OUTPUT, PSL_LOCATION)
    path = tmp + "/etld_data.inc"
    with open(path, "r") as f:
        print(f.read())
    # import make_dafsa
    # import prepare_tlds
