"""Decision figures, decided live in the reader with ctrl's engine (figures.py, the pugh kind;
pugh-figure.js; artifact-ui.md, Decision figures).

Reader: whoever changes how a decision figure is decided, laid out or printed.

One artifact of the pugh fixture Document (fixtures/build_documents.py, pugh) serves every test:
ctrl's test matrix with a fourth option and a chosen runner-up, and a matrix of ten options. The
read-only checks share one page; the tests that change weights or the viewport lease their own.
Every page runs with every request outside the artifact refused and recorded.
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
"""The fixture's option figure decides ctrl's matrix with the fourth option C (build_documents.py, DECISION)."""

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
        """What the figure shows: its winner, its options' totals, the check and the column labels."""
        return self.page.evaluate("""anchor => {
            const figure = document.getElementById(anchor);
            const number = text => Number(text.replace('\\u2212', '-').replace('\\u00d7', '').trim());
            const check = figure.querySelector('[data-pugh-check]');
            return {
                winner: figure.dataset.pughWinner,
                totals: Object.fromEntries([...figure.querySelectorAll('[data-pugh-total]')]
                    .map(cell => [cell.dataset.pughTotal, number(cell.textContent)])),
                columns: [...figure.querySelectorAll('thead [data-pugh-option]')].map(cell => cell.dataset.pughOption),
                labels: [...figure.querySelectorAll('thead [data-pugh-option]')].map(cell => cell.firstChild.textContent),
                marked: [...figure.querySelectorAll('thead .pugh-winner')].map(cell => cell.dataset.pughOption),
                verdict: figure.querySelector('[data-pugh-verdict]')?.dataset.pughVerdict,
                check: check && {option: check.dataset.pughCheck,
                                 tie: check.querySelector('[data-pugh-tie]')?.dataset.pughTie,
                                 single: check.querySelector('[data-pugh-single]')?.dataset.pughSingle,
                                 all: check.querySelector('[data-pugh-all]')?.dataset.pughAll},
                folds: [...figure.querySelectorAll('details.pugh-fold')].map(fold => [fold.querySelector('summary').textContent, fold.open]),
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


def test_the_page_decides_ctrls_test_vectors_and_the_figure_shows_the_decision(shared_reader) -> None:
    reader = shared_reader
    decided = reader.page.evaluate("""matrices => matrices.map(({matrix}) => {
        const result = globalThis.obsPughEngine.decide(matrix);
        return {totals: Object.fromEntries(result.candidates.map(c => [c.key, c.total])), ranking: result.ranking,
                suggestion: result.suggestion?.key ?? null, verdict: result.sensitivity?.verdict ?? null,
                ties: Object.fromEntries((result.sensitivity?.all ?? []).map(x => [x.key, x.tie && {
                    criterion: x.tie.criterion, to: x.tie.to, now: x.tie.now, reasonable: x.tie.reasonable}]))};
    })""", VECTORS["matrices"])
    view = reader.view(OPTION)

    assert decided == [vector["expected"] for vector in VECTORS["matrices"]]
    expected = SMALL_WITH_C["expected"]
    assert view["winner"] == expected["suggestion"] == "B"
    assert view["totals"] == expected["totals"]
    assert view["columns"] == ["D", "A", "B", "C"] and view["marked"] == ["B"]
    assert view["verdict"] == expected["verdict"]
    # The chosen A is a runner-up: the check names its tie point, on speed, outside the band.
    assert view["check"] == {"option": "A", "tie": expected["ties"]["A"]["criterion"], "single": "unreasonable",
                             "all": "reasonable"}
    assert view["folds"] == [["What each option means", False], ["Sensitivity", False]]
    reader.clean()


def test_changing_a_weight_moves_the_winner_at_its_tie_point_and_prints_the_readers_view(artifact,
                                                                                        reader_browser) -> None:
    reader = Reader(reader_browser, artifact)
    tie = SMALL_WITH_C["expected"]["ties"]["A"]

    reader.weigh(tie["criterion"], tie["to"] + 0.1)
    before = reader.view(OPTION)
    reader.weigh(tie["criterion"], tie["to"] - 0.1)
    after = reader.view(OPTION)
    printed = reader.page.evaluate("""async anchor => {
        const copy = document.getElementById(anchor).cloneNode(true), book = document.createElement('div');
        book.append(copy);
        await obsFigures.preparePrint(book);
        return {fields: copy.querySelectorAll('input').length, caption: copy.querySelector('figcaption').textContent,
                weight: copy.querySelector('[data-pugh-criterion="speed"] .pugh-weight').textContent};
    }""", OPTION)
    figure = reader.page.locator(f"#{OPTION}")
    figure.locator(":scope > .options-menu-toggle").click()
    figure.locator(".options-menu .pugh-reset").click()

    assert before["winner"] == "B" and before["check"]["option"] == "A"
    assert after["winner"] == "A" and after["check"] is None and after["marked"] == ["A"]
    assert printed == {"fields": 0, "caption": "The option decision. View changed by the reader.",
                       "weight": str(round(tie["to"] - 0.1, 3))}
    assert reader.view(OPTION)["winner"] == "B"
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
    assert view["labels"] == [f"O{index}" for index in range(10)]
    reader.clean()
