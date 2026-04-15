import logging
from unittest.mock import patch

import pytest
from papaya.iiif2 import ImageService
from papaya.source import RepositoryService
from requests import RequestException

from fetcher import get_url, fetch_iiif_image, FetcherContext


@pytest.fixture
def image_service():
    return ImageService(endpoint='http://example.com/iiif/2')


@pytest.fixture
def repo_service():
    return RepositoryService(endpoint='http://example.com/fcrepo/rest')


class MockSuccessResponse:
    ok = True
    content = b'x' * 1024


class MockFailureResponse:
    ok = False
    status_code = 404
    reason = 'Not Found'


@patch('fetcher.REPO_ENDPOINT', 'http://example.com/fcrepo/rest')
@patch('fetcher.REPO_PREFIX', 'fcrepo:')
def test_get_iiif_identifier(monkeypatch):
    ctx = FetcherContext()
    identifier = ctx.repo_service.get_iiif_id('http://example.com/fcrepo/rest/foo/bar/123')
    assert identifier == 'fcrepo:foo:bar:123'


@patch('requests.get', return_value=MockSuccessResponse)
@patch('fetcher.REPO_ENDPOINT', 'http://example.com/fcrepo/rest')
@patch('fetcher.REPO_PREFIX', 'fcrepo:')
def test_successful_retrieval(image_service, caplog):
    ctx = FetcherContext()
    caplog.set_level(logging.INFO)
    resource = image_service.resource(ctx.repo_service.get_iiif_id('http://example.com/fcrepo/rest/foo'))
    fetch_iiif_image(resource)
    assert 'Fetched 1024 bytes' in caplog.text


@patch('requests.get', return_value=MockFailureResponse)
@patch('fetcher.REPO_ENDPOINT', 'http://example.com/fcrepo/rest')
@patch('fetcher.REPO_PREFIX', 'fcrepo:')
def test_failed_retrieval_http_error(image_service, caplog):
    ctx = FetcherContext()
    caplog.set_level(logging.INFO)
    resource = image_service.resource(ctx.repo_service.get_iiif_id('http://example.com/fcrepo/rest/foo'))
    with pytest.raises(RuntimeError) as e:
        fetch_iiif_image(resource)
        assert 'Unable to retrieve' in str(e)
        assert 'HTTP error' in str(e)


@patch('requests.get', side_effect=RequestException)
@patch('fetcher.REPO_ENDPOINT', 'http://example.com/fcrepo/rest')
@patch('fetcher.REPO_PREFIX', 'fcrepo:')
def test_failed_retrieval_request_exception(image_service, caplog):
    ctx = FetcherContext()
    caplog.set_level(logging.INFO)
    resource = image_service.resource(ctx.repo_service.get_iiif_id('http://example.com/fcrepo/rest/foo'))
    with pytest.raises(RuntimeError) as e:
        fetch_iiif_image(resource)
        assert 'Unable to retrieve' in str(e)
        assert 'Request error' in str(e)


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
