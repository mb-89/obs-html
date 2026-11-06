"""Decision figures on a phone: rows over columns, letters as keys, a chapter's sections as tabs
(pugh-figure.js; artifact-ui.md, Decision figures; obs input-model, Pugh decision figures).

Reader: whoever changes how a decision figure is laid out at a narrow width, or what its tabs hold.

The artifact is the phone deck (fixtures/phone-deck), built through the core once per run: a
chapter whose figure has three options and two ``##`` sections after it, and one of five
options. The pages are phones in Playwright's emulation (touch, a mobile viewport, a phone's device
scale; conftest.py, PHONE_CONTEXT) at 360 and 390 px.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT, built_once
from obs_html import cli

pytestmark = pytest.mark.browser
DECK = ROOT / "test" / "fixtures" / "phone-deck" / "manifest.md"
THREE, FIVE = "three--figure-1", "five--figure-1"
WIDTHS = (360, 390)


def details(anchor: str) -> str:
    """Where a decision chapter's figure draws its tabs: the chapter's Details (artifact-ui.md, Decision figures)."""
    return f'[data-pugh-details="{anchor}"]'


@pytest.fixture(scope="module")
def deck(tmp_path_factory) -> Path:
    def build(folder: Path) -> None:
        subprocess.run([sys.executable, "-m", "obs.document", "--source", str(DECK),
                        "--document", str(folder / "deck.json")], check=True)
        assert cli.main([str(folder / "deck.json"), str(folder / "deck.html")]) == 0

    return built_once(tmp_path_factory, "phone-deck", build) / "deck.html"


def _open(browser, deck: Path, width: int, chapter: str):
    page = browser.new_page(viewport={"width": width, "height": 780})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(deck.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate(f"obsArtifact.activateChapter('{chapter}')")
    page.wait_for_selector(f"#{chapter}--figure-1.figure-pugh-ready")
    return page, errors


LAYOUT = """anchor => {
    const figure = document.getElementById(anchor), width = innerWidth;
    const parts = [figure, document.querySelector(`[data-pugh-details="${anchor}"]`)];
    const all = selector => parts.flatMap(part => [...part.querySelectorAll(selector)]);
    const shown = node => node.getClientRects().length > 0;
    const keys = all('button, input').filter(shown);
    const outside = keys.filter(key => { const box = key.getBoundingClientRect(); return box.left < -0.5 || box.right > width + 0.5; });
    const covered = keys.filter(key => {
        key.scrollIntoView({block: 'center', inline: 'nearest'});
        const box = key.getBoundingClientRect(), hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
        return !(hit && (hit === key || key.contains(hit)));
    });
    scrollTo(0, 0);
    const sideways = all('*').filter(node => node.scrollWidth > node.clientWidth + 1
        && ['auto', 'scroll'].includes(getComputedStyle(node).overflowX));
    const describe = node => node.dataset.pughMark || node.dataset.pughStep || node.dataset.pughTab || node.className || node.tagName;
    return {page: document.scrollingElement.scrollWidth, width, form: all('[data-pugh-form]')[0]?.dataset.pughForm,
            outside: outside.map(describe), covered: covered.map(describe), sideways: sideways.map(describe),
            mobile: matchMedia('(pointer: coarse)').matches && devicePixelRatio > 1,
            heads: all('[data-pugh-form] [data-pugh-head]').map(node => node.textContent.trim()),
            names: all('[data-pugh-form="rows"] .pugh-column-name').length,
            tabs: all('[data-pugh-tab]').map(tab => tab.querySelector('.tab-label').textContent),
            order: [...figure.querySelector('.pugh-figure-view').children].map(part => part.dataset.pughPart),
            details: [...parts[1].querySelector('.pugh-figure-view').children].slice(0, 1).map(part => part.dataset.pughPart),
            counts: all('[data-pugh-form="rows"] [data-pugh-texts] [data-pugh-count]').map(count =>
                `${count.closest('[data-pugh-texts]').dataset.pughTexts} ${count.dataset.pughCount} ${count.textContent.trim()}`),
            lines: all('.pugh-row-cells').map(cells =>
                new Set([...cells.children].map(cell => Math.round(cell.getBoundingClientRect().bottom))).size)};
}"""


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("anchor", [THREE, FIVE])
def test_on_a_phone_the_matrix_is_rows_of_letters_and_nothing_scrolls_sideways(phone_browser, deck, width, anchor):
    page, errors = _open(phone_browser, deck, width, anchor.split("--")[0])

    layout = page.evaluate(LAYOUT, anchor)
    letters = ["A", "B", "C"] if anchor == THREE else ["A", "B", "C", "D", "E"]

    assert layout["mobile"]
    assert layout["form"] == "rows"
    assert layout["page"] <= layout["width"] == width
    assert layout["sideways"] == [] and layout["outside"] == [] and layout["covered"] == []
    # Every option is its letter: a head per option and criterion line, no option name in the rows.
    assert layout["heads"][:len(letters)] == letters and set(layout["heads"]) == set(letters)
    assert layout["names"] == 0
    # Up to five options, the stepper and the cells of each line share one line.
    assert layout["lines"] and set(layout["lines"]) == {1}
    # Potential solutions, then Details: the order and the Wins and Losses counts are the table's (artifact-ui.md,
    # Decision figures on a phone); a count counts the option's own texts and its arguments.
    assert layout["order"] == ["options"]
    assert layout["details"] == ["tabs"]
    assert layout["counts"] == ["wins B 2", "losses A 1", "losses C 2"] if anchor == THREE else layout["counts"]
    # Without sections after the figure, the figure has its four tabs only.
    assert anchor == THREE or layout["tabs"] == ["Matrix", "Checklist", "Sensitivity", "Pareto"]
    assert errors == []


# What a tab shows on a phone (artifact-ui.md, Decision figures on a phone): nothing scrolls sideways,
# and the Sensitivity grid is one block per option, its letter, then a line per criterion.
TAB = """anchor => {
    const panel = document.querySelector(`[data-pugh-details="${anchor}"] [role="tabpanel"]:not([hidden])`);
    const outside = [...panel.querySelectorAll('*')].filter(node => node.getClientRects().length
        && (node.getBoundingClientRect().left < -0.5 || node.getBoundingClientRect().right > innerWidth + 0.5));
    return {page: document.scrollingElement.scrollWidth, outside: outside.map(node => node.className.baseVal ?? node.className),
            sideways: [...panel.querySelectorAll('*')].filter(node => node.scrollWidth > node.clientWidth + 1
                && ['auto', 'scroll'].includes(getComputedStyle(node).overflowX)).length,
            grid: panel.querySelector('[data-pugh-grid]')?.dataset.pughGrid ?? null,
            blocks: [...panel.querySelectorAll('[data-pugh-block]')].map(block => [block.dataset.pughBlock,
                block.querySelector('[data-pugh-column]').textContent.trim().slice(0, 1), block.querySelectorAll('.pugh-grid-line').length]),
            lines: panel.querySelectorAll('polyline[data-pugh-line]').length};
}"""


@pytest.mark.parametrize("width", WIDTHS)
def test_on_a_phone_the_sensitivity_grid_is_a_block_per_option_and_both_tabs_fit(phone_browser, deck, width):
    page, errors = _open(phone_browser, deck, width, "five")
    figure = page.locator(details(FIVE))
    criteria = figure.locator("[data-pugh-form] [data-pugh-criterion]").count()

    figure.locator('[data-pugh-tab="sensitivity"]').tap()
    sensitivity = page.evaluate(TAB, FIVE)
    figure.locator('[data-pugh-cell]').first.tap()
    ruling = figure.locator("[data-pugh-ruling-for]").count()
    figure.locator('[data-pugh-tab="pareto"]').tap()
    pareto = page.evaluate(TAB, FIVE)

    for tab in (sensitivity, pareto):
        assert tab["page"] <= width and tab["outside"] == [] and tab["sideways"] == 0
    blocks = sensitivity["blocks"]
    assert sensitivity["grid"] == "blocks" and len(blocks) == 4 and ruling == 1
    assert all(letter == head for letter, head, _ in blocks) and {lines for *_, lines in blocks} == {criteria}
    assert pareto["lines"] == 5
    assert errors == []


@pytest.mark.parametrize("width", WIDTHS)
def test_on_a_phone_a_mark_a_weight_and_a_pick_take_one_tap_each(phone_browser, deck, width):
    page, errors = _open(phone_browser, deck, width, "three")
    figure, matrix = page.locator(f"#{THREE}"), page.locator(details(THREE))

    matrix.locator('[data-pugh-mark="C:readable"] .pugh-mark-button').tap()
    matrix.locator('[data-pugh-mark="C:readable"] [data-pugh-choice="2"]').tap()
    matrix.locator('[data-pugh-step="effort:+"]').tap()
    figure.locator('[data-pugh-pick="C"]').tap()
    state = page.evaluate("obsPugh.readerState()")[THREE]
    picked = page.evaluate("obsBless.verdicts()")
    radios = f"Object.fromEntries([...document.querySelectorAll('#{THREE} [data-pugh-pick]')].map(radio => [radio.value, radio.checked]))"
    shown = page.evaluate(radios)
    figure.locator('[data-pugh-pick="none"]').tap()
    none = (page.evaluate(f"obsBless.picked('{THREE}')"), page.evaluate(radios)["none"])
    figure.locator('[data-pugh-pick="none"]').tap()
    cleared = (page.evaluate(f"obsBless.picked('{THREE}')"), page.evaluate(radios))

    assert state["marks"] == {"C": {"readable": 2}} and state["weights"] == {"effort": 1.5}
    # The options list's radios, one per option and None of the above: the band's pick state (artifact-ui.md, Decision figures).
    assert picked["three"]["pick"] == {"figure": THREE, "option": "C"}
    assert shown == {"A": False, "B": False, "C": True, "none": False}
    assert none == ("none", True)
    # The active pick, chosen again, clears to pending.
    assert cleared == (None, {"A": False, "B": False, "C": False, "none": False})
    assert sorted(matrix.locator(".pugh-changed").evaluate_all("nodes => nodes.map(n => n.dataset.pughMark || n.dataset.pughWeight)")) \
        == ["C:readable", "effort"]
    assert errors == []


@pytest.mark.parametrize("width", WIDTHS)
def test_a_chapters_sections_after_the_figure_are_its_tabs(phone_browser, deck, width):
    page, errors = _open(phone_browser, deck, width, "three")
    figure = page.locator(details(THREE))

    tabs = figure.locator("[data-pugh-tab]").evaluate_all("tabs => tabs.map(tab => tab.querySelector('.tab-label').textContent)")
    below = page.evaluate("""anchor => [...document.querySelector('[data-active-chapter] .chapter-body, .chapter-body').querySelectorAll('*')]
        .filter(node => !node.closest(`#${anchor}, [data-pugh-details="${anchor}"]`) && node.childElementCount === 0 && /record of earlier verdicts/.test(node.textContent))
        .length""", THREE)
    figure.locator('[data-pugh-tab="extra-1"]').tap()
    shown = figure.locator('[role="tabpanel"]:not([hidden])').inner_text()
    layout = page.evaluate(LAYOUT, THREE)
    page.set_viewport_size({"width": 1200, "height": 900})
    wide = figure.locator('[role="tabpanel"]:not([hidden])').inner_text()

    assert tabs == ["Matrix", "Checklist", "Sensitivity", "Pareto", "The record", "Earlier attempts"]
    assert below == 0
    assert "record of earlier verdicts" in shown and "Kept answers" in shown and "comment export was tried" not in shown
    assert layout["page"] <= width and layout["outside"] == [] and layout["sideways"] == []
    assert wide == shown
    assert errors == []


def test_a_link_to_a_section_in_a_tab_opens_the_tab_at_it_and_the_contents_lists_it(phone_browser, deck):
    page, errors = _open(phone_browser, deck, 390, "five")
    contents = page.evaluate("""[...document.querySelectorAll('a[href^="#three/"]')].map(link => [link.textContent.trim(), link.getAttribute('href')])""")

    page.evaluate("obsArtifact.activateChapter('three/the-record')")
    page.wait_for_selector(f"#{THREE}.figure-pugh-ready")
    shown = page.evaluate("""() => { const section = document.getElementById('three--the-record'), box = section.getBoundingClientRect();
        return {tab: document.querySelector('[data-pugh-tab][aria-selected="true"]').dataset.pughTab,
                hidden: section.hidden, top: box.top, bottom: box.bottom, height: innerHeight}; }""")

    # The heading stays in the chapter's contents, and the one link-following path opens its tab.
    assert ["The record", "#three/the-record"] in contents and ["Earlier attempts", "#three/earlier-attempts"] in contents
    assert shown["tab"] == "extra-1"
    assert shown["hidden"] is False and 0 <= shown["top"] < shown["height"] and shown["bottom"] > shown["top"]
    assert errors == []


@pytest.mark.parametrize("width", WIDTHS)
def test_on_a_phone_tapping_a_letter_shows_the_options_name_and_sentence(phone_browser, deck, width):
    page, errors = _open(phone_browser, deck, width, "three")
    head = page.locator(f'{details(THREE)} [data-pugh-mark="B:places"] [data-pugh-head]')
    card = "#hover-card"
    shown = f"(() => {{ const node = document.querySelector('{card}'); return Boolean(node && !node.hidden && node.getClientRects().length); }})()"

    head.tap()
    page.wait_for_selector(f"{card}:not([hidden])")
    text = page.locator(card).inner_text()
    described = head.evaluate("node => node.getAttribute('aria-describedby')")
    box, viewport = page.locator(card).bounding_box(), page.viewport_size
    page.locator("[data-chapter-body] h1").tap()
    elsewhere = page.evaluate(shown)

    # The letter's card is the artifact's hover card (artifact-ui.md, Overlays), the letter's description.
    assert described == card[1:]
    # The label "Answered artifact" says no more than the short name "Artifact", so it is not shown.
    assert "B · Artifact" in text and "Answered artifact" not in text and "obs-document --answers builds the artifact" in text
    assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"]
    assert elsewhere is False
    assert page.evaluate("document.querySelectorAll('dialog[open]').length") == 0
    assert errors == []


def test_where_there_is_room_an_option_reads_as_its_letter_and_short_name(phone_browser, deck):
    page, errors = _open(phone_browser, deck, 1200, "three")
    figure, matrix = page.locator(f"#{THREE}"), page.locator(details(THREE))

    heads = matrix.locator("thead [data-pugh-option]").evaluate_all(
        "cells => cells.map(cell => cell.querySelector('.pugh-column-name')?.textContent ?? '')")
    said = page.locator(f'[data-pugh-proposed="{THREE}"] [data-pugh-part="statement"]').inner_text()
    listed = figure.locator(".pugh-option-list summary").first.inner_text()
    matrix.locator('[data-pugh-tab="sensitivity"]').click()
    share = matrix.locator("[data-pugh-share]").inner_text()
    page.evaluate("obsArtifact.activateChapter('five')")
    page.wait_for_selector(f"#{FIVE}.figure-pugh-ready")
    five = page.locator(f"{details(FIVE)} thead [data-pugh-option]").evaluate_all(
        "cells => cells.map(cell => cell.querySelector('.pugh-column-name')?.textContent ?? '')")

    # A short name is the fence's short, else a label of at most 5 words; a longer label leaves the letter alone.
    assert heads == ["Comment export", "Artifact", "Answers file alone"]
    assert "for B · Artifact" in said and "A · Comment export" in said
    assert listed == "A · Comment export"
    assert share.startswith("B · Artifact wins ")
    assert five[3] == "" and five[1] == "An object bucket"
    assert errors == []


# The table's rows, heads and columns (artifact-ui.md, The decision matrix).
MATRIX = """anchor => {
    const table = document.querySelector(`[data-pugh-details="${anchor}"] .pugh-matrix`), box = node => node.getBoundingClientRect();
    // Its text's lines: the text's boxes, those whose middles lie within 8 px of each other one line.
    const lines = node => { const range = document.createRange(); range.selectNodeContents(node);
        const middles = [...range.getClientRects()].filter(rect => rect.width > 0).map(rect => rect.top + rect.height / 2).sort((a, b) => a - b);
        return middles.filter((middle, index) => !index || middle - middles[index - 1] > 8).length; };
    const names = [...table.querySelectorAll('tbody th.pugh-criterion')];
    const heads = [...table.querySelectorAll('thead [data-pugh-option]')];
    return {heights: [...table.querySelectorAll('tbody tr')].map(row => Math.round(box(row).height)),
            names: names.map(name => [name.textContent, name.scrollWidth <= name.clientWidth + 1 && lines(name) === 1]),
            heads: heads.map(head => lines(head.querySelector('[data-pugh-head]') || head)),
            criterion: box(names[0]).width, options: heads.map(head => box(head).width)};
}"""


def test_at_1100_px_criteria_read_in_full_options_are_narrow_and_every_row_is_one_line(reader_browser, deck):
    page, errors = _open(reader_browser, deck, 1100, "three")

    matrix = page.evaluate(MATRIX, THREE)

    # Every criterion name in full, on one line ("Readable as the decision it answers").
    assert [name for name, _ in matrix["names"]][:3] == [
        "Places that hold the verdict", "Readable as the decision it answers", "Effort for the reader"]
    assert all(full for _, full in matrix["names"])
    # One line each: every data row of one height, and each option's head one line.
    assert len(set(matrix["heights"])) == 1 and set(matrix["heads"]) == {1}
    # The criterion column takes the free width; the option columns are narrow.
    assert all(matrix["criterion"] > 1.5 * width for width in matrix["options"])
    assert errors == []


def test_the_readers_changes_survive_a_resize_between_the_table_and_the_rows(phone_browser, deck):
    page, errors = _open(phone_browser, deck, 1200, "three")
    figure = page.locator(details(THREE))
    form = f"document.querySelector('{details(THREE)} [data-pugh-form]').dataset.pughForm"

    wide = page.evaluate(form)
    field = figure.locator('[data-pugh-weight="places"]')
    field.fill("1")
    field.press("Enter")
    page.set_viewport_size({"width": 360, "height": 780})
    page.wait_for_function(f"{form} === 'rows'")
    narrow = page.evaluate(f"""() => ({{weight: document.querySelector('{details(THREE)} [data-pugh-weight="places"]').textContent,
        winner: document.getElementById('{THREE}').dataset.pughWinner}})""")
    figure.locator('[data-pugh-mark="B:effort"] .pugh-mark-button').tap()
    figure.locator('[data-pugh-mark="B:effort"] [data-pugh-choice="-2"]').tap()
    page.set_viewport_size({"width": 1200, "height": 900})
    page.wait_for_function(f"{form} === 'table'")
    back = page.evaluate(f"""() => ({{weight: document.querySelector('{details(THREE)} [data-pugh-weight="places"]').value,
        mark: document.querySelector('{details(THREE)} [data-pugh-mark="B:effort"]').textContent}})""")

    assert wide == "table"
    assert narrow["weight"] == "1"
    assert back == {"weight": "1", "mark": "−−"}
    assert page.evaluate("obsPugh.readerState()")[THREE]["weights"] == {"places": 1}
    assert errors == []


# What a walk arrow lies over in the active chapter's screen (artifact-ui.md, Screens): each text and
# matrix element sampled at its start, middle and end on its middle line, and the side gutters
# beside the text, where the arrows float, every 40 px down the screen; each point where the
# topmost element is an arrow is named.
UNDER_ARROWS = """() => {
    const body = document.querySelector('[data-active-chapter] .chapter-body');
    const arrow = (x, y) => document.elementFromPoint(x, y)?.closest('.chapter-nav-zone');
    const shown = node => node.getClientRects().length > 0;
    const leaves = [...body.querySelectorAll('h1, h2, h3, p, li, dt, dd, th, td, button, [data-pugh-head], [data-pugh-mark]')]
        .filter(node => shown(node) && node.textContent.trim());
    const text = leaves.filter(node => {
        const box = node.getBoundingClientRect(), y = box.top + box.height / 2;
        return y > 0 && y < innerHeight && [box.left + 1, box.left + box.width / 2, box.right - 1].some(x => arrow(x, y));
    }).map(node => node.dataset.pughMark || node.dataset.pughHead || node.textContent.trim().slice(0, 30));
    const top = body.closest('[data-chapter-scroll]').getBoundingClientRect().top, gutters = [];
    for (let y = top + 20; y < innerHeight; y += 40) for (const x of [4, innerWidth - 4]) if (arrow(x, y)) gutters.push(`gutter ${x},${Math.round(y)}`);
    return [...text, ...gutters];
}"""


def test_in_screens_on_a_phone_no_walk_arrow_lies_over_the_screen(phone_browser, deck):
    page, errors = _open(phone_browser, deck, 390, "three")
    scroll = "document.querySelector('[data-active-chapter] .chapter-body').closest('[data-chapter-scroll]')"
    covered = []
    for top in range(0, page.evaluate(f"{scroll}.scrollHeight"), 600):
        page.evaluate(f"{scroll}.scrollTo(0, {top})")
        covered += page.evaluate(UNDER_ARROWS)
    margins = page.evaluate("getComputedStyle(document.querySelector('[data-active-chapter] .chapter-body')).paddingInline")

    assert page.evaluate("document.documentElement.classList.contains('screens-mode')")
    assert covered == []
    # The gutter the arrows held goes to the content: a text margin is left on each side.
    assert margins == "12px"
    assert errors == []


def test_with_a_mouse_the_walk_arrows_stay_in_screens(reader_browser, deck):
    page, errors = _open(reader_browser, deck, 1200, "three")
    zones = page.evaluate("""() => [...document.querySelectorAll('.chapter-nav-zone')]
        .map(zone => Math.round(zone.getBoundingClientRect().width))""")
    margins = page.evaluate("getComputedStyle(document.querySelector('[data-active-chapter] .chapter-body')).paddingInline")

    assert page.evaluate("document.documentElement.classList.contains('screens-mode')")
    assert zones == [28, 28] and margins == "28px"
    assert errors == []


# Each option of the options list, expanded: its line, and the label and sentence it shows
# (artifact-ui.md, Decision figures).
LISTED = """anchor => [...document.querySelectorAll(`#${anchor} .pugh-option-list details`)].map(item => {
    item.open = true;
    const line = selector => { const node = item.querySelector(selector); return node && node.getClientRects().length ? node.textContent.trim() : null; };
    return {name: line('summary'), label: line('.pugh-option-label'), what: line('.pugh-option-what')};
})"""


@pytest.mark.parametrize("anchor, names", [
    (THREE, ["A · Comment export", "B · Artifact winner", "C · Answers file alone"]),
    (FIVE, ["A · A local disk", "B · An object bucket", "C · The repository winner", "D · A page of the team wiki",
            "E · Mail to the owner"])])
def test_the_options_list_says_each_name_once(phone_browser, deck, anchor, names):
    page, errors = _open(phone_browser, deck, 390, anchor.split("--")[0])

    listed = page.evaluate(LISTED, anchor)

    # Without a short name the line carries the label ("D · A page of the team wiki"), so no option
    # here says its label again inside.
    assert [item["name"] for item in listed] == names
    assert [item["label"] for item in listed] == [None] * len(names)
    assert all(item["what"] for item in listed)
    assert errors == []


# The options list, read through the print projection that shows it expanded, and each column head's hover
# card (artifact-ui.md, Decision figures): a label is said only where it adds words to the short name.
SAID = """async anchor => {
    const copy = document.getElementById(anchor).cloneNode(true), book = document.createElement('div');
    book.append(copy);
    await obsFigures.preparePrint(book);
    const texts = nodes => [...nodes].map(node => node.textContent.trim());
    const card = head => { const node = document.createElement('div'); obsPugh.hover(head).render(node); return texts(node.children); };
    return {list: texts(copy.querySelectorAll('.pugh-option-list summary')),
            abouts: [...document.querySelectorAll(`[data-pugh-details="${anchor}"] [data-pugh-form] [data-pugh-head]`)]
                .filter((head, index, heads) => heads.findIndex(other => other.dataset.pughHead === head.dataset.pughHead) === index).map(card)};
}"""


def test_the_options_list_and_the_popover_say_each_name_once(phone_browser, deck):
    page, errors = _open(phone_browser, deck, 390, "three")

    said = page.evaluate(SAID, THREE)

    assert said["list"] == ["A · Comment export", "B · Artifact winner", "C · Answers file alone"]
    assert said["abouts"] == [
        ["A · Comment export (the datum)", "A document-level comment in the comment export."],
        ["B · Artifact (the winner)", "obs-document --answers builds the artifact with the answers in it."],
        ["C · Answers file alone", "The answers.json the server writes."]]
    assert errors == []
