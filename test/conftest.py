import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest
from filelock import FileLock
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

import network_guard

network_guard.install()

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "test" / "fixtures" / "documents" / "document.json"
# The browser tier's feature fixture (obs quality.md, Testing boundaries): every registered feature
# in a few chapters (test/fixtures/build_documents.py, features).
FEATURE_FIXTURE = ROOT / "test" / "fixtures" / "documents" / "features.json"
CORE_ROOT = ROOT.parents[1]


def _core_module(name: str) -> types.ModuleType:
    """A module of the core's tests: test/suite.py, which owns the Node test packages' setup,
    test/spec_build.py, which owns the run's one build of obs's spec, or test/bounds.py, which
    owns each test's timeout."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, CORE_ROOT / "test" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


suite = _core_module("suite")
spec_build = _core_module("spec_build")
bounds = _core_module("bounds")


def pytest_sessionstart(session):
    """A focused run installs the suite's Node test packages where they are missing or stale; the
    JUnit report, where the run writes one, names the part's worker count (test/suite.py)."""
    suite.set_up_focused_run(session.config)
    suite.record_workers(session.config)


@pytest.fixture(scope="session")
def core_root() -> Path:
    """The core of this repository; tests read its JSON contracts, never its Python code."""
    return CORE_ROOT


@pytest.fixture(scope="session")
def document_validator(core_root: Path) -> Draft202012Validator:
    # Every core schema, by its file name, which the Document schema's references name
    # (figure.schema.json, answers.schema.json).
    schemas = core_root / "src" / "obs"
    registry = Registry().with_resources(
        (path.name, Resource.from_contents(json.loads(path.read_text(encoding="utf-8"))))
        for path in schemas.glob("*.schema.json"))
    schema = json.loads((schemas / "document.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, registry=registry)


def built_once(tmp_path_factory, name: str, build) -> Path:
    """The folder ``build(folder)`` fills, built once per run and shared by every xdist worker.

    Workers' temporary folders sit side by side in the run's folder; the first worker to ask
    builds there under a lock and the others wait for it and read what it built.
    """
    root = tmp_path_factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        root = root.parent
    folder = root / name
    with FileLock(f"{folder}.lock"):
        if not (folder / ".built").is_file():
            shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir()
            build(folder)
            (folder / ".built").touch()
    return folder


PIXEL = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


@pytest.fixture(scope="session")
def fixture_artifact(tmp_path_factory) -> Path:
    """The fixture Document rendered by this adapter, once per run; tests only read it."""
    from obs_html import cli

    def build(folder: Path) -> None:
        assert cli.main([str(FIXTURE), str(folder / "artifact.html")]) == 0, \
            "test/conftest.py: obs-html could not render the fixture Document test/fixtures/documents/document.json"

    return built_once(tmp_path_factory, "fixture-artifact", build) / "artifact.html"


@pytest.fixture(scope="session")
def feature_artifact(tmp_path_factory) -> str:
    """The feature fixture rendered by this adapter, once per run and shared by every worker; the
    browser tier's reading script and covered-control sweep read it in place of obs's spec."""
    from obs_html import cli

    def build(folder: Path) -> None:
        assert cli.main([str(FEATURE_FIXTURE), str(folder / "artifact.html")]) == 0, \
            "test/conftest.py: obs-html could not render the feature fixture test/fixtures/documents/features.json"

    return (built_once(tmp_path_factory, "feature-artifact", build) / "artifact.html").read_text(encoding="utf-8")


def _uv(*arguments: str, cwd: Path, environment: dict[str, str]) -> None:
    result = subprocess.run(["uv", *arguments], cwd=cwd, env=environment, capture_output=True, text=True)
    assert result.returncode == 0, f"test/conftest.py: uv {' '.join(arguments)} failed:\n{result.stderr}"


@pytest.fixture(scope="session")
def installed_wheels(tmp_path_factory) -> Path:
    """The Python of a fresh virtual environment outside the checkout with the obs and obs-html
    wheels, built once per run and shared by every test of the installed wheels; the lockfile's
    dependencies come from uv's cache."""
    if shutil.which("uv") is None:
        pytest.fail("test/conftest.py: uv is not on PATH; install it (https://docs.astral.sh/uv/) to build the wheels")

    def build(folder: Path) -> None:
        environment = {key: value for key, value in os.environ.items() if key not in ("VIRTUAL_ENV", "PYTHONPATH")}
        environment["UV_PROJECT_ENVIRONMENT"] = str(folder / "venv")
        _uv("build", "--all-packages", "--wheel", "--offline", "--out-dir", str(folder / "dist"),
            cwd=CORE_ROOT, environment=environment)
        # The lockfile's dependencies of obs-html, from uv's cache; then the two wheels just built.
        _uv("sync", "--frozen", "--offline", "--no-dev", "--no-install-workspace", "--package", "obs-html",
            cwd=CORE_ROOT, environment=environment)
        _uv("pip", "install", "--offline", "--no-deps", "--python", str(_venv_python(folder)),
            *map(str, sorted((folder / "dist").glob("*.whl"))), cwd=folder, environment=environment)

    return _venv_python(built_once(tmp_path_factory, "installed-wheels", build))


def _venv_python(folder: Path) -> Path:
    return folder / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


@pytest.fixture
def document() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    with network_guard.running(item.nodeid), bounds.running(item, os.environ.get(spec_build.RUN_FOLDER)):
        return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    network_guard.fail(report)
    crashed(report)
    if bounds.timed_out(report):
        for pool in POOLS:
            pool.abandon()
    bounds.explain(item, report)
    return report


def pytest_collection_modifyitems(config, items):
    """Keep a module's tests on one xdist worker (`--dist loadgroup`), so its module fixtures are
    built once per run. A test with its own ``xdist_group`` mark is a long one that runs on a
    worker of its own; those run first, so no worker is left with one at the end. Each test gets
    its tier's timeout (test/bounds.py in the core)."""
    bounds.mark(items)
    own = [item for item in items if item.get_closest_marker("xdist_group")]
    rest = [item for item in items if not item.get_closest_marker("xdist_group")]
    for item in rest:
        item.add_marker(pytest.mark.xdist_group(item.nodeid.split("::")[0]))
    items[:] = own + rest


@pytest.fixture(scope="session")
def worker_playwright():
    """One Playwright driver per test process.

    A process runs one sync driver at a time, so while this one runs, the PDF path's own
    ``sync_playwright()`` uses it too; a test of the PDF path leases its browser through
    ``pdf_browser``.
    """
    from obs_html import pdf
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright, pytest.MonkeyPatch.context() as patch:
        patch.setattr(pdf, "sync_playwright", lambda: contextlib.nullcontext(playwright))
        yield playwright


# The bulk browser tier's engine (obs quality.md, Testing boundaries): Playwright's
# chromium-headless-shell, which costs about half the CPU of full Chromium per page. Playwright
# installs it in its browsers folder as <revision folder>/<platform folder>/<executable>; the
# newest revision installed is used.
HEADLESS_SHELL = ("chromium_headless_shell-*", "chrome-headless-shell-*",
                  "chrome-headless-shell.exe" if sys.platform == "win32" else "chrome-headless-shell")
HEADLESS_SHELL_INSTALL = "uv run playwright install chromium-headless-shell"


class BrowserEngineError(RuntimeError):
    """A browser engine the tests need is not installed; the message names where it was looked for and the remedy."""


def playwright_browsers(environment=os.environ) -> Path:
    """Playwright's browsers folder: PLAYWRIGHT_BROWSERS_PATH, else Playwright's default for this system."""
    if environment.get("PLAYWRIGHT_BROWSERS_PATH"):
        return Path(environment["PLAYWRIGHT_BROWSERS_PATH"])
    if sys.platform == "win32":
        return Path(environment["LOCALAPPDATA"]) / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path(environment.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "ms-playwright"


def headless_shell(browsers: Path) -> str:
    """The HEADLESS_SHELL executable of the newest revision installed in ``browsers``."""
    revision, platform, executable = HEADLESS_SHELL
    found = sorted((int(re.sub(r"\D", "", folder.name) or 0), path)
                   for folder in browsers.glob(revision) for path in folder.glob(f"{platform}/{executable}"))
    if not found:
        raise BrowserEngineError(
            f"test/conftest.py: HEADLESS_SHELL, the browser tests' engine (Playwright's chromium-headless-shell), "
            f"is not installed in {browsers} ({'/'.join(HEADLESS_SHELL)}). Remedy: run `{HEADLESS_SHELL_INSTALL}` "
            "in adapters/html, or set PLAYWRIGHT_BROWSERS_PATH to the folder that holds it.")
    return str(found[-1][1])


# The pools' engines, as a crash or a failed launch names them.
HEADLESS_SHELL_ENGINE = "chromium-headless-shell"
FULL_CHROMIUM_ENGINE = "Chromium"
# How long a pool waits for its browser to start (Playwright's launch timeout); it starts in about
# a second, and a launch past it fails the test that asked, naming the engine.
LAUNCH_TIMEOUT_MS = 30_000


def launcher(playwright, engine: str, executable: str, args: tuple[str, ...] = ()):
    """What launches a pool's browser: ``executable``, with an explicit launch timeout; a failed
    launch names the engine and the executable."""
    from playwright.sync_api import Error as PlaywrightError

    def launch():
        try:
            return playwright.chromium.launch(executable_path=executable, args=list(args),
                                              timeout=LAUNCH_TIMEOUT_MS)
        except PlaywrightError as error:
            raise BrowserEngineError(
                f"test/conftest.py: the {engine} browser {executable} did not start within "
                f"{LAUNCH_TIMEOUT_MS} ms (LAUNCH_TIMEOUT_MS): {str(error).strip().splitlines()[0]}. Remedy: run "
                "one browser test alone; where it fails the same way, reinstall the engine.") from error
    return launch


# Playwright's default viewport, which a leased page gets where the test names none.
DEFAULT_VIEWPORT = {"width": 1280, "height": 720}
# What a test can set on a page that a navigation does not undo; a page a test set one of them
# on is closed when the test ends instead of going back to the pool.
PAGE_SETTINGS = ("add_init_script", "route", "route_from_har", "route_web_socket", "expose_function",
                 "expose_binding", "set_extra_http_headers", "set_default_timeout",
                 "set_default_navigation_timeout")
# A new context's media emulation, which a pooled page gets back when the test ends: emulate_media
# is the one page setting the pool undoes.
CONTEXT_MEDIA = {"media": "null", "color_scheme": "light", "reduced_motion": "no-preference",
                 "forced_colors": "none", "contrast": "no-preference"}


class PagePool:
    """The test process's open pages, each in a browser context of its own, leased to one test at a time.

    The pool launches its browser itself (``launch``). Where that browser has died, the pool forgets
    its pages and launches a fresh one for the next lease; a browser that dies while a test holds
    one of its pages fails that test, "browser crashed", naming the engine (``take_crash``). A
    browser that stops answering, one Playwright never sees die, is ended when the test holding
    its page runs past its timeout (``abandon``), and the next lease launches a fresh one too.

    Opening a page in a new context costs about a CPU second (its renderer process starts); a
    pooled page is made blank again in about a third of that. When a test ends, its page drops
    the listeners the test added, closes the pages the test opened beside it, goes back to
    about:blank and loses the cookies and stored data of every origin it showed, so the next test
    sees what a new context shows, media emulation included (CONTEXT_MEDIA). Session storage,
    which lives in the tab, is cleared for the origins the page shows when the test ends; neither
    the artifact nor a test keeps any in an origin it navigates away from. A page the test
    closed or changed another page setting on (PAGE_SETTINGS) is closed with its context instead.
    """

    def __init__(self, engine: str, launch, context: dict | None = None):
        from playwright.sync_api import Page

        self.engine = engine
        self._launch = launch
        self._context = context or {}
        self._browser = None
        self._crashed = False
        self._idle = []
        self._listeners: dict[object, list] = {}
        self._origins: dict[object, set[str]] = {}
        self._changed: set[object] = set()
        self._emulated: set[object] = set()
        self._on = Page.on

    def lease(self, viewport: dict | None = None):
        from playwright.sync_api import Error as PlaywrightError

        try:
            page = self._ready_page(viewport)
        except PlaywrightError:
            if self._browser.is_connected():
                raise
            page = self._ready_page(viewport)  # The browser died since its last use: a fresh one serves.
        self._listeners[page] = []
        return page

    def _ready_page(self, viewport: dict | None):
        if self._browser is None or not self._browser.is_connected():
            self._relaunch()
        page = self._idle.pop() if self._idle else self._open()
        page.set_viewport_size(viewport or DEFAULT_VIEWPORT)
        return page

    def _relaunch(self) -> None:
        """Forget the pages of a browser that died, and launch a fresh one."""
        for page in self._idle:
            self._origins.pop(page, None)
        self._idle.clear()
        browser = self._launch()
        browser.on("disconnected", lambda _: self._lost(browser))
        session = browser.new_browser_cdp_session()
        processes = session.send("SystemInfo.getProcessInfo")["processInfo"]
        session.detach()
        self._process = next(each["id"] for each in processes if each["type"] == "browser")
        self._browser = browser

    def abandon(self) -> None:
        """Where a test holds one of the pool's pages, end the browser, which may no longer answer,
        without asking it anything, and forget its pages; the next lease launches a fresh one."""
        if not self._listeners:
            return
        import signal

        self._browser = None
        with contextlib.suppress(OSError):
            os.kill(self._process, getattr(signal, "SIGKILL", signal.SIGTERM))
        for each in (self._idle, self._listeners, self._origins, self._changed, self._emulated):
            each.clear()

    def _lost(self, browser) -> None:
        """The browser disconnected without the pool closing it: a crash, if a test holds one of its pages."""
        if browser is self._browser and self._listeners:
            self._crashed = True

    def take_crash(self) -> bool:
        """Whether the browser crashed while a test held one of its pages since the last call."""
        crashed, self._crashed = self._crashed, False
        return crashed

    def _open(self):
        page = self._browser.new_context(**self._context).new_page()
        self._origins[page] = set()
        self._on(page, "framenavigated", lambda frame: self._origins[page].add(origin(frame.url)))
        return page

    def listened(self, page, event: str, handler) -> None:
        """A test added a listener to a leased page; it is removed when the test ends."""
        if page in self._listeners:
            self._listeners[page].append((event, handler))

    def emulated(self, page) -> None:
        """A test changed a leased page's media emulation; the release sets it back."""
        if page in self._listeners:
            self._emulated.add(page)

    def changed(self, page) -> None:
        """A test changed a page setting a navigation does not undo; the page is not reused."""
        if page in self._listeners:
            self._changed.add(page)

    def release(self, page) -> None:
        if page not in self._listeners:  # The pool abandoned its browser.
            return
        listeners = self._listeners.pop(page)
        context = page.context
        if not context.browser.is_connected():
            for each in (self._changed, self._emulated):
                each.discard(page)
            self._origins.pop(page, None)
            return
        if page.is_closed() or page in self._changed:
            self._changed.discard(page)
            self._emulated.discard(page)
            self._origins.pop(page)
            context.close()
            return
        for event, handler in listeners:
            page.remove_listener(event, handler)
        for other in context.pages:
            if other != page:
                other.close()
        if page in self._emulated:
            self._emulated.discard(page)
            page.emulate_media(**CONTEXT_MEDIA)
        # A tab's session storage outlives navigations, and clearing an origin's data leaves it, so
        # it is cleared from the frames the page shows (an opaque origin has none and throws).
        for frame in page.frames:
            frame.evaluate("() => { try { sessionStorage.clear(); } catch (error) {} }")
        page.goto("about:blank")
        shown = self._origins[page] - {""}
        if shown:
            session = context.new_cdp_session(page)
            for each in shown:
                session.send("Storage.clearDataForOrigin", {"origin": each, "storageTypes": "all"})
            session.detach()
        self._origins[page].clear()
        context.clear_cookies()
        page.mouse.move(0, 0)
        self._idle.append(page)

    def close(self) -> None:
        browser, self._browser = self._browser, None
        self._idle.clear()
        if browser is not None and browser.is_connected():
            browser.close()


def origin(url: str) -> str:
    """The storage origin of a page URL: file:// for files, scheme://host[:port] for http(s), "" otherwise."""
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    if parts.scheme == "file":
        return "file://"
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme in ("http", "https") else ""


# The live page pools of this test process; the Page and BrowserContext patches page_patches sets
# tell each of them what a test did to its pages.
POOLS: list[PagePool] = []


@pytest.fixture(scope="session")
def page_patches():
    """The Page and BrowserContext patches that tell each live pool (POOLS) what a test did to its pages."""
    from playwright.sync_api import BrowserContext, Page

    with pytest.MonkeyPatch.context() as patch:
        for name in ("on", "once"):
            def listen(page, event, handler, _listen=getattr(Page, name)):
                for each in POOLS:
                    each.listened(page, event, handler)
                return _listen(page, event, handler)
            patch.setattr(Page, name, listen)
        def emulate(page, *arguments, _emulate=Page.emulate_media, **options):
            for each in POOLS:
                each.emulated(page)
            return _emulate(page, *arguments, **options)
        patch.setattr(Page, "emulate_media", emulate)
        for name in PAGE_SETTINGS:
            def change(page, *arguments, _change=getattr(Page, name), **options):
                for each in POOLS:
                    each.changed(page)
                return _change(page, *arguments, **options)
            patch.setattr(Page, name, change)
            if hasattr(BrowserContext, name):
                def change_context(context, *arguments, _change=getattr(BrowserContext, name), **options):
                    for page in context.pages:
                        for each in POOLS:
                            each.changed(page)
                    return _change(context, *arguments, **options)
                patch.setattr(BrowserContext, name, change_context)
        yield


@contextlib.contextmanager
def live_pool(engine: str, launch, context: dict | None = None):
    """A page pool over the browser ``launch`` starts, its pages in contexts made with ``context``,
    in POOLS while it lives."""
    pool = PagePool(engine, launch, context)
    POOLS.append(pool)
    try:
        yield pool
    finally:
        pool.close()
        POOLS.remove(pool)


@pytest.fixture(scope="session")
def page_pool(worker_playwright, page_patches):
    """The test process's page pool over one headless shell (HEADLESS_SHELL); tests lease its pages
    through ``reader_browser``."""
    # Frames stay capped at 60 Hz. Uncapped (--disable-frame-rate-limit), a lone test ends sooner,
    # but every animation-frame wait in the artifact and the tests draws frames as fast as the CPU
    # allows; in the complete suite, which keeps every CPU busy, that cost the adapter's part about
    # a quarter of its CPU time and the suite about 20 s.
    shell = headless_shell(playwright_browsers())
    with live_pool(HEADLESS_SHELL_ENGINE, launcher(worker_playwright, HEADLESS_SHELL_ENGINE, shell)) as pool:
        yield pool


@pytest.fixture(scope="session")
def full_page_pool(worker_playwright, page_patches):
    """The page pool over one full Chromium, found as the PDF path finds it, for the named set of
    checks whose behaviour can differ in the headless shell (test/structure/test_quality.py,
    FULL_CHROMIUM_TESTS); tests lease its pages through ``full_chromium_browser``."""
    from obs_html.pdf import _executable

    with live_pool(FULL_CHROMIUM_ENGINE, launcher(worker_playwright, FULL_CHROMIUM_ENGINE, _executable())) as pool:
        yield pool


@pytest.fixture(scope="session")
def overlay_scrollbar_pool(worker_playwright, page_patches):
    """A page pool over a second headless shell with overlay scrollbars, as on touch devices and
    macOS: scrollbars take no room, so the reader's clearance for the chapter arrows is at its narrowest."""
    engine = f"{HEADLESS_SHELL_ENGINE} (overlay scrollbars)"
    launch = launcher(worker_playwright, engine, headless_shell(playwright_browsers()),
                      ("--enable-features=OverlayScrollbar",))
    with live_pool(engine, launch) as pool:
        yield pool


# A phone as Playwright emulates one: touch, a mobile viewport and a phone's device scale. The
# width is the test's (its viewport), so one pool serves every phone width.
PHONE_CONTEXT = {"is_mobile": True, "has_touch": True, "device_scale_factor": 3}


@pytest.fixture(scope="session")
def phone_pool(worker_playwright, page_patches):
    """A page pool over a second headless shell whose pages are phones (PHONE_CONTEXT); tests lease
    its pages through ``phone_browser``."""
    engine = f"{HEADLESS_SHELL_ENGINE} (phone)"
    launch = launcher(worker_playwright, engine, headless_shell(playwright_browsers()))
    with live_pool(engine, launch, PHONE_CONTEXT) as pool:
        yield pool


def crashed(report) -> None:
    """Fail a test phase's report where a pool's browser crashed while the test held one of its pages."""
    engines = [pool.engine for pool in POOLS if pool.take_crash()]
    if engines:
        report.outcome = "failed"
        report.longrepr = (
            f"test/conftest.py: browser crashed: the {', '.join(engines)} browser died while {report.nodeid} ran "
            f"({report.when}); its pool launches a fresh one for the next test (PagePool). Remedy: run the test "
            "alone; where its browser crashes again, find what the page does just before.\n\n"
            + (str(report.longrepr) if report.longrepr else ""))


class BrowserLease:
    """A test's view of the worker's page pool: the pages it leased go back to the pool when it ends."""

    def __init__(self, pool: PagePool):
        self._pool = pool
        self._pages = []

    def new_page(self, viewport: dict | None = None, color_scheme: str | None = None):
        """A leased page with the viewport and, where given, the host's preferred colour scheme."""
        page = self._pool.lease(viewport)
        self._pages.append(page)
        if color_scheme:
            page.emulate_media(color_scheme=color_scheme)
        return page

    def close(self) -> None:
        pages, self._pages = self._pages, []
        for page in pages:
            self._pool.release(page)


class PoolChromium:
    """``chromium`` of the PDF path's Playwright in a test process: its launch leases the pool.

    The PDF path (obs_html/pdf.py) launches the browser ``_executable()`` finds, opens one page
    and closes the browser; here the launch returns a lease on the full-Chromium pool, whose
    browser was launched with that executable, so no second Chromium starts.
    """

    def __init__(self, pool: PagePool):
        self._pool = pool

    def launch(self, executable_path: str | None = None) -> BrowserLease:
        from obs_html.pdf import _executable

        assert executable_path == _executable(), (
            f"test/conftest.py: the PDF path launches {executable_path!r}, not the full-Chromium pool's browser "
            f"{_executable()!r}; lease what it launches or launch it in full_page_pool")
        return BrowserLease(self._pool)


@pytest.fixture(scope="session")
def pdf_browser(full_page_pool):
    """The PDF path's browser for the rest of the test process: a lease on the full-Chromium pool (PoolChromium)."""
    from obs_html import pdf

    chromium = types.SimpleNamespace(chromium=PoolChromium(full_page_pool))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(pdf, "sync_playwright", lambda: contextlib.nullcontext(chromium))
        yield


@pytest.fixture
def reader_browser(page_pool):
    """The native-browser tier's browser for one test: pages leased from the worker's pool, on the
    headless shell (HEADLESS_SHELL)."""
    lease = BrowserLease(page_pool)
    try:
        yield lease
    finally:
        lease.close()


@pytest.fixture(scope="module")
def shared_reader_browser(page_pool):
    """As ``reader_browser``, for a module: several read-only checks of one artifact share the
    page it leases and so one page load; its pages go back to the pool when the module ends."""
    lease = BrowserLease(page_pool)
    try:
        yield lease
    finally:
        lease.close()


@pytest.fixture
def full_chromium_browser(full_page_pool):
    """As ``reader_browser``, on full Chromium: only for the named set FULL_CHROMIUM_TESTS
    (test/structure/test_quality.py), the checks whose behaviour can differ in the headless shell."""
    lease = BrowserLease(full_page_pool)
    try:
        yield lease
    finally:
        lease.close()


@pytest.fixture(scope="module")
def shared_full_chromium_browser(full_page_pool):
    """As ``shared_reader_browser``, on full Chromium (``full_chromium_browser``)."""
    lease = BrowserLease(full_page_pool)
    try:
        yield lease
    finally:
        lease.close()


@pytest.fixture
def phone_browser(phone_pool):
    """As ``reader_browser``, on an emulated phone (``phone_pool``)."""
    lease = BrowserLease(phone_pool)
    try:
        yield lease
    finally:
        lease.close()


@pytest.fixture
def overlay_scrollbar_browser(overlay_scrollbar_pool):
    """As ``reader_browser``, with overlay scrollbars (``overlay_scrollbar_pool``)."""
    lease = BrowserLease(overlay_scrollbar_pool)
    try:
        yield lease
    finally:
        lease.close()
