"""The limited-host banner on the fake browser (architecture.md, Limited-host banner): a page that
declares it needs scripts and storage shows one plain line in a simulated sandbox without them, and
nothing in a normal page. The sandbox without storage is the recorded viewer frame, whose storage
throws as Chromium's did; the one without scripts is a fake page that runs none
(browser/browser-door.md, Classification)."""
import json
from pathlib import Path

import pytest

from browser.fake_page import expect
from browser.viewer import open_fake_viewer
from conftest import built_once
from documents import chapter, document, heading, paragraph
from obs_html import cli

NEEDS = ["scripts", "storage"]
TABLE = json.loads((Path(cli.__file__).parent / "limited-host.json").read_text(encoding="utf-8"))

pytestmark = pytest.mark.dom


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


def test_a_normal_page_shows_no_banner(artifact: Path, fake_page) -> None:
    page = fake_page
    page.set_viewport_size({"width": 1200, "height": 800})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri())
    expect(page.locator("#limited-host")).to_be_hidden()
    assert page.evaluate("[...globalThis.obsLimitedHost.missing]") == []
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    assert errors == []


def test_a_sandbox_without_storage_says_what_does_not_work_and_where_to_open_the_page(
        artifact: Path, tmp_path: Path, fake_page) -> None:
    """A scripts-only sandbox (an opaque origin, as a preview's frame) refuses browser storage."""
    _page, frame = open_fake_viewer(fake_page, tmp_path, [], artifact.read_text(encoding="utf-8"))
    banner = frame.locator("#limited-host")
    expect(banner).to_be_visible()
    storage = TABLE["needs"]["storage"]
    expect(banner).to_have_text(f"Limited viewer: {storage['missing']}. {storage['openInstead']}.")
    expect(banner).to_have_attribute("data-limited-host-missing", "storage")


def test_a_sandbox_without_scripts_keeps_the_banners_own_line(artifact: Path, fake_page) -> None:
    page = fake_page
    page.set_viewport_size({"width": 1100, "height": 700})
    page.set_java_script_enabled(False)
    page.goto(artifact.as_uri())
    banner = page.locator("#limited-host")
    expect(banner).to_be_visible()
    expect(banner).to_have_text(TABLE["noScripts"])
