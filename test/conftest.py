import contextlib
import functools
import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
import types
from pathlib import Path

import pytest
from filelock import FileLock
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

import library_fakes
import network_guard
import style_component
from browser import door

network_guard.install()
library_fakes.install()

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "test" / "fixtures" / "documents" / "document.json"
# The browser tier's feature fixture (obs quality.md, Testing boundaries): every registered feature
# in a few chapters (test/fixtures/build_documents.py, features).
FEATURE_FIXTURE = ROOT / "test" / "fixtures" / "documents" / "features.json"
# The core's checkout beside this repository, at the tag pyproject.toml's obs source pins (README
# "Core"); OBS_CORE_ROOT names another.
CORE_ROOT = Path(os.environ.get("OBS_CORE_ROOT") or ROOT.parent / "obs").resolve()
if not (CORE_ROOT / "src" / "obs" / "document.schema.json").is_file():
    raise pytest.UsageError(f"test/conftest.py: {CORE_ROOT} holds no checkout of obs. Remedy: clone obs at the tag "
                            "pyproject.toml's [tool.uv.sources] obs names beside this repository, as ../obs, or name "
                            "the checkout in OBS_CORE_ROOT (README, Core).")
# The made-up local themes the feature fixture carries (spec/configuration.md, Local themes).
LOCAL_THEMES = door.LOCAL_THEMES
# No test, and no build a test starts, reads the build machine's local themes: the folder named
# here does not exist. A test that needs themes sets the variable for its own call.
os.environ["OBS_HTML_LOCAL_FOLDER"] = str(ROOT.resolve() / "test" / "fixtures" / "no-local-folder")
# No build a test starts reads the build machine's installed components (obs's
# spec/design_input/components.md, Installed components): each process gets a machine folder of its
# own whose installed components are this checkout, as the adapter component obs-html, the name
# adapter.json declares, and the default style component se.toml requires, obs-html-style-generic,
# from the cache test/style_component.py installs it into once.
COMPONENT = json.loads((ROOT / "adapter.json").read_text(encoding="utf-8"))["name"]
MACHINE = Path(tempfile.mkdtemp(prefix="obs-html-machine-"))
(MACHINE / "components").mkdir()
(MACHINE / "components" / COMPONENT).symlink_to(ROOT.resolve(), target_is_directory=True)
try:
    DEFAULT_STYLE = style_component.install_into(MACHINE, CORE_ROOT)
except style_component.ProvisionError as error:
    raise pytest.UsageError(str(error)) from error
(MACHINE / "components.json").write_text(json.dumps({"components": [{
    "name": COMPONENT, "kind": "adapter",
    "version": tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"],
    "commit": "0" * 40}, DEFAULT_STYLE]}), encoding="utf-8")
os.environ["OBS_LOCAL_FOLDER"] = str(MACHINE)


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
# The core's suite names this repository by the part name it had in obs's tree, adapters/html, so its
# committed weights deal this suite's groups (test/suite.py, heaviest_first).
_core_part_name = suite.part_name
suite.part_name = lambda part: "adapters/html" if part.resolve() == ROOT.resolve() else _core_part_name(part)
# This repository's Node test package, which the core's suite does not hold.
NODE_PACKAGE = ROOT / "test" / "browser"


def pytest_addoption(parser):
    parser.addoption("--record", action="store_true", default=False,
                     help="the hot tests that record write the browser door's recordings, "
                          "test/browser/recordings/<state>.yaml (test/browser/browser-door.md, Recording and replay); "
                          "run as `uv run pytest -m hot --record`")


@pytest.fixture
def recording(request) -> bool:
    """Whether this run records the browser door's states (``--record``); a hot test that records
    skips without it, so a run without it starts no browser for one (browser-door.md, When hot tests run)."""
    if not request.config.getoption("--record"):
        pytest.skip(f"records the browser door's states only with --record: run `{door.REMEDY}`")
    return True


# The xdist group of the hot tests under --record: one worker, and so one Chromium, runs them all.
HOT_GROUP = "hot"
# Whether this test process records (--record): its hot tests lease every page from the one full
# Chromium (RECORD_POOLS).
RECORDING: list[bool] = [False]


def pytest_configure(config):
    RECORDING[0] = bool(config.getoption("--record"))


def pytest_sessionstart(session):
    """A run installs this repository's Node test package where it is missing or stale, as the
    core's suite installs its own (test/suite.py, install_node_packages), and the headless shell the
    installed Playwright pins where it is missing (install_pinned_shell); the JUnit report, where the
    run writes one, names the worker count (test/suite.py)."""
    if not hasattr(session.config, "workerinput"):
        lock = Path(tempfile.gettempdir()) / "obs-html-node-setup.lock"
        try:
            with FileLock(lock):
                suite.install_node_packages([NODE_PACKAGE])
                install_pinned_shell(suite.playwright_browsers())
        except (suite.InstallError, BrowserEngineError) as error:
            pytest.exit(str(error), returncode=1)
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
    builds there under a lock and the others wait for it and read what it built. A build inside
    ``library_fakes.real()`` embeds the real browser libraries and has a folder of its own.
    """
    root = tmp_path_factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        root = root.parent
    folder = root / (name if library_fakes.mode() == library_fakes.FAKE else f"{name}-{library_fakes.REAL}")
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
    def build(folder: Path) -> None:
        # With its notes' way from the page and the fixture's local themes (browser/door.py,
        # build_feature_file), as the browser door's states build it.
        door.build_feature_file(FEATURE_FIXTURE, folder / "artifact.html")

    return (built_once(tmp_path_factory, "feature-artifact", build) / "artifact.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def door_artifact(tmp_path_factory):
    """The artifact of a browser door's state (test/browser/expectations.yaml), as a function of the
    state's name: built once per run for each artifact the states name, with the library fakes and the build instant fixed
    (browser/door.py, build_artifact), and shared by every worker; tests only read it."""
    def artifact(name: str) -> Path:
        # By the state's artifact, not its name: states of one page at other contexts share one build.
        source = re.sub(r"[^a-z0-9]+", "-", door.states()[name]["artifact"].lower()).strip("-")
        return built_once(tmp_path_factory, f"door-{source}", lambda folder: door.build_artifact(name, folder)) / "artifact.html"

    return artifact


@pytest.fixture(scope="session")
def own_spec(tmp_path_factory) -> Path:
    """The adapter's own specification as ``obs-html --build-own-spec`` builds it (spec/cli.md,
    Building its own specification), once per run and shared by every worker; tests only read it."""
    from obs_html import cli

    def build(folder: Path) -> None:
        assert cli.main(["--build-own-spec", str(folder / "obs-html-specification.html")]) == 0, \
            "test/conftest.py: obs-html --build-own-spec could not build the adapter's specification"

    return built_once(tmp_path_factory, "own-spec", build) / "obs-html-specification.html"


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
        # The core's wheel from its checkout, this adapter's from this one.
        for checkout in (CORE_ROOT, ROOT):
            _uv("build", "--wheel", "--offline", "--out-dir", str(folder / "dist"), cwd=checkout, environment=environment)
        # The lockfile's dependencies of obs-html but the core, from uv's cache; then the two wheels just built.
        _uv("sync", "--frozen", "--offline", "--no-dev", "--no-install-project", "--no-install-package", "obs",
            cwd=ROOT, environment=environment)
        _uv("pip", "install", "--offline", "--no-deps", "--python", str(_venv_python(folder)),
            *map(str, sorted((folder / "dist").glob("*.whl"))), cwd=folder, environment=environment)

    return _venv_python(built_once(tmp_path_factory, "installed-wheels", build))


def _venv_python(folder: Path) -> Path:
    return folder / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


@pytest.fixture
def document() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    """Launch the browsers of the pools the test needs before its timeout starts (warm), then run it.
    This wrapper is outside pytest-timeout's, whose timer covers setup, call and teardown."""
    warm(item)
    with network_guard.running(item.nodeid), bounds.running(item, os.environ.get(spec_build.RUN_FOLDER)):
        return (yield)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session):
    """End the test process's page pools and its Playwright driver, after the session's fixtures."""
    for pool in POOLS:
        pool.close()
    POOLS.clear()
    PROCESS_POOLS.clear()
    FAKE_BROWSER.close()
    if process_playwright.cache_info().currsize:
        process_playwright().stop()
        process_playwright.cache_clear()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    fake_defaults(report)
    network_guard.fail(report)
    crashed(report)
    if bounds.timed_out(report):
        for pool in POOLS:
            pool.abandon()
    bounds.explain(item, report)
    return report


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """Keep a module's tests on one xdist worker (`--dist loadgroup`), so its module fixtures are
    built once per run. A test with its own ``xdist_group`` mark is a long one that runs on a
    worker of its own; those run first, so no worker is left with one at the end. Each test gets
    its tier's timeout (test/bounds.py in the core). The heaviest group runs first, by the weights
    the suite recorded or, without them, the committed ones (test/suite.py in the core,
    heaviest_first). It runs before
    xdist's own hook, which reads the groups as it collects."""
    bounds.mark(items)
    if not config.getoption("--record"):
        for item in items:
            if "recording" in getattr(item, "fixturenames", ()):
                item.add_marker(pytest.mark.skip(
                    reason=f"records the browser door's states only with --record: run `{door.REMEDY}`"))
    else:
        for item in items:
            if item.get_closest_marker("hot") is None:
                continue
            if item.get_closest_marker("hot").kwargs.get("own_browser"):
                item.add_marker(pytest.mark.skip(
                    reason="its browser is its own, the subject of its test; the one Chromium of --record holds the "
                           "hot tests that record (test/browser/browser-door.md, When hot tests run)"))
            # The hot tests share one xdist group, so one worker holds the one Chromium (HOT_GROUP);
            # prepended, so it is the closest group mark.
            item.add_marker(pytest.mark.xdist_group(HOT_GROUP), append=False)
    own = [item for item in items if item.get_closest_marker("xdist_group")]
    rest = [item for item in items if not item.get_closest_marker("xdist_group")]
    for item in rest:
        item.add_marker(pytest.mark.xdist_group(item.nodeid.split("::")[0]))
    items[:] = own + rest
    suite.keep_shard(config, items, bounds)
    suite.heaviest_first(ROOT, items, bounds)


@functools.cache
def process_playwright():
    """The test process's one Playwright driver, started on first use; pytest_sessionfinish stops it."""
    from playwright.sync_api import sync_playwright

    return sync_playwright().start()


@pytest.fixture(scope="session")
def worker_playwright():
    """One Playwright driver per test process (process_playwright).

    A process runs one sync driver at a time, so while this one runs, the PDF path's own
    ``sync_playwright()`` uses it too; a test of the PDF path leases its browser through
    ``pdf_browser``.
    """
    from obs_html import pdf

    playwright = process_playwright()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(pdf, "sync_playwright", lambda: contextlib.nullcontext(playwright))
        yield playwright


class BrowserEngineError(RuntimeError):
    """A browser engine the tests need is not installed; the message names where it was looked for and the remedy."""


def pinned_revision(package=None) -> str:
    """The chromium-headless-shell revision the installed Playwright names in its browsers.json: the
    engine CI installs and the tests pass on. A host whose browsers folder already holds another
    revision, as a Claude Code cloud container holds a newer one, gives a newer Chromium whose
    sandboxed frames report a focus without user activation as a console error."""
    import playwright

    package = package or Path(playwright.__file__).parent / "driver" / "package"
    browsers = json.loads((package / "browsers.json").read_text(encoding="utf-8"))["browsers"]
    return next(entry["revision"] for entry in browsers if entry["name"] == "chromium-headless-shell")


def headless_shell(browsers: Path, revision: str | None = None) -> str:
    """The bulk browser tier's engine (obs quality.md, Testing boundaries): test/suite.py's
    HEADLESS_SHELL at the revision the installed Playwright pins (pinned_revision), in ``browsers``,
    or a failure that names it; never another revision installed beside it."""
    revision = revision or pinned_revision()
    folder, platform, executable = suite.HEADLESS_SHELL
    found = sorted((browsers / folder.replace("*", revision)).glob(f"{platform}/{executable}"))
    if not found:
        raise BrowserEngineError(
            f"test/conftest.py: the browser tests' engine, test/suite.py's HEADLESS_SHELL (Playwright's "
            f"chromium-headless-shell) at revision {revision}, which the installed Playwright pins, is not "
            f"installed in {browsers} ({'/'.join(suite.HEADLESS_SHELL)}). Remedy: run "
            f"`{' '.join(suite.BROWSER_INSTALL)}`, which a test run does where it is missing, or set "
            "PLAYWRIGHT_BROWSERS_PATH to the folder that holds it.")
    return str(found[-1])


def install_pinned_shell(browsers: Path, run=subprocess.run) -> bool:
    """Install the pinned headless shell (headless_shell) with Playwright where ``browsers`` lacks it,
    beside any other revision there; whether it installed."""
    try:
        headless_shell(browsers)
        return False
    except BrowserEngineError:
        pass
    result = run(suite.BROWSER_INSTALL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        raise suite.InstallError(f"test/conftest.py: `{' '.join(suite.BROWSER_INSTALL)}` failed (exit code "
                                 f"{result.returncode}).\n{result.stdout}")
    headless_shell(browsers)
    return True


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


# How long making a released page blank again may take: an answering page takes a fraction of a
# second, so a release past it waits on a locked or lost page, and the pool ends its browser.
RELEASE_TIMEOUT_MS = 2_000


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
    closed or changed another page setting on (PAGE_SETTINGS) is closed with its context instead,
    as is a page that fails while it is made blank; one that does not answer then ends the
    browser (``release``).
    """

    def __init__(self, engine: str, launch, context: dict | None = None, host: "PagePool | None" = None,
                 prepare=None):
        from playwright.sync_api import Page

        self.engine = engine
        self._launch = launch
        self._context = context or {}
        # A pool whose pages are contexts of another pool's browser (SHARED_POOLS): it launches
        # none and closes none of its own; ``prepare(page)`` sets what its contexts add.
        self._host = host
        self._prepare = prepare
        self._browser = None
        self._crashed = False
        self._ended = False
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

    def launched(self) -> bool:
        """Whether the pool's browser is up."""
        return self._browser is not None and self._browser.is_connected()

    def warm(self) -> None:
        """Launch the pool's browser where it is not up: a first launch, or one after its browser
        died. It draws one page, which the next lease takes: a cold browser's first page starts its
        renderer and readies its fonts and graphics, which on a fresh CI runner took seconds."""
        if not self.launched():
            self._relaunch()
            page = self._open()
            page.set_content("<!doctype html><p>Warm.</p>")
            page.evaluate("() => document.body.getBoundingClientRect().height")
            self._idle.append(page)

    def _ready_page(self, viewport: dict | None):
        self.warm()
        page = self._idle.pop() if self._idle else self._open()
        page.set_viewport_size(viewport or DEFAULT_VIEWPORT)
        return page

    def _relaunch(self) -> None:
        """Forget the pages of a browser that died, and launch a fresh one."""
        for page in self._idle:
            self._origins.pop(page, None)
        self._idle.clear()
        if self._host is not None:
            self._host.warm()
            self._browser, self._process = self._host._browser, self._host._process
            self._browser.on("disconnected", lambda _, browser=self._browser: self._lost(browser))
            return
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
        if browser is self._browser and self._listeners and not self._ended:
            self._crashed = True

    def take_crash(self) -> bool:
        """Whether the browser crashed while a test held one of its pages since the last call."""
        crashed, self._crashed = self._crashed, False
        return crashed

    def _open(self):
        page = self._browser.new_context(**self._context).new_page()
        if self._prepare is not None:
            self._prepare(page)
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
        """Make the test's page blank again for the next lease. A page that fails is closed with its
        context; one that does not answer within RELEASE_TIMEOUT_MS is not waited on: the pool ends
        its browser, and the next lease launches a fresh one."""
        from playwright.sync_api import Error as PlaywrightError

        if page not in self._listeners:  # The pool abandoned its browser.
            return
        listeners = self._listeners.pop(page)
        context = page.context
        if not context.browser.is_connected():
            self._forget(page)
            return
        if page.is_closed() or page in self._changed:
            self._forget(page)
            context.close()
            return
        import threading

        # A page that does not answer, its main thread locked, would hold its release forever:
        # past RELEASE_TIMEOUT_MS the watchdog ends the browser, the reset's call fails, and the
        # next lease launches a fresh one.
        watchdog = threading.Timer(RELEASE_TIMEOUT_MS / 1000, self._end_browser)
        watchdog.start()
        try:
            self._reset(page, context, listeners)
        except PlaywrightError:
            self._forget(page)
            if self._ended:
                self._abandoned()
            else:
                context.close()
            return
        finally:
            watchdog.cancel()
        if self._ended:  # The watchdog ended the browser as the reset finished.
            self._abandoned()
            return
        self._idle.append(page)

    def _end_browser(self) -> None:
        """From the release's watchdog thread: end the browser without asking it anything."""
        import signal

        self._ended = True
        with contextlib.suppress(OSError):
            os.kill(self._process, getattr(signal, "SIGKILL", signal.SIGTERM))

    def _abandoned(self) -> None:
        """Forget the browser the watchdog ended and every page of it."""
        self._ended = False
        self._browser = None
        for each in (self._idle, self._origins, self._changed, self._emulated):
            each.clear()

    def _forget(self, page) -> None:
        for each in (self._changed, self._emulated):
            each.discard(page)
        self._origins.pop(page, None)

    def _reset(self, page, context, listeners) -> None:
        """Make a released page show what a new context shows (the class's docstring)."""
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

    def close(self) -> None:
        browser, self._browser = self._browser, None
        self._idle.clear()
        if browser is not None and browser.is_connected() and self._host is None:
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
# The test process's page pools by the fixture that hands each out (POOL_KINDS); process_pool
# makes each on first use and pytest_sessionfinish ends them.
PROCESS_POOLS: dict[str, PagePool] = {}


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


def _shell() -> str:
    return headless_shell(suite.playwright_browsers())


def _full_chromium() -> str:
    from obs_html.pdf import _executable

    return _executable()


# A phone as Playwright emulates one: touch, a mobile viewport and a phone's device scale. The
# width is the test's (its viewport), so one pool serves every phone width.
PHONE_CONTEXT = {"is_mobile": True, "has_touch": True, "device_scale_factor": 3}

# Each pool fixture's pool: its engine, what finds the browser's executable, the browser's launch
# arguments and its pages' context. Frames stay capped at 60 Hz in every pool. Uncapped
# (--disable-frame-rate-limit), a lone test ends sooner, but every animation-frame wait in the
# artifact and the tests draws frames as fast as the CPU allows; in the complete suite, which keeps
# every CPU busy, that cost the adapter's part about a quarter of its CPU time and the suite about 20 s.
POOL_KINDS = {
    # One headless shell (HEADLESS_SHELL); tests lease its pages through ``reader_browser``.
    "page_pool": (HEADLESS_SHELL_ENGINE, _shell, (), None),
    # One full Chromium, found as the PDF path finds it, for the named set of checks whose behaviour
    # can differ in the headless shell (test/structure/test_quality.py, FULL_CHROMIUM_TESTS).
    "full_page_pool": (FULL_CHROMIUM_ENGINE, _full_chromium, (), None),
    # A second headless shell with overlay scrollbars, as on touch devices and macOS: scrollbars
    # take no room, so the reader's clearance for the chapter arrows is at its narrowest.
    "overlay_scrollbar_pool": (f"{HEADLESS_SHELL_ENGINE} (overlay scrollbars)", _shell,
                               ("--enable-features=OverlayScrollbar",), None),
    # A further headless shell whose pages are phones (PHONE_CONTEXT).
    "phone_pool": (f"{HEADLESS_SHELL_ENGINE} (phone)", _shell, (), PHONE_CONTEXT),
}


def hide_scrollbars(page) -> None:
    """Scrollbars that take no room, as the overlay scrollbars of touch devices and macOS: Chromium's
    emulation of hidden scrollbars, set on a page of the one Chromium instead of a launch flag."""
    session = page.context.new_cdp_session(page)
    session.send("Emulation.setScrollbarsHidden", {"hidden": True})


# The pools whose pages are contexts of another pool's browser: pool -> (its engine, the pool whose
# browser it shares, its pages' context, what each of its pages sets). The phone is a context of
# the one full Chromium, and so are scrollbars that take no room under --record.
SHARED_POOLS = {
    # Full Chromium whose pages are phones: the browser door records a phone's state there
    # (test/test_door_recordings_browser.py), and the hot tests' phones lease it under --record.
    "full_phone_pool": (f"{FULL_CHROMIUM_ENGINE} (phone)", "full_page_pool", PHONE_CONTEXT, None),
    # Full Chromium whose scrollbars take no room, for the hot tests of the overlay-scrollbar pool
    # under --record.
    "full_overlay_scrollbar_pool": (f"{FULL_CHROMIUM_ENGINE} (hidden scrollbars)", "full_page_pool", None,
                                    hide_scrollbars),
}
# Under --record, the pool that serves each pool fixture: the hot tests share one full Chromium
# (test/browser/browser-door.md, When hot tests run), its phones and hidden scrollbars contexts of it.
RECORD_POOLS = {"page_pool": "full_page_pool", "phone_pool": "full_phone_pool",
                "overlay_scrollbar_pool": "full_overlay_scrollbar_pool"}


def process_pool(name: str) -> PagePool:
    """The test process's pool of the fixture ``name`` (POOL_KINDS, SHARED_POOLS), made on first use;
    under --record, the pool of the one full Chromium that serves it (RECORD_POOLS). A missing
    engine raises BrowserEngineError."""
    if RECORDING[0]:
        name = RECORD_POOLS.get(name, name)
    if name not in PROCESS_POOLS:
        if name in SHARED_POOLS:
            engine, host, context, prepare = SHARED_POOLS[name]
            pool = PagePool(engine, None, context, host=process_pool(host), prepare=prepare)
        else:
            engine, executable, args, context = POOL_KINDS[name]
            pool = PagePool(engine, launcher(process_playwright(), engine, executable(), args), context)
        PROCESS_POOLS[name] = pool
        POOLS.append(pool)
    return PROCESS_POOLS[name]


def warm(item) -> None:
    """Launch the browser of each pool the test needs, so that no test's timeout pays for a cold
    launch. A pool whose engine is missing or whose launch fails is left cold: its fixture or its
    first lease fails the test, naming the engine. A test that skips starts none."""
    if item.get_closest_marker("skip"):
        return
    for name in (POOL_KINDS.keys() | SHARED_POOLS.keys()) & set(getattr(item, "fixturenames", ())):
        with contextlib.suppress(BrowserEngineError):
            process_pool(name).warm()


@pytest.fixture(scope="session")
def page_pool(worker_playwright, page_patches):
    """The test process's page pool over one headless shell (POOL_KINDS)."""
    return process_pool("page_pool")


@pytest.fixture(scope="session")
def full_page_pool(worker_playwright, page_patches):
    """The test process's page pool over one full Chromium (POOL_KINDS); tests lease its pages
    through ``full_chromium_browser``."""
    return process_pool("full_page_pool")


@pytest.fixture(scope="session")
def overlay_scrollbar_pool(worker_playwright, page_patches):
    """The test process's page pool over a headless shell with overlay scrollbars (POOL_KINDS)."""
    return process_pool("overlay_scrollbar_pool")


@pytest.fixture(scope="session")
def phone_pool(worker_playwright, page_patches):
    """The test process's page pool whose pages are phones (POOL_KINDS); tests lease its pages
    through ``phone_browser``."""
    return process_pool("phone_pool")


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


@pytest.fixture(scope="session")
def full_phone_pool(worker_playwright, page_patches):
    """The test process's page pool whose pages are phones in contexts of the one full Chromium (SHARED_POOLS)."""
    return process_pool("full_phone_pool")


@pytest.fixture
def full_phone_browser(full_phone_pool):
    """As ``full_chromium_browser``, on an emulated phone (``full_phone_pool``): only the browser
    door's recorder takes it, for a phone's state."""
    lease = BrowserLease(full_phone_pool)
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


# The fake browser (test/browser/browser-door.md, The fake browser): one Node process per test
# process hosts happy-dom, started on the first ``fake_page``; pytest_sessionfinish ends it.
from browser.fake_page import FakeBrowser  # noqa: E402

FAKE_BROWSER = FakeBrowser()
# The fake pages of the running test, whose default answers its report lists (fake_defaults).
FAKE_PAGES: list = []
# The report section that lists them.
FAKE_DEFAULTS_SECTION = "fake browser: default answers"


@pytest.fixture
def fake_page():
    """A page of the fake browser, happy-dom in Node, at Playwright's default viewport; a logic test
    takes it in place of ``reader_browser`` (browser-door.md, Classification). It starts no Chromium."""
    page = FAKE_BROWSER.new_page()
    FAKE_PAGES.append(page)
    try:
        yield page
    finally:
        page.close()


def fake_defaults(report) -> None:
    """Add to a test phase's report the default answers its fake pages gave during that phase: each
    call, the element's key and the answer, with how often (browser-door.md, Recording and replay)."""
    if not FAKE_PAGES:
        return
    given: dict[str, int] = {}
    for page in FAKE_PAGES:
        for entry in page.take_defaults():
            given[entry["answer"]] = given.get(entry["answer"], 0) + entry["times"]
    if report.when == "teardown":
        FAKE_PAGES.clear()
    if given:
        report.sections.append((f"{FAKE_DEFAULTS_SECTION} ({report.when})", "\n".join(
            f"{answer} ({times}x)" for answer, times in sorted(given.items()))))
