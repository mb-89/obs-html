import os
import re
from pathlib import Path

import pytest

from artifacts import artifact_html
from documents import chapter, document, heading, paragraph
from preview import SANDBOXES, click_where_visible, http_origin, open_preview


def keep_screenshot(page, name: str) -> None:
    """Save a screenshot to $OBS_HTML_SCREENSHOTS, when set, for a field report to show."""
    folder = os.environ.get("OBS_HTML_SCREENSHOTS")
    if folder:
        page.screenshot(path=str(Path(folder) / f"{name}.png"))


def preview_artifact() -> str:
    return artifact_html(document(
        "Preview",
        chapter("one", "One", heading(1, "One"), paragraph("First chapter text.")),
        chapter("two", "Two", heading(1, "Two"), paragraph("Second chapter text.")),
        chapter("three", "Three", heading(1, "Three"), paragraph("Third chapter text.")),
    ))


def open_page(reader_browser, path: Path, errors: list[str]):
    page = reader_browser.new_page(viewport={"width": 1200, "height": 800})
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.goto(path.as_uri())
    return page


def open_sandboxed(tmp_path: Path, reader_browser, errors: list[str]):
    """Claude's preview: the HTML as srcdoc of a frame sandboxed to scripts only."""
    return open_preview(tmp_path, reader_browser, errors, preview_artifact(), "null-origin")


@pytest.mark.browser
def test_artifact_runs_as_srcdoc_of_a_scripts_only_sandbox(tmp_path: Path, full_chromium_browser) -> None:
    """Claude's preview shows HTML as srcdoc of a sandboxed frame that cannot change its URL."""
    from playwright.sync_api import expect

    errors: list[str] = []
    _page, frame = open_sandboxed(tmp_path, full_chromium_browser, errors)
    chapter_element = frame.locator("[data-active-chapter]")
    expect(chapter_element).to_have_attribute("data-chapter", "home")

    frame.locator('[data-step="1"]').first.click()
    expect(chapter_element).to_have_attribute("data-chapter", "one")
    expect(frame.locator("[data-chapter-body]")).to_contain_text("First chapter text.")
    frame.locator('[data-step="1"]').first.click()
    expect(chapter_element).to_have_attribute("data-chapter", "two")
    frame.locator('[data-step="-1"]').first.click()
    expect(chapter_element).to_have_attribute("data-chapter", "one")
    assert errors == []



@pytest.fixture(scope="module")
def shared_sandboxed(tmp_path_factory, shared_full_chromium_browser):
    """The preview artifact opened once in the scripts-only sandbox, and the errors it raises, for
    the module's checks that only read what its canaries found."""
    errors: list[str] = []
    _page, frame = open_sandboxed(tmp_path_factory.mktemp("sandboxed"), shared_full_chromium_browser, errors)
    return frame, errors


@pytest.mark.browser
def test_canaries_find_what_a_scripts_only_sandbox_limits(shared_sandboxed) -> None:
    frame, errors = shared_sandboxed
    limits = frame.locator("html").evaluate("() => globalThis.obsCapabilities.limits")
    assert [entry["key"] for entry in limits] == ["history", "storage", "clipboard"]
    assert all(entry["refused"] and entry["reason"] and entry["remedy"] for entry in limits)
    # The frame hides its sandbox flags, so the canaries that read them cannot decide.
    results = frame.locator("html").evaluate("() => globalThis.obsCapabilities.results")
    assert [entry["key"] for entry in results if not entry["decided"]] == ["printing", "downloads"]
    assert errors == []


@pytest.mark.browser
def test_a_sandboxed_frame_lists_its_limits_as_warning_notices(tmp_path: Path, full_chromium_browser) -> None:
    from playwright.sync_api import expect

    errors: list[str] = []
    page, frame = open_sandboxed(tmp_path, full_chromium_browser, errors)
    keys = frame.locator("html").evaluate("() => globalThis.obsCapabilities.limits.map(({key}) => key)")
    icon = frame.locator('[data-header-notices] [data-notice-icon="warning"]')
    expect(icon.locator("[data-notice-count]")).to_have_text(str(len(keys)))
    expect(frame.locator("[data-header-notices] [data-notice-icon]:visible")).to_have_count(1)
    warnings = frame.locator('[data-notice-list="warning"]')
    entries = warnings.locator('[data-notice^="capability-"]')
    expect(entries).to_have_count(len(keys))
    expect(warnings).to_be_hidden()
    keep_screenshot(page, "limited-functionality-collapsed")
    icon.click()
    storage = warnings.locator('[data-notice="capability-storage"]')
    expect(storage.locator("[data-notice-title]")).to_have_text("Limited functionality: Saved settings")
    storage.locator("[data-notice-title]").click()
    details = storage.locator("[data-notice-details]")
    expect(details).to_be_visible()
    expect(details).to_contain_text("Saved settings")
    expect(details).to_contain_text("browser storage")
    expect(details).to_contain_text("Open the HTML file directly in a browser to keep reader settings.")
    expect(warnings.locator('[data-notice="capability-printing"]')).to_have_count(0)
    expect(warnings.locator('[data-notice="capability-dialogs"]')).to_have_count(0)
    keep_screenshot(page, "limited-functionality-expanded")
    frame.locator("html").evaluate("() => globalThis.obsFilter.setExpression('file.name == \\'One\\'')")
    information = frame.locator('[data-notice-icon="information"]')
    expect(information).to_be_visible()
    information.click()
    frame.locator('[data-notice="applied-filter"] [data-notice-title]').click()
    frame.locator('[data-notice="applied-filter"] [data-filter-clear]').click()
    expect(information).to_be_hidden()
    expect(icon).to_be_visible()
    page.emulate_media(media="print")
    expect(icon).to_be_hidden()
    assert errors == []


@pytest.mark.browser
def test_the_same_artifact_opened_normally_shows_no_notice(tmp_path: Path, reader_browser) -> None:
    from playwright.sync_api import expect

    path = tmp_path / "artifact.html"
    path.write_text(preview_artifact(), encoding="utf-8")
    errors: list[str] = []
    page = open_page(reader_browser, path, errors)
    expect(page.locator("html")).to_have_attribute("data-artifact-status", "ready")
    assert page.evaluate("globalThis.obsCapabilities.limits.length") == 0
    expect(page.locator('[data-notice^="capability-"]')).to_have_count(0)
    assert errors == []

@pytest.mark.browser
def test_print_to_pdf_in_a_sandboxed_frame_ends_in_an_inline_message(tmp_path: Path, full_chromium_browser) -> None:
    from playwright.sync_api import expect

    errors: list[str] = []
    _page, frame = open_sandboxed(tmp_path, full_chromium_browser, errors)
    frame.locator("[data-menu-button]").click()
    frame.locator('[data-dock-bar="settings"]').first.click()
    frame.locator("[data-export-pdf]").click()
    status = frame.locator("[data-export-status]")
    expect(status).to_be_visible()
    expect(status).to_contain_text("PDF export failed: Print to PDF is limited here")
    expect(status).to_contain_text("Open the HTML file directly in a browser to print.")
    # Ctrl+P has no visible control, so its failure reveals the printing entry.
    revealed = frame.locator('[data-notice="capability-printing"] [data-notice-details]')
    expect(revealed).to_be_hidden()
    frame.locator("html").evaluate(
        "() => document.dispatchEvent(new KeyboardEvent('keydown', {key: 'p', ctrlKey: true}))")
    expect(revealed).to_be_visible()
    expect(frame.locator("html")).not_to_have_class(re.compile("preparing-print"))
    # The browser reports the ignored print() call itself; the export logs its own inline failure.
    assert [error for error in errors if "print" not in error.lower()] == []


@pytest.mark.browser
def test_a_message_without_modal_dialogs_appears_beside_its_control(tmp_path: Path, reader_browser) -> None:
    from playwright.sync_api import expect

    errors: list[str] = []
    dialogs: list[str] = []
    page, frame = open_sandboxed(tmp_path, reader_browser, errors)
    page.on("dialog", lambda dialog: dialogs.append(dialog.message))
    frame.locator("[data-chapter-body]").evaluate("""(body) => {
        const link = document.createElement("a");
        link.href = "#tag";
        link.dataset.tagKind = "nothing";
        link.dataset.tagLabel = "nowhere";
        link.textContent = "untabled tag";
        body.append(link);
    }""")
    frame.get_by_text("untabled tag").dispatch_event("click")
    expect(frame.locator("[data-capability-message]")).to_have_text("No table here includes this tag.")
    assert dialogs == []
    assert errors == []



@pytest.mark.browser
@pytest.mark.parametrize("frame_kind", SANDBOXES)
@pytest.mark.parametrize("page_mode", ["pages", "continuous"])
def test_home_and_the_chapter_chooser_are_not_covered_by_the_previous_arrow(
        tmp_path: Path, reader_browser, frame_kind: str, page_mode: str) -> None:
    """Home opens Home from every chapter when clicked where it is shown, in both preview frames."""
    from playwright.sync_api import expect

    errors: list[str] = []
    with http_origin(tmp_path) as origin:
        page, frame = open_preview(tmp_path, reader_browser, errors, preview_artifact(), frame_kind,
                                   origin if frame_kind == "same-origin" else None)
        if page_mode == "continuous":
            frame.locator("html").evaluate("() => globalThis.obsPages.setPaged(false)")
        chapter_element = frame.locator("[data-active-chapter]")
        for steps in (1, 2, 3):
            for _ in range(steps):
                click_where_visible(page, frame, '[data-step="1"] .chapter-nav-icon')
            expect(chapter_element).not_to_have_attribute("data-chapter", "home")
            click_where_visible(page, frame, ".chapter-breadcrumb-toggle")
            expect(frame.locator(".chapter-breadcrumb-chooser[open]")).to_have_count(1)
            page.keyboard.press("Escape")
            click_where_visible(page, frame, ".chapter-home-link")
            expect(chapter_element).to_have_attribute("data-chapter", "home")
    assert errors == []


@pytest.mark.browser
@pytest.mark.parametrize("frame_kind", SANDBOXES)
def test_applying_or_clearing_a_filter_does_not_claim_the_html_changed(
        tmp_path: Path, reader_browser, frame_kind: str) -> None:
    """A filter is reader state, not a content change (obs artifact-ui.md, input-model.md)."""
    from playwright.sync_api import expect

    errors: list[str] = []
    with http_origin(tmp_path) as origin:
        page, frame = open_preview(tmp_path, reader_browser, errors, preview_artifact(), frame_kind,
                                   origin if frame_kind == "same-origin" else None)
        frame.locator("html").evaluate("() => globalThis.obsArtifact.openBar('filter')")
        frame.locator("[data-filter-input]").fill("file.name == 'nothing'")
        expect(frame.locator('[data-notice="applied-filter"]')).to_have_count(1)
        expect(frame.locator('[data-notice="changed-html"]')).to_have_count(0)
        frame.locator('[data-notice="applied-filter"] [data-filter-clear]').dispatch_event("click")
        expect(frame.locator('[data-notice="applied-filter"]')).to_have_count(0)
        expect(frame.locator('[data-notice="changed-html"]')).to_have_count(0)
        keep_screenshot(page, f"filtered-without-changed-notice-{frame_kind}")
    assert errors == []


@pytest.mark.browser
def test_each_canary_says_what_it_observed(shared_sandboxed) -> None:
    """The notice's details name each canary and what it saw, so its count can be read off."""
    from playwright.sync_api import expect

    frame, errors = shared_sandboxed
    results = frame.locator("html").evaluate("() => globalThis.obsCapabilities.results")
    assert [entry["key"] for entry in results] == [
        "history", "storage", "printing", "downloads", "clipboard"]
    assert all(entry["observation"] for entry in results)
    observed = {entry["key"]: entry["observation"] for entry in results}
    assert observed["history"].startswith("it threw SecurityError:")
    assert observed["printing"] == "an enclosing frame hides its sandbox flags (cross-origin host)"
    for entry in results:
        notice = frame.locator(f'[data-notice="capability-{entry["key"]}"]')
        if not entry["refused"]:
            expect(notice).to_have_count(0)
        else:
            observed = notice.locator("[data-notice-details] dt", has_text="Observed")
            expect(observed).to_have_count(1)
            assert observed.evaluate("(term) => term.nextElementSibling.textContent") == entry["observation"]
    assert errors == []


@pytest.mark.browser
@pytest.mark.parametrize("frame_kind", list(SANDBOXES))
def test_opening_a_preview_fails_at_once_when_the_artifact_cannot_start(
        tmp_path: Path, reader_browser, frame_kind: str) -> None:
    """open_preview waits on the artifact's ready event; a failed startup fails it, naming its owner."""
    from playwright.sync_api import Error

    artifact = re.sub(r"(<script[^>]*data-artifact-data[^>]*>)[^<]*", r"\1{}", preview_artifact(), count=1)
    assert artifact != preview_artifact(), "the artifact's data island was not found"
    errors: list[str] = []
    with http_origin(tmp_path) as origin, pytest.raises(Error, match="test/preview.py"):
        open_preview(tmp_path, reader_browser, errors, artifact, frame_kind,
                     origin if frame_kind == "same-origin" else None)
