from unittest.mock import MagicMock

import pytest
import stomp


# Fixtures

@pytest.fixture(scope='session')
def mock_stomp_connection():
    return MagicMock(spec=stomp.Connection11)
