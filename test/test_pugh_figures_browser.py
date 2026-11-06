"""Decision figures, decided live in the reader with ctrl's engine (figures.py, the pugh kind;
pugh-figure.js; artifact-ui.md, Decision figures).

Reader: whoever changes how a decision figure is decided, laid out or printed.

One artifact of the pugh fixture Document (fixtures/build_documents.py, pugh) serves every test:
ctrl's test matrix with a fourth option, a chosen runner-up and a checklist, and a matrix of ten
options with a Checklist row. The read-only checks share one page; the tests that change the
reader's view or the viewport lease their own. Every page runs with every request outside the
artifact refused and recorded.
"""
import json
from pathlib import Path

import pytest

from conftest import ROOT, built_once
from obs_html import cli


PUGH = ROOT / "test" / "fixtures" / "documents" / "pugh.json"
VECTORS = json.loads((ROOT / "test" / "fixtures" / "pugh-vectors.json").read_text(encoding="utf-8"))
OPTION, WIDE = "decisions--block-option", "decisions--block-wide"
SMALL_WITH_C = next(vector for vector in VECTORS["matrices"] if vector["name"] == "small with C")
LETTERS = {"D": "A", "A": "B", "B": "C", "C": "D"}
"""The option figure decides ctrl's matrix with the fourth option C (build_documents.py, DECISION),
whose options the fence lists D, A, B, C: their letters."""

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def artifact(tmp_path_factory) -> Path:
    def build(folder: Path) -> None:
        assert cli.main([str(PUGH), str(folder / "artifact.html")]) == 0

    return built_once(tmp_path_factory, "pugh-artifact", build) / "artifact.html"


class Reader:
    """A page of the artifact whose requests beyond the file itself are refused and recorded."""

    def __init__(self, browser, artifact: Path, width: int = 1200):
        self.page = browser.new_page(viewport={"width": width, "height": 900})
        self.requests: list[str] = []
        self.errors: list[str] = []

        def refuse(route):
            self.requests.append(route.request.url)
            route.abort()

        self.page.route("**/*", lambda route: route.continue_()
                        if route.request.url.startswith(("file:", "data:", "blob:")) else refuse(route))
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(artifact.as_uri())
        self.page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
        self.page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('decisions')")
        for anchor in (OPTION, WIDE):
            self.page.wait_for_selector(f"#{anchor}.figure-pugh-ready")

    def view(self, anchor: str) -> dict:
        """What the figure shows: its parts in order, the options list, winner, totals and columns by
        letter, the Wins and Losses counts, changed cells, and each tab with its badge."""
        return self.page.evaluate("""anchor => {
            const figure = document.getElementById(anchor);
            const number = text => Number(text.replace('\\u2212', '-').replace('\\u00d7', '').trim());
            return {
                order: [...figure.querySelector('.pugh-figure-view').children].map(part => part.dataset.pughPart || 'panel'),
                options: [...figure.querySelectorAll('.pugh-option-list [data-pugh-option]')].map(item =>
                    [item.dataset.pughOption, item.querySelector('details').open]),
                winner: figure.dataset.pughWinner,
                totals: Object.fromEntries([...figure.querySelectorAll('[data-pugh-total]')]
                    .map(cell => [cell.dataset.pughTotal, number(cell.textContent)])),
                columns: [...figure.querySelectorAll('thead [data-pugh-option]')].map(cell => cell.dataset.pughOption),
                marked: [...figure.querySelectorAll('thead .pugh-winner')].map(cell => cell.dataset.pughOption),
                criteria: [...figure.querySelectorAll('[data-pugh-criterion]')].map(row => row.dataset.pughCriterion),
                texts: [...figure.querySelectorAll('[data-pugh-texts]')].map(row => row.dataset.pughTexts),
                counts: Object.fromEntries([...figure.querySelectorAll('[data-pugh-texts]')].map(row => [row.dataset.pughTexts,
                    Object.fromEntries([...row.querySelectorAll('[data-pugh-count]')].map(count =>
                        [count.dataset.pughCount, count.textContent.trim()]))])),
                changed: [...figure.querySelectorAll('.pugh-changed')].map(node =>
                    node.dataset.pughMark || node.dataset.pughWeight),
                verdict: figure.querySelector('[data-pugh-verdict]')?.dataset.pughVerdict,
                tabs: [...figure.querySelectorAll('[data-pugh-tab]')].map(tab =>
                    [tab.dataset.pughTab, tab.getAttribute('aria-selected'), tab.disabled,
                     tab.querySelector('[data-tab-badge]')?.dataset.tabBadge ?? null]),
                unless: figure.querySelector('[data-pugh-unless]')?.dataset.pughUnless,
                chosen: figure.querySelector('[data-pugh-chosen]')?.dataset.pughChosen,
                flagged: figure.querySelector('[data-pugh-tab="sensitivity"]').getAttribute('aria-label'),
            };
        }""", anchor)

    def weigh(self, criterion: str, weight: float) -> None:
        field = self.page.locator(f'#{OPTION} [data-pugh-weight="{criterion}"]')
        field.fill(str(weight))
        field.press("Enter")
        field.blur()

    def clean(self) -> None:
        assert self.requests == []
        assert self.errors == []


@pytest.fixture(scope="module")
def shared_reader(artifact, shared_reader_browser) -> Reader:
    """One page of the artifact for the module's checks that only read what it decided."""
    return Reader(shared_reader_browser, artifact)


def test_the_page_decides_ctrls_test_vectors_and_the_matrix_tab_shows_the_decision(shared_reader) -> None:
    reader = shared_reader
    decided = reader.page.evaluate("""matrices => matrices.map(({matrix}) => {
        const result = globalThis.obsPughEngine.decide(matrix);
        return {totals: Object.fromEntries(result.candidates.map(c => [c.key, c.total])), ranking: result.ranking,
                suggestion: result.suggestion?.key ?? null, verdict: result.sensitivity?.verdict ?? null,
                ties: Object.fromEntries((result.sensitivity?.all ?? []).map(x => [x.key, x.tie && {
                    criterion: x.tie.criterion, to: x.tie.to, now: x.tie.now, reasonable: x.tie.reasonable}]))};
    })""", VECTORS["matrices"])
    # The all-weights world the figure states is the change the engine measures.
    worlds = reader.page.evaluate("""matrices => matrices.flatMap(({matrix}) => {
        const result = globalThis.obsPughEngine.decide(matrix);
        return (result.sensitivity?.all ?? []).filter(entry => entry.minChange).map(entry => {
            const weights = globalThis.obsPugh.allWeights(result, entry.key);
            return [entry.minChange.rel, Math.hypot(...weights.map((w, i) => w - result.weights[i])) / Math.hypot(...result.weights)];
        });
    })""", VECTORS["matrices"])
    view = reader.view(OPTION)
    expected = SMALL_WITH_C["expected"]

    assert decided == [vector["expected"] for vector in VECTORS["matrices"]]
    assert worlds and all(abs(engine - figure) < 1e-9 for engine, figure in worlds)
    assert view["winner"] == LETTERS[expected["suggestion"]] == "C"
    assert view["totals"] == {LETTERS[key]: total for key, total in expected["totals"].items()}
    assert view["columns"] == ["A", "B", "C", "D"] and view["marked"] == ["C"]
    assert view["verdict"] == expected["verdict"]
    assert view["criteria"] == ["err", "speed", "cost"] and view["texts"] == ["wins", "losses"]
    # Top to bottom: the options, one line each and closed; the winner line; the tabs (artifact-ui.md, Decision figures).
    assert view["order"][:3] == ["options", "winner", "tabs"] and set(view["order"][3:]) == {"panel"}
    assert view["options"] == [[letter, False] for letter in "ABCD"]
    # Wins and losses are counts in the matrix, their texts on hover or tap.
    assert view["counts"] == {"wins": {"A": "1", "C": "1"}, "losses": {"B": "2"}}
    # The badges replace the Raised list: the failed checklist item (it names no option, so no Checklist
    # row) is counted on the Checklist tab, and the chosen B, not the winner, flags Sensitivity.
    assert view["tabs"] == [["matrix", "true", False, None], ["checklist", "false", False, "1"],
                            ["sensitivity", "false", False, "flag"], ["pareto", "false", True, None]]
    # The chosen B's world, which the Raised list showed, is the Sensitivity tab's second line.
    assert view["chosen"] == "B"
    wide = reader.view(WIDE)
    assert wide["criteria"][-1] == "checklist" and wide["tabs"][1] == ["checklist", "false", False, "1"]
    assert reader.page.evaluate("""() => [...document.querySelectorAll(
        '#decisions--block-wide [data-pugh-criterion="checklist"] [data-pugh-mark]')].map(cell => cell.textContent)""") \
        == ["S"] * 8 + ["−"] * 2
    reader.clean()


def test_the_reader_expands_an_option_changes_weights_and_marks_and_rules_a_world(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact)
    page, figure = reader.page, reader.page.locator(f"#{OPTION}")
    tie = SMALL_WITH_C["expected"]["ties"]["A"]

    figure.locator('.pugh-option-list [data-pugh-option="B"] summary').click()
    expanded = figure.locator('.pugh-option-list [data-pugh-option="B"]').inner_text()

    reader.weigh(tie["criterion"], tie["to"] + 0.1)
    before = reader.view(OPTION)
    reader.weigh(tie["criterion"], tie["to"] - 0.1)
    after = reader.view(OPTION)
    figure.locator('[data-pugh-mark="B:err"] button').click()
    figure.locator('[data-pugh-mark="B:err"] [data-pugh-choice="-2"]').click()
    marked = reader.view(OPTION)
    printed = page.evaluate("""async anchor => {
        const copy = document.getElementById(anchor).cloneNode(true), book = document.createElement('div');
        book.append(copy);
        await obsFigures.preparePrint(book);
        return {fields: copy.querySelectorAll('input, button.pugh-mark-button, [role=tab]').length,
                options: [...copy.querySelectorAll('.pugh-option-list details')].filter(item => item.open).length,
                caption: copy.querySelector('figcaption').textContent};
    }""", OPTION)
    figure.locator(".pugh-view .pugh-reset").click()
    reset = reader.view(OPTION)

    figure.locator('[data-pugh-tab="sensitivity"]').click()
    unless = reader.view(OPTION)["unless"]
    figure.locator('[data-pugh-world="B"] [data-pugh-ruling="could"]').click()
    tripwire = figure.locator('[data-pugh-tripwire="B"]')
    tripwire.fill("Error rates matter less than speed")
    tripwire.press("Enter")
    figure.locator('[data-pugh-tab="matrix"]').click()
    ruled = reader.view(OPTION)

    # Expanding an option shows its sentence, wins and losses; the option stays open while the figure redraws.
    assert expanded.splitlines()[0] == "B · Precise" and "Precise but dear." in expanded
    assert "A new licence" in expanded and "Training" in expanded
    assert before["winner"] == "C" and before["changed"] == [tie["criterion"]]
    assert before["options"][1] == ["B", True]
    # With B the winner the chosen option wins, so only the weights' closeness flags Sensitivity.
    assert before["flagged"] == "Sensitivity, the choice depends on the weights; the chosen option does not win"
    assert after["winner"] == "B" and after["flagged"] == "Sensitivity, the choice depends on the weights"
    assert marked["winner"] == "C" and marked["totals"]["B"] == -2 * 3 + 0 - 1
    assert sorted(marked["changed"]) == ["B:err", tie["criterion"]]
    assert printed == {"fields": 0, "options": 4, "caption": "The option decision. View changed by the reader."}
    assert reset["winner"] == "C" and reset["changed"] == []
    assert unless == "B"
    assert ruled["tabs"][2] == ["sensitivity", "false", False, "flag"]
    assert page.evaluate("obsPugh.readerState()") == {OPTION: {
        "weights": {}, "marks": {}, "rulings": {"B": {"ruling": "could",
                                                            "tripwire": "Error rates matter less than speed"}},
        "winner": "C"}}
    reader.clean()


def test_at_phone_width_the_matrix_is_rows_and_a_wide_table_scrolls_with_its_criteria_held(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact, width=390)

    phone = reader.page.evaluate("""anchor => {
        const rows = document.querySelector(`#${anchor} [data-pugh-form="rows"]`), cells = rows.querySelector('.pugh-row-cells');
        return {page: document.scrollingElement.scrollWidth, viewport: innerWidth, right: rows.getBoundingClientRect().right,
                lines: new Set([...cells.children].map(cell => Math.round(cell.getBoundingClientRect().bottom))).size,
                letters: [...cells.querySelectorAll('[data-pugh-head]')].map(head => head.textContent)};
    }""", WIDE)
    reader.page.set_viewport_size({"width": 900, "height": 900})
    reader.page.wait_for_selector(f'#{WIDE} [data-pugh-form="table"]')
    layout = reader.page.evaluate("""anchor => {
        const box = document.querySelector(`#${anchor} .pugh-scroll`);
        const name = box.querySelector('tbody .pugh-criterion');
        const before = name.getBoundingClientRect().left;
        box.scrollLeft = box.scrollWidth;
        return {page: document.scrollingElement.scrollWidth, viewport: innerWidth,
                right: box.getBoundingClientRect().right, scrolls: box.scrollWidth > box.clientWidth,
                held: Math.abs(name.getBoundingClientRect().left - before) < 1};
    }""", WIDE)
    view = reader.view(WIDE)

    # Ten options: the rows wrap their cells to a further line rather than scroll.
    assert phone["page"] <= phone["viewport"] == 390 and phone["right"] <= 390
    assert phone["lines"] > 1 and phone["letters"] == [chr(ord("A") + index) for index in range(10)]
    assert layout["page"] <= layout["viewport"] == 900
    assert layout["right"] <= 900 and layout["scrolls"] and layout["held"]
    assert view["columns"] == [chr(ord("A") + index) for index in range(10)]
    reader.clean()
