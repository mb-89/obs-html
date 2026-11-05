"""The network guard: a test that opens a network connection fails, naming itself, the host and the remedy.

Reader: whoever writes a test that needs data from outside, or changes this part's conftest.

`install()` replaces the socket calls that reach a host by name (`socket.getaddrinfo`, which
`socket.create_connection` and urllib use) or by address (`socket.socket.connect`). A call to a
loopback or unspecified address and a local socket stay open: preview servers and the browser
driver use them. A refused call raises `NetworkGuardError` and is recorded; `fail()` turns the
report of the test phase that made it into a failure, so a test fails even where the code under
test catches the error, as the vault does for a remote image.
"""
from __future__ import annotations

import contextlib
import ipaddress
import socket

OWNER = "test/network_guard.py (adapters/html)"
REMEDY = ("read the asset from a file under test/fixtures, or build the core's Document through the "
          "core's test/offline_obs_document.py, which serves remote images without the network")


class NetworkGuardError(OSError):
    """A test tried to reach the network; the message names the test, the host and the remedy."""


_attempts: list[str] = []
_test = ["no test (collection or a session fixture)"]
_original = {}


def _local(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if host in (None, "", "localhost"):
        return True
    try:
        address = ipaddress.ip_address(str(host).split("%")[0])
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


def _refuse(host, port) -> None:
    message = (f"{OWNER}: test {_test[-1]} opened a network connection to {host}:{port}. No test "
               f"reaches the network. Remedy: {REMEDY}.")
    _attempts.append(message)
    raise NetworkGuardError(message)


def _getaddrinfo(host, port, *args, **kwargs):
    if not _local(host):
        _refuse(host, port)
    return _original["getaddrinfo"](host, port, *args, **kwargs)


def _checked(name: str):
    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _local(address[0]):
            _refuse(address[0], address[1])
        return _original[name](self, address)
    return connect


def install() -> None:
    """Guard this process for its whole run; installing twice changes nothing."""
    if _original:
        return
    _original.update(getaddrinfo=socket.getaddrinfo, connect=socket.socket.connect,
                     connect_ex=socket.socket.connect_ex)
    socket.getaddrinfo = _getaddrinfo
    socket.socket.connect = _checked("connect")
    socket.socket.connect_ex = _checked("connect_ex")


@contextlib.contextmanager
def running(test: str):
    """Name the running test in the guard's messages."""
    _test.append(test)
    try:
        yield
    finally:
        _test.pop()


def take() -> list[str]:
    """The attempts recorded since the last call; a test that provokes one takes it."""
    attempts = list(_attempts)
    _attempts.clear()
    return attempts


def fail(report) -> None:
    """Fail a test phase's report when that phase tried to reach the network."""
    attempts = take()
    if attempts:
        report.outcome = "failed"
        report.longrepr = "\n".join(attempts)
