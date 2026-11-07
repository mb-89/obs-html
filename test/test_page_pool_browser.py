"""The page pool (test/conftest.py): a page goes back to the pool as a new context would show it.

Reader: whoever changes the pool or a browser test that leases its pages.
"""
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

# Stores a value in each storage the artifact or a test can reach, and asks before it unloads
# once the reader clicked, as the artifact's comments bar does with unsaved comments.
STATEFUL = """<!doctype html><meta charset="utf-8"><body><button id="b">Change</button><script>
localStorage.setItem("kept", "yes");
sessionStorage.setItem("kept", "yes");
document.cookie = "kept=yes";
document.getElementById("b").addEventListener("click", () => {
    window.addEventListener("beforeunload", (event) => { event.preventDefault(); event.returnValue = ""; });
});
</script>"""

STORED = """() => ({local: localStorage.getItem("kept"), session: sessionStorage.getItem("kept"), cookie: document.cookie,
    dark: matchMedia("(prefers-color-scheme: dark)").matches, print: matchMedia("print").matches,
    width: innerWidth})"""


def stateful(tmp_path: Path, name: str) -> str:
    path = tmp_path / name
    path.write_text(STATEFUL, encoding="utf-8")
    return path.as_uri()


def test_a_released_page_is_reused_as_a_new_context_shows_it(tmp_path: Path, page_pool) -> None:
    page = page_pool.lease({"width": 900, "height": 600})
    heard = []
    page.on("console", lambda message: heard.append(message.text))
    page.goto(stateful(tmp_path, "one.html"))
    page.click("#b")
    page.emulate_media(media="print", color_scheme="dark")
    page.context.new_page()
    page_pool.release(page)

    again = page_pool.lease(None)
    assert again is page, "test/conftest.py: the pool opened a new page instead of reusing the released one"
    assert again.context.pages == [again]
    blank = tmp_path / "blank.html"
    blank.write_text("<!doctype html><title>Blank</title>", encoding="utf-8")
    again.goto(blank.as_uri())
    assert again.evaluate(STORED) == {"local": None, "session": None, "cookie": "", "dark": False,
                                      "print": False, "width": 1280}
    again.evaluate("() => console.log('after release')")
    assert heard == []
    page_pool.release(again)


def test_a_page_with_a_setting_a_navigation_keeps_is_not_reused(tmp_path: Path, page_pool) -> None:
    page = page_pool.lease(None)
    page.route("**/*", lambda route: route.abort())
    page_pool.release(page)
    assert page.is_closed()

    other = page_pool.lease(None)
    assert other is not page
    other.goto(stateful(tmp_path, "one.html"))
    assert other.evaluate("() => localStorage.getItem('kept')") == "yes"
    page_pool.release(other)


def test_a_page_the_test_closed_is_replaced(page_pool) -> None:
    page = page_pool.lease(None)
    page.close()
    page_pool.release(page)
    other = page_pool.lease(None)
    assert not other.is_closed()
    page_pool.release(other)


# A test that kills its pool's own browser process mid-test, through the browser's DevTools
# process list, then waits for a page that cannot answer; and the test after it.
CRASHING = """import os
import signal


def test_kills_its_browser(reader_browser):
    page = reader_browser.new_page()
    processes = page.context.browser.new_browser_cdp_session().send("SystemInfo.getProcessInfo")["processInfo"]
    os.kill(next(each["id"] for each in processes if each["type"] == "browser"), getattr(signal, "SIGKILL", signal.SIGTERM))
    page.evaluate("() => new Promise(() => {})")


def test_runs_on_a_fresh_browser(reader_browser):
    assert reader_browser.new_page().evaluate("1 + 1") == 2
"""


def test_a_test_whose_browser_crashes_fails_naming_itself_and_the_next_gets_a_fresh_browser(tmp_path: Path) -> None:
    output = run_inner(tmp_path, CRASHING)

    assert "1 failed, 1 passed" in output, output
    assert ("test/conftest.py: browser crashed: the chromium-headless-shell browser died while "
            "test_inner.py::test_kills_its_browser ran") in output, output
    assert "pytest-timeout" not in output, output


# A test whose browser stops answering, as a browser Playwright never sees die does: its process
# is stopped mid-test. Its timeout fails it; the test after it runs on a fresh browser.
STOPPED = """import os
import signal

import pytest


@pytest.mark.timeout(2)
def test_its_browser_stops_answering(reader_browser):
    page = reader_browser.new_page()
    processes = page.context.browser.new_browser_cdp_session().send("SystemInfo.getProcessInfo")["processInfo"]
    os.kill(next(each["id"] for each in processes if each["type"] == "browser"), signal.SIGSTOP)
    page.evaluate("1 + 1")


def test_runs_on_a_fresh_browser(reader_browser):
    assert reader_browser.new_page().evaluate("1 + 1") == 2
"""


def run_inner(tmp_path: Path, source: str, plugins: dict[str, str] | None = None) -> str:
    """Run ``source`` as a test module with this folder's conftest.py as a plugin, and each of
    ``plugins`` (a module name and its source) after it; its output."""
    import os
    import subprocess
    import sys

    (tmp_path / "test_inner.py").write_text(source, encoding="utf-8")
    loaded = []
    for name, plugin in (plugins or {}).items():
        (tmp_path / f"{name}.py").write_text(plugin, encoding="utf-8")
        loaded += ["-p", name]
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join([str(Path(__file__).parent), str(tmp_path),
                                                                os.environ.get("PYTHONPATH", "")])}
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "conftest", *loaded,
                           "--rootdir", str(tmp_path), str(tmp_path / "test_inner.py")],
                          cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=120).stdout


@pytest.mark.skipif(not hasattr(__import__("signal"), "SIGSTOP"), reason="Windows cannot stop a process (SIGSTOP)")
def test_a_test_whose_browser_stops_answering_fails_by_its_timeout_and_the_next_gets_a_fresh_browser(
        tmp_path: Path) -> None:
    output = run_inner(tmp_path, STOPPED)

    assert "1 failed, 1 passed" in output, output
    assert "test/bounds.py: test_inner.py::test_its_browser_stops_answering ran past its timeout of 2 s" in output, output


# Names in each test's report, as its timeout starts (pytest-timeout's set-timer hook), the
# engines of the pools whose browser is up then.
TIMER_PROBE = """import pytest

import conftest


@pytest.hookimpl(tryfirst=True)
def pytest_timeout_set_timer(item, settings):
    item.user_properties.append(("launched", sorted(pool.engine for pool in conftest.POOLS if pool.launched())))
    item.user_properties.append(("warm pages", [len(pool._idle) for pool in conftest.POOLS if pool.launched()]))
"""

# A test that needs no browser, then the first test of the process that needs the shell's pages:
# its pool's browser is up, with one page drawn, before its timeout starts, and no other pool's is.
FIRST_LEASE = """def test_needs_no_browser(request):
    assert dict(request.node.user_properties)["launched"] == []


def test_first_to_need_the_shell(reader_browser, request):
    assert dict(request.node.user_properties)["launched"] == ["chromium-headless-shell"]
    assert dict(request.node.user_properties)["warm pages"] == [1]
"""


def test_a_cold_browser_launch_is_done_before_the_timeout_of_the_first_test_that_needs_it(tmp_path: Path) -> None:
    output = run_inner(tmp_path, FIRST_LEASE, {"timer_probe": TIMER_PROBE})

    assert "2 passed" in output, output

# Locks its main thread as soon as anything clears its session storage, as the pool's release does.
LOCKS_ON_RELEASE = """<!doctype html><meta charset="utf-8"><script>
Storage.prototype.clear = () => { for (;;) {} };
</script>"""


def test_a_page_that_locks_while_it_is_released_is_replaced_without_waiting_on_it(tmp_path: Path,
                                                                                  page_pool) -> None:
    """The release gives up on the page after RELEASE_TIMEOUT_MS (test/conftest.py); a release that
    waited on it would run until the test's tier timeout ends the test."""
    path = tmp_path / "locks.html"
    path.write_text(LOCKS_ON_RELEASE, encoding="utf-8")
    page = page_pool.lease(None)
    page.goto(path.as_uri())
    page_pool.release(page)
    again = page_pool.lease(None)
    try:
        assert again is not page, "test/conftest.py: the pool kept a page whose main thread is locked"
        assert again.evaluate("1 + 1") == 2
    finally:
        page_pool.release(again)
