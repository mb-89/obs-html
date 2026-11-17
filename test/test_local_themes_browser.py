"""Local themes in the browser: a page opens in its start theme, in each appearance, prints light,
and a guided card's window shows the page's theme.

The design owner is spec/artifact-ui.md (Styling). The pages carry the made-up fixture theme
(test/fixtures/local-themes) or a copy of it whose local.json names it.
"""
import shutil

import pytest

from artifacts import artifact_html
from browser.viewer import open_viewer
from documents import chapter, document, heading, paragraph
from test_appearance_browser import choose, rgba
from test_features import with_context_note
from test_local_themes import COLOURS, LOCAL_THEMES, VARIABLE
from obs_html.style_choice import local_style_choice

pytestmark = pytest.mark.browser

DEFAULT = {"canvas": {"light": "#ffffff", "dark": "#1f1f1f"}, "surface": {"light": "#ffffff", "dark": "#202020"},
           "text": {"light": "#000000", "dark": "#dddddd"}}
THEME = {name: COLOURS[name]["value"] for name in ("canvas", "surface", "text")}
PAINTED = """(selector) => {
    const computed = getComputedStyle(document.querySelector(selector));
    return {background: computed.backgroundColor, color: computed.color};
}"""


def rgb(hex_colour: str) -> tuple[float, float, float, float]:
    return tuple(float(int(hex_colour[index:index + 2], 16)) for index in (1, 3, 5)) + (1.0,)


def starting_in(tmp_path, start: str):
    """The fixture's choice, from a copy of its folder whose local.json names ``start``."""
    folder = tmp_path / "obs-html"
    shutil.copytree(LOCAL_THEMES, folder)
    (folder / "local.json").write_text(f'{{"startTheme": "{start}"}}', encoding="utf-8")
    return local_style_choice({VARIABLE: str(folder)})


def themed(tmp_path, start: str) -> str:
    return artifact_html(document("Themes", chapter("one", "One", heading(1, "One"), paragraph("Text."))),
                         style_choice=starting_in(tmp_path, start))


@pytest.mark.parametrize("start, colours", [("contrast", THEME), ("default", DEFAULT)])
def test_a_page_opens_in_its_start_theme_in_each_appearance(tmp_path, reader_browser, start, colours) -> None:
    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, themed(tmp_path, start), "light")
    assert frame.evaluate("() => document.documentElement.dataset.style") == start
    for appearance in ("light", "dark"):
        choose(frame, appearance)
        painted = frame.evaluate(PAINTED, "html")
        assert rgba(painted["background"]) == rgb(colours["canvas"][appearance]), f"{appearance}: {painted}"
        assert rgba(painted["color"]) == rgb(colours["text"][appearance]), f"{appearance}: {painted}"
    assert errors == []


def test_a_themed_page_prints_light(tmp_path, reader_browser) -> None:
    errors: list[str] = []
    page, frame = open_viewer(tmp_path, reader_browser, errors, themed(tmp_path, "contrast"), "dark")
    choose(frame, "dark")
    page.emulate_media(media="print")
    painted = frame.evaluate(PAINTED, "body")
    assert rgba(painted["background"]) == rgb(THEME["surface"]["light"]), painted
    assert rgba(painted["color"]) == rgb(THEME["text"]["light"]), painted
    assert errors == []


def test_a_guided_card_window_opens_in_the_page_theme(tmp_path, reader_browser) -> None:
    artifact = tmp_path / "context.html"
    artifact.write_text(artifact_html(with_context_note(), style_choice=starting_in(tmp_path, "contrast")),
                        encoding="utf-8")
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
    assert window.evaluate("() => document.documentElement.dataset.style") == "contrast"
    painted = window.evaluate(PAINTED, "html")
    assert rgba(painted["background"]) == rgb(THEME["canvas"]["light"]), painted
    window.close()
    assert errors == []
