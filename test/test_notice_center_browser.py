"""The notice center: at most three severity icons with count pills, each opening its list."""
import re
from pathlib import Path

import pytest

from test_moved_dom_contracts import _artifact
from test_sandboxed_preview_browser import keep_screenshot, open_page, preview_artifact


pytestmark = pytest.mark.browser


def open_artifact(tmp_path: Path, reader_browser, errors: list[str]):
    from playwright.sync_api import expect

    path = tmp_path / "artifact.html"
    path.write_text(preview_artifact(), encoding="utf-8")
    page = open_page(reader_browser, path, errors)
    expect(page.locator("html")).to_have_attribute("data-artifact-status", "ready")
    return page


def post(page, notices: list[dict]) -> None:
    page.evaluate("(notices) => notices.forEach((notice) => globalThis.obsNotices.post(notice))", notices)


def visible_icons(page) -> dict[str, str]:
    icons = page.locator("[data-header-notices] [data-notice-icon]:visible")
    return {icons.nth(index).get_attribute("data-notice-icon"): icons.nth(index).inner_text().strip()
            for index in range(icons.count())}


def test_three_severities_give_exactly_three_icons_with_counts(tmp_path: Path, reader_browser) -> None:
    errors: list[str] = []
    page = open_artifact(tmp_path, reader_browser, errors)
    assert visible_icons(page) == {}
    # The icons take their place in the top band's one row; the reader below never moves.
    reader_top = lambda: page.locator("[data-chapter-scroll]").bounding_box()["y"]
    top = reader_top()
    post(page, [
        {"id": "e1", "severity": "error", "title": "Broken figure", "details": "The figure failed."},
        {"id": "w1", "severity": "warning", "title": "First warning"},
        {"id": "w2", "severity": "warning", "title": "Second warning"},
        {"id": "i1", "severity": "information", "title": "Filtered view"},
        {"id": "i2", "severity": "information", "title": "Second note"},
        {"id": "i3", "severity": "information", "title": "Third note"},
    ])
    icons = page.locator("[data-header-notices] [data-notice-icon]:visible")
    assert [icons.nth(index).get_attribute("data-notice-icon") for index in range(icons.count())] == [
        "error", "warning", "information"]
    assert [icons.nth(index).locator("[data-notice-count]").inner_text() for index in range(3)] == [
        "1", "2", "3"]
    assert icons.nth(1).get_attribute("aria-label") == "Warnings: 2 notices"
    assert reader_top() == top
    keep_screenshot(page, "notice-center-three-icons")
    page.evaluate("['e1', 'w1', 'w2', 'i1', 'i2', 'i3'].forEach((id) => globalThis.obsNotices.remove(id))")
    assert visible_icons(page) == {}
    assert reader_top() == top
    assert errors == []


def test_ten_notices_of_one_severity_give_one_icon_with_pill_ten(tmp_path: Path, reader_browser) -> None:
    errors: list[str] = []
    page = open_artifact(tmp_path, reader_browser, errors)
    post(page, [{"id": f"w{index}", "severity": "warning", "title": f"Warning {index}"} for index in range(10)])
    icons = page.locator("[data-header-notices] [data-notice-icon]:visible")
    assert icons.count() == 1
    assert icons.first.locator("[data-notice-count]").inner_text() == "10"
    assert errors == []


def test_icon_opens_its_list_an_entry_expands_and_escape_closes(tmp_path: Path, reader_browser) -> None:
    from playwright.sync_api import expect

    errors: list[str] = []
    page = open_artifact(tmp_path, reader_browser, errors)
    post(page, [
        {"id": "e1", "severity": "error", "title": "Broken figure", "details": "The figure failed."},
        {"id": "w1", "severity": "warning", "title": "Disk almost full",
         "details": ["Why: little space is left.", "Remedy: free some space."]},
        {"id": "i1", "severity": "information", "title": "Filtered view"},
    ])
    icon = page.locator('[data-notice-icon="warning"]')
    notices = page.locator('[data-notice-list="warning"]')
    expect(notices).to_be_hidden()
    icon.click()
    expect(icon).to_have_attribute("aria-expanded", "true")
    expect(notices).to_be_visible()
    expect(page.locator('[data-notice-list="error"]')).to_be_hidden()
    keep_screenshot(page, "notice-center-open-list")
    entry = notices.locator('[data-notice="w1"]')
    details = entry.locator("[data-notice-details]")
    expect(details).to_be_hidden()
    entry.locator("[data-notice-title]").click()
    expect(details).to_be_visible()
    expect(details).to_contain_text("Remedy: free some space.")
    expect(entry.locator("[data-notice-title]")).to_have_attribute("aria-expanded", "true")
    keep_screenshot(page, "notice-center-expanded-entry")
    page.keyboard.press("Escape")
    expect(notices).to_be_hidden()
    expect(icon).to_be_focused()
    page.keyboard.press("Enter")
    expect(notices).to_be_visible()
    icon.click()
    expect(notices).to_be_hidden()
    page.emulate_media(media="print")
    expect(icon).to_be_hidden()
    assert errors == []


def test_an_unknown_severity_names_the_post_and_the_choices(tmp_path: Path, reader_browser) -> None:
    errors: list[str] = []
    page = open_artifact(tmp_path, reader_browser, errors)
    message = page.evaluate("""() => {
        try { globalThis.obsNotices.post({id: "x", severity: "fatal", title: "X"}); }
        catch (error) { return error.message; }
    }""")
    assert message == 'obsNotices.post(x): unknown severity "fatal"; use one of error, warning, information.'


def test_changed_html_and_the_applied_filter_are_entries_that_keep_their_behaviour(
        tmp_path: Path, reader_browser) -> None:
    from playwright.sync_api import expect

    errors: list[str] = []
    page = open_page(reader_browser, _artifact(tmp_path, "artifact-change"), errors)
    expect(page.locator("html")).to_have_attribute("data-artifact-status", "ready")
    unload_prevented = """() => {
        const event = new Event("beforeunload", {cancelable: true});
        window.dispatchEvent(event);
        return event.defaultPrevented;
    }"""
    assert page.evaluate(unload_prevented) is False
    # Reader state is never a change (artifact-ui.md "What counts as a change"); a property edit is.
    page.evaluate("globalThis.obsArtifact.setViewSelection('proof', ['a'], ['a', 'b'])")
    page.evaluate("globalThis.obsFilter.setExpression(\"file.name == 'One'\")")
    changed = page.locator('[data-notice-list="information"] [data-notice="changed-html"]')
    applied = page.locator('[data-notice-list="information"] [data-notice="applied-filter"]')
    expect(applied).to_have_count(1)
    expect(changed).to_have_count(0)
    assert page.evaluate(unload_prevented) is False
    expect(applied.locator("[data-notice-title]")).to_have_text(re.compile(r"^Filtered view · \d+/2 chapters$"))
    page.evaluate("globalThis.obsArtifact.commitProperty('one', 'explanation', 'Changed')")
    expect(changed).to_have_count(1)
    assert page.evaluate(unload_prevented) is True
    expect(page.locator('[data-notice-icon="information"] [data-notice-count]')).to_have_text("2")
    page.locator('[data-notice-icon="information"]').click()
    changed.locator("[data-notice-title]").click()
    expect(changed.locator("[data-artifact-download]")).to_be_visible()
    applied.locator("[data-notice-title]").click()
    expect(applied).to_contain_text("Filter: file.name == 'One'")
    applied.locator("[data-filter-clear]").click()
    expect(applied).to_have_count(0)
    assert page.evaluate("globalThis.obsArtifact.filterSummary().empty") is True
    expect(changed).to_have_count(1)
    page.evaluate("globalThis.obsArtifact.commitProperty('one', 'explanation', 'Original')")
    expect(changed).to_have_count(0)
    assert page.evaluate(unload_prevented) is False
    assert errors == []
