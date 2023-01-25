import pytest
import stomp

from fetcher import create_stomp_connection


@pytest.fixture
def dummy_stomp_connect(monkeypatch):
    monkeypatch.setattr(stomp.Connection11, 'connect', lambda _: True)


class TestListener(stomp.ConnectionListener):
    def __init__(self, connection):
        self.connection = connection


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
    conn = create_stomp_connection('localhost:61613', listeners=[('test', TestListener)])
    assert isinstance(conn.get_listener('test'), TestListener)
    assert conn.get_listener('test').connection == conn
