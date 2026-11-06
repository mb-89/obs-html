"""Native-browser tier: bless verdicts in the top band, the swipe walk, Send and the screens the deck
opens in (bless.js, screens.js; artifact-ui.md, Bless verdicts, Screens and Reading shell;
spec/capabilities/bless.md).

Reader: whoever changes the verdict keys, Send, the answered record, the chapter swipe or screens.

The artifact is the example deck of obs's spec (spec/examples/bless-deck), built through the core
once per run: Home, then two chapters that ask for a bless, each with a decision figure, so it opens
in screens (artifact-ui.md, Screens: the default of a deck); the phone checks open it so, on a phone. Send posts
to the real obs-html serve (test/serving.py); the answers it writes build the answered deck, which
shows each verdict read-only.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import serving
from artifacts import artifact_html
from conftest import CORE_ROOT, built_once
from documents import chapter, document, heading, paragraph
from obs_html import cli

pytestmark = pytest.mark.browser
DECK = CORE_ROOT / "spec" / "examples" / "bless-deck" / "manifest.md"
ANSWERS_SCHEMA = CORE_ROOT / "src" / "obs" / "answers.schema.json"
FIGURE = "record--figure-1"
PHONE = {"width": 390, "height": 800}
PENDING = "Bless pending"


def _artifact(folder: Path, name: str, answers: Path | None = None) -> Path:
    """The deck's Document, as obs-document builds it (with ``answers``, --answers), and its artifact."""
    subprocess.run([sys.executable, "-m", "obs.document", "--source", str(DECK), "--document", str(folder / f"{name}.json"),
                    *(["--answers", str(answers)] if answers else [])], check=True)
    assert cli.main([str(folder / f"{name}.json"), str(folder / f"{name}.html")]) == 0
    return folder / f"{name}.html"


def _versions(folder: Path) -> dict[str, str]:
    document = json.loads((folder / "deck.json").read_text(encoding="utf-8"))
    return {chapter["id"]: chapter["bless"]["version"] for chapter in document["chapters"] if "bless" in chapter}


def _answers(versions: dict[str, str]) -> dict:
    """The verdicts the Send test gives, at the deck's versions."""
    return {"verdicts": [
        {"chapter": "record", "version": versions["record"], "verdict": "pick", "comment": "C needs no second place.",
         "pick": {"figure": FIGURE, "option": "C"},
         "figures": {FIGURE: {"weights": {"places": 1}, "marks": {}, "rulings": {}, "winner": "B"}}},
        {"chapter": "swipe", "version": versions["swipe"], "verdict": "bless"}]}


def _build(folder: Path) -> None:
    """The deck, and the deck built with the answers the Send test gives (obs-document --answers)."""
    _artifact(folder, "deck")
    (folder / "answers").mkdir()
    (folder / "answers" / "answers.json").write_text(json.dumps(_answers(_versions(folder))), encoding="utf-8")
    _artifact(folder, "answered", folder / "answers" / "answers.json")


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    return built_once(tmp_path_factory, "bless-deck", _build)


@pytest.fixture(scope="module")
def deck(built) -> Path:
    return built / "deck.html"


def _open(reader_browser, url: str, viewport: dict | None = None, chapter: str = "record"):
    page = reader_browser.new_page(viewport=viewport)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("dialog", lambda dialog: errors.append(f"dialog: {dialog.message}"))
    page.goto(f"{url}#{chapter}")
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate("obsPages.setPaged(false)")
    return page, errors


def _active(page) -> str:
    return page.locator("[data-active-chapter]").get_attribute("data-chapter")


# Each shown control of the top band: its name, its box and whether a pointer at its centre reaches it;
# the breadcrumbs' choosers (toggle) are small triangles, not squares.
BAND = """() => [...document.querySelectorAll(
        '.top-band a.chapter-home-link, .top-band button, .top-band [data-bless-pill], .top-band [data-screens-position], '
        + '.top-band summary.chapter-breadcrumb-toggle')]
    .filter(node => node.checkVisibility() && !node.closest('.notice-list, .bless-entry, .chapter-breadcrumb-menu'))
    .map(node => {
        const box = node.getBoundingClientRect(), hit = document.elementFromPoint(
            box.left + box.width / 2, box.top + box.height / 2);
        return {name: node.getAttribute('aria-label') || node.textContent.trim(), pill: node.matches('[data-bless-pill]'),
                toggle: node.matches('summary'),
                left: box.left, right: box.right, width: box.width, height: box.height,
                reached: Boolean(hit) && node.contains(hit)};
    })"""


def _fits(page) -> list[dict]:
    """No sideways page scroll, and every shown control of the band inside the viewport, reached by a
    pointer at its centre (none lies under another), and every control but the pill a square of one
    size; returns the controls."""
    controls = page.evaluate(BAND)
    width = page.evaluate("innerWidth")
    assert page.evaluate("document.documentElement.scrollWidth") == width
    assert [item["name"] for item in controls if item["left"] < -0.5 or item["right"] > width + 0.5
            or not item["reached"]] == []
    squares = {(round(item["width"]), round(item["height"])) for item in controls
               if not item["pill"] and not item["toggle"]}
    assert len(squares) == 1 and len({*squares.pop()}) == 1, controls
    return controls


SWIPE = """([selector, across]) => {
    const target = document.querySelector(selector), box = target.getBoundingClientRect();
    const x = box.left + box.width / 2, y = box.top + Math.min(box.height / 2, 20);
    const touch = (clientX) => new Touch({identifier: 1, target, clientX, clientY: y});
    const pointer = (type, clientX) => new PointerEvent(type, {pointerType: "touch", isPrimary: true, clientX, clientY: y,
        bubbles: true});
    target.dispatchEvent(pointer("pointerdown", x));
    target.dispatchEvent(new TouchEvent("touchstart", {touches: [touch(x)], changedTouches: [touch(x)], bubbles: true}));
    target.dispatchEvent(pointer("pointerup", x + across));
    target.dispatchEvent(new TouchEvent("touchend", {touches: [], changedTouches: [touch(x + across)], bubbles: true}));
}"""
"""A touch swipe of ``across`` pixels from the middle of the first ``selector``: its pointer and its touch events."""


def test_the_pill_and_keys_show_only_on_asking_chapters_and_the_page_fits_a_phone(deck, reader_browser) -> None:
    from playwright.sync_api import expect

    page, errors = _open(reader_browser, deck.as_uri(), PHONE)
    expect(page.locator("[data-bless-pill]")).to_have_text("Bless pending")
    assert page.locator("[data-bless-key]:visible").evaluate_all(
        "keys => keys.map(key => key.getAttribute('aria-label'))") == ["Bless", "Decline", "Ask", "Pick"]
    expect(page.locator("[data-bless-send]")).to_have_text("Send 0/2")
    expect(page.locator("[data-bless-send]")).to_be_disabled()
    _fits(page)

    page.evaluate("obsArtifact.activateChapter('home')")
    expect(page.locator("[data-bless-pill]")).to_be_hidden()
    expect(page.locator("[data-bless-key]:visible")).to_have_count(0)
    expect(page.locator("[data-bless-send]")).to_be_visible()
    _fits(page)
    assert errors == []


@pytest.mark.parametrize("width", [360, 390])
def test_the_band_holds_every_key_in_one_row_at_phone_width_with_the_notices_shown(deck, reader_browser,
                                                                                   width: int) -> None:
    """The band of a chapter with a decision figure, all three notice icons shown, as in a real deck."""
    page, errors = _open(reader_browser, deck.as_uri(), {"width": width, "height": 800})
    page.evaluate("""() => obsNotices.severities.forEach(severity =>
        obsNotices.post({id: severity, severity, title: severity}))""")
    names = [item["name"] for item in _fits(page)]
    assert names == ["Home", "Choose chapter", "Show frontmatter", "Chapter 1 of 2", PENDING, "Bless", "Decline", "Ask", "Pick", "Send 0 of 2 verdicts",
                     "Errors: 1 notice", "Warnings: 1 notice", "Information: 1 notice", "Open bars menu"]
    # Short of space, the breadcrumb has shrunk and the pill is a square of the band's size showing
    # only its state colour, its label its tooltip and accessible name.
    pill = page.locator("[data-bless-pill]")
    assert pill.get_attribute("title") == PENDING
    box, menu = pill.bounding_box(), page.locator("[data-menu-button]").bounding_box()
    assert (round(box["width"]), round(box["height"])) == (round(menu["width"]), round(menu["height"]))
    assert pill.evaluate("node => parseFloat(getComputedStyle(node).fontSize)") == 0
    assert errors == []


def test_the_pill_keeps_its_text_while_the_band_has_room(deck, reader_browser) -> None:
    """The breadcrumb shrinks first: on a wide band the pill shows its label."""
    page, errors = _open(reader_browser, deck.as_uri(), {"width": 1100, "height": 800})
    pill = page.locator("[data-bless-pill]")
    assert pill.evaluate(
        "node => node.scrollWidth <= node.clientWidth && parseFloat(getComputedStyle(node).fontSize) > 0")
    assert pill.bounding_box()["width"] > page.locator("[data-menu-button]").bounding_box()["width"] * 1.5
    _fits(page)
    assert errors == []


def test_decline_without_a_comment_cannot_be_sent_and_a_complete_verdict_opens_the_next(deck, reader_browser) -> None:
    from playwright.sync_api import expect

    page, errors = _open(reader_browser, deck.as_uri(), PHONE)
    page.locator('[data-bless-key="decline"]').click()
    comment = page.locator("[data-bless-comment]")
    expect(comment).to_be_focused()
    expect(page.locator("[data-bless-pill]")).to_have_text("Declined · needs a comment")
    expect(page.locator("[data-bless-send]")).to_be_disabled()
    _fits(page)
    comment.press("Enter")  # Without a comment nothing completes, and the chapter stays.
    assert _active(page) == "record" and page.evaluate("obsBless.payload()") == {"verdicts": []}

    comment.fill("It keeps the verdict in two places.")
    expect(page.locator("[data-bless-send]")).to_have_text("Send 1/2")
    expect(page.locator("[data-bless-send]")).to_be_enabled()
    comment.press("Enter")
    expect(page.locator("[data-active-chapter]")).to_have_attribute("data-chapter", "swipe")
    expect(page.locator("[data-bless-entry]")).to_be_hidden()
    assert errors == []


def test_a_swipe_walks_the_chapters_and_does_not_decide(deck, reader_browser) -> None:
    from playwright.sync_api import expect

    page, errors = _open(reader_browser, deck.as_uri(), PHONE)
    page.evaluate(SWIPE, ["[data-chapter-body] h1", -120])
    expect(page.locator("[data-active-chapter]")).to_have_attribute("data-chapter", "swipe")
    page.evaluate(SWIPE, ["[data-chapter-body] h1", 120])
    expect(page.locator("[data-active-chapter]")).to_have_attribute("data-chapter", "record")
    assert page.evaluate("obsBless.verdicts()") == {}
    expect(page.locator("[data-bless-pill]")).to_have_text("Bless pending")

    # A swipe that starts in a box that scrolls sideways stays with it. At this width the figure's
    # matrix is rows and scrolls no more (artifact-ui.md, Decision figures), so the box is built here.
    page.wait_for_selector(f"#{FIGURE}.figure-pugh-ready [data-pugh-form='rows']")
    assert page.evaluate("""() => {
        const box = Object.assign(document.createElement('div'), {className: 'swipe-box'});
        box.style.overflowX = 'auto';
        box.append(Object.assign(document.createElement('p'), {textContent: 'wide'}));
        box.firstChild.style.width = '200vw';
        document.querySelector('[data-active-chapter] [data-chapter-body], [data-chapter-body]').append(box);
        return box.scrollWidth > box.clientWidth;
    }""")
    page.evaluate(SWIPE, [".swipe-box p", -120])
    assert _active(page) == "record"
    assert errors == []


def test_send_hands_the_payload_with_the_weights_the_reader_set(built, reader_browser, tmp_path: Path) -> None:
    from playwright.sync_api import expect

    artifact = tmp_path / "deck.html"  # Served alone, so its answers.json is this test's.
    artifact.write_bytes((built / "deck.html").read_bytes())
    served = serving.started(artifact, "--wait", "--timeout", serving.WAIT)
    try:
        page, errors = _open(reader_browser, served.url)
        weight = page.locator(f'#{FIGURE} [data-pugh-weight="places"]')
        weight.fill("1")
        weight.dispatch_event("change")
        expect(page.locator(f"#{FIGURE}")).to_have_attribute("data-pugh-winner", "B")
        page.locator(f'#{FIGURE} [data-bless-column-pick="{FIGURE}:C"]').click()
        expect(page.locator("[data-bless-comment]")).to_be_focused()
        page.locator("[data-bless-comment]").fill("C needs no second place.")
        page.locator("[data-bless-comment]").press("Enter")
        expect(page.locator("[data-active-chapter]")).to_have_attribute("data-chapter", "swipe")
        page.locator('[data-bless-key="bless"]').click()
        expect(page.locator("[data-bless-send]")).to_have_text("Send 2/2")
        page.locator("[data-bless-send]").click()
        code, out, err = served.finished()
    finally:
        served.stop()
    assert code == 0, err
    payload = json.loads((tmp_path / "answers.json").read_text(encoding="utf-8"))
    assert json.loads(out.strip().splitlines()[-1]) == payload
    Draft202012Validator(json.loads(ANSWERS_SCHEMA.read_text(encoding="utf-8"))).validate(payload)
    assert payload == _answers(_versions(built))
    expect(page.locator("[data-bless-pill]")).to_have_text("Blessed · sent")
    assert errors == []


def test_the_answered_deck_shows_each_verdict_read_only(built, reader_browser) -> None:
    from playwright.sync_api import expect

    page, errors = _open(reader_browser, (built / "answered.html").as_uri())
    record = page.locator("[data-bless-record]")
    expect(record).to_have_attribute("data-bless-record", "answer")
    expect(record.locator("[data-bless-record-verdict]")).to_have_text("Picked C · Answers file alone")
    expect(record.locator("[data-bless-record-comment]")).to_have_text("C needs no second place.")
    expect(record).to_contain_text("Weight of Places that hold it: 1 (was 3)")
    expect(page.locator("[data-bless-pill]")).to_have_text("Picked C · Answers file alone · recorded")
    expect(page.locator("[data-bless-key]:visible")).to_have_count(0)
    expect(page.locator("[data-bless-send]")).to_be_hidden()
    expect(page.locator(f"#{FIGURE} [data-pugh-weight]")).to_have_count(0)  # The figure shows the answer read-only.
    expect(page.locator(f'#{FIGURE} [data-pugh-criterion="places"] .pugh-weight')).to_have_text("1")
    assert errors == []


# What the reader shows as a page: paper sheets, their running headers and footers, and the cover.
PAGE_FRAME = """() => [...document.querySelectorAll(
        '.paper-sheet, .paper-header, .paper-footer, .paper-page-number, .document-heading')]
    .filter(node => node.checkVisibility()).length"""


@pytest.mark.parametrize("width", [360, 390])
def test_the_deck_opens_in_screens_on_a_phone_that_fit_and_walk_by_swipe_and_keys(deck, phone_browser,
                                                                                  width: int) -> None:
    """artifact-ui.md, Screens: no sideways scroll, no page frame, the band's title and position, and the
    band fits (Reading shell, the top band); swipe and the keys walk, the arrows are hidden on touch, and
    Home has no cover."""
    from playwright.sync_api import expect

    page = phone_browser.new_page(viewport={"width": width, "height": 780})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{deck.as_uri()}#record")
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    assert page.evaluate("[matchMedia('(pointer: coarse)').matches, innerWidth]") == [True, width]
    assert page.evaluate("document.documentElement.className.split(' ').filter(name => name.endsWith('-mode'))") \
        == ["screens-mode"]
    position = page.locator("[data-screens-position]")
    expect(position).to_have_text("1 / 2")
    expect(page.locator("[data-screens-title]")).to_have_attribute("title", "Bless verdicts, two decisions")
    assert page.evaluate(PAGE_FRAME) == 0
    assert "Chapter 1 of 2" in [item["name"] for item in _fits(page)]
    # The chapter takes the reader's width; on touch the arrows are hidden.
    body = page.locator("[data-chapter-body]").bounding_box()
    assert body["width"] >= width - 2 * 32
    expect(page.locator("[data-step]")).to_have_count(2)
    assert page.locator("[data-step]").evaluate_all("steps => steps.filter(step => step.getClientRects().length)") == []

    page.evaluate(SWIPE, ["[data-chapter-body] h1", -120])
    expect(page.locator("[data-active-chapter]")).to_have_attribute("data-chapter", "swipe")
    expect(position).to_have_text("2 / 2")
    _fits(page)
    page.evaluate(SWIPE, ["[data-chapter-body] h1", 120])
    expect(page.locator("[data-active-chapter]")).to_have_attribute("data-chapter", "record")
    page.evaluate("obsArtifact.whenChapterReady()")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("[data-active-chapter]")).to_have_attribute("data-chapter", "home")
    expect(position).to_be_hidden()
    assert page.evaluate(PAGE_FRAME) == 0
    _fits(page)
    page.keyboard.press("ArrowRight")
    expect(position).to_have_text("1 / 2")
    assert errors == []


def test_printing_from_screens_prints_each_screen_from_a_new_page_without_a_page_frame(deck, reader_browser) -> None:
    """artifact-ui.md, Screens: the print projection holds Home without its cover, then each chapter
    from a new sheet, with no front pages, running header, footer or page number."""
    page, errors = _open(reader_browser, deck.as_uri(), PHONE)
    page.evaluate("dispatchEvent(new Event('beforeprint'))")
    sheets = page.evaluate("""() => [...document.querySelectorAll('.print-book > .paper-sheet')].map(sheet => ({
        chapter: sheet.dataset.pageChapter, id: sheet.id,
        frame: sheet.querySelectorAll('.paper-header, .paper-footer, .document-heading, .title-page').length}))""")
    page.evaluate("dispatchEvent(new Event('afterprint'))")
    assert [sheet["chapter"] for sheet in sheets if sheet["id"]] == ["home", "record", "swipe"]
    assert {sheet["frame"] for sheet in sheets} == {0}
    assert page.evaluate("document.documentElement.classList.contains('screens-mode')")
    assert errors == []


def _nested_deck() -> str:
    """A deck whose second chapter, with a decision figure, is a subchapter of the first: its
    breadcrumbs hold two choosers, Choose chapter and Choose subchapter."""
    decisions = json.loads((Path(__file__).parent / "fixtures" / "documents" / "pugh.json").read_text(encoding="utf-8"))
    figure = next(item for entry in decisions["chapters"] for item in entry["content"]
                  if item["type"] == "figures" and item["attrs"]["kind"] == "pugh")
    asks = {"obs": {"bless": "pending"}}
    source = document("Nested deck", chapter(
        "parent", "Parent decision", heading(1, "Parent decision"), paragraph("Bless this."), metadata=asks,
        children=(chapter("child", "Child decision", heading(1, "Child decision"), figure, metadata=asks),)))
    for entry in (source["chapters"][0], source["chapters"][0]["children"][0]):
        entry["bless"] = {"version": "0" * 64}
    return artifact_html(source)


def test_the_band_of_a_nested_bless_chapter_fits_at_360_px(phone_browser, tmp_path: Path) -> None:
    """Both breadcrumb choosers, the position, the pill and every key in one row, none under another."""
    from playwright.sync_api import expect

    (tmp_path / "nested.html").write_text(_nested_deck(), encoding="utf-8")
    page = phone_browser.new_page(viewport={"width": 360, "height": 780})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{(tmp_path / 'nested.html').as_uri()}#child")
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    expect(page.locator("[data-screens-position]")).to_have_text("2 / 2")
    names = [item["name"] for item in _fits(page)]
    assert names == ["Home", "Choose chapter", "Choose subchapter", "Show frontmatter", "Chapter 2 of 2", PENDING,
                     "Bless", "Decline", "Ask", "Pick", "Send 0 of 2 verdicts", "Open bars menu"]
    # A pick names its option by the figure's short name; the band still fits.
    page.locator('[data-bless-key="pick"]').click()
    page.locator("[data-bless-pick]").last.click()
    assert re.fullmatch(r"Picked [A-Z] · \S.* · needs a comment", page.locator("[data-bless-pill]").get_attribute("title"))
    _fits(page)
    assert errors == []


# What the pill shows: its parts on its one visible line (base.css, the pill), and its label.
PILL = """() => { const pill = document.querySelector('[data-bless-pill]'), box = pill.getBoundingClientRect();
    return {label: pill.title, shown: [...pill.children].filter(part => {
        const line = part.getBoundingClientRect();
        return line.width > 0 && line.bottom <= box.bottom + 0.5;
    }).map(part => part.textContent).join('')}; }"""
SHORT = "Picked C · Answers file alone"


@pytest.mark.parametrize(("width", "shown"), [(360, ""), (390, ""), (520, "Picked C"), (660, SHORT), (1100, SHORT)])
def test_the_pill_names_the_pick_by_its_short_name_where_the_band_has_room(deck, phone_browser, width: int,
                                                                         shown: str) -> None:
    """artifact-ui.md, Bless verdicts: "Picked C · <short name>" where the band has room; short of it,
    the details drop whole ("Picked C"), and on a phone's bless band the pill is a square, its label
    its tooltip. The short name is the decision figure's own (obsPugh.options)."""
    page = phone_browser.new_page(viewport={"width": width, "height": 780})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{deck.as_uri()}#record")
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.locator('[data-bless-key="pick"]').click()
    page.locator(f'[data-bless-pick="{FIGURE}:C"]').click()
    assert page.evaluate(PILL) == {"label": f"{SHORT} · needs a comment", "shown": shown}
    _fits(page)
    assert errors == []
