"""A focused run of this adapter's tests installs the suite's Node test packages itself
(obs test/suite.py, set_up_focused_run), so a fresh checkout needs no setup step first.

Reader: whoever changes how this adapter's tests are set up.
"""
from types import SimpleNamespace

import conftest


def test_the_session_start_sets_up_a_focused_run(monkeypatch) -> None:
    seen = []
    monkeypatch.setattr(conftest.suite, "set_up_focused_run", lambda config: seen.append(("set up", config)))
    monkeypatch.setattr(conftest.suite, "record_workers", lambda config: seen.append(("workers", config)))
    config = SimpleNamespace()
    conftest.pytest_sessionstart(SimpleNamespace(config=config))

    assert seen == [("set up", config), ("workers", config)]
    assert conftest.suite.__file__ == str(conftest.CORE_ROOT / "test" / "suite.py")
