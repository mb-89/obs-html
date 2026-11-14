"""The limited-host banner in a browser (architecture.md, Limited-host banner): a page that declares
it needs scripts and storage shows one plain line in a simulated sandbox without them, and nothing in
a normal page."""
import json
from pathlib import Path

import pytest

from conftest import built_once
from documents import chapter, document, heading, paragraph
from obs_html import cli
from preview import load_preview, preview_wrapper

NEEDS = ["scripts", "storage"]
TABLE = json.loads((Path(cli.__file__).parent / "limited-host.json").read_text(encoding="utf-8"))

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def artifact(tmp_path_factory) -> Path:
    """A page built with artifact.limitedHostNeeds, as a deck's own settings would declare them."""
    def build(folder: Path) -> None:
        source = folder / "needs.json"
        source.write_text(json.dumps(document("Needs", chapter(
            "one", "One", heading(1, "One"), paragraph("First chapter text.")))), encoding="utf-8")
        settings = folder / "cfg.json"
        settings.write_text(json.dumps({"artifact": {"limitedHostNeeds": NEEDS}}), encoding="utf-8")
        assert cli.main(["--config", str(settings), str(source), str(folder / "artifact.html")]) == 0

    return built_once(tmp_path_factory, "limited-host-artifact", build) / "artifact.html"


def test_a_normal_page_shows_no_banner(artifact: Path, reader_browser) -> None:
    from playwright.sync_api import expect

    page = reader_browser.new_page(viewport={"width": 1200, "height": 800})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri())
    expect(page.locator("#limited-host")).to_be_hidden()
    assert page.evaluate("[...globalThis.obsLimitedHost.missing]") == []
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    assert errors == []


def test_a_sandbox_without_storage_says_what_does_not_work_and_where_to_open_the_page(
        artifact: Path, tmp_path: Path, reader_browser) -> None:
    """A scripts-only sandbox (an opaque origin, as a preview's frame) refuses browser storage."""
    from playwright.sync_api import expect

    _page, frame = load_preview(tmp_path, reader_browser, [], artifact.read_text(encoding="utf-8"), "null-origin")
    banner = frame.locator("#limited-host")
    expect(banner).to_be_visible()
    storage = TABLE["needs"]["storage"]
    expect(banner).to_have_text(f"Limited viewer: {storage['missing']}. {storage['openInstead']}.")
    expect(banner).to_have_attribute("data-limited-host-missing", "storage")


def test_a_sandbox_without_scripts_keeps_the_banners_own_line(artifact: Path, tmp_path: Path, reader_browser) -> None:
    from playwright.sync_api import expect

    wrapper = tmp_path / "no-scripts.html"
    wrapper.write_text(preview_wrapper(artifact.read_text(encoding="utf-8"), ""), encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": 1200, "height": 800})
    page.goto(wrapper.as_uri())
    frame = page.locator("#artifact").element_handle().content_frame()
    banner = frame.locator("#limited-host")
    expect(banner).to_be_visible()
    expect(banner).to_have_text(TABLE["noScripts"])
