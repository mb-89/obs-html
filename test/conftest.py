import contextlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


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


@pytest.fixture
def document() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


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
