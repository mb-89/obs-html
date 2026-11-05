"""No test reaches the network: a connection fails the test and names the test, the host and the remedy."""
import socket
from types import SimpleNamespace

import pytest

import network_guard


def test_a_connection_to_a_host_fails_naming_the_test_the_host_and_the_remedy(request) -> None:
    with pytest.raises(network_guard.NetworkGuardError) as raised:
        socket.create_connection(("example.invalid", 443), timeout=1)

    assert network_guard.take() == [str(raised.value)]
    message = str(raised.value)
    assert message.startswith(f"{network_guard.OWNER}: test {request.node.nodeid} ")
    assert "example.invalid:443" in message
    assert "test/fixtures" in message


def test_an_attempt_the_code_caught_still_fails_the_test_phase() -> None:
    with socket.socket() as connection, pytest.raises(OSError):
        connection.connect(("192.0.2.1", 80))
    report = SimpleNamespace(outcome="passed", longrepr=None)

    network_guard.fail(report)

    assert report.outcome == "failed"
    assert "192.0.2.1:80" in report.longrepr
