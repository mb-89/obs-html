"""The Theme select in the browser: on a page that carries local themes, the Settings bar offers
Default and each theme below Appearance; choosing one restyles the page at once in the current
appearance, lays its sheets and tables out again, prints in the theme's light colours, and is
never stored.

The design owner is spec/artifact-ui.md (Styling, and What counts as a change). The pages carry the
made-up fixture theme (test/fixtures/local-themes) or a copy of it whose local.json names it; the
choice logic's pure core is style-choice.test.js's.

The select's width and the printed theme are hot: they open the viewer fixture
(test/browser/viewer.py) in the real Chromium. The others run on the fake browser
(test/browser/browser-door.md), each page from the recording of its state
(test/browser/expectations.yaml) at desktop size; the fake has no frames, so the artifact is the
top-level page, as it is in the viewer's frame. Where a theme lays the page out again, they check
that the runtime measured again in the theme's styles, from what the page asked the fake after the
choice, not the recorded sizes.
"""
import re
from pathlib import Path

import pytest

from artifacts import artifact_html
from browser import door
from browser.fake_page import expect
from browser.viewer import open_viewer
from documents import chapter, document, heading, node, paragraph
from test_appearance_browser import choose, rgba
from test_features import with_context_note
from test_local_themes import fixture_choice, with_style
from test_local_themes_browser import DEFAULT, PAINTED, THEME, rgb, starting_in

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
SELECTS = """() => ["[data-theme-select]", "[data-style-select]"].map(selector => {
    const select = document.querySelector(selector);
    return {select: selector, parent: select.parentElement.className,
            right: select.getBoundingClientRect().right, label: select.closest("label").getBoundingClientRect().right};
})"""
TABLE_BOX = """() => {
    const box = document.querySelector("[data-active-chapter] .data-table-shell table").getBoundingClientRect();
    return [Math.round(box.width), Math.round(box.height)];
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


# The pages of the browser door's states (test/browser/expectations.yaml), each built in the current
# folder (browser/door.py, build_artifact).

def plain_page() -> dict:
    return document("Plain", chapter("one", "One", heading(1, "One"), paragraph("Text.")))


def text_page_default() -> str:
    return text_page()


def text_page_contrast() -> str:
    return text_page("contrast", Path.cwd())


def long_page_default() -> str:
    return long_page(fixture_choice())


def table_default() -> str:
    return artifact_html(table_document(), style_choice=fixture_choice())


def table_contrast() -> str:
    return artifact_html(table_document(), style_choice=starting_in(Path.cwd(), "contrast"))


def _bold(start: str | None) -> str:
    folder = with_style(Path.cwd(), ".data-table-scroll table { font-weight: 700; }\n")
    if start:
        (folder / "local.json").write_text(f'{{"startTheme": "{start}"}}', encoding="utf-8")
    return artifact_html(table_document(), style_choice=fixture_choice(folder))


def bold_table_default() -> str:
    """A table whose theme contrast changes only its text metrics: bold."""
    return _bold(None)


def bold_table_contrast() -> str:
    return _bold("contrast")


def guided_card_page() -> str:
    return artifact_html(with_context_note(), style_choice=fixture_choice())


def colour(value: str) -> tuple[float, float, float, float]:
    """A computed colour as red, green, blue and alpha: Chromium writes rgb(), the fake hex."""
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return rgb(value)
    return rgba(value)


def opened(fake_page, door_artifact, state: str, errors: list[str], url: str | None = None):
    """The state's page in the fake browser, opened from its recording, as the top-level page;
    ``errors`` collects page errors and console errors, as the viewer fixture's do."""
    fake_page.on("pageerror", lambda error: errors.append(str(error)))
    fake_page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    door.open_recorded(fake_page, state, door_artifact(state), url=url)
    expect(fake_page.locator("html")).to_have_attribute("data-artifact-status", "ready")
    return fake_page


def measured_fonts(page) -> set[str]:
    """The fonts of the texts the runtime measured since the last call (the fake's text-width calls)."""
    return {key.split("|", 1)[0] for kinds in page.asked().values() for key in kinds.get("text-width", [])}


def asked_boxes(page) -> set[str]:
    """The elements whose box or sizes the runtime asked for since the last call."""
    return {key for kinds in page.asked().values() for kind in ("box", "sizes") for key in kinds.get(kind, [])}


@pytest.mark.dom
def test_a_page_without_local_themes_offers_no_theme(door_artifact, fake_page) -> None:
    html = artifact_html(plain_page())
    assert "data-style-select" not in html and 'id="feature-styles-style-choice"' not in html
    assert "obsStyleChoice" not in html and ".settings-style" not in html
    errors: list[str] = []
    frame = opened(fake_page, door_artifact, "theme-choice-plain", errors)
    assert frame.locator(SELECT).count() == 0
    assert frame.evaluate("() => document.documentElement.hasAttribute('data-style')") is False
    assert errors == []


@pytest.mark.dom
def test_the_settings_bar_offers_default_then_each_theme_below_appearance(door_artifact, fake_page) -> None:
    errors: list[str] = []
    frame = opened(fake_page, door_artifact, "theme-choice-text", errors)
    assert frame.evaluate(SETTINGS) == {
        "count": 1, "afterAppearance": True, "label": "Theme", "aria": "Theme",
        "options": [["default", "Default"], ["contrast", "contrast"]], "value": "default", "root": "default"}
    frame = opened(fake_page, door_artifact, "theme-choice-text-contrast", errors)
    settings = frame.evaluate(SETTINGS)
    assert (settings["count"], settings["value"], settings["root"]) == (1, "contrast", "contrast"), settings
    assert errors == []


@pytest.mark.dom
@pytest.mark.parametrize("host_scheme", ["light", "dark"])
def test_choosing_a_theme_restyles_at_once_in_each_appearance(door_artifact, fake_page, host_scheme) -> None:
    errors: list[str] = []
    frame = opened(fake_page, door_artifact, "theme-choice-text", errors)
    frame.emulate_media(color_scheme=host_scheme)
    for appearance in ("light", "dark"):
        choose(frame, appearance)
        for style, colours in (("contrast", THEME), ("default", DEFAULT)):
            pick(frame, style)
            assert frame.evaluate("() => document.documentElement.dataset.style") == style
            painted = frame.evaluate(PAINTED, "html")
            assert colour(painted["background"]) == rgb(colours["canvas"][appearance]), f"{appearance} {style}: {painted}"
            assert colour(painted["color"]) == rgb(colours["text"][appearance]), f"{appearance} {style}: {painted}"
    pick(frame, "contrast")
    for appearance in ("light", "dark"):
        choose(frame, appearance)
        assert frame.evaluate("() => document.documentElement.dataset.style") == "contrast"
        painted = frame.evaluate(PAINTED, "html")
        assert colour(painted["background"]) == rgb(THEME["canvas"][appearance]), f"{appearance}: {painted}"
    assert errors == []


def _sheets(frame):
    frame.wait_for_function(MEASURED)
    return frame.evaluate(SHEETS)


@pytest.mark.dom
def test_choosing_a_theme_lays_the_sheets_out_again(door_artifact, fake_page) -> None:
    """The sheets are laid out again in the chosen theme: after the choice the runtime measures again
    the blocks it laid the sheets out from, and numbers every sheet; where the sheets break is the
    recorded Chromium's layout, which a logic test does not assert."""
    errors: list[str] = []
    frame = opened(fake_page, door_artifact, "theme-choice-long", errors)
    _sheets(frame)
    paged = asked_boxes(frame)
    pick(frame, "contrast")
    sheets = _sheets(frame)
    again = asked_boxes(frame)
    assert again & paged, "choosing a theme measured none of the blocks the sheets were laid out from again"
    assert sheets and all(number for _first, _last, number in sheets), sheets
    assert errors == []


def _columns(frame):
    frame.evaluate("() => { obsPages.setPaged(false); obsArtifact.activateChapter('one'); }")
    frame.locator("[data-active-chapter] .data-table-shell thead th").first.wait_for()
    frame.evaluate("() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))")
    return measured_fonts(frame)


@pytest.mark.dom
def test_choosing_a_theme_measures_the_table_columns_again(door_artifact, fake_page) -> None:
    """The columns take the widths of their texts in the chosen theme: after the choice the runtime
    measures the table's texts again, in fonts a page opened in that theme measures them in."""
    errors: list[str] = []
    expected = _columns(opened(fake_page, door_artifact, "theme-choice-table-contrast", errors))
    frame = opened(fake_page, door_artifact, "theme-choice-table", errors)
    before = _columns(frame)
    assert before and before != expected, "the fixture theme's font sizes the columns differently"
    pick(frame, "contrast")
    frame.evaluate("() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))")
    after = measured_fonts(frame)
    assert after and after <= expected, (after, expected)
    assert errors == []


@pytest.mark.hot("theme-choice-text")
@pytest.mark.browser
@pytest.mark.parametrize("width", [390, 1180])
def test_the_theme_select_is_as_wide_as_its_options_as_the_appearance_select_is(tmp_path, reader_browser, width) -> None:
    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, text_page(), "light", width=width)
    frame.evaluate("() => obsArtifact.openBar('settings')")
    frame.locator(SELECT).wait_for()
    for placed in frame.evaluate(SELECTS):
        assert placed["parent"] == "settings-appearance-control", placed
        assert placed["right"] < placed["label"] - 1, placed
    assert errors == []


@pytest.mark.dom
def test_a_theme_that_changes_only_text_metrics_measures_the_columns_again(door_artifact, fake_page) -> None:
    """A theme that only makes the table bold leaves the table's box as it is, so no resize measures
    it again: the choice itself does, in the fonts a page opened in that theme measures in and no
    longer in the fixture theme's plain cells' font."""
    errors: list[str] = []
    expected = _columns(opened(fake_page, door_artifact, "theme-choice-bold-table-contrast", errors))
    frame = opened(fake_page, door_artifact, "theme-choice-bold-table", errors)
    before = _columns(frame)
    assert before - expected, "the fixture theme measures the plain cells in a font the bold theme does not"
    pick(frame, "contrast")
    frame.evaluate("() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))")
    after = measured_fonts(frame)
    assert after and after <= expected, (after, expected, before)
    assert errors == []


@pytest.mark.dom
def test_the_theme_choice_is_session_only(door_artifact, fake_page) -> None:
    errors: list[str] = []
    page = opened(fake_page, door_artifact, "theme-choice-text", errors)
    stored, unsaved = page.evaluate(STORED), page.evaluate(UNSAVED)
    assert unsaved["changed"] is False and unsaved["warned"] is False
    pick(page, "contrast")
    assert page.evaluate("() => document.documentElement.dataset.style") == "contrast"
    assert page.evaluate(STORED) == stored
    assert page.evaluate(UNSAVED) == unsaved
    page.reload()
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    assert page.evaluate("() => document.documentElement.dataset.style") == "default"
    assert page.evaluate("() => document.querySelector('[data-style-select]').value") == "default"
    assert errors == []


@pytest.mark.dom
def test_a_saved_copy_reopens_in_the_start_theme_with_one_theme_select(door_artifact, fake_page, tmp_path) -> None:
    errors: list[str] = []
    frame = opened(fake_page, door_artifact, "theme-choice-text", errors)
    unchosen = frame.evaluate("obsComments.reviewedHtml()")
    pick(frame, "contrast")
    copy = frame.evaluate("obsComments.reviewedHtml()")
    assert "data-style-select" not in copy
    assert copy == unchosen, "a saved copy holds nothing of the reader's theme"
    saved = tmp_path / "copy.html"
    saved.write_text(copy, encoding="utf-8")
    reopened = opened(fake_page, door_artifact, "theme-choice-text", errors, url=saved.as_uri())
    assert reopened.evaluate("() => document.documentElement.dataset.style") == "default"
    assert reopened.locator(SELECT).count() == 1
    assert errors == []


# The window the guided card opened, kept for the test: window.open as the page has it.
KEEP_WINDOW = """() => {
    const open = window.open;
    window.open = (...args) => (globalThis.openedWindow = open.apply(window, args));
}"""
WINDOW_PAINTED = """() => {
    const child = globalThis.openedWindow;
    const computed = child.getComputedStyle(child.document.documentElement);
    return {style: child.document.documentElement.dataset.style, background: computed.backgroundColor,
            card: Boolean(child.document.querySelector(".guided-card-window"))};
}"""


@pytest.mark.dom
def test_a_guided_card_window_follows_the_theme(door_artifact, fake_page) -> None:
    errors: list[str] = []
    page = opened(fake_page, door_artifact, "theme-choice-guided-card", errors)
    page.evaluate("() => { obsPages.setPaged(false); obsArtifact.activateChapter('one'); }")
    choose(page, "light")
    page.evaluate(KEEP_WINDOW)
    page.locator("[data-chapter-body] a[href='#aside']").click()
    page.wait_for_function("() => globalThis.openedWindow?.document.querySelector('.guided-card-window')")
    for style, colours in (("contrast", THEME), ("default", DEFAULT)):
        pick(page, style)
        page.wait_for_function("(style) => globalThis.openedWindow.document.documentElement.dataset.style === style",
                               arg=style)
        painted = page.evaluate(WINDOW_PAINTED)
        assert painted["card"] and colour(painted["background"]) == rgb(colours["canvas"]["light"]), f"{style}: {painted}"
    page.evaluate("() => globalThis.openedWindow.close()")
    assert errors == []


@pytest.mark.hot("theme-choice-text")
@pytest.mark.browser
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
