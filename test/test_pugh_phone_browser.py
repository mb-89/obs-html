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
    const shown = node => node.getClientRects().length > 0;
    const keys = [...figure.querySelectorAll('button, input')].filter(shown);
    const outside = keys.filter(key => { const box = key.getBoundingClientRect(); return box.left < -0.5 || box.right > width + 0.5; });
    const covered = keys.filter(key => {
        key.scrollIntoView({block: 'center', inline: 'nearest'});
        const box = key.getBoundingClientRect(), hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
        return !(hit && (hit === key || key.contains(hit)));
    });
    scrollTo(0, 0);
    const sideways = [...figure.querySelectorAll('*')].filter(node => node.scrollWidth > node.clientWidth + 1
        && ['auto', 'scroll'].includes(getComputedStyle(node).overflowX));
    const describe = node => node.dataset.pughMark || node.dataset.pughStep || node.dataset.pughTab || node.className || node.tagName;
    return {page: document.scrollingElement.scrollWidth, width, form: figure.querySelector('[data-pugh-form]')?.dataset.pughForm,
            outside: outside.map(describe), covered: covered.map(describe), sideways: sideways.map(describe),
            mobile: matchMedia('(pointer: coarse)').matches && devicePixelRatio > 1,
            heads: [...figure.querySelectorAll('[data-pugh-form] [data-pugh-head]')].map(node => node.textContent.trim()),
            names: [...figure.querySelectorAll('[data-pugh-form="rows"] .pugh-column-name')].length,
            tabs: [...figure.querySelectorAll('[data-pugh-tab]')].map(tab => tab.textContent),
            lines: [...figure.querySelectorAll('.pugh-row-cells')].map(cells =>
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
    # Without sections after the figure, the figure has its three tabs only.
    assert anchor == THREE or layout["tabs"] == ["Matrix", "Checklist", "What if"]
    assert errors == []


@pytest.mark.parametrize("width", WIDTHS)
def test_on_a_phone_a_mark_a_weight_and_a_pick_take_one_tap_each(phone_browser, deck, width):
    page, errors = _open(phone_browser, deck, width, "three")
    figure = page.locator(f"#{THREE}")

    figure.locator('[data-pugh-mark="C:readable"] .pugh-mark-button').tap()
    figure.locator('[data-pugh-mark="C:readable"] [data-pugh-choice="2"]').tap()
    figure.locator('[data-pugh-step="effort:+"]').tap()
    figure.locator(f'[data-bless-column-pick="{THREE}:C"]').tap()
    state = page.evaluate("obsPugh.readerState()")[THREE]
    picked = page.evaluate("obsBless.verdicts()")

    assert state["marks"] == {"C": {"readable": 2}} and state["weights"] == {"effort": 1.5}
    assert picked["three"]["pick"] == {"figure": THREE, "option": "C"}
    assert sorted(figure.locator(".pugh-changed").evaluate_all("nodes => nodes.map(n => n.dataset.pughMark || n.dataset.pughWeight)")) \
        == ["C:readable", "effort"]
    assert errors == []


@pytest.mark.parametrize("width", WIDTHS)
def test_a_chapters_sections_after_the_figure_are_its_tabs(phone_browser, deck, width):
    page, errors = _open(phone_browser, deck, width, "three")
    figure = page.locator(f"#{THREE}")

    tabs = figure.locator("[data-pugh-tab]").evaluate_all("tabs => tabs.map(tab => tab.textContent)")
    below = page.evaluate("""anchor => [...document.querySelector('[data-active-chapter] .chapter-body, .chapter-body').querySelectorAll('*')]
        .filter(node => !node.closest(`#${anchor}`) && node.childElementCount === 0 && /record of earlier verdicts/.test(node.textContent))
        .length""", THREE)
    figure.locator('[data-pugh-tab="extra-1"]').tap()
    shown = figure.locator('[role="tabpanel"]:not([hidden])').inner_text()
    layout = page.evaluate(LAYOUT, THREE)
    page.set_viewport_size({"width": 1200, "height": 900})
    wide = figure.locator('[role="tabpanel"]:not([hidden])').inner_text()

    assert tabs == ["Matrix", "Checklist", "What if", "The record", "Earlier attempts"]
    assert below == 0
    assert "record of earlier verdicts" in shown and "Kept answers" in shown and "comment export was tried" not in shown
    assert layout["page"] <= width and layout["outside"] == [] and layout["sideways"] == []
    assert wide == shown
    assert errors == []


@pytest.mark.parametrize("width", WIDTHS)
def test_on_a_phone_tapping_a_letter_shows_the_options_label_and_sentence(phone_browser, deck, width):
    page, errors = _open(phone_browser, deck, width, "three")
    head = page.locator(f'#{THREE} [data-pugh-mark="B:places"] [data-pugh-head]')
    about = f"#{THREE}--pugh-about-B"
    shown = f"(selector => {{ const node = document.querySelector(selector); return node && !node.hidden && node.getClientRects().length > 0; }})"

    head.tap()
    opened = page.evaluate(f"{shown}('{about}')")
    text = page.locator(about).inner_text()
    described = head.evaluate("node => node.getAttribute('aria-describedby')")
    box, viewport = page.locator(about).bounding_box(), page.viewport_size
    head.tap()
    second = page.evaluate(f"{shown}('{about}')")
    head.tap()
    page.locator("[data-chapter-body] h1").tap()
    elsewhere = page.evaluate(f"{shown}('{about}')")

    assert opened and described == about[1:]
    assert "B" in text and "Answered artifact" in text and "obs-document --answers builds the artifact" in text
    assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"]
    assert second is False and elsewhere is False
    assert page.evaluate("document.querySelectorAll('dialog[open]').length") == 0
    assert errors == []


def test_where_there_is_room_an_option_reads_as_its_letter_and_short_name(phone_browser, deck):
    page, errors = _open(phone_browser, deck, 1200, "three")
    figure = page.locator(f"#{THREE}")

    heads = figure.locator("thead [data-pugh-option]").evaluate_all(
        "cells => cells.map(cell => cell.querySelector('.pugh-column-name')?.textContent ?? '')")
    bottom = figure.locator(".pugh-bottom").inner_text()
    card = figure.locator(".pugh-option-name").inner_text()
    figure.locator('[data-pugh-tab="whatif"]').click()
    worlds = figure.locator(".pugh-whatif").inner_text()
    page.evaluate("obsArtifact.activateChapter('five')")
    page.wait_for_selector(f"#{FIVE}.figure-pugh-ready")
    five = page.locator(f"#{FIVE} thead [data-pugh-option]").evaluate_all(
        "cells => cells.map(cell => cell.querySelector('.pugh-column-name')?.textContent ?? '')")

    # A short name is the fence's short, else a label of at most 5 words; a longer label leaves the letter alone.
    assert heads == ["Comment export", "Artifact", "Answers file alone"]
    assert "B · Artifact" in bottom and "A · Comment export" in bottom
    assert card == "A · Comment export"
    assert "B · Artifact wins unless" in worlds
    assert five[3] == "" and five[1] == "An object bucket"
    assert errors == []


def test_the_readers_changes_survive_a_resize_between_the_table_and_the_rows(phone_browser, deck):
    page, errors = _open(phone_browser, deck, 1200, "three")
    figure = page.locator(f"#{THREE}")
    form = f"document.querySelector('#{THREE} [data-pugh-form]').dataset.pughForm"

    wide = page.evaluate(form)
    field = figure.locator('[data-pugh-weight="places"]')
    field.fill("1")
    field.press("Enter")
    page.set_viewport_size({"width": 360, "height": 780})
    page.wait_for_function(f"{form} === 'rows'")
    narrow = page.evaluate(f"""() => ({{weight: document.querySelector('#{THREE} [data-pugh-weight="places"]').textContent,
        winner: document.getElementById('{THREE}').dataset.pughWinner}})""")
    figure.locator('[data-pugh-mark="B:effort"] .pugh-mark-button').tap()
    figure.locator('[data-pugh-mark="B:effort"] [data-pugh-choice="-2"]').tap()
    page.set_viewport_size({"width": 1200, "height": 900})
    page.wait_for_function(f"{form} === 'table'")
    back = page.evaluate(f"""() => ({{weight: document.querySelector('#{THREE} [data-pugh-weight="places"]').value,
        mark: document.querySelector('#{THREE} [data-pugh-mark="B:effort"]').textContent}})""")

    assert wide == "table"
    assert narrow["weight"] == "1"
    assert back == {"weight": "1", "mark": "−−"}
    assert page.evaluate("obsPugh.readerState()")[THREE]["weights"] == {"places": 1}
    assert errors == []
