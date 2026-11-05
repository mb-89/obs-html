import base64
import contextlib
import json
import os
import shutil
from pathlib import Path

import pytest
from filelock import FileLock
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

import network_guard

network_guard.install()

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "test" / "fixtures" / "document.json"
CORE_ROOT = ROOT.parents[1]


@pytest.fixture(scope="session")
def core_root() -> Path:
    """The core of this repository; tests read its JSON contracts, never its Python code."""
    return CORE_ROOT


@pytest.fixture(scope="session")
def document_validator(core_root: Path) -> Draft202012Validator:
    schemas = core_root / "src" / "obs"
    figure = json.loads((schemas / "figure.schema.json").read_text(encoding="utf-8"))
    registry = Registry().with_resource("figure.schema.json", Resource.from_contents(figure))
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
        (folder / "images").mkdir()
        (folder / "images" / "logo.png").write_bytes(base64.b64decode(PIXEL))
        assert cli.main([str(FIXTURE), str(folder / "artifact.html"), "--execute-commands",
                         "--command-root", str(folder)]) == 0, \
            "test/conftest.py: obs-html could not render the fixture Document test/fixtures/document.json"

    return built_once(tmp_path_factory, "fixture-artifact", build) / "artifact.html"


@pytest.fixture
def document() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    with network_guard.running(item.nodeid):
        return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    network_guard.fail(report)
    return report


def pytest_collection_modifyitems(config, items):
    """Keep a module's tests on one xdist worker (`--dist loadgroup`), so its module fixtures are
    built once per run. A test with its own ``xdist_group`` mark is a long one that runs on a
    worker of its own; those run first, so no worker is left with one at the end."""
    own = [item for item in items if item.get_closest_marker("xdist_group")]
    rest = [item for item in items if not item.get_closest_marker("xdist_group")]
    for item in rest:
        item.add_marker(pytest.mark.xdist_group(item.nodeid.split("::")[0]))
    items[:] = own + rest


# Headless Chromium otherwise caps animation frames at 60 Hz; the artifact waits for frames as it
# opens and switches chapters, so an uncapped frame rate saves seconds per test.
FAST_FRAMES = ["--disable-frame-rate-limit", "--disable-gpu-vsync"]


@pytest.fixture(scope="session")
def worker_playwright():
    """One Playwright driver per test process.

    A process runs one sync driver at a time, so while this one runs, the PDF path's own
    ``sync_playwright()`` uses it too; the PDF path still launches and closes its own browser.
    """
    from obs_html import pdf
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright, pytest.MonkeyPatch.context() as patch:
        patch.setattr(pdf, "sync_playwright", lambda: contextlib.nullcontext(playwright))
        yield playwright


@pytest.fixture(scope="session")
def worker_browser(worker_playwright):
    """One Chromium per test process, found as the PDF path finds it; tests lease it."""
    from obs_html.pdf import _executable

    browser = worker_playwright.chromium.launch(executable_path=_executable(), args=FAST_FRAMES)
    try:
        yield browser
    finally:
        browser.close()


class BrowserLease:
    """A test's view of the worker's browser: its pages and contexts close when the test ends."""

    def __init__(self, browser):
        self._browser = browser
        self._contexts = []

    def new_context(self, **options):
        context = self._browser.new_context(**options)
        self._contexts.append(context)
        return context

    def new_page(self, **options):
        return self.new_context(**options).new_page()

    def close(self) -> None:
        contexts, self._contexts = self._contexts, []
        for context in contexts:
            context.close()


@pytest.fixture
def reader_browser(worker_browser):
    """The native-browser tier's browser for one test: a fresh context per page, one Chromium."""
    lease = BrowserLease(worker_browser)
    try:
        yield lease
    finally:
        lease.close()
