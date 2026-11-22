"""A run of this adapter's tests installs its Node test package itself (the core's test/suite.py,
install_node_packages), so a fresh checkout needs no setup step first.

Reader: whoever changes how this adapter's tests are set up.
"""
from types import SimpleNamespace

import conftest


def test_the_session_start_installs_this_repositorys_node_package(monkeypatch) -> None:
    seen = []
    monkeypatch.setattr(conftest.suite, "install_node_packages", lambda packages: seen.append(("set up", packages)))
    monkeypatch.setattr(conftest.suite, "record_workers", lambda config: seen.append(("workers", config)))
    config = SimpleNamespace()
    conftest.pytest_sessionstart(SimpleNamespace(config=config))

    assert seen == [("set up", [conftest.ROOT / "test" / "browser"]), ("workers", config)]
    assert conftest.suite.__file__ == str(conftest.CORE_ROOT / "test" / "suite.py")
