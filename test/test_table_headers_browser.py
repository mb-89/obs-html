"""Native-browser tier: a table's column headers sort and carry no hover help.

The owner is generic-tables.md (the sorting rules): a click on a header sorts, Shift-click adds or
reverses a further level, headers expose their sort state accessibly and carry no hover help, so a
tap on a phone sorts and opens no card. The card is the artifact's one hover card (artifact-ui.md,
Overlays); it shows a trigger's text after its configured delay.
"""
import json

import pytest

from artifacts import artifact_html
from documents import chapter, document as build, heading, node
from obs_html.config import load_config

pytestmark = pytest.mark.browser
CARD = "#hover-card"
HEADERS = "[data-active-chapter] thead th[data-column-key]"
ROWS = (("r1", "beta", 2), ("r2", "alpha", 2), ("r3", "gamma", 1))
TABLE = build(
    "Headers",
    chapter("register", "Register", heading(1, "Register"), node("bases", source="", spec={
        "filters": {"or": ['kind == "row"']},
        "views": [{"type": "table", "name": "Rows", "order": ["label", "rank"]}]})),
    records=tuple({"id": name, "type": "note", "path": f"{name}.md",
                   "fields": {"kind": "row", "label": label, "rank": rank}} for name, label, rank in ROWS))
# Past the card's delay: a timeout queued after a hover with this delay runs after the card's own.
SETTLED = "delay => new Promise(resolve => setTimeout(resolve, delay))"
CARD_SHOWN = f"(() => {{ const card = document.querySelector('{CARD}'); return !card.hidden; }})()"


@pytest.fixture(scope="module")
def artifact(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("table-headers") / "headers.html"
    path.write_text(artifact_html(TABLE), encoding="utf-8")
    return path.as_uri()


def _open(browser, artifact: str, viewport: dict):
    page = browser.new_page(viewport=viewport)
    page.set_default_timeout(5000)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact)
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate("obsPages.setPaged(false)")
    page.evaluate("obsArtifact.activateChapter('register')")
    page.locator("[data-active-chapter] .data-table-shell").wait_for()
    return page, errors


def _labels(page) -> list[str]:
    return page.locator("[data-active-chapter] tbody tr[data-row-key] td:first-child").all_inner_texts()


def _sorts(page) -> dict[str, str]:
    return dict(page.locator(HEADERS).evaluate_all(
        "cells => cells.map(cell => [cell.dataset.columnKey, cell.getAttribute('aria-sort')])"))


def _delay() -> int:
    return load_config().artifact["hoverCard"]["showDelayMilliseconds"]


def test_on_a_desktop_a_header_hover_shows_no_card_and_click_shift_click_and_enter_sort(reader_browser, artifact):
    page, errors = _open(reader_browser, artifact, {"width": 1280, "height": 900})
    helped = page.locator("[data-active-chapter] thead [data-hover-help]").count()
    label, rank = page.locator(f"{HEADERS}[data-column-key='label']"), page.locator(f"{HEADERS}[data-column-key='rank']")

    label.hover()
    page.evaluate(SETTLED, _delay())
    hovered = page.evaluate(CARD_SHOWN)
    label.click()
    by_label = _labels(page), _sorts(page)
    rank.click(modifiers=["Shift"])
    by_label_then_rank = _sorts(page)
    rank.click()
    by_rank = _labels(page), _sorts(page)
    rank.click(modifiers=["Shift"])
    reversed_rank = _labels(page), _sorts(page)
    label.press("Enter")
    by_key = _labels(page), _sorts(page)

    assert hovered is False
    assert helped == 0
    assert by_label == (["alpha", "beta", "gamma"], {"label": "ascending", "rank": "none"})
    assert by_label_then_rank == {"label": "ascending", "rank": "ascending"}
    # A plain click keeps only its column and turns its direction; equal ranks keep source order.
    assert by_rank == (["beta", "alpha", "gamma"], {"label": "none", "rank": "descending"})
    assert reversed_rank == (["gamma", "beta", "alpha"], {"label": "none", "rank": "ascending"})
    assert by_key == (["alpha", "beta", "gamma"], {"label": "ascending", "rank": "none"})
    assert errors == []


def test_on_a_phone_a_tap_on_a_header_sorts_and_opens_no_card(phone_browser, artifact):
    page, errors = _open(phone_browser, artifact, {"width": 390, "height": 844})
    header = page.locator(f"{HEADERS}[data-column-key='label']")

    header.tap()
    page.evaluate(SETTLED, _delay())
    tapped = page.evaluate(CARD_SHOWN), header.get_attribute("aria-describedby")
    sorted_once = _labels(page), _sorts(page)
    header.tap()
    page.evaluate(SETTLED, _delay())
    again = page.evaluate(CARD_SHOWN), _labels(page), _sorts(page)

    assert page.evaluate("matchMedia('(pointer: coarse)').matches") is True
    assert tapped == (False, None)
    assert page.locator("[data-active-chapter] thead [data-hover-help]").count() == 0
    assert sorted_once == (["alpha", "beta", "gamma"], {"label": "ascending", "rank": "none"})
    assert again == (False, ["gamma", "beta", "alpha"], {"label": "descending", "rank": "none"})
    assert errors == []
