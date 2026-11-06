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
        """What the figure shows: winner, totals and columns by letter, changed cells, Raised, tabs, option."""
        return self.page.evaluate("""anchor => {
            const figure = document.getElementById(anchor);
            const number = text => Number(text.replace('\\u2212', '-').replace('\\u00d7', '').trim());
            return {
                winner: figure.dataset.pughWinner,
                totals: Object.fromEntries([...figure.querySelectorAll('[data-pugh-total]')]
                    .map(cell => [cell.dataset.pughTotal, number(cell.textContent)])),
                columns: [...figure.querySelectorAll('thead [data-pugh-option]')].map(cell => cell.dataset.pughOption),
                marked: [...figure.querySelectorAll('thead .pugh-winner')].map(cell => cell.dataset.pughOption),
                criteria: [...figure.querySelectorAll('[data-pugh-criterion]')].map(row => row.dataset.pughCriterion),
                texts: [...figure.querySelectorAll('[data-pugh-texts]')].map(row => row.dataset.pughTexts),
                changed: [...figure.querySelectorAll('.pugh-changed')].map(node =>
                    node.dataset.pughMark || node.dataset.pughWeight),
                verdict: figure.querySelector('[data-pugh-verdict]')?.dataset.pughVerdict,
                raised: [...figure.querySelectorAll('[data-pugh-raised]')].map(item => item.dataset.pughRaised),
                tabs: [...figure.querySelectorAll('[data-pugh-tab]')].map(tab =>
                    [tab.dataset.pughTab, tab.getAttribute('aria-selected'), tab.disabled]),
                option: figure.querySelector('.pugh-option-count')?.textContent,
                unless: figure.querySelector('[data-pugh-unless]')?.dataset.pughUnless,
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
    # Raised: the failed checklist item (it names no option, so no Checklist row) and the chosen B's world.
    assert view["raised"] == ["checklist", "chosen"]
    assert view["tabs"] == [["matrix", "true", False], ["checklist", "false", False], ["whatif", "false", False]]
    assert view["option"] == "Option A of 4"
    wide = reader.view(WIDE)
    assert wide["criteria"][-1] == "checklist" and wide["raised"][0] == "checklist"
    assert reader.page.evaluate("""() => [...document.querySelectorAll(
        '#decisions--block-wide [data-pugh-criterion="checklist"] [data-pugh-mark]')].map(cell => cell.textContent)""") \
        == ["S"] * 8 + ["−"] * 2
    reader.clean()


def test_the_reader_walks_the_options_changes_weights_and_marks_and_rules_a_world(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact)
    page, figure = reader.page, reader.page.locator(f"#{OPTION}")
    tie = SMALL_WITH_C["expected"]["ties"]["A"]

    figure.locator(".pugh-next").click()
    card = figure.locator(".pugh-option")
    card.focus()
    page.keyboard.press("ArrowRight")
    walked = reader.view(OPTION)["option"]
    box = card.bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.7, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.2, box["y"] + box["height"] / 2, steps=4)
    page.mouse.up()
    swiped = reader.view(OPTION)["option"]
    chapter = page.evaluate("document.querySelector('[data-active-chapter]').dataset.chapter")

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
                options: copy.querySelectorAll('.pugh-option-list dt').length,
                caption: copy.querySelector('figcaption').textContent};
    }""", OPTION)
    figure.locator(".pugh-view .pugh-reset").click()
    reset = reader.view(OPTION)

    figure.locator('[data-pugh-tab="whatif"]').click()
    unless = reader.view(OPTION)["unless"]
    figure.locator('[data-pugh-world="B"] [data-pugh-ruling="could"]').click()
    tripwire = figure.locator('[data-pugh-tripwire="B"]')
    tripwire.fill("Error rates matter less than speed")
    tripwire.press("Enter")
    figure.locator('[data-pugh-tab="matrix"]').click()
    ruled = reader.view(OPTION)

    assert (walked, swiped, chapter) == ("Option C of 4", "Option D of 4", "decisions")
    assert before["winner"] == "C" and before["changed"] == [tie["criterion"]]
    assert after["winner"] == "B" and "chosen" not in after["raised"]
    assert marked["winner"] == "C" and marked["totals"]["B"] == -2 * 3 + 0 - 1
    assert sorted(marked["changed"]) == ["B:err", tie["criterion"]]
    assert printed == {"fields": 0, "options": 4, "caption": "The option decision. View changed by the reader."}
    assert reset["winner"] == "C" and reset["changed"] == []
    assert unless == "B"
    assert ruled["raised"] == ["checklist", "world-B", "chosen"]
    assert page.evaluate("obsPugh.readerState()") == {OPTION: {
        "weights": {}, "marks": {}, "rulings": {"B": {"ruling": "could",
                                                            "tripwire": "Error rates matter less than speed"}},
        "winner": "C"}}
    reader.clean()


def test_at_phone_width_only_the_matrix_scrolls_and_its_criteria_hold(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact, width=390)

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

    assert layout["page"] <= layout["viewport"] == 390
    assert layout["right"] <= 390 and layout["scrolls"] and layout["held"]
    assert view["columns"] == [chr(ord("A") + index) for index in range(10)]
    reader.clean()
