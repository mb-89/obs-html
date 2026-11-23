"""Decision figures, decided live in the reader with the upstream engine (figures.py, the pugh kind;
pugh-figure.js; artifact-ui.md, Decision figures).

Reader: whoever changes how a decision figure is decided, laid out or printed.

One artifact of the pugh fixture Document (fixtures/build_documents.py, pugh) serves every test:
The upstream project's test matrix with a fourth option, a chosen runner-up and a checklist, and a matrix of ten
options with a Checklist row. The computed verdict's tests read a second, of the decision-verdict
fixture, whose vault turns artifact.figures.decisionVerdict on and adds the upstream project's matrix with a gate; the printed
verdict's test reads a third, the same Document with an answer to its decisions chapter. The read-only checks share one page; the tests that change the
reader's view or the viewport lease their own. Every page runs with every request outside the
artifact refused and recorded.
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from browser import door
from conftest import ROOT, built_once
from obs_html import cli


PUGH = ROOT / "test" / "fixtures" / "documents" / "pugh.json"
PUGH_VERDICT = ROOT / "test" / "fixtures" / "documents" / "decision-verdict.json"
VECTORS = json.loads((ROOT / "test" / "fixtures" / "pugh-vectors.json").read_text(encoding="utf-8"))
OPTION, WIDE, GATED = "decisions--block-option", "decisions--block-wide", "decisions--block-gated"
SMALL_WITH_C = next(vector for vector in VECTORS["matrices"] if vector["name"] == "small with C")
LETTERS = {"D": "A", "A": "B", "B": "C", "C": "D"}
"""The option figure decides the upstream project's matrix with the fourth option C (build_documents.py, DECISION),
whose options the fence lists D, A, B, C: their letters."""



STATES = {"plain": "pugh-figures-desktop", "verdict": "pugh-verdict-desktop", "answered": "pugh-verdict-answered-desktop"}
"""The browser door's states the logic tests open (test/browser/expectations.yaml): the pugh fixture's,
the decision-verdict fixture's and the answered decision-verdict Document's decisions chapter at
desktop size, each built by a function below."""


def _built(document: Path) -> str:
    """The artifact of ``document`` built in the current folder, as the browser door builds a state's."""
    assert cli.main([str(document), "artifact.html"]) == 0
    return Path("artifact.html").read_text(encoding="utf-8")


def pugh_artifact() -> str:
    """The artifact of the state pugh-figures-desktop: the pugh fixture Document's."""
    return _built(PUGH)


def verdict_artifact() -> str:
    """The artifact of the state pugh-verdict-desktop: the decision-verdict fixture Document's."""
    return _built(PUGH_VERDICT)


def answered_verdict_artifact() -> str:
    """The artifact of the state pugh-verdict-answered-desktop: the decision-verdict Document whose
    decisions chapter carries ANSWER."""
    Path("document.json").write_text(json.dumps(_answered(), ensure_ascii=False), encoding="utf-8")
    return _built(Path("document.json"))


ANSWER = {"verdict": "bless", "figures": {
    OPTION: {"weights": {"speed": 0.5}, "marks": {"D": {"err": 1}}},
    WIDE: {"weights": {"speed": 1}},
    GATED: {"vetoes": ["C"], "lifts": {"B": ["gate0"]}}}}
"""A reader's answer to the decisions chapter with figure changes of every kind the engine takes
(obs input-model, Answers): a weight and a mark, a weight alone, and a veto with a lifted gate."""


def _answered() -> dict:
    """The decision-verdict Document whose decisions chapter carries ANSWER."""
    document = json.loads(PUGH_VERDICT.read_text(encoding="utf-8"))
    [chapter] = [chapter for chapter in document["chapters"] if chapter["id"] == "decisions"]
    chapter["bless"] = {"answer": ANSWER}
    return document


@pytest.fixture(scope="module")
def answered_verdict(tmp_path_factory) -> Path:
    """The folder of the decision-verdict Document whose decisions chapter carries ANSWER."""
    def build(folder: Path) -> None:
        (folder / "document.json").write_text(json.dumps(_answered(), ensure_ascii=False), encoding="utf-8")

    return built_once(tmp_path_factory, "pugh-verdict-answered-document", build)


@pytest.fixture(scope="module")
def printed_verdicts(tmp_path_factory, answered_verdict) -> dict[str, dict[str, list[list]]]:
    """What obs-html DOCUMENT --print-verdicts --verdict-format json states for the plain and the
    answered Document, printed once: by anchor, each decision's lines as [part, letter, text], the
    shape Reader.bottom reads from the page."""
    documents = {"plain": PUGH_VERDICT, "answered": answered_verdict / "document.json"}

    def build(folder: Path) -> None:
        for name, document in documents.items():
            with contextlib.redirect_stdout(io.StringIO()) as out:
                assert cli.main([str(document), "--print-verdicts", "--verdict-format", "json"]) == 0
            (folder / f"{name}.json").write_text(out.getvalue(), encoding="utf-8")

    folder = built_once(tmp_path_factory, "pugh-verdict-prints", build)
    return {name: {decision["anchor"]: [[line["part"], line.get("letter"), line["text"]] for line in decision["lines"]]
                   for decision in json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))["decisions"]}
            for name in documents}


class Reader:
    """A page of the artifact, on the fake browser at its recorded state, whose requests beyond the
    file itself are recorded (the fake refuses every one, test/browser/browser-door.md)."""

    def __init__(self, page, artifact: Path, state: str, anchors: tuple[str, ...] = (OPTION, WIDE)):
        self.page = page
        self.requests: list[str] = []
        self.errors: list[str] = []
        self.page.on("request", lambda request: None if request.url.startswith(("file:", "data:", "blob:"))
                     else self.requests.append(request.url))
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        door.open_recorded(self.page, state, artifact)
        self.page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('decisions')")
        for anchor in anchors:
            self.page.wait_for_selector(f"#{anchor}.figure-pugh-ready")

    @classmethod
    def opened(cls, fake_page, door_artifact, kind: str = "plain", anchors: tuple[str, ...] = (OPTION, WIDE)) -> Reader:
        """The reader of the state STATES names for ``kind``."""
        return cls(fake_page, door_artifact(STATES[kind]), STATES[kind], anchors)

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
                chosen: figure.querySelector('[data-pugh-chosen]')?.dataset.pughChosen,
                flagged: figure.querySelector('[data-pugh-tab="sensitivity"]').getAttribute('aria-label'),
            };
        }""", anchor)

    def grid(self, anchor: str) -> dict:
        """What the Sensitivity grid shows: each cell's tie weight (None for a dash) by option letter
        and criterion, the cells within reach, the winner's share,
        and the engine's numbers for the same decision (pugh-figure.js, decide) by letter."""
        return self.page.evaluate("""anchor => {
            const figure = document.getElementById(anchor), value = text => (text === undefined ? null : Number(text));
            const {result, figureModel} = obsPugh.decide(JSON.parse(figure.dataset.figureSpec), {
                weights: obsPugh.readerState()[anchor]?.weights ?? {}, marks: obsPugh.readerState()[anchor]?.marks ?? {}});
            const letter = key => figureModel.byKey[key].letter;
            return {
                cells: Object.fromEntries([...figure.querySelectorAll('[data-pugh-cell]')].map(cell =>
                    [cell.dataset.pughCell, value(cell.dataset.pughTie)])),
                reach: [...figure.querySelectorAll('[data-pugh-cell][data-pugh-reach]')].map(cell => cell.dataset.pughCell),
                share: value(figure.querySelector('[data-pugh-share]').dataset.pughShare),
                engine: {share: result.sensitivity.share, holdShare: result.sensitivity.holdShare,
                    ties: Object.fromEntries(result.sensitivity.all.filter(entry => entry.tie && !entry.tie.now).map(entry =>
                        [`${letter(entry.key)}:${entry.tie.criterion}`, [entry.tie.to, entry.tie.reasonable]]))},
            };
        }""", anchor)

    def bottom(self, anchor: str) -> list[list]:
        """The computed verdict's lines in the figure's Proposed winner box: each line's part, option and text."""
        return self.page.evaluate("""anchor => [...document.getElementById(anchor).querySelectorAll('.pugh-bottom')]
            .map(line => [line.dataset.pughPart, line.dataset.pughFor ?? null, line.textContent])""", anchor)

    def weigh(self, criterion: str, weight: float) -> None:
        field = self.page.locator(f'#{OPTION} [data-pugh-weight="{criterion}"]')
        field.fill(str(weight))
        field.press("Enter")
        field.blur()

    def clean(self) -> None:
        assert self.requests == []
        assert self.errors == []


class BrowserReader(Reader):
    """A page of the artifact in the real browser, for the hot test, whose requests beyond the file
    itself are refused and recorded."""

    def __init__(self, browser, artifact: Path, width: int = 1200, anchors: tuple[str, ...] = (OPTION, WIDE)):
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
        for anchor in anchors:
            self.page.wait_for_selector(f"#{anchor}.figure-pugh-ready")


@pytest.mark.dom
def test_the_page_decides_the_upstream_test_vectors_and_the_matrix_tab_shows_the_decision(fake_page, door_artifact) -> None:
    reader = Reader.opened(fake_page, door_artifact)
    decided = reader.page.evaluate("""matrices => matrices.map(({matrix}) => {
        const result = globalThis.obsPughEngine.decide(matrix);
        return {totals: Object.fromEntries(result.candidates.map(c => [c.key, c.total])), ranking: result.ranking,
                suggestion: result.suggestion?.key ?? null, verdict: result.sensitivity?.verdict ?? null,
                ties: Object.fromEntries((result.sensitivity?.all ?? []).map(x => [x.key, x.tie && {
                    criterion: x.tie.criterion, to: x.tie.to, now: x.tie.now, reasonable: x.tie.reasonable}]))};
    })""", VECTORS["matrices"])
    view = reader.view(OPTION)
    expected = SMALL_WITH_C["expected"]

    assert decided == [vector["expected"] for vector in VECTORS["matrices"]]
    assert view["winner"] == LETTERS[expected["suggestion"]] == "C"
    assert view["totals"] == {LETTERS[key]: total for key, total in expected["totals"].items()}
    assert view["columns"] == ["A", "B", "C", "D"] and view["marked"] == ["C"]
    assert view["verdict"] == expected["verdict"]
    assert view["criteria"] == ["err", "speed", "cost"] and view["texts"] == ["wins", "losses"]
    # Top to bottom: the options, one line each and closed; the Proposed winner box; the tabs (artifact-ui.md,
    # Decision figures). Two decision figures in one chapter each hold their own box and tabs.
    assert view["order"][:3] == ["options", "proposed", "tabs"] and set(view["order"][3:]) == {"panel"}
    assert view["options"] == [[letter, False] for letter in "ABCD"]
    # Wins and losses are counts in the matrix, their texts on hover or tap.
    assert view["counts"] == {"wins": {"A": "1", "C": "1"}, "losses": {"B": "2"}}
    # The badges replace the Raised list: the failed checklist item (it names no option, so no Checklist
    # row) is counted on the Checklist tab, and the chosen B, not the winner, flags Sensitivity.
    assert view["tabs"] == [["matrix", "true", False, None], ["checklist", "false", False, "1"],
                            ["sensitivity", "false", False, "flag"], ["pareto", "false", False, None]]
    assert view["flagged"] == "Sensitivity, the chosen option does not win"
    # The chosen B, not the winner, is the line under the Sensitivity grid.
    assert view["chosen"] == "B"
    # The grid is the engine's numbers laid out (artifact-ui.md, Sensitivity): each option's smallest move
    # is the engine's tie point, its other cells move a weight as far or further; a dash where no weight
    # ties it; the bar is its share of the draws.
    grid = reader.grid(OPTION)
    assert grid["cells"] == {**{f"{letter}:{key}": None for letter in "ABD" for key in ("err", "speed", "cost")},
                             "B:err": 6, "B:speed": 0.5}
    assert {cell: grid["cells"][cell] for cell in grid["engine"]["ties"]} == {
        cell: to for cell, (to, _) in grid["engine"]["ties"].items()}
    assert grid["reach"] == [cell for cell, (_, reasonable) in grid["engine"]["ties"].items() if reasonable] == []
    assert grid["share"] == grid["engine"]["share"]
    # Without artifact.figures.decisionVerdict the figure is what it was: no verdict lines, no keys of its part.
    assert reader.bottom(OPTION) == [] and reader.page.evaluate("typeof globalThis.obsPughVerdict") == "undefined"
    wide = reader.view(WIDE)
    assert wide["criteria"][-1] == "checklist" and wide["tabs"][1] == ["checklist", "false", False, "1"]
    assert reader.page.evaluate("""() => [...document.querySelectorAll(
        '#decisions--block-wide [data-pugh-criterion="checklist"] [data-pugh-mark]')].map(cell => cell.textContent)""") \
        == ["0"] * 8 + ["−"] * 2
    # A mark of 0 reads "0" everywhere the figure shows a mark, the datum's column included (artifact-ui.md, Decision figures).
    assert reader.page.evaluate("() => [...document.querySelectorAll('[data-pugh-mark]')].filter(cell => cell.textContent.trim() === 'S').length") == 0
    reader.clean()


@pytest.mark.dom
def test_the_reader_expands_an_option_changes_weights_and_marks_and_rules_a_world(fake_page, door_artifact) -> None:
    reader = Reader.opened(fake_page, door_artifact)
    page, figure = reader.page, reader.page.locator(f"#{OPTION}")
    tie = SMALL_WITH_C["expected"]["ties"]["A"]

    figure.locator('.pugh-option-list [data-pugh-option="B"] summary').click()
    expanded = figure.locator('.pugh-option-list [data-pugh-option="B"]').inner_text()

    reader.weigh(tie["criterion"], tie["to"] + 0.1)
    before = reader.view(OPTION)
    reach = reader.grid(OPTION)
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
    figure.locator('[data-pugh-cell="B:speed"]').click()
    figure.locator('[data-pugh-ruling-for="B"] [data-pugh-ruling="could"]').click()
    tripwire = figure.locator('[data-pugh-tripwire="B"]')
    tripwire.fill("Error rates matter less than speed")
    tripwire.press("Enter")
    figure.locator('[data-pugh-tab="matrix"]').click()
    ruled = reader.view(OPTION)

    # Expanding an option shows its sentence, wins and losses; the option stays open while the figure redraws.
    # The fence's chosen B, not the winner, is marked so on its line.
    assert expanded.splitlines()[0] == "B · Precise chosen" and "Precise but dear." in expanded
    assert "A new licence" in expanded and "Training" in expanded
    assert before["winner"] == "C" and before["changed"] == [tie["criterion"]]
    assert before["options"][1] == ["B", True]
    # Speed 0.1 above B's tie leaves C ahead of B by 0.2: each of B's cells is within reach, the engine's
    # tie among them, which flags Sensitivity, with the winner's share under the hold share where it is.
    assert reach["reach"] == ["B:err", "B:speed", "B:cost"] and list(reach["engine"]["ties"]) == ["B:speed"]
    assert reach["cells"]["B:speed"] == reach["engine"]["ties"]["B:speed"][0] == pytest.approx(tie["to"])
    assert [reach["cells"][cell] for cell in ("B:err", "B:cost")] == pytest.approx([3.2, 0.9])
    assert before["flagged"] == "Sensitivity, " + "; ".join(
        ["a tie within reach"] + [f"the winner wins under {100 * reach['engine']['holdShare']:.1f} % of draws"]
        * (reach["engine"]["share"] < reach["engine"]["holdShare"]) + ["the chosen option does not win"])
    assert after["winner"] == "B" and after["flagged"].startswith("Sensitivity, a tie within reach")
    assert marked["winner"] == "C" and marked["totals"]["B"] == -2 * 3 + 0 - 1
    assert sorted(marked["changed"]) == ["B:err", tie["criterion"]]
    assert printed == {"fields": 0, "options": 4, "caption": "The option decision. View changed by the reader."}
    assert reset["winner"] == "C" and reset["changed"] == []
    assert ruled["tabs"][2] == ["sensitivity", "false", False, "flag"]
    assert ruled["flagged"] == "Sensitivity, an option could win; the chosen option does not win"
    assert page.evaluate("obsPugh.readerState()") == {OPTION: {
        "weights": {}, "marks": {}, "rulings": {"B": {"ruling": "could",
                                                            "tripwire": "Error rates matter less than speed"}},
        "winner": "C"}}
    reader.clean()


@pytest.mark.dom
def test_an_option_the_reader_opens_stays_open_through_a_redraw_before_its_toggle_event(fake_page, door_artifact) -> None:
    """A details element's toggle event is a task of its own, queued after the click that opened it,
    so a redraw that runs first (a weight's change, CI's flake on the test above) must still find
    the option open: here the click and the redraw share one task, before any toggle event fires."""
    reader = Reader.opened(fake_page, door_artifact)
    opened = reader.page.evaluate("""anchor => {
        const figure = document.getElementById(anchor), option = () => figure.querySelector('.pugh-option-list [data-pugh-option="B"] details');
        option().querySelector('summary').click();
        const field = figure.querySelector('[data-pugh-weight="speed"]');
        field.value = '9';
        field.dispatchEvent(new Event('change'));
        return {redrawn: !figure.contains(field), open: option().open};
    }""", OPTION)

    assert opened == {"redrawn": True, "open": True}
    assert reader.view(OPTION)["options"][1] == ["B", True]
    reader.clean()


@pytest.mark.dom
def test_a_print_reads_the_readers_view_and_never_writes_it(fake_page, door_artifact) -> None:
    """artifact-ui.md, Printing: Export PDF prints the reader's weights with every option expanded,
    and afterwards the reader's view shows only the option the reader opened, on the tab they left."""
    reader = Reader.opened(fake_page, door_artifact)
    page, figure = reader.page, reader.page.locator(f"#{OPTION}")
    figure.locator('.pugh-option-list [data-pugh-option="B"] summary').click()
    reader.weigh("speed", 9)
    figure.locator('[data-pugh-tab="checklist"]').click()
    before = reader.view(OPTION), page.evaluate("obsPugh.readerState()")

    printed = page.evaluate("""async anchor => {
        let shown;
        window.print = () => {
            dispatchEvent(new Event('beforeprint'));
            const copy = [...document.querySelectorAll('.print-book [data-figure-kind="pugh"]')]
                .find(printed => printed.id.endsWith(anchor));
            shown = {options: [...copy.querySelectorAll('.pugh-option-list details')].filter(item => item.open).length,
                     speed: copy.querySelector('[data-pugh-criterion="speed"] .pugh-weight').textContent,
                     note: copy.querySelectorAll('.figure-view-note').length};
        };
        await obsPages.exportPDF();
        dispatchEvent(new Event('afterprint'));
        await new Promise(requestAnimationFrame);
        return shown;
    }""", OPTION)
    after = reader.view(OPTION), page.evaluate("obsPugh.readerState()")

    assert printed == {"options": 4, "speed": "9", "note": 1}
    assert [option for option, shown in after[0]["options"] if shown] == ["B"]
    assert after == before and after[0]["tabs"][1][:2] == ["checklist", "true"]
    reader.clean()


@pytest.mark.hot
@pytest.mark.browser
def test_at_phone_width_the_matrix_is_rows_and_a_wide_table_scrolls_with_its_criteria_held(door_artifact, reader_browser) -> None:
    reader = BrowserReader(reader_browser, door_artifact(STATES["plain"]), width=390)

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


PARETO = """anchor => {
    const figure = document.getElementById(anchor), panel = figure.querySelector('[data-pugh-pareto]');
    return {sentence: panel.querySelector('[data-pugh-pareto-said]').textContent,
            dominated: panel.dataset.pughPareto,
            lines: Object.fromEntries([...panel.querySelectorAll('polyline[data-pugh-line]')].map(line =>
                [line.dataset.pughLine, line.getAttribute('class').split(' ').filter(name => name !== 'pl-s').sort()])),
            axes: panel.querySelectorAll('polyline.pl-reference').length,
            flag: figure.querySelector('[data-pugh-tab="pareto"]').getAttribute('aria-label'),
            badge: figure.querySelector('[data-pugh-tab="pareto"] [data-tab-badge]')?.dataset.tabBadge ?? null};
}"""


@pytest.mark.dom
def test_the_pareto_tab_draws_the_options_with_the_engines_plot_and_flags_a_dominated_winner(fake_page, door_artifact) -> None:
    reader = Reader.opened(fake_page, door_artifact)
    figure = reader.page.locator(f"#{OPTION}")
    figure.locator('[data-pugh-tab="pareto"]').click()
    front = reader.page.evaluate(PARETO, OPTION)
    # B at ++ on speed and + on cost dominates C, and with err weighed 0 they tie, C first by its tie-break.
    figure.locator('[data-pugh-tab="matrix"]').click()
    for criterion, mark in (("speed", 2), ("cost", 1)):
        figure.locator(f'[data-pugh-mark="B:{criterion}"] button').click()
        figure.locator(f'[data-pugh-mark="B:{criterion}"] [data-pugh-choice="{mark}"]').click()
    reader.weigh("err", 0)
    figure.locator('[data-pugh-tab="pareto"]').click()
    dominated = reader.page.evaluate(PARETO, OPTION)

    # A (0, 0, 0), B (2, 0, −1), C (1, 2, 1), D (0, 2, 0): the winner thickest, the dominated dashed.
    assert front["sentence"] == ("An option is ruled out where another is at least as good on every criterion and better on "
                                 "one: A · What runs today by C · Quick and D · Middling; D · Middling by C · Quick.")
    assert front["dominated"] == "A D" and front["axes"] == 3
    assert front["lines"] == {"A": ["pl-other", "pugh-dominated"], "B": ["pl-front"], "C": ["pl-option"],
                              "D": ["pl-other", "pugh-dominated"]}
    assert front["flag"] is None and front["badge"] is None
    assert reader.view(OPTION)["winner"] == "C"
    assert dominated["sentence"] == ("An option is ruled out where another is at least as good on every criterion and better on "
                                     "one: A · What runs today by B · Precise, C · Quick and D · Middling; C · Quick by B · Precise; "
                                     "D · Middling by B · Precise and C · Quick.")
    assert dominated["lines"]["C"] == ["pl-option", "pugh-dominated"] and dominated["lines"]["B"] == ["pl-front"]
    assert dominated["flag"] == "Pareto, the winner is dominated by B" and dominated["badge"] == "flag"
    reader.clean()


ENGINE_FIELDS = {"chosen", "checklist", "what", "wins", "losses"}
"""The gated fence's fields that are obs's, not the engine's (capabilities/pugh-decisions, Fence fields and the engine)."""


@pytest.mark.dom
def test_with_the_option_on_the_proposed_winner_states_the_verdict_each_runner_ups_tie_and_each_veto(
        fake_page, door_artifact) -> None:
    """artifact-ui.md, The engine's bottom line: the engine's verdict, each runner-up's single-weight
    tie and whether that change is reasonable, and each vetoed option with its reasons."""
    reader = Reader.opened(fake_page, door_artifact, "verdict", anchors=(OPTION, WIDE, GATED))

    assert reader.bottom(OPTION) == [
        ["verdict", None, "The choice holds: C · Quick wins 96.0 % of the weight draws within ±1."],
        ["runner-up", "B", "B · Precise ties if Speed goes 2 → 0.5: not a reasonable change."],
        ["runner-up", "D", "No single weight makes D · Middling tie."],
        ["runner-up", "A", "No single weight makes A · What runs today tie."]]
    assert reader.bottom(WIDE)[:3] == [
        ["verdict", None, "The choice depends on the weights: G wins 88.3 % of the weight draws within ±1."],
        ["runner-up", "H", "H ties it now."], ["runner-up", "C", "C ties if Speed goes 2 → 1: a reasonable change."]]
    assert reader.bottom(GATED)[-1] == ["veto", "B", "B · Precise is out: over budget: Cost of ownership 19 above 15."]
    # The verdict is the engine's, and so is the Sensitivity tab's: one decision.
    assert reader.view(OPTION)["verdict"] == "holds"
    reader.clean()


@pytest.mark.dom
def test_the_readers_vetoes_lifts_and_datum_feed_the_engine_and_the_page_decides_again_at_once(
        fake_page, door_artifact) -> None:
    """artifact-ui.md, The reader's vetoes and datum: each key is one of the engine's overrides, and the
    figure shows what decide() gives with them, at once."""
    from fixtures.build_documents import GATED as gated
    matrix = {key: value for key, value in gated.items() if key not in ENGINE_FIELDS}
    matrix["candidates"] = [{key: value for key, value in option.items() if key not in ENGINE_FIELDS}
                            for option in gated["candidates"]]
    reader = Reader.opened(fake_page, door_artifact, "verdict", anchors=(OPTION, WIDE, GATED))
    page, figure = reader.page, reader.page.locator(f"#{GATED}")
    letters = {"D": "A", "A": "B", "B": "C", "C": "D"}

    def expand(letter: str) -> None:
        if not figure.locator(f'.pugh-option-list [data-pugh-option="{letter}"] details').evaluate("node => node.open"):
            figure.locator(f'.pugh-option-list [data-pugh-option="{letter}"] summary').click()

    def engine(*overrides: dict) -> dict:
        return page.evaluate("""matrix => { const r = obsPughEngine.decide(matrix);
            return {winner: r.suggestion.key, totals: Object.fromEntries(r.candidates.map(c => [c.key, c.total]))}; }""",
                             {**matrix, "overrides": [{**override, "comment": "x"} for override in overrides]})

    def shown() -> dict:
        view = reader.view(GATED)
        keys = {letter: key for key, letter in letters.items()}
        return {"winner": keys[view["winner"]], "totals": {keys[letter]: total for letter, total in view["totals"].items()}}

    closed = figure.locator('[data-pugh-actions="B"]').is_hidden()
    expand("B")
    gate = figure.locator('[data-pugh-lift="B:gate0"]')
    held = gate.get_attribute("aria-pressed")
    gate.click()
    lifted = (shown(), reader.bottom(GATED), figure.locator('[data-pugh-lift="B:gate0"]').inner_text())
    expand("C")
    figure.locator('[data-pugh-actions="C"] [data-pugh-action="veto"]').click()
    vetoed = (shown(), reader.bottom(GATED))
    expand("D")
    figure.locator('[data-pugh-actions="D"] [data-pugh-action="datum"]').click()
    moved = (shown(), page.evaluate("obsPugh.readerState()"))
    figure.locator(".pugh-view .pugh-reset").click()
    reset = (shown(), reader.bottom(GATED)[-1], page.evaluate("obsPugh.readerState()"))

    lift = {"kind": "lift", "candidate": "A", "veto": "gate0"}
    veto = {"kind": "option", "candidate": "B", "action": "veto"}
    datum = {"kind": "datum", "candidate": "C"}
    # A closed expander's keys are hidden, not merely folded.
    assert closed and held == "false"
    # Lifting the gate's veto puts B back in, as decide() does with that lift; the box says it is in.
    assert lifted[0] == engine(lift) and lifted[2] == "Restore"
    assert ["veto", "B", "B · Precise is in: lifted: over budget: Cost of ownership 19 above 15."] in lifted[1]
    # Vetoing the winner C: decide() with both changes, at once; the box names the reader's veto.
    assert vetoed[0] == engine(lift, veto) and vetoed[0]["winner"] == "A"
    assert ["veto", "C", "C · Quick is out: vetoed by you."] in vetoed[1]
    assert vetoed[1][0][0] == "verdict" and "B · Precise" in vetoed[1][0][2]
    # Making D the datum sets every mark again against it.
    assert moved[0] == engine(datum, veto, lift)
    assert moved[1] == {GATED: {"weights": {}, "marks": {}, "vetoes": ["C"], "lifts": {"B": ["gate0"]}, "datum": "D",
                                "rulings": {}, "winner": letters[moved[0]["winner"]]}}
    # Reset restores the fence's vetoes and datum.
    assert reset[0] == engine() and reset[0]["winner"] == "B"
    assert reset[1] == ["veto", "B", "B · Precise is out: over budget: Cost of ownership 19 above 15."] and reset[2] == {}
    reader.clean()


@pytest.mark.parametrize("answered", [False, True], ids=["plain", "answered"])
@pytest.mark.dom
def test_the_printed_verdict_is_every_line_the_page_draws_for_every_decision(
        answered, printed_verdicts, fake_page, door_artifact) -> None:
    """cli.md, Printing the verdicts: the print states each decision as the page shows it, every line
    of its bottom line; answered, as the answer left it (verdicts.py and the page map the anchors and
    the answer apart: render.py, figures.py)."""
    printed = printed_verdicts["answered" if answered else "plain"]
    assert list(printed) == [OPTION, WIDE, GATED]
    reader = Reader.opened(fake_page, door_artifact, "answered" if answered else "verdict", anchors=tuple(printed))
    assert {anchor: reader.bottom(anchor) for anchor in printed} == printed
    # The answered page decides the answer, not the fence: its lines differ from the plain print's.
    assert answered is (printed != printed_verdicts["plain"])
    reader.clean()
