"""A decision chapter reads as its potential solutions, then its details (artifact-ui.md, Decision
figures; obs input-model, Pugh decision figures).

Reader: whoever changes what a decision page shows above its tabs, its Y-statement, its hovers or
its Pareto and Sensitivity framing.

The artifact is the phone deck (fixtures/phone-deck), built through the core once per run, as
test_pugh_phone_browser.py builds it: "three" has context, concern, success criteria and marks with
reasons, and two ``##`` sections after its figure; "five" is superseded, and one of its criteria's
labels starts with an acronym, another with a code span. Pages are a desktop reader
(1200 px) or an emulated phone (390 px, conftest.py, PHONE_CONTEXT).
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
CARD = "#hover-card"


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


def _card(page) -> str | None:
    """The hover card's text where it shows, else None."""
    return page.evaluate(f"""() => {{ const card = document.querySelector('{CARD}');
        return card && !card.hidden && card.getClientRects().length ? card.innerText.trim().replace(/\\n+/g, '\\n') : null; }}""")


# The chapter's headings in order, where the figure and its tabs sit, and the chapter's contents.
SECTIONS = """anchor => {
    const body = document.querySelector('[data-active-chapter] [data-chapter-body]');
    const figure = document.getElementById(anchor), details = document.querySelector(`[data-pugh-details="${anchor}"]`);
    const sectionOf = node => node?.closest('[data-heading-section]')?.dataset.headingSection ?? null;
    return {headings: [...body.querySelectorAll('h1, h2')].filter(node => !node.closest('.paged-reader'))
                .map(node => [node.tagName, node.textContent.trim(), Boolean(node.closest('.collapsible-heading'))]),
            figure: sectionOf(figure), tabs: sectionOf(details?.querySelector('[data-pugh-part="tabs"]')),
            options: Boolean(figure.querySelector('[data-pugh-part="options"]')),
            winnerLine: figure.querySelectorAll('.pugh-bottom, [data-pugh-part="winner"]').length,
            contents: [...document.querySelectorAll('a[href^="#three/"]')].map(link => [link.textContent.trim(),
                link.closest('[data-toc-children]')?.parentElement.querySelector('a')?.textContent.trim() ?? null])};
}"""


def test_a_decision_chapter_reads_potential_solutions_then_details(reader_browser, deck):
    page, errors = _open(reader_browser, deck, 1200, "three")

    sections = page.evaluate(SECTIONS, THREE)
    page.locator('[data-heading-section-target="three--details"]').click()
    folded = page.evaluate(f"""() => document.querySelector('[data-pugh-details="{THREE}"] [data-pugh-part="tabs"]')
        .getClientRects().length""")

    # The note's text, then the three sections the page draws, which fold like the note's own headings.
    assert [heading for heading in sections["headings"] if heading[0] == "H2"] == [
        ["H2", "Potential solutions", True], ["H2", "Proposed winner", True], ["H2", "Details", True]]
    assert sections["figure"] == "three--potential-solutions" and sections["options"]
    assert sections["tabs"] == "three--details"
    assert sections["winnerLine"] == 0
    # They stand in the chapter's contents; the sections after the figure, now tabs, under Details.
    assert ["Potential solutions", "Three options and the record"] in sections["contents"]
    assert ["Proposed winner", "Three options and the record"] in sections["contents"]
    assert ["Details", "Three options and the record"] in sections["contents"]
    assert ["The record", "Details"] in sections["contents"] and ["Earlier attempts", "Details"] in sections["contents"]
    assert folded == 0
    assert errors == []


# The options list: each row's letter, short name, radio and marks; then the Proposed winner box: the
# Y-statement and the success criterion.
SOLUTIONS = """anchor => {
    const figure = document.getElementById(anchor), list = figure.querySelector('[data-pugh-part="options"]');
    const box = document.querySelector(`[data-pugh-proposed="${anchor}"]`) ?? figure;
    return {rows: [...list.querySelectorAll('[data-pugh-option]')].map(row => ({option: row.dataset.pughOption,
                line: row.querySelector('summary, .pugh-none-line')?.textContent.trim().replace(/\\s+/g, ' '),
                radio: row.querySelector('input[type="radio"][data-pugh-pick]')?.value ?? null,
                checked: row.querySelector('[data-pugh-pick]')?.checked ?? null,
                tags: [...row.querySelectorAll('[data-pugh-tag]')].map(tag => tag.dataset.pughTag)})),
            statement: box.querySelector('[data-pugh-part="statement"]')?.textContent.trim(),
            success: box.querySelector('[data-pugh-part="success"]')?.textContent.trim() ?? null,
            inFigure: figure.querySelectorAll('[data-pugh-part="statement"], [data-pugh-part="proposed"]').length,
            matrixPicks: document.querySelectorAll(`[data-pugh-details="${anchor}"] [data-pugh-pick], #${anchor} .pugh-matrix [data-pugh-pick], #${anchor} [data-pugh-form] [data-pugh-pick]`).length};
}"""
STATEMENT = ("In the context of a deck read on phones, facing where a verdict is kept, we decided for B · Artifact "
             "and against A · Comment export and C · Answers file alone, to achieve readable as the decision it answers, "
             "places that hold the verdict and effort for the reader.")
SUCCESS_B = "Success criterion: The answers check refuses an artifact without its answers."
SUCCESS_C = "Success criterion: The server keeps every answers file it writes."


def test_the_options_list_carries_the_pick_the_winner_mark_and_the_y_statement(phone_browser, deck):
    page, errors = _open(phone_browser, deck, 390, "three")
    figure = page.locator(f"#{THREE}")

    shown = page.evaluate(SOLUTIONS, THREE)
    figure.locator('[data-pugh-option="C"] [data-pugh-pick]').tap()
    picked = page.evaluate(SOLUTIONS, THREE), page.evaluate(f"obsBless.picked('{THREE}')")
    page.evaluate(f"obsBless.pick('{THREE}', 'none')")  # The band's pick, as its Pick key gives it.
    none = page.evaluate(SOLUTIONS, THREE)
    figure.locator('[data-pugh-pick="none"]').tap()
    cleared = page.evaluate(SOLUTIONS, THREE), page.evaluate(f"obsBless.picked('{THREE}')")

    assert [row["option"] for row in shown["rows"]] == ["A", "B", "C", "none"]
    assert [row["line"] for row in shown["rows"]] == [
        "A · Comment export", "B · Artifact winner", "C · Answers file alone", "None of the above"]
    assert [row["radio"] for row in shown["rows"]] == ["A", "B", "C", "none"]
    assert [row["tags"] for row in shown["rows"]] == [[], ["winner"], [], []]
    assert shown["matrixPicks"] == 0
    assert shown["statement"] == STATEMENT
    assert shown["success"] == SUCCESS_B and shown["inFigure"] == 0
    # A pick is the band's pick; the sentence follows it; the band's pick checks its radio.
    assert picked[1] == "C" and [row["checked"] for row in picked[0]["rows"]] == [False, False, True, False]
    assert picked[0]["statement"] == (
        "In the context of a deck read on phones, facing where a verdict is kept, we decided for C · Answers file alone "
        "and against A · Comment export and B · Artifact, to achieve places that hold the verdict and effort for the reader, "
        "accepting readable as the decision it answers.")
    assert picked[0]["success"] == SUCCESS_C
    assert [row["checked"] for row in none["rows"]] == [False, False, False, True]
    assert none["statement"] == ("In the context of a deck read on phones, facing where a verdict is kept, we decided "
                                 "against all of A · Comment export, B · Artifact and C · Answers file alone.")
    assert none["success"] is None
    assert cleared[1] is None and not any(row["checked"] for row in cleared[0]["rows"])
    assert cleared[0]["statement"] == STATEMENT and cleared[0]["success"] == SUCCESS_B
    assert errors == []


def test_a_superseded_decision_says_so_at_its_top_and_its_statement_needs_no_context(reader_browser, deck):
    page, errors = _open(reader_browser, deck, 1200, "five")

    top = page.evaluate("""() => { const body = document.querySelector('[data-active-chapter] [data-chapter-body]');
        const note = body.querySelector('[data-pugh-superseded]'), heading = body.querySelector('h1');
        return {text: note?.textContent.trim(), after: Boolean(note && heading.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING),
                before: Boolean(note && [...body.querySelectorAll('p')].indexOf(note) === 0)}; }""")
    statement = page.locator(f'[data-pugh-proposed="{FIVE}"] [data-pugh-part="statement"]').inner_text()

    assert top == {"text": "Superseded by Decision 7, the deck moves to the wiki", "after": True, "before": True}
    assert statement.startswith("We decided for C · The repository and against ")
    # A label spliced in keeps its case where it starts with an acronym or a code span.
    assert statement.endswith(", to achieve `serve` reach from a phone and CI upkeep.")
    assert page.locator(f'[data-pugh-proposed="{FIVE}"] [data-pugh-part="success"]').count() == 0
    assert errors == []


def test_a_marks_reason_is_an_argument_in_the_hover_card_of_its_cell_and_its_count(reader_browser, deck):
    page, errors = _open(reader_browser, deck, 1200, "three")
    figure = page.locator(f"#{THREE}")
    details = page.locator(f'[data-pugh-details="{THREE}"]')

    def hover(selector: str) -> str | None:
        page.mouse.move(0, 0)
        page.keyboard.press("Escape")
        details.locator(selector).first.hover()
        page.wait_for_selector(f"{CARD}:not([hidden])", timeout=1500)
        return _card(page)

    good = hover('[data-pugh-mark="B:readable"]')
    neutral = hover('[data-pugh-mark="A:readable"]')
    bad = hover('[data-pugh-mark="C:readable"]')
    bare = details.locator('[data-pugh-mark="B:effort"]').first.evaluate(
        "cell => [cell, ...cell.querySelectorAll('*')].some(node => node.dataset.pughHover?.startsWith('mark'))")
    wins = hover('[data-pugh-texts="wins"] [data-pugh-count="B"]')
    losses = hover('[data-pugh-texts="losses"] [data-pugh-count="C"]')
    counts = details.locator("[data-pugh-count]").evaluate_all(
        "nodes => nodes.map(node => `${node.closest('[data-pugh-texts]').dataset.pughTexts} ${node.dataset.pughCount} ${node.textContent.trim()}`)")
    expander = figure.locator('[data-pugh-option="B"]').inner_text()

    assert good == "Good, because the verdict sits in the decision it answers."
    assert neutral == "Neutral, because it is where comments live today."
    assert bad == "Bad, because the file holds no decision."
    # A mark without a reason has no card.
    assert bare is False
    assert wins is not None and wins.splitlines() == [
        "B · Artifact · 2 wins", "The changed artifact is its own record.",
        "Readable as the decision it answers: Good, because the verdict sits in the decision it answers."]
    assert losses is not None and losses.splitlines() == [
        "C · Answers file alone · 2 losses", "Read without the decision it answers.",
        "Readable as the decision it answers: Bad, because the file holds no decision."]
    assert counts == ["wins B 2", "losses A 1", "losses C 2"]
    # The arguments are hovers only, not more text in the option's expander.
    assert "because" not in expander
    assert errors == []


# Where the hover card shows against the matrix: in the top layer, outside the figure, over the matrix and
# whole at each corner (nothing of the matrix clips or covers it), with no scroll bar.
OVER = """anchor => {
    const card = document.getElementById('hover-card'), box = document.querySelector(`[data-pugh-details="${anchor}"] [data-pugh-form]`);
    const a = card.getBoundingClientRect(), b = box.getBoundingClientRect();
    const scrolls = [...document.querySelectorAll(`[data-pugh-details="${anchor}"] *`)].filter(node =>
        node.scrollHeight > node.clientHeight + 1 && ['auto', 'scroll'].includes(getComputedStyle(node).overflowY)).length;
    const corners = [[a.left + 10, a.top + 10], [a.right - 10, a.top + 10], [a.left + 10, a.bottom - 10], [a.right - 10, a.bottom - 10]];
    return {over: b.top < a.bottom && a.top < b.bottom && corners.every(([x, y]) => card.contains(document.elementFromPoint(x, y))),
            top: card.matches(':popover-open'),
            inside: Boolean(card.closest('[data-pugh-details], .obs-figure')), scrolls,
            sideways: document.scrollingElement.scrollWidth > innerWidth};
}"""


@pytest.mark.parametrize("width", [390, 1200])
def test_a_counts_hover_card_lies_over_the_matrix_unclipped_and_a_tap_elsewhere_hides_it(phone_browser, deck, width):
    page, errors = _open(phone_browser, deck, width, "three")
    count = page.locator(f'[data-pugh-details="{THREE}"] [data-pugh-texts="losses"] [data-pugh-count="C"]')

    count.evaluate("node => node.scrollIntoView({block: 'center'})")
    count.tap()
    page.wait_for_selector(f"{CARD}:not([hidden])", timeout=1500)
    shown = _card(page), page.evaluate(OVER, THREE)
    page.locator("[data-chapter-body] h1").tap()
    hidden = _card(page)

    assert shown[0] is not None and shown[0].startswith("C · Answers file alone · 2 losses")
    assert shown[1] == {"over": True, "top": True, "inside": False, "scrolls": 0, "sideways": False}
    assert hidden is None
    assert page.evaluate(f"document.querySelectorAll('#{THREE} .pugh-about, #{THREE} .pugh-texts-pop, [data-pugh-details] .pugh-texts-pop').length") == 0
    assert errors == []


def test_sensitivity_leads_with_the_share_and_keeps_the_draw_range_in_its_hover_card(reader_browser, deck):
    page, errors = _open(reader_browser, deck, 1200, "three")
    details = page.locator(f'[data-pugh-details="{THREE}"]')

    details.locator('[data-pugh-tab="sensitivity"]').click()
    share = details.locator("[data-pugh-share]").inner_text()
    grid = details.locator('[role="tabpanel"]:not([hidden])').inner_text()
    details.locator("[data-pugh-share] .pugh-share-bar").hover()
    page.wait_for_selector(f"{CARD}:not([hidden])", timeout=1500)
    card = _card(page)

    assert share == "B · Artifact wins 100.0 % of draws"
    assert "±" not in grid and "All weights together" not in grid and details.locator("[data-pugh-all]").count() == 0
    assert card is not None and "each weight within ±1 of its own" in card and "75.0 %" in card
    assert errors == []


# The Pareto tab: each line's colour beside its option's chip, the axes' labels and the sentence.
PARETO = """anchor => {
    const details = document.querySelector(`[data-pugh-details="${anchor}"]`), figure = document.getElementById(anchor);
    const chip = letter => getComputedStyle(figure.querySelector(`[data-pugh-option="${letter}"] .pugh-letter`)).backgroundColor;
    return {lines: [...details.querySelectorAll('polyline[data-pugh-line]')].map(line =>
                [line.dataset.pughLine, getComputedStyle(line).stroke === chip(line.dataset.pughLine), getComputedStyle(line).stroke,
                 parseFloat(getComputedStyle(line).strokeWidth)]),
            axes: [...details.querySelectorAll('[data-pugh-axis]')].map(label => [label.dataset.pughAxis, label.textContent.trim()]),
            said: details.querySelector('[data-pugh-pareto-said]').textContent.trim()};
}"""


def test_the_pareto_plot_colours_each_option_as_its_chip_and_labels_its_axes(reader_browser, deck):
    page, errors = _open(reader_browser, deck, 1200, "five")
    page.locator(f'[data-pugh-details="{FIVE}"] [data-pugh-tab="pareto"]').click()

    pareto = page.evaluate(PARETO, FIVE)

    lines = {letter: (same, colour, width) for letter, same, colour, width in pareto["lines"]}
    assert set(lines) == set("ABCDE") and all(same for same, _, _ in lines.values())
    assert len({colour for _, colour, _ in lines.values()}) == 5
    assert max(lines, key=lambda letter: lines[letter][2]) == "C"
    assert pareto["axes"] == [["y", "Mark against the datum, −− to ++"], ["x", "Criterion, numbered as in the key"]]
    assert pareto["said"] == ("An option is ruled out where another is at least as good on every criterion and better "
                              "on one: A · A local disk by C · The repository; D by C · The repository.")
    assert errors == []


def test_a_print_shows_the_solutions_expanded_and_the_matrix_under_details(reader_browser, deck):
    """artifact-ui.md, Decision figures: print shows every option expanded, the Proposed winner box,
    then under Details the Matrix tab and the chapter's sections, with no tabs; the
    reader's view is as before afterwards."""
    page, errors = _open(reader_browser, deck, 1200, "three")
    page.locator(f'[data-pugh-details="{THREE}"] [data-pugh-tab="pareto"]').click()

    printed = page.evaluate("""async anchor => {
        let shown;
        window.print = () => {
            dispatchEvent(new Event('beforeprint'));
            const book = document.querySelector('.print-book');
            const copy = [...book.querySelectorAll('[data-figure-kind="pugh"]')].find(node => node.dataset.pughAnchor === anchor);
            const details = [...book.querySelectorAll(`[data-pugh-details="${anchor}"]`)];
            const boxes = [...book.querySelectorAll(`[data-pugh-proposed="${anchor}"] [data-pugh-part="proposed"]`)];
            shown = {open: [...copy.querySelectorAll('.pugh-option-list details')].filter(item => item.open).length,
                     parts: [...copy.querySelector('.pugh-figure-view').children].map(part => part.dataset.pughPart),
                     proposed: boxes.map(box => [...box.children].map(part => part.dataset.pughPart)),
                     details: details.length, matrix: details.reduce((total, node) => total + node.querySelectorAll('.pugh-matrix').length, 0),
                     tabs: book.querySelectorAll('[data-pugh-tab], [data-pugh-pick]').length,
                     record: book.textContent.split('Every answer is kept with the version').length - 1};
        };
        await obsPages.exportPDF();
        dispatchEvent(new Event('afterprint'));
        await new Promise(requestAnimationFrame);
        return shown;
    }""", THREE)
    after = page.locator(f'[data-pugh-details="{THREE}"] [data-pugh-tab][aria-selected="true"]').get_attribute("data-pugh-tab")

    # Details may run over more than one sheet; the matrix and each section print once.
    assert printed["details"] >= 1
    assert {key: value for key, value in printed.items() if key != "details"} == {
        "open": 3, "parts": ["options"], "proposed": [["statement", "success"]], "matrix": 1, "tabs": 0, "record": 1}
    assert after == "pareto"
    assert errors == []


# The Proposed winner section: its box, how it is drawn beside a real bottom-line-up-front box, and
# an option's success criterion in its expander.
PROPOSED = """anchor => {
    const holder = document.querySelector(`[data-pugh-proposed="${anchor}"]`);
    const box = holder?.querySelector('[data-pugh-part="proposed"]'), statement = box?.querySelector('[data-pugh-part="statement"]');
    const bluf = Object.assign(document.createElement('aside'), {className: 'content-card content-emphasis'});
    bluf.append(Object.assign(document.createElement('p'), {textContent: 'Bottom line.'}));
    holder.closest('[data-chapter-body]').append(bluf);
    const look = node => { const style = getComputedStyle(node);
        return [style.backgroundColor, style.borderTopColor, style.borderTopWidth, style.borderRadius, style.paddingTop]; };
    const said = {section: holder?.closest('[data-heading-section]')?.dataset.headingSection ?? null,
            classes: box ? [...box.classList].filter(name => name.startsWith('content-')) : [],
            sameLook: Boolean(box) && JSON.stringify(look(box)) === JSON.stringify(look(bluf)),
            parts: box ? [...box.children].map(part => part.dataset.pughPart) : [],
            bold: statement ? Number(getComputedStyle(statement).fontWeight) >= 600 || Boolean(statement.querySelector('strong, b')) : null,
            expanded: Object.fromEntries([...document.getElementById(anchor).querySelectorAll('[data-pugh-option] details')].map(details =>
                [details.closest('[data-pugh-option]').dataset.pughOption,
                 details.querySelector('[data-pugh-part="option-success"]')?.textContent.trim() ?? null]))};
    bluf.remove();
    return said;
}"""


def test_the_proposed_winner_is_a_box_like_the_bottom_line_and_each_option_says_its_success(phone_browser, deck):
    """artifact-ui.md, Decision figures: after Potential solutions, the Proposed winner section holds
    one box drawn as the report's bottom-line-up-front box, the Y-statement, not bold, then the
    proposed option's success criterion; each option's expander shows its own."""
    page, errors = _open(phone_browser, deck, 390, "three")

    shown = page.evaluate(PROPOSED, THREE)

    assert shown["section"] == "three--proposed-winner"
    assert shown["classes"] == ["content-card", "content-emphasis"] and shown["sameLook"]
    assert shown["parts"] == ["statement", "success"] and shown["bold"] is False
    assert shown["expanded"] == {"A": None, "B": SUCCESS_B, "C": SUCCESS_C}
    assert errors == []


# Each options row's centre lines: the radio, the expander's arrow, the letter chip and the short
# name (the text after the chip), or the None of the above line; in px from the row's top.
CENTRES = """anchor => {
    const centre = node => { const box = node.getBoundingClientRect(); return (box.top + box.bottom) / 2; };
    const textCentre = (node, after) => {
        const range = document.createRange();
        range.setStartAfter(after);
        range.setEnd(node, node.childNodes.length);
        const box = range.getClientRects()[0];
        return box ? (box.top + box.bottom) / 2 : null;
    };
    return [...document.getElementById(anchor).querySelectorAll('[data-pugh-option]')].map(row => {
        const chip = row.querySelector('summary .pugh-letter'), arrow = row.querySelector('summary [data-pugh-arrow]');
        const parts = {radio: centre(row.querySelector('[data-pugh-pick]'))};
        if (chip) Object.assign(parts, {arrow: arrow ? centre(arrow) : null, chip: centre(chip), name: textCentre(chip.parentElement, chip)});
        else parts.line = centre(row.querySelector('.pugh-none-line'));
        return [row.dataset.pughOption, parts];
    });
}"""


@pytest.mark.parametrize("width", [390, 1200])
def test_each_options_row_holds_its_radio_arrow_letter_and_name_on_one_centre_line(request, deck, width):
    """artifact-ui.md, Decision figures: in every row of Potential solutions, None of the above
    included, the radio, the expander's arrow, the letter chip and the short name share one
    vertical centre, on a phone and on a desktop."""
    browser = request.getfixturevalue("phone_browser" if width < 600 else "reader_browser")
    page, errors = _open(browser, deck, width, "three")

    rows = page.evaluate(CENTRES, THREE)

    assert [option for option, _ in rows] == ["A", "B", "C", "none"]
    for option, parts in rows:
        assert None not in parts.values(), (option, parts)
        assert max(parts.values()) - min(parts.values()) <= 1, (option, parts)
    assert errors == []


# Each Details chart's question line: the panel's questions in order, and what each comes before.
QUESTIONS = """anchor => [...document.querySelectorAll(`[data-pugh-details="${anchor}"] [role="tabpanel"]`)]
    .filter(panel => !panel.classList.contains('pugh-extra')).map(panel => [panel.id.split('--pugh-panel-')[1],
        [...panel.querySelectorAll('[data-pugh-question]')].map(line => {
            const next = line.nextElementSibling;
            return [line.textContent.trim(), next?.dataset.pughForm ?? (next?.dataset.pughShare !== undefined ? 'share' : null)
                ?? next?.dataset.pughGrid ?? next?.querySelector('[data-pugh-grid]')?.dataset.pughGrid ?? null];
        })])"""
MATRIX_QUESTION = "How does each option compare with the datum, criterion by criterion?"
SHARE_QUESTION = "Does the winner still win when every weight shifts a little at random?"
GRID_QUESTION = "How far must each weight move before another option wins?"


@pytest.mark.parametrize("width", [390, 1200])
def test_each_chart_opens_with_the_question_it_answers(request, deck, width):
    """artifact-ui.md, Decision figures: the matrix, the Sensitivity bar and the Sensitivity grid each
    open with one line, the question it answers; the Checklist and Pareto have none."""
    browser = request.getfixturevalue("phone_browser" if width < 600 else "reader_browser")
    page, errors = _open(browser, deck, width, "three")

    questions = dict(page.evaluate(QUESTIONS, THREE))

    form, grid = ("rows", "blocks") if width < 600 else ("table", "table")
    assert questions["matrix"] == [[MATRIX_QUESTION, form]]
    assert questions["sensitivity"] == [[SHARE_QUESTION, "share"], [GRID_QUESTION, grid]]
    assert questions["checklist"] == [] and questions["pareto"] == []
    assert errors == []
