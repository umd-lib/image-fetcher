import logging

import pytest
import requests

import fetcher
from fetcher import fetch_iiif_from_repo_uri
from iiif import ImageServer


@pytest.fixture
def image_server():
    return ImageServer('http://example.com/iiif/')


class MockSuccessResponse:
    ok = True
    content = b'x' * 1024


class MockFailureResponse:
    ok = False
    status_code = 404
    reason = 'Not Found'


def test_repo_uri_outside_repo(monkeypatch, image_server):
    monkeypatch.setattr(fetcher, 'REPO_ENDPOINT_URI', 'http://example.com/fcrepo/rest')
    with pytest.raises(AssertionError):
        fetch_iiif_from_repo_uri(image_server, 'http://other.example.com/foo')


def test_repo_path_no_leading_slash(monkeypatch, image_server):
    monkeypatch.setattr(fetcher, 'REPO_ENDPOINT_URI', 'http://example.com/fcrepo/rest')
    with pytest.raises(AssertionError):
        fetch_iiif_from_repo_uri(image_server, 'http://example.com/fcrepo/rest?foo')


def test_successful_retrieval(monkeypatch, image_server, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(fetcher, 'REPO_ENDPOINT_URI', 'http://example.com/fcrepo/rest')
    monkeypatch.setattr(requests, 'get', lambda *args, **kwargs: MockSuccessResponse())
    fetch_iiif_from_repo_uri(image_server, 'http://example.com/fcrepo/rest/foo')
    assert 'Fetched 1024 bytes' in caplog.text


def test_failed_retrieval(monkeypatch, image_server, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(fetcher, 'REPO_ENDPOINT_URI', 'http://example.com/fcrepo/rest')
    monkeypatch.setattr(requests, 'get', lambda *args, **kwargs: MockFailureResponse())
    with pytest.raises(RuntimeError) as e:
        fetch_iiif_from_repo_uri(image_server, 'http://example.com/fcrepo/rest/foo')
        assert 'Unable to retrieve' in str(e)
