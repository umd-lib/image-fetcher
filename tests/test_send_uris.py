from unittest.mock import MagicMock

import pytest
from stomp.exception import NotConnectedException

from fetcher import UnsentURIs, send_uris


def test_send_uris_failure(mock_stomp_connection):
    uris = ['foo', 'bar']
    mock_stomp_connection.send = MagicMock(side_effect=NotConnectedException)
    with pytest.raises(UnsentURIs) as e:
        send_uris(mock_stomp_connection, uris)
    assert isinstance(e.value, UnsentURIs)
    assert len(e.value.uris) == 2


def test_send_uris_success(mock_stomp_connection):
    uris = ['foo', 'bar']
    mock_stomp_connection.send = MagicMock()
    send_uris(mock_stomp_connection, uris)
    mock_stomp_connection.send.assert_called()
    assert mock_stomp_connection.send.call_count == 2
