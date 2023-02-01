import logging
from threading import Event
from unittest.mock import MagicMock

import pytest
import stomp
from stomp.utils import Frame

import fetcher
from fetcher import DisconnectListener, LoggingListener, ProcessingListener


@pytest.fixture
def mock_fetch_iiif_from_repo_uri_failed():
    return MagicMock(side_effect=RuntimeError('FAILED!'))


@pytest.fixture
def mock_stomp_connection():
    return MagicMock(spec=stomp.Connection11)


@pytest.fixture
def stomp_frame():
    return Frame(
        cmd='MESSAGE',
        headers={
            'CamelFcrepoUri': 'http://example.com/fcrepo/rest/1',
            'message-id': 'foo',
            'subscription': 'image-fetcher',
            'destination': '/queue/images',
        }
    )


def test_logging_listener_default_level():
    listener = LoggingListener()
    assert listener.level == logging.INFO


def test_logging_listener_custom_level():
    listener = LoggingListener(logging.DEBUG)
    assert listener.level == logging.DEBUG


def test_logging_listener_output(caplog):
    caplog.set_level(logging.INFO)
    listener = LoggingListener()
    listener.on_message(Frame('MESSAGE'))
    assert "on_message" in caplog.text


def test_disconnect_listener():
    listener = DisconnectListener(Event())
    assert not listener.disconnected.is_set()
    listener.on_disconnected()
    assert listener.disconnected.is_set()


def test_processing_listener_success(mocker, monkeypatch, stomp_frame):
    monkeypatch.setattr(fetcher, 'IIIF_BASE_URI', 'http://example.com/iiif/2/')
    mocker.patch('fetcher.fetch_iiif_from_repo_uri')
    connection = mocker.MagicMock(stomp.Connection11)
    listener = ProcessingListener(connection)
    assert listener.connection is connection
    listener.on_message(stomp_frame)
    connection.ack.assert_called_once_with('foo', 'image-fetcher')


def test_processing_listener_failure(monkeypatch, stomp_frame, mock_stomp_connection, mock_fetch_iiif_from_repo_uri_failed):
    monkeypatch.setattr(fetcher, 'IIIF_BASE_URI', 'http://example.com/iiif/2/')
    monkeypatch.setattr(fetcher, 'fetch_iiif_from_repo_uri', mock_fetch_iiif_from_repo_uri_failed)
    listener = ProcessingListener(mock_stomp_connection)
    listener.on_message(stomp_frame)
    mock_stomp_connection.send.assert_called_once_with(
        destination='/queue/images.errors',
        headers={
            **stomp_frame.headers,
            'Error': 'FAILED!',
            'original-destination': stomp_frame.headers['destination'],
        },
        body=stomp_frame.body,
    )
    mock_fetch_iiif_from_repo_uri_failed.assert_called()
