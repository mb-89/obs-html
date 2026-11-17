"""The Theme select in the browser: on a page that carries local themes, the Settings bar offers
Default and each theme below Appearance; choosing one restyles the page at once in the current
appearance, lays its sheets and tables out again, prints in the theme's light colours, and is
never stored.

The design owner is spec/artifact-ui.md (Styling, and What counts as a change). The pages carry the
made-up fixture theme (test/fixtures/local-themes) or a copy of it whose local.json names it; the
choice logic's pure core is style-choice.test.js's.
"""
import pytest

from artifacts import artifact_html
from browser.viewer import open_viewer
from documents import chapter, document, heading, node, paragraph
from test_appearance_browser import choose, rgba
from test_features import with_context_note
from test_local_themes import fixture_choice
from test_local_themes_browser import DEFAULT, PAINTED, THEME, rgb, starting_in

pytestmark = pytest.mark.browser

SELECT = "[data-style-select]"
SETTINGS = """() => {
    const select = document.querySelector("[data-style-select]");
    const label = select.closest("label");
    return {
        count: document.querySelectorAll("[data-style-select]").length,
        afterAppearance: label.previousElementSibling.contains(document.querySelector("[data-theme-select]")),
        label: label.firstChild.textContent,
        aria: select.getAttribute("aria-label"),
        options: [...select.options].map(option => [option.value, option.textContent]),
        value: select.value,
        root: document.documentElement.dataset.style,
    };
}"""
SHEETS = """() => [...document.querySelectorAll(".paged-reader .paper-sheet:not([hidden])")].map(sheet => {
    const content = sheet.querySelector(".paper-content");
    return [content.firstElementChild?.textContent.slice(0, 24), content.lastElementChild?.textContent.slice(-24),
            sheet.querySelector(".paper-page-number")?.textContent];
})"""
MEASURED = """() => ![...document.querySelectorAll(".paged-reader .paper-page-number")]
    .some(number => number.textContent.startsWith("Calculating"))"""
COLUMNS = """() => [...document.querySelectorAll("[data-active-chapter] .data-table-shell thead th")]
    .map(cell => Math.round(cell.getBoundingClientRect().width))"""
STORED = """() => {
    const read = (name) => { try { return JSON.stringify({...globalThis[name]}); } catch { return null; } };
    return {local: read("localStorage"), session: read("sessionStorage")};
}"""
UNSAVED = """() => {
    const event = new Event("beforeunload", {cancelable: true});
    window.dispatchEvent(event);
    return {changed: obsNotices.has("changed-html"), warned: event.defaultPrevented,
            state: JSON.stringify(obsArtifact.readerState())};
}"""


def pick(frame, style: str) -> None:
    """Choose ``style`` in the Theme select, as a reader does."""
    frame.evaluate("""(value) => {
        const select = document.querySelector("[data-style-select]");
        select.value = value;
        select.dispatchEvent(new Event("change"));
    }""", style)


def text_page(start=None, tmp_path=None) -> str:
    source = document("Themes", chapter("one", "One", heading(1, "One"), paragraph("Text.")))
    return artifact_html(source, style_choice=starting_in(tmp_path, start) if start else fixture_choice())


def long_page(choice) -> str:
    """A chapter of many paragraphs, which pages over several sheets."""
    paragraphs = [paragraph(f"Paragraph {index}: " + "words that fill the sheet " * 12) for index in range(40)]
    return artifact_html(document("Long", chapter("one", "One", heading(1, "One"), *paragraphs)), style_choice=choice)


def table_document() -> dict:
    """A Base table whose columns take the widths of their contents."""
    records = [{"id": f"r{index}", "type": "note", "path": f"r{index}.md", "fields": {
        "kind": "row", "code": f"R-{index}", "owner": "Operations team " * (index % 3 + 1), "state": "open"}}
        for index in range(4)]
    base = node("bases", source="", spec={"filters": {"or": ['kind == "row"']}, "views": [{
        "type": "table", "name": "Rows", "order": ["file.name", "code", "owner", "state"]}]})
    return document("Table", chapter("one", "One", heading(1, "One"), base), records=records)


def open_chapter(frame) -> None:
    frame.locator('[data-step="1"]').first.click()
    frame.locator("[data-chapter-body] h1, .paged-reader h1").first.wait_for()


def test_a_page_without_local_themes_offers_no_theme(tmp_path, reader_browser) -> None:
    source = document("Plain", chapter("one", "One", heading(1, "One"), paragraph("Text.")))
    html = artifact_html(source)
    assert "data-style-select" not in html and 'id="feature-styles-style-choice"' not in html
    assert "obsStyleChoice" not in html and ".settings-style" not in html
    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, html, "light")
    assert frame.locator(SELECT).count() == 0
    assert frame.evaluate("() => document.documentElement.hasAttribute('data-style')") is False
    assert errors == []


def test_the_settings_bar_offers_default_then_each_theme_below_appearance(tmp_path, reader_browser) -> None:
    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, text_page(), "light")
    assert frame.evaluate(SETTINGS) == {
        "count": 1, "afterAppearance": True, "label": "Theme", "aria": "Theme",
        "options": [["default", "Default"], ["contrast", "contrast"]], "value": "default", "root": "default"}
    _page, frame = open_viewer(tmp_path, reader_browser, errors, text_page("contrast", tmp_path), "light")
    settings = frame.evaluate(SETTINGS)
    assert (settings["count"], settings["value"], settings["root"]) == (1, "contrast", "contrast"), settings
    assert errors == []


@pytest.mark.parametrize("host_scheme", ["light", "dark"])
def test_choosing_a_theme_restyles_at_once_in_each_appearance(tmp_path, reader_browser, host_scheme) -> None:
    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, text_page(), host_scheme)
    for appearance in ("light", "dark"):
        choose(frame, appearance)
        for style, colours in (("contrast", THEME), ("default", DEFAULT)):
            pick(frame, style)
            assert frame.evaluate("() => document.documentElement.dataset.style") == style
            painted = frame.evaluate(PAINTED, "html")
            assert rgba(painted["background"]) == rgb(colours["canvas"][appearance]), f"{appearance} {style}: {painted}"
            assert rgba(painted["color"]) == rgb(colours["text"][appearance]), f"{appearance} {style}: {painted}"
    pick(frame, "contrast")
    for appearance in ("light", "dark"):
        choose(frame, appearance)
        assert frame.evaluate("() => document.documentElement.dataset.style") == "contrast"
        painted = frame.evaluate(PAINTED, "html")
        assert rgba(painted["background"]) == rgb(THEME["canvas"][appearance]), f"{appearance}: {painted}"
    assert errors == []


def _sheets(frame):
    frame.wait_for_function(MEASURED)
    return frame.evaluate(SHEETS)


def test_choosing_a_theme_lays_the_sheets_out_again(tmp_path, reader_browser) -> None:
    errors: list[str] = []
    _page, opened = open_viewer(tmp_path, reader_browser, errors, long_page(starting_in(tmp_path, "contrast")), "light")
    open_chapter(opened)
    expected = _sheets(opened)
    _page, frame = open_viewer(tmp_path, reader_browser, errors, long_page(fixture_choice()), "light")
    open_chapter(frame)
    before = _sheets(frame)
    assert before != expected, "the fixture theme's spacing pages the chapter differently"
    pick(frame, "contrast")
    assert _sheets(frame) == expected
    assert errors == []


def _columns(frame):
    frame.evaluate("() => { obsPages.setPaged(false); obsArtifact.activateChapter('one'); }")
    frame.locator("[data-active-chapter] .data-table-shell thead th").first.wait_for()
    return frame.evaluate(COLUMNS)


def test_choosing_a_theme_measures_the_table_columns_again(tmp_path, reader_browser) -> None:
    errors: list[str] = []
    contrast = artifact_html(table_document(), style_choice=starting_in(tmp_path, "contrast"))
    _page, opened = open_viewer(tmp_path, reader_browser, errors, contrast, "light")
    expected = _columns(opened)
    _page, frame = open_viewer(tmp_path, reader_browser, errors, artifact_html(
        table_document(), style_choice=fixture_choice()), "light")
    before = _columns(frame)
    assert before != expected, "the fixture theme's font and padding size the columns differently"
    pick(frame, "contrast")
    frame.wait_for_function(f"(expected) => JSON.stringify(({COLUMNS})()) === JSON.stringify(expected)", arg=expected)
    assert errors == []


def test_the_theme_choice_is_session_only(tmp_path, reader_browser) -> None:
    errors: list[str] = []
    page, frame = open_viewer(tmp_path, reader_browser, errors, text_page(), "light")
    stored, unsaved = frame.evaluate(STORED), frame.evaluate(UNSAVED)
    assert unsaved["changed"] is False and unsaved["warned"] is False
    pick(frame, "contrast")
    assert frame.evaluate("() => document.documentElement.dataset.style") == "contrast"
    assert frame.evaluate(STORED) == stored
    assert frame.evaluate(UNSAVED) == unsaved
    page.reload()
    frame = page.locator("#artifact").element_handle().content_frame()
    frame.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    assert frame.evaluate("() => document.documentElement.dataset.style") == "default"
    assert frame.evaluate("() => document.querySelector('[data-style-select]').value") == "default"
    assert errors == []


def test_a_saved_copy_reopens_in_the_start_theme_with_one_theme_select(tmp_path, reader_browser) -> None:
    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, text_page(), "light")
    unchosen = frame.evaluate("obsComments.reviewedHtml()")
    pick(frame, "contrast")
    copy = frame.evaluate("obsComments.reviewedHtml()")
    assert "data-style-select" not in copy
    assert copy == unchosen, "a saved copy holds nothing of the reader's theme"
    _page, reopened = open_viewer(tmp_path, reader_browser, errors, copy, "light")
    assert reopened.evaluate("() => document.documentElement.dataset.style") == "default"
    assert reopened.locator(SELECT).count() == 1
    assert errors == []


def test_a_guided_card_window_follows_the_theme(tmp_path, reader_browser) -> None:
    artifact = tmp_path / "context.html"
    artifact.write_text(artifact_html(with_context_note(), style_choice=fixture_choice()), encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": 1100, "height": 800})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate("() => { obsPages.setPaged(false); obsArtifact.activateChapter('one'); }")
    choose(page, "light")
    with page.expect_popup() as opened:
        page.locator("[data-chapter-body] a[href='#aside']").click()
    window = opened.value
    window.wait_for_selector(".guided-card-window")
    for style, colours in (("contrast", THEME), ("default", DEFAULT)):
        pick(page, style)
        window.wait_for_function("(style) => document.documentElement.dataset.style === style", arg=style)
        painted = window.evaluate(PAINTED, "html")
        assert rgba(painted["background"]) == rgb(colours["canvas"]["light"]), f"{style}: {painted}"
    window.close()
    assert errors == []


def test_export_to_pdf_prints_the_chosen_theme_in_light(tmp_path, reader_browser) -> None:
    errors: list[str] = []
    page, frame = open_viewer(tmp_path, reader_browser, errors, text_page(), "dark")
    choose(frame, "dark")
    pick(frame, "contrast")
    page.emulate_media(media="print")
    painted = frame.evaluate(PAINTED, "body")
    assert rgba(painted["background"]) == rgb(THEME["surface"]["light"]), painted
    assert rgba(painted["color"]) == rgb(THEME["text"]["light"]), painted
    assert errors == []
