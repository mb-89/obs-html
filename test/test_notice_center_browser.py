"""The notice center: at most three severity icons with count pills, each opening its list."""
import json
import re
from pathlib import Path

import pytest

from conftest import built_once
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


def test_icon_opens_its_list_an_entry_expands_and_escape_closes(tmp_path: Path, full_chromium_browser) -> None:
    from playwright.sync_api import expect

    errors: list[str] = []
    page = open_artifact(tmp_path, full_chromium_browser, errors)
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
    # Its details name only what marks the HTML changed: comments and edits, never reader settings.
    expect(changed).to_contain_text("Comments or edits changed since this HTML was last saved.")
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


# The passing line (artifact-ui.md, Dock menu: the notice center's passing line; notices.js, brief):
# a deck whose two chapters ask for a bless, the first with a figure that opens in an overlay, built
# with a test bundle whose sink gives its name, with the line on (a short time) and with the default.
BRIEF_MILLISECONDS = 1200
"""The line's time on the pages that turn it on: short, so a test sees it go."""
SINK_ID = "claude-artifact"
SINK_BUNDLE = f"""globalThis.obsArtifact.registerApplication({{id: "sink-v1", actions: []}});
globalThis.received = [];
globalThis.obsArtifact.trustedExtension("obsHtml.answers").register({{id: "{SINK_ID}", name: "Claude",
    send: async payload => {{ globalThis.received.push(payload); return "saved"; }}}});"""
SENT_VIEWPORTS = [{"width": 390, "height": 844}, {"width": 1100, "height": 800}]
DRAWING = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 60" width="300" height="60">'
           '<rect x="4" y="4" width="60" height="24"/></svg>')
BAND_BOXES = """() => [...document.querySelectorAll('.top-band a, .top-band button, .top-band summary, '
        + '.top-band [data-bless-pill], .top-band [data-screens-title]')]
    .filter(node => node.checkVisibility() && !node.closest('.notice-list, .bless-entry, .chapter-breadcrumb-menu'))
    .map(node => {
        const box = node.getBoundingClientRect();
        return [node.getAttribute('aria-label') || node.textContent.trim(), box.left, box.top, box.width, box.height];
    })"""
"""Each shown control of the top band, the title of screens with them: its name and its box."""
LINE_BOX = """() => {
    const line = document.querySelector('[data-brief-notice]'), band = document.querySelector('[data-top-band]');
    const box = line.getBoundingClientRect(), outer = band.getBoundingClientRect(), style = getComputedStyle(band);
    return {left: box.left, right: box.right, top: box.top, bottom: box.bottom,
            bandBottom: outer.bottom, bandLeft: outer.left + parseFloat(style.paddingLeft),
            bandRight: outer.right - parseFloat(style.paddingRight), width: innerWidth, height: innerHeight};
}"""
FADES = """() => new Promise(resolve => {
    const line = document.querySelector('[data-brief-notice]');
    let animated = false;
    const look = () => {
        animated ||= line.getAnimations().length > 0;
        if (line.hidden) resolve(animated); else requestAnimationFrame(look);
    };
    look();
})"""
"""Whether the shown line runs an animation before it goes: its fade."""


def _sent_deck() -> str:
    from documents import chapter, document, heading, paragraph

    source = document("Sent", chapter("one", "One", heading(1, "One"), paragraph("Bless this."),
                                      {"type": "figures", "attrs": {"kind": "svg", "alt": "A drawing"},
                                       "children": [{"type": "svg", "attrs": {"svg": DRAWING}, "children": []}]}),
                      chapter("two", "Two", heading(1, "Two"), paragraph("And this.")))
    source["chapters"][0]["bless"] = {"version": "0" * 64}
    source["chapters"][1]["bless"] = {"version": "1" * 64}
    return json.dumps(source)


def _build_sent(folder: Path, settings: dict | None, bundled: bool, name: str) -> Path:
    from obs_html import cli

    source, bundle = folder / "deck.json", folder / "sink.js"
    source.write_text(_sent_deck(), encoding="utf-8")
    bundle.write_text(SINK_BUNDLE, encoding="utf-8")
    options = []
    if settings is not None:
        (folder / "cfg.json").write_text(json.dumps(settings), encoding="utf-8")
        options += ["--config", str(folder / "cfg.json")]
    if bundled:
        options += ["--trusted-runtime-bundle", f"sink-v1={bundle}"]
    assert cli.main([*options, str(source), str(folder / name)]) == 0
    return folder / name


@pytest.fixture(scope="module")
def line_on(tmp_path_factory) -> Path:
    """The deck with the line on and the named sink."""
    settings = {"artifact": {"reading": {"briefNoticeMilliseconds": BRIEF_MILLISECONDS}}}
    return built_once(tmp_path_factory, "sent-line-on",
                      lambda folder: _build_sent(folder, settings, True, "deck.html")) / "deck.html"


@pytest.fixture(scope="module")
def line_served(tmp_path_factory) -> Path:
    """The deck with the line on and no bundle, so Send posts to obs-html serve."""
    settings = {"artifact": {"reading": {"briefNoticeMilliseconds": BRIEF_MILLISECONDS}}}
    return built_once(tmp_path_factory, "sent-line-served",
                      lambda folder: _build_sent(folder, settings, False, "deck.html")) / "deck.html"


@pytest.fixture(scope="module")
def line_absent(tmp_path_factory) -> Path:
    """The deck with the named sink and without the setting."""
    return built_once(tmp_path_factory, "sent-line-absent",
                      lambda folder: _build_sent(folder, None, True, "deck.html")) / "deck.html"


@pytest.fixture(scope="module")
def line_zero(tmp_path_factory) -> Path:
    """The deck with the named sink and the setting's default, 0, given."""
    settings = {"artifact": {"reading": {"briefNoticeMilliseconds": 0}}}
    return built_once(tmp_path_factory, "sent-line-zero",
                      lambda folder: _build_sent(folder, settings, True, "deck.html")) / "deck.html"


def _open_deck(reader_browser, url: str, viewport: dict):
    page = reader_browser.new_page(viewport=viewport)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{url}#one")
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    return page, errors


def _send_a_verdict(page) -> None:
    page.locator('[data-bless-key="bless"]').click()
    page.locator("[data-bless-send]").click()


@pytest.mark.parametrize("viewport", SENT_VIEWPORTS, ids=["phone", "desktop"])
def test_a_confirmed_send_shows_the_sinks_name_under_the_band_and_the_line_goes(
        line_on: Path, reader_browser, viewport: dict) -> None:
    """Requirements 1, 3 and 6: after Send the line says where the answers went, under the band and
    no wider than its content, in the viewport; it moves no control of the band and goes after its
    time; the entry says the same in plain words, without the file or the sink's id."""
    from playwright.sync_api import expect

    page, errors = _open_deck(reader_browser, line_on.as_uri(), viewport)
    _send_a_verdict(page)
    line = page.locator("[data-brief-notice]")
    expect(line).to_have_text("Sent to Claude.")
    expect(line).to_have_attribute("role", "status")
    expect(line).to_have_attribute("data-transient-view", "")
    keep_screenshot(page, f"sent-line-{viewport['width']}-shown")
    box = page.evaluate(LINE_BOX)
    assert box["top"] >= box["bandBottom"] - 0.5 and box["bottom"] <= box["height"] + 0.5, box
    assert abs(box["left"] - box["bandLeft"]) <= 0.5 and abs(box["right"] - box["bandRight"]) <= 0.5, box
    assert box["left"] >= 0 and box["right"] <= box["width"], box
    shown = page.evaluate(BAND_BOXES)
    assert page.evaluate(FADES) is True
    expect(line).to_be_hidden(timeout=BRIEF_MILLISECONDS + 2000)
    assert page.get_by_role("status").filter(has_text="Sent to Claude.").count() == 0
    keep_screenshot(page, f"sent-line-{viewport['width']}-gone")
    assert page.evaluate(BAND_BOXES) == shown
    entry = page.locator('[data-notice="bless-send"]')
    expect(entry.locator("[data-notice-details]")).to_have_text("1 verdict and 0 comments sent to Claude.",
                                                                  use_inner_text=False)
    assert "answers.json" not in entry.text_content() and SINK_ID not in entry.text_content()
    assert page.evaluate("() => globalThis.received.length") == 1
    assert errors == []


def test_a_new_line_replaces_the_shown_one_and_reduced_motion_drops_the_fade(line_on: Path, reader_browser) -> None:
    """Requirement 1: one line at a time, the new text restarting the time; with reduced motion it
    goes without the fade; it is never printed."""
    from playwright.sync_api import expect

    page, errors = _open_deck(reader_browser, line_on.as_uri(), SENT_VIEWPORTS[0])
    page.emulate_media(reduced_motion="reduce")
    page.evaluate("globalThis.obsNotices.brief('First.'); globalThis.obsNotices.brief('Second.')")
    line = page.locator("[data-brief-notice]")
    assert line.count() == 1
    expect(line).to_have_text("Second.")
    page.emulate_media(media="print", reduced_motion="reduce")
    expect(line).to_be_hidden()
    page.emulate_media(media="screen", reduced_motion="reduce")
    expect(line).to_be_visible()
    assert page.evaluate(FADES) is False
    expect(line).to_be_hidden()
    assert errors == []


def test_in_a_figure_overlay_the_line_shows_with_the_notice_icons(line_on: Path, reader_browser) -> None:
    """Requirement 1: where a figure overlay holds the notice icons, the line shows there with them."""
    from playwright.sync_api import expect

    page, errors = _open_deck(reader_browser, line_on.as_uri(), SENT_VIEWPORTS[0])
    page.locator("[data-chapter-body] .figure-expand").first.click()
    overlay = page.locator("dialog.figure-overlay")
    expect(overlay).to_be_visible()
    page.evaluate("globalThis.obsNotices.brief('Shown in the overlay.')")
    line = overlay.locator("[data-brief-notice]")
    expect(line).to_be_visible()
    box = line.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 390 and box["y"] >= 0 and box["y"] + box["height"] <= 844
    assert errors == []


def test_through_obs_html_serve_the_line_says_sent(line_served: Path, reader_browser, tmp_path: Path) -> None:
    """Requirements 3 and 6: the local server gives no name, so the line and the entry name no place."""
    import serving
    from playwright.sync_api import expect

    artifact = tmp_path / "deck.html"
    artifact.write_bytes(line_served.read_bytes())
    served = serving.started(artifact)
    try:
        page, errors = _open_deck(reader_browser, served.url, SENT_VIEWPORTS[0])
        _send_a_verdict(page)
        expect(page.locator("[data-brief-notice]")).to_have_text("Sent.")
        entry = page.locator('[data-notice="bless-send"] [data-notice-details]')
        expect(entry).to_have_text("1 verdict and 0 comments sent.", use_inner_text=False)
    finally:
        served.stop()
    assert (tmp_path / "answers.json").exists()
    assert errors == []


@pytest.mark.parametrize("built", ["line_absent", "line_zero"], ids=["absent", "zero"])
def test_with_the_default_no_line_shows_and_the_entry_says_what_was_sent(request, reader_browser, built: str) -> None:
    """Requirement 2: with the default the line is off and no part of the page (features.py, the bless
    feature's part brief-notice): obsNotices.brief is absent, Send raises no page error and the entry
    alone says what was sent, in plain words."""
    from playwright.sync_api import expect

    page, errors = _open_deck(reader_browser, request.getfixturevalue(built).as_uri(), SENT_VIEWPORTS[0])
    assert page.evaluate("() => 'brief' in globalThis.obsNotices || 'obsNoticeBrief' in globalThis") is False
    _send_a_verdict(page)
    entry = page.locator('[data-notice="bless-send"] [data-notice-details]')
    expect(entry).to_have_text("1 verdict and 0 comments sent to Claude.", use_inner_text=False)
    assert page.locator("[data-brief-notice]").count() == 0
    assert errors == []
