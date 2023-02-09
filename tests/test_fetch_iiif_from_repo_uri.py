import logging
from unittest.mock import patch

import pytest
from requests import RequestException

from fetcher import get_url, get_iiif_identifier, fetch_iiif_image
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


@patch('fetcher.REPO_ENDPOINT_URI', 'http://example.com/fcrepo/rest')
def test_repo_uri_outside_repo(monkeypatch):
    with pytest.raises(AssertionError, match='must start with the endpoint URI'):
        get_iiif_identifier('http://other.example.com/foo')


@patch('fetcher.REPO_ENDPOINT_URI', 'http://example.com/fcrepo/rest')
def test_repo_path_no_leading_slash(monkeypatch):
    with pytest.raises(AssertionError, match='must start with "/"'):
        get_iiif_identifier('http://example.com/fcrepo/rest?foo')


@patch('fetcher.REPO_ENDPOINT_URI', 'http://example.com/fcrepo/rest')
def test_get_iiif_identifier(monkeypatch):
    identifier = get_iiif_identifier('http://example.com/fcrepo/rest/foo/bar/123')
    assert identifier == 'fcrepo:foo:bar:123'


@patch('requests.get', return_value=MockSuccessResponse)
@patch('fetcher.REPO_ENDPOINT_URI', 'http://example.com/fcrepo/rest')
def test_successful_retrieval(monkeypatch, image_server, caplog):
    caplog.set_level(logging.INFO)
    image_uri = image_server.image_uri(get_iiif_identifier('http://example.com/fcrepo/rest/foo'))
    fetch_iiif_image(image_uri)
    assert 'Fetched 1024 bytes' in caplog.text


@patch('requests.get', return_value=MockFailureResponse)
@patch('fetcher.REPO_ENDPOINT_URI', 'http://example.com/fcrepo/rest')
def test_failed_retrieval(monkeypatch, image_server, caplog):
    caplog.set_level(logging.INFO)
    image_uri = image_server.image_uri(get_iiif_identifier('http://example.com/fcrepo/rest/foo'))
    with pytest.raises(RuntimeError) as e:
        fetch_iiif_image(image_uri)
        assert 'Unable to retrieve' in str(e)


@patch('requests.get', side_effect=RequestException)
def test_get_url_failure(mock_get):
    with pytest.raises(RequestException):
        get_url('http://example.com')
    mock_get.assert_called()
    assert mock_get.call_count == 3


@patch('requests.get', side_effect=[RequestException, MockSuccessResponse])
def test_get_url_succeed_within_retries(mock_get):
    response = get_url('http://example.com')
    mock_get.assert_called()
    assert mock_get.call_count == 2
    assert response.ok


@patch('requests.get', return_value=MockSuccessResponse)
def test_get_url_success(mock_get):
    response = get_url('http://example.com')
    mock_get.assert_called_once()
    assert response.ok
