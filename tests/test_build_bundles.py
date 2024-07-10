import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest
import responses

from commands.build_bundles import (
    KintoClient,
    build_bundles,
    call_parallel,
    fetch_all_changesets,
    fetch_attachment,
    get_modified_timestamp,
    sync_cloud_storage,
    write_zip,
)


@pytest.fixture
def mock_fetch_all_changesets():
    with patch("commands.build_bundles.fetch_all_changesets") as mock_fetch:
        yield mock_fetch


@pytest.fixture
def mock_write_zip():
    with patch("commands.build_bundles.write_zip") as mock_write:
        yield mock_write


@pytest.fixture
def mock_sync_cloud_storage():
    with patch("commands.build_bundles.sync_cloud_storage") as mock_sync_cloud_storage:
        yield mock_sync_cloud_storage


@pytest.fixture
def mock_storage_client():
    with patch("commands.build_bundles.storage.Client") as mock_client:
        mock_bucket = MagicMock()
        mock_client.return_value.bucket.return_value = mock_bucket
        yield mock_bucket


@pytest.fixture
def mock_environment(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/path/creds.json")


def test_call_parallel():
    def dummy_func(x, y):
        return x + y

    args_list = [(1, 2), (3, 4), (5, 6)]
    results = call_parallel(dummy_func, args_list)
    assert results == [3, 7, 11]


@responses.activate
@patch("commands.build_bundles.random")
def test_fetch_all_changesets(mock_random):
    mock_random.randint.return_value = 42
    changeset_url = (
        "http://example.com/v1/buckets/{bid}/collections/{cid}/changeset?_expected={expected}"
    )
    responses.add(
        responses.GET,
        changeset_url.format(bid="monitor", cid="changes", expected=42),
        json={
            "changes": [
                {"bucket": "bucket1", "collection": "collection1", "last_modified": 123},
                {"bucket": "bucket2", "collection": "collection2", "last_modified": 456},
            ]
        },
    )
    responses.add(
        responses.GET,
        changeset_url.format(bid="bucket1", cid="collection1", expected=123),
        json={"metadata": {"id": "collection1"}, "changes": [{"id": "abc"}]},
    )
    responses.add(
        responses.GET,
        changeset_url.format(bid="bucket2", cid="collection2", expected=456),
        json={"metadata": {"id": "collection2"}, "changes": [{"id": "edf"}]},
    )

    client = KintoClient(server_url="http://example.com/v1")

    changesets = fetch_all_changesets(client)
    assert len(changesets) == 2
    assert changesets[0]["bucket"] == "bucket1"
    assert changesets[0]["metadata"]["id"] == "collection1"
    assert changesets[1]["bucket"] == "bucket2"
    assert changesets[1]["metadata"]["id"] == "collection2"


@responses.activate
def test_fetch_attachment():
    url = "http://example.com/file"
    responses.add(responses.GET, url, body=b"file_content", status=200)

    content = fetch_attachment(url)
    assert content == b"file_content"


@responses.activate
def test_get_modified_timestamp():
    url = "http://example.com/file"
    responses.add(
        responses.GET,
        url,
        body=b"file_content",
        headers={"Last-Modified": "Wed, 03 Jul 2024 11:04:48 GMT"},
    )
    timestamp = get_modified_timestamp(url)
    assert timestamp == 1720004688000


@responses.activate
def test_get_modified_timestamp_missing():
    url = "http://example.com/file"
    responses.add(responses.GET, url, status=404)
    timestamp = get_modified_timestamp(url)
    assert timestamp is None


def test_write_zip(tmpdir):
    content = [("file1.txt", "content1"), ("file2.txt", "content2")]
    output_path = os.path.join(tmpdir, "test.zip")
    write_zip(output_path, content)

    with zipfile.ZipFile(output_path, "r") as zip_file:
        assert set(zip_file.namelist()) == {"file1.txt", "file2.txt"}
        assert zip_file.read("file1.txt") == b"content1"
        assert zip_file.read("file2.txt") == b"content2"


@responses.activate
def test_build_bundles(mock_fetch_all_changesets, mock_write_zip, mock_sync_cloud_storage):
    server_url = "http://testserver"
    event = {"server": server_url}

    responses.add(
        responses.GET,
        server_url,
        json={"capabilities": {"attachments": {"base_url": f"{server_url}/attachments/"}}},
    )
    responses.add(responses.GET, f"{server_url}/attachments/file.jpg", body=b"jpeg_content")

    responses.add(
        responses.GET,
        f"{server_url}/attachments/bundles/changesets.zip",
        headers={
            "Last-Modified": "Wed, 03 Jul 2024 11:04:48 GMT"  # 1720004688000
        },
    )

    mock_fetch_all_changesets.return_value = [
        {  # collection hasn't changed since last bundling
            "bucket": "bucket0",
            "changes": [
                {"id": "record1", "attachment": {"location": "file.jpg", "size": 10}},
                {"id": "record2"},
            ],
            "metadata": {"id": "collection0", "attachment": {"bundle": True}},
            "timestamp": 1720004688000 - 10,
        },
        {
            "bucket": "bucket1",
            "changes": [
                {"id": "record1", "attachment": {"location": "file.jpg", "size": 10}},
                {"id": "record2"},
            ],
            "metadata": {"id": "collection1", "attachment": {"bundle": True}},
            "timestamp": 1720004688000 + 10,
        },
        {  # collection without bundle flag
            "bucket": "bucket2",
            "changes": [{"id": "record2"}],
            "metadata": {"id": "collection2"},
            "timestamp": 1720004688000 + 10,
        },
        {  # collection without attachments
            "bucket": "bucket3",
            "changes": [{"id": "record3"}],
            "metadata": {"id": "collection3", "attachment": {"bundle": True}},
            "timestamp": 1720004688000 + 10,
        },
        {  # attachments too big
            "bucket": "bucket4",
            "changes": [
                {"id": "id1", "attachment": {"size": 10_000_000}},
                {"id": "id2", "attachment": {"size": 10_000_000}},
                {"id": "id3", "attachment": {"size": 10_000_000}},
            ],
            "metadata": {"id": "collection4", "attachment": {"bundle": True}},
            "timestamp": 1720004688000 + 10,
        },
    ]

    build_bundles(event, context={})

    assert mock_write_zip.call_count == 2  # One for changesets and only one for the attachments
    calls = mock_write_zip.call_args_list

    # Assert the first call (changesets.zip)
    changesets_zip_path, changesets_zip_files = calls[0][0]
    assert changesets_zip_path == "changesets.zip"
    assert len(changesets_zip_files) == 5
    assert changesets_zip_files[0][0] == "bucket0--collection0.json"
    assert changesets_zip_files[1][0] == "bucket1--collection1.json"
    assert changesets_zip_files[2][0] == "bucket2--collection2.json"
    assert changesets_zip_files[3][0] == "bucket3--collection3.json"

    # Assert the second call (attachments zip)
    attachments_zip_path, attachments_zip_files = calls[1][0]
    assert attachments_zip_path == "bucket1--collection1.zip"
    assert len(attachments_zip_files) == 2
    assert attachments_zip_files[0][0] == "record1.meta.json"
    assert attachments_zip_files[1][0] == "record1"
    assert attachments_zip_files[1][1] == b"jpeg_content"

    mock_sync_cloud_storage.assert_called_once_with(
        "remote-settings-test-local-attachments",
        "bundles",
        [
            "changesets.zip",
            "bucket1--collection1.zip",
        ],
        [
            "bucket2--collection2.zip",
            "bucket3--collection3.zip",
        ],
    )


def test_sync_cloud_storage_upload_and_delete(mock_storage_client, mock_environment):
    bucket = mock_storage_client

    mock_blob1 = MagicMock()
    mock_blob2 = MagicMock()
    bucket.blob.side_effect = [mock_blob1, mock_blob2]

    mock_blob3 = MagicMock()
    mock_blob3.name = "remote/file3.txt"
    bucket.list_blobs.return_value = [mock_blob1, mock_blob2, mock_blob3]

    sync_cloud_storage(
        "remote-bucket", "remote", ["file1.txt", "file2.txt"], ["file3.txt", "file4.txt"]
    )

    # Check uploads
    mock_blob1.upload_from_filename.assert_called_once_with("file1.txt")
    mock_blob2.upload_from_filename.assert_called_once_with("file2.txt")

    # Check deletions
    mock_blob3.delete.assert_called_once()
