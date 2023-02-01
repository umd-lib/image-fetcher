import pytest
import stomp
from stomp.exception import ConnectFailedException

from fetcher import create_stomp_connection


@pytest.fixture
def dummy_stomp_connect(monkeypatch):
    monkeypatch.setattr(stomp.Connection11, 'connect', lambda _: True)


class MockListener(stomp.ConnectionListener):
    def __init__(self, connection):
        self.connection = connection


class MockFailedConnection:
    def connect(self):
        raise ConnectFailedException()


def test_creates_connection(dummy_stomp_connect):
    conn = create_stomp_connection('localhost:61613')
    assert isinstance(conn, stomp.Connection11)


def test_invalid_listener():
    with pytest.raises(ValueError):
        create_stomp_connection('localhost:61613', listeners=[('foo', 'bar')])


def test_listener_object(dummy_stomp_connect):
    conn = create_stomp_connection('localhost:61613', listeners=[('print', stomp.PrintingListener())])
    assert isinstance(conn.get_listener('print'), stomp.PrintingListener)


def test_listener_callable(dummy_stomp_connect):
    conn = create_stomp_connection('localhost:61613', listeners=[('print', lambda c: stomp.PrintingListener())])
    assert isinstance(conn.get_listener('print'), stomp.PrintingListener)


def test_listener_class(dummy_stomp_connect):
    conn = create_stomp_connection('localhost:61613', listeners=[('test', MockListener)])
    assert isinstance(conn.get_listener('test'), MockListener)
    assert conn.get_listener('test').connection == conn


def test_failed_connection(monkeypatch):
    monkeypatch.setattr(stomp, 'Connection11', lambda *args, **kwargs: MockFailedConnection())
    with pytest.raises(ConnectFailedException):
        create_stomp_connection('localhost:61613')
