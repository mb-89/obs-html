"""Appearance in Claude's artifact viewer: the chosen appearance decides every colour the reader sees.

The design owner is spec/artifact-ui.md (Appearance). Each test opens the artifact in
the viewer fixture (test/browser/viewer.py) with the host in dark and in light
`prefers-color-scheme`; nothing the artifact shows may take a colour from the host.
"""
import re

import pytest

from artifacts import artifact_html
from browser.viewer import HOST_SCHEMES, open_viewer
from documents import chapter, document, heading, paragraph

# appearance -> the root's color-scheme
APPEARANCES = {"light": "light", "dark": "dark", "system": "light dark"}

# What the reader sees, and the background each is read against.
COLOURS = """() => {
    const style = (selector) => {
        const computed = getComputedStyle(document.querySelector(selector));
        return {background: computed.backgroundColor, color: computed.color, scheme: computed.colorScheme};
    };
    return {
        html: style("html"), body: style("body"),
        heading: style("[data-chapter-body] h1"), text: style("[data-chapter-body] p"),
        select: style("[data-theme-select]"),
    };
}"""


def appearance_artifact(appearance: str | None = None) -> str:
    """The test page; `appearance`, where given, is its manifest's obsHtml.appearance."""
    return artifact_html(document(
        "Appearance",
        chapter("one", "One", heading(1, "One"), paragraph("First chapter text.")),
        metadata={"obsHtml": {"appearance": appearance}} if appearance else None,
    ))


def rgba(value: str) -> tuple[float, float, float, float]:
    match = re.fullmatch(r"rgba?\(([\d.]+), ([\d.]+), ([\d.]+)(?:, ([\d.]+))?\)", value)
    assert match, f"unparsed computed colour {value!r}"
    red, green, blue, alpha = match.groups()
    return float(red), float(green), float(blue), float(alpha if alpha is not None else 1)


def luminance(value: str) -> float:
    def channel(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    red, green, blue, _alpha = rgba(value)
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def choose(frame, appearance: str) -> None:
    frame.evaluate("""(value) => {
        const select = document.querySelector("[data-theme-select]");
        select.value = value;
        select.dispatchEvent(new Event("change"));
    }""", appearance)


def open_chapter(tmp_path, reader_browser, errors, host_scheme, appearance: str | None = None):
    _page, frame = open_viewer(tmp_path, reader_browser, errors, appearance_artifact(appearance), host_scheme)
    frame.locator('[data-step="1"]').first.click()
    frame.locator("[data-chapter-body] p").wait_for()
    return frame


def selected(frame) -> str:
    """The value the Settings bar's Appearance select shows."""
    return frame.evaluate('() => document.querySelector("[data-theme-select]").value')


def assert_white_page(colours: dict) -> None:
    for element in ("html", "body"):
        assert rgba(colours[element]["background"]) == (255, 255, 255, 1), f"{element} {colours[element]}"
        assert rgba(colours[element]["color"])[:3] == (0, 0, 0), f"{element} text {colours[element]}"


def assert_near_black_page(colours: dict) -> None:
    for element in ("html", "body"):
        page = rgba(colours[element]["background"])
        assert page[3] == 1, f"{element} {colours[element]}"
        assert all(abs(channel - 0x1f) <= 8 for channel in page[:3]), f"{element} {colours[element]}"
        assert luminance(colours[element]["color"]) > 0.5, f"{element} text {colours[element]}"


@pytest.mark.browser
def test_opening_follows_a_dark_system_scheme(tmp_path, reader_browser) -> None:
    """A page that declares no obsHtml.appearance opens in System: near-black in a dark scheme."""
    errors: list[str] = []
    frame = open_chapter(tmp_path, reader_browser, errors, "dark")
    colours = frame.evaluate(COLOURS)

    assert_near_black_page(colours)
    assert colours["html"]["scheme"] == "light dark"
    assert selected(frame) == "system"
    assert errors == []


@pytest.mark.browser
def test_opening_follows_a_light_system_scheme(tmp_path, reader_browser) -> None:
    """The same page in a light scheme is white with black text."""
    errors: list[str] = []
    frame = open_chapter(tmp_path, reader_browser, errors, "light")
    colours = frame.evaluate(COLOURS)

    assert_white_page(colours)
    assert colours["html"]["scheme"] == "light dark"
    assert selected(frame) == "system"
    assert errors == []


@pytest.mark.browser
def test_a_declared_light_appearance_opens_light_in_a_dark_host(tmp_path, reader_browser) -> None:
    errors: list[str] = []
    frame = open_chapter(tmp_path, reader_browser, errors, "dark", "light")
    colours = frame.evaluate(COLOURS)

    assert_white_page(colours)
    assert colours["html"]["scheme"] == "light"
    assert selected(frame) == "light"
    assert errors == []


@pytest.mark.browser
def test_a_declared_dark_appearance_opens_dark_in_a_light_host(tmp_path, reader_browser) -> None:
    errors: list[str] = []
    frame = open_chapter(tmp_path, reader_browser, errors, "light", "dark")
    colours = frame.evaluate(COLOURS)

    assert_near_black_page(colours)
    assert colours["html"]["scheme"] == "dark"
    assert selected(frame) == "dark"
    choose(frame, "light")
    assert_white_page(frame.evaluate(COLOURS))
    assert errors == []


@pytest.mark.browser
@pytest.mark.parametrize("host_scheme", HOST_SCHEMES)
def test_printing_is_light_in_every_appearance_and_scheme(tmp_path, reader_browser, host_scheme) -> None:
    """artifact-ui.md: printing always uses light colours, whatever the appearance and the system scheme."""
    errors: list[str] = []
    page, frame = open_viewer(tmp_path, reader_browser, errors, appearance_artifact(), host_scheme)
    page.emulate_media(media="print")
    for appearance in APPEARANCES:
        choose(frame, appearance)
        colours = frame.evaluate("""() => Object.fromEntries(["html", "body"].map((selector) => {
            const computed = getComputedStyle(document.querySelector(selector));
            return [selector, {background: computed.backgroundColor, color: computed.color}];
        }))""")
        for element in ("html", "body"):
            assert rgba(colours[element]["background"]) == (255, 255, 255, 1), f"{appearance}: {element} {colours[element]}"
            assert rgba(colours[element]["color"])[:3] == (0, 0, 0), f"{appearance}: {element} {colours[element]}"
    assert errors == []


@pytest.mark.browser
@pytest.mark.parametrize("host_scheme", HOST_SCHEMES)
def test_each_appearance_paints_its_own_opaque_readable_colours(tmp_path, reader_browser, host_scheme) -> None:
    errors: list[str] = []
    frame = open_chapter(tmp_path, reader_browser, errors, host_scheme)
    seen = {}
    for appearance in APPEARANCES:
        choose(frame, appearance)
        colours = frame.evaluate(COLOURS)
        seen[appearance] = colours
        assert colours["html"]["scheme"] == APPEARANCES[appearance]
        for element in ("html", "body"):
            assert rgba(colours[element]["background"])[3] == 1, f"{appearance}: {element} {colours[element]}"
        for element in ("body", "heading", "text"):
            ratio = contrast(colours[element]["color"], colours["body"]["background"])
            assert ratio >= 4.5, f"{appearance}: {element} contrast {ratio:.2f} {colours[element]}"

    assert seen["light"]["body"]["background"] != seen["dark"]["body"]["background"]
    for colour in ("background", "color"):
        assert seen["system"]["body"][colour] == seen[host_scheme]["body"][colour], "System follows the host"
    assert errors == []


@pytest.mark.browser
def test_switching_appearance_recolours_at_once_with_native_controls(tmp_path, reader_browser) -> None:
    errors: list[str] = []
    frame = open_chapter(tmp_path, reader_browser, errors, "light")
    choose(frame, "light")
    light = frame.evaluate(COLOURS)

    choose(frame, "dark")
    dark = frame.evaluate(COLOURS)

    assert dark["body"]["background"] != light["body"]["background"]
    assert dark["text"]["color"] != light["text"]["color"]
    assert (light["select"]["scheme"], dark["select"]["scheme"]) == ("light", "dark")
    assert errors == []


@pytest.mark.browser
def test_dark_is_a_near_black_page_with_white_headings_and_light_grey_text(tmp_path, reader_browser) -> None:
    """Dark is the look the owner chose; Light keeps the white page with black text."""
    errors: list[str] = []
    frame = open_chapter(tmp_path, reader_browser, errors, "light")
    choose(frame, "light")
    light = frame.evaluate(COLOURS)
    choose(frame, "dark")
    dark = frame.evaluate(COLOURS)

    page = rgba(dark["html"]["background"])
    assert all(abs(channel - 0x1f) <= 8 for channel in page[:3]), f"dark page {dark['html']}"
    assert rgba(dark["heading"]["color"])[:3] == (255, 255, 255), f"dark heading {dark['heading']}"
    assert 0.5 < luminance(dark["text"]["color"]) < 0.9, f"dark text is light grey {dark['text']}"
    assert rgba(light["html"]["background"])[:3] == (255, 255, 255), f"light page {light['html']}"
    assert rgba(light["text"]["color"])[:3] == (0, 0, 0), f"light text {light['text']}"
    assert errors == []
