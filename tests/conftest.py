import socket
import sys
from pathlib import Path

import pytest

# Let tests import from scripts/ and src/ when pytest is run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.store import Store
from scripts.dev_sheet import FakeSpreadsheet

LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests must never reach Google. Any attempt to open a connection fails the test."""

    # Connections to this machine are allowed: on Windows, asyncio's event loop
    # (used by the API's TestClient) talks to itself over 127.0.0.1.
    real_connect = socket.socket.connect
    real_create_connection = socket.create_connection

    def is_local(address) -> bool:
        return isinstance(address, tuple) and address[0] in LOOPBACK

    def guarded_connect(sock, address):
        if not is_local(address):
            raise RuntimeError("A test tried to use the network. Fake the Google call instead.")
        return real_connect(sock, address)

    def guarded_create_connection(address, *args, **kwargs):
        if not is_local(address):
            raise RuntimeError("A test tried to use the network. Fake the Google call instead.")
        return real_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)


@pytest.fixture
def spreadsheet() -> FakeSpreadsheet:
    return FakeSpreadsheet()


@pytest.fixture
def store(spreadsheet) -> Store:
    return Store(spreadsheet, editor_email="pipeline@example.iam.gserviceaccount.com")
