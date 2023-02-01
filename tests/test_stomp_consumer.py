from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from stomp.exception import ConnectFailedException

import fetcher


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_connection_failure(monkeypatch, cli_runner):
    mock_create_stomp_connection_fail = MagicMock(side_effect=ConnectFailedException)
    monkeypatch.setattr(fetcher, 'create_stomp_connection', mock_create_stomp_connection_fail)
    result = cli_runner.invoke(fetcher.stomp_consumer)
    assert isinstance(result.exception, SystemExit)
    assert result.exit_code != 0
