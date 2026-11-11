"""Equation figures, plotted live in the reader (figures.py, the equations kind; equations.js;
artifact-ui.md, Equation figures).

Reader: whoever changes how an equation figure is evaluated, sampled, solved or explored.

One artifact of the equations fixture Document (fixtures/build_documents.py, equations) serves
every test, and the checks that only read what it plotted share one page of it: the torque family over a quantity note's range with a second axis, the saturated
oscillator the core leaves as a differential system, and the quintic it leaves for Newton's
method; in a second chapter, which computes only where a test opens it, a step response swept
over a grid with computed axes and a grid of 8000 combinations above the parallel plot's cap.
Every page runs with every request outside the artifact refused and recorded.
"""
import cmath
import json
import math
from pathlib import Path

import pytest

import library_fakes
from conftest import CORE_ROOT, ROOT, built_once
from obs_html import cli


EQUATIONS = ROOT / "test" / "fixtures" / "documents" / "equations.json"
VECTORS = CORE_ROOT / "test" / "fixtures" / "expression-vectors.json"
TORQUE, SATURATED, QUINTIC = "curves--block-torque", "curves--block-saturated", "curves--block-quintic"

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def artifact(tmp_path_factory) -> Path:
    def build(folder: Path) -> None:
        assert cli.main([str(EQUATIONS), str(folder / "artifact.html")]) == 0

    with library_fakes.real():  # Its subject is what math.js and Plotly compute and draw.
        return built_once(tmp_path_factory, "equations-artifact", build) / "artifact.html"


class Reader:
    """A page of the artifact whose requests beyond the file itself are refused and recorded, opened
    on ``chapter`` once its figures ``anchors`` have plotted; a chapter computes only once opened."""

    def __init__(self, reader_browser, artifact: Path, chapter: str = "curves",
                 anchors: tuple[str, ...] = (TORQUE, SATURATED, QUINTIC)):
        self.page = reader_browser.new_page(viewport={"width": 1200, "height": 1000})
        self.requests: list[str] = []

        def refuse(route):
            self.requests.append(route.request.url)
            route.abort()

        self.page.route("**/*", lambda route: route.continue_()
                        if route.request.url.startswith(("file:", "data:", "blob:")) else refuse(route))
        self.errors: list[str] = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(artifact.as_uri())
        self.page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
        self.page.evaluate(f"obsPages.setPaged(false); obsArtifact.activateChapter('{chapter}')")
        for anchor in anchors:
            self.page.wait_for_selector(f"#{anchor}.figure-plot-ready")

    def traces(self, anchor: str) -> list[dict]:
        return self.page.evaluate("""anchor => document.getElementById(anchor).querySelector('.figure-chart')
            .data.map(trace => ({name: trace.name, x: trace.x, y: trace.y, xaxis: trace.xaxis || 'x',
                                 yaxis: trace.yaxis || 'y'}))""", anchor)

    def layout(self, anchor: str) -> dict:
        return self.page.evaluate("""anchor => {
            const layout = document.getElementById(anchor).querySelector('.figure-chart')._fullLayout;
            const axis = name => layout[name] && {title: layout[name].title.text, side: layout[name].side,
                                                 range: layout[name].range};
            return {xaxis: axis('xaxis'), yaxis: axis('yaxis'), yaxis2: axis('yaxis2'), xaxis2: axis('xaxis2')};
        }""", anchor)

    def draws(self, anchor: str) -> int:
        return int(self.page.evaluate("anchor => document.getElementById(anchor).dataset.equationDraws", anchor))

    def wait_for_draw(self, anchor: str, after: int) -> None:
        self.page.wait_for_function(
            "([anchor, after]) => Number(document.getElementById(anchor).dataset.equationDraws) > after "
            "&& !document.getElementById(anchor).classList.contains('equation-computing')", arg=[anchor, after])

    def menu(self, anchor: str):
        figure = self.page.locator(f"#{anchor}")
        figure.locator(":scope > .options-menu-toggle").click()
        return figure.locator(".options-menu")

    def clean(self) -> None:
        assert self.requests == []
        assert self.errors == []


@pytest.fixture(scope="module")
def shared_reader(artifact, shared_reader_browser) -> Reader:
    """One page of the artifact for the module's checks that only read what it plotted and computed."""
    return Reader(shared_reader_browser, artifact)


def _torque(speed_rpm: float, throttle: float) -> float:
    return 250 * throttle * (1 - (speed_rpm / 6000) ** 2)


def test_the_torque_family_renders_from_the_document_with_the_network_blocked(shared_reader) -> None:
    reader = shared_reader

    traces = reader.traces(TORQUE)
    layout = reader.layout(TORQUE)

    assert [trace["name"] for trace in traces] == [
        f"{y}, throttle = {value}" for value in (0.25, 0.5, 1) for y in ("T", "T*n")]
    for index, throttle in enumerate((0.25, 0.5, 1)):
        torque, power = traces[2 * index], traces[2 * index + 1]
        assert torque["x"][0] == pytest.approx(800) and torque["x"][-1] == pytest.approx(6000)
        for speed, value in zip(torque["x"], torque["y"]):
            assert value == pytest.approx(_torque(speed, throttle), rel=1e-9)
        assert (torque["yaxis"], power["yaxis"]) == ("y", "y2")
        # T*n is in SI: N*m times rad/s.
        speed, value = power["x"][120], power["y"][120]
        assert value == pytest.approx(_torque(speed, throttle) * speed * 2 * math.pi / 60, rel=1e-9)
    assert layout["xaxis"]["title"] == "n [rpm]"
    assert layout["yaxis"]["title"].startswith("T [") and layout["yaxis"]["side"] == "left"
    assert layout["yaxis2"]["title"].startswith("T*n [") and layout["yaxis2"]["side"] == "right"
    reader.clean()


def _inside(trace: dict, low: float, high: float) -> int:
    return sum(low <= x <= high for x, y in zip(trace["x"], trace["y"]) if y is not None)


def test_zooming_in_samples_the_visible_range_again(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact)
    before = _inside(reader.traces(TORQUE)[0], 2000, 2500)
    draws = reader.draws(TORQUE)

    reader.page.evaluate("Plotly.relayout(document.querySelector('#curves--block-torque .figure-chart'), "
                         "{'xaxis.range': [2000, 2500]})")
    reader.wait_for_draw(TORQUE, draws)
    after = reader.traces(TORQUE)[0]

    assert before < 30
    assert _inside(after, 2000, 2500) > 200
    for speed, value in zip(after["x"], after["y"]):
        assert value == pytest.approx(_torque(speed, 0.25), rel=1e-9)
    reader.clean()


def _saturated(times: list[float], zeta=0.3, w=2.0, u=1.5, step=1e-3) -> list[float]:
    """The saturated oscillator y'' + 2 zeta w y' + w^2 min(max(y, -1), 1) = w^2 u from rest,
    integrated by classical Runge-Kutta with a fixed small step: the reference curve."""
    def rate(state):
        y, slope = state
        return slope, w * w * u - w * w * min(max(y, -1), 1) - 2 * zeta * w * slope

    def rk4(state, h):
        k1 = rate(state)
        k2 = rate([s + h / 2 * k for s, k in zip(state, k1)])
        k3 = rate([s + h / 2 * k for s, k in zip(state, k2)])
        k4 = rate([s + h * k for s, k in zip(state, k3)])
        return [s + h / 6 * (a + 2 * b + 2 * c + d) for s, a, b, c, d in zip(state, k1, k2, k3, k4)]

    state, time, values = [0.0, 0.0], 0.0, []
    for target in times:
        while time < target - 1e-12:
            h = min(step, target - time)
            state, time = rk4(state, h), time + h
        values.append(state[0])
    return values


def test_the_numeric_systems_plot_through_the_integrator_and_newtons_method(shared_reader) -> None:
    reader = shared_reader

    [oscillator] = reader.traces(SATURATED)
    [quintic] = reader.traces(QUINTIC)

    assert oscillator["x"][0] == 0 and oscillator["x"][-1] == pytest.approx(10)
    assert oscillator["y"] == pytest.approx(_saturated(oscillator["x"]), abs=1e-6)
    assert max(oscillator["y"]) > 1  # The saturation lets the response overshoot past y = 1.
    assert len(quintic["x"]) == 241 and None not in quintic["y"]
    for a, y in zip(quintic["x"], quintic["y"]):
        assert y ** 5 + y == pytest.approx(a, abs=1e-9)
    reader.clean()


def test_the_shared_test_vectors_pass_in_the_browser(shared_reader) -> None:
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
    reader = shared_reader

    results = reader.page.evaluate("""vectors => vectors.map(vector =>
        obsEquations.evaluate(vector.tree, vector.values, vector.derivatives || []))""", vectors["vectors"])

    assert len(results) == len(vectors["vectors"]) >= 25
    for vector, result in zip(vectors["vectors"], results):
        if vector["expected"] is None:
            assert result is None, vector["name"]
        else:
            assert result == pytest.approx(vector["expected"], rel=vectors["tolerance"], abs=1e-12), vector["name"]
    reader.clean()


def test_the_menu_adds_a_trace_over_the_figures_variables(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact)
    menu = reader.menu(QUINTIC)
    draws = reader.draws(QUINTIC)

    menu.get_by_label("Expression").fill("frobnicate(y)")
    menu.get_by_role("button", name="Add trace").click()
    refused = menu.get_by_role("alert").inner_text()
    menu.get_by_label("Expression").fill("2*y - a/10")
    menu.get_by_role("button", name="Add trace").click()
    reader.wait_for_draw(QUINTIC, draws)
    traces = reader.traces(QUINTIC)

    assert "frobnicate" in refused and "y" in refused
    assert [trace["name"] for trace in traces] == ["y", "2*y - a/10"]
    for a, y, added in zip(traces[0]["x"], traces[0]["y"], traces[1]["y"]):
        assert added == pytest.approx(2 * y - a / 10, rel=1e-9, abs=1e-12)
    assert reader.page.evaluate("JSON.stringify(Object.entries(localStorage).sort())").count("2*y") == 0
    reader.clean()


def test_the_menu_puts_the_second_y_axis_on_the_left_or_a_trace_on_it(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact)
    menu = reader.menu(TORQUE)
    draws = reader.draws(TORQUE)

    menu.get_by_label("Second y axis", exact=True).select_option("left")
    reader.wait_for_draw(TORQUE, draws)
    sides = reader.layout(TORQUE)
    draws = reader.draws(TORQUE)
    menu.get_by_label("T*n on y axis", exact=True).select_option("primary")
    reader.wait_for_draw(TORQUE, draws)

    assert (sides["yaxis2"]["side"], sides["yaxis"]["side"]) == ("left", "right")
    assert {trace["yaxis"] for trace in reader.traces(TORQUE)} == {"y"}
    assert reader.layout(TORQUE)["yaxis2"] is None
    reader.clean()


def test_the_menu_swaps_x_and_y(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact)
    [before] = reader.traces(QUINTIC)
    draws = reader.draws(QUINTIC)

    reader.menu(QUINTIC).get_by_role("button", name="Swap x and y").click()
    reader.wait_for_draw(QUINTIC, draws)
    [after] = reader.traces(QUINTIC)

    assert (after["x"], after["y"]) == (before["y"], before["x"])
    assert reader.layout(QUINTIC)["yaxis"]["title"] == "a" and reader.layout(QUINTIC)["xaxis"]["title"] == "y"
    reader.clean()


def test_the_menu_draws_a_family_over_a_third_variable_with_progress(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact)
    menu = reader.menu(SATURATED)
    draws = reader.draws(SATURATED)
    reader.page.evaluate("""() => {
        window.progressSeen = [];
        new MutationObserver(() => {
            const status = document.querySelector('#curves--block-saturated .equation-progress');
            if (status && !status.hidden) window.progressSeen.push(status.textContent);
        }).observe(document.getElementById('curves--block-saturated'),
                   {subtree: true, childList: true, characterData: true, attributes: true});
    }""")

    menu.get_by_label("Family over").select_option("zeta")
    menu.get_by_label("By", exact=True).select_option("steps")
    menu.get_by_label("Steps or values").fill("8")
    menu.get_by_role("button", name="Apply family").click()
    reader.wait_for_draw(SATURATED, draws)
    traces = reader.traces(SATURATED)
    seen = reader.page.evaluate("window.progressSeen")

    assert [trace["name"] for trace in traces] == [
        f"y, zeta = {value:g}" for value in (0.05, 0.328571, 0.607143, 0.885714, 1.16429, 1.44286, 1.72143, 2)]
    assert traces[0]["y"] == pytest.approx(_saturated(traces[0]["x"], zeta=0.05), abs=1e-6)
    assert any(text.startswith("Computing curve") and text.endswith("of 8…") for text in seen), seen
    assert reader.page.locator(f"#{SATURATED} .equation-progress").is_hidden()
    reader.clean()


def test_print_shows_the_readers_view_with_a_note_where_it_changed(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact)
    draws = reader.draws(QUINTIC)
    reader.menu(QUINTIC).get_by_role("button", name="Swap x and y").click()
    reader.wait_for_draw(QUINTIC, draws)

    reader.page.evaluate("window.print = () => {}; obsPages.exportPDF()")
    reader.page.wait_for_selector(".print-book [data-figure-kind='equations'] > img.figure-default")
    captions = reader.page.evaluate("""() => Object.fromEntries([...document.querySelectorAll(
        ".print-book [data-figure-kind='equations']")].map(figure => [
            figure.querySelector('figcaption').textContent.includes('View changed by the reader.')
              ? 'changed' : 'initial', figure.querySelector(':scope > img').src.startsWith('data:image/svg')]))""")

    assert captions == {"changed": True, "initial": True}
    assert reader.page.locator(".print-book [data-figure-kind='equations'] figcaption",
                               has_text="View changed by the reader.").count() == 1
    reader.clean()


STEP, CAP = "sweeps--block-step", "sweeps--block-cap"
CFG = ROOT / "src" / "obs_html" / "cfg.json"


def _step_response(zeta: float, w: float, times: list[float]) -> list[float]:
    """y'' + 2 zeta w y' + w^2 y = w^2 from rest, in closed form (complex where overdamped)."""
    root = cmath.sqrt(1 - zeta * zeta)
    return [(1 - cmath.exp(-zeta * w * t) * (cmath.cos(w * root * t) + zeta / root * cmath.sin(w * root * t))).real
            for t in times]


def _settling(times: list[float], values: list[float], tolerance: float) -> float:
    """The first sampled time after which the curve stays within tolerance * |final - first| of its final value."""
    final, band = values[-1], tolerance * abs(values[-1] - values[0])
    outside = [index for index, value in enumerate(values) if abs(value - final) > band]
    return times[outside[-1] + 1] if outside else times[0]


def _absolute_area(times: list[float], values: list[float]) -> float:
    area = 0.0
    for t0, t1, a, b in zip(times, times[1:], values, values[1:]):
        area += (t1 - t0) * ((a * a + b * b) / (2 * (abs(a) + abs(b))) if a * b < 0 else abs(a + b) / 2)
    return area


def _axis(reader: Reader, anchor: str, label: str) -> dict:
    return reader.page.evaluate("""([anchor, label]) => {
        const axis = [...document.querySelectorAll(`#${anchor} .parallel-axis`)].find(item => item.dataset.label === label);
        const line = axis.querySelector('.parallel-axis-line').getBoundingClientRect();
        const name = axis.querySelector('.parallel-axis-label').getBoundingClientRect();
        return {min: Number(axis.dataset.min), max: Number(axis.dataset.max), distinct: Number(axis.dataset.distinct),
                top: line.top, bottom: line.bottom, x: line.left,
                label: {x: name.left + name.width / 2, y: name.top + name.height / 2},
                bins: [...axis.querySelectorAll('.parallel-histogram rect')].map(bar => Number(bar.dataset.count))};
    }""", [anchor, label])


def _plot(reader: Reader, anchor: str) -> dict:
    return reader.page.evaluate("""anchor => {
        const plot = document.querySelector(`#${anchor} .equation-parallel`);
        const warning = plot.querySelector('.equation-parallel-warning');
        return {hidden: plot.hidden, combinations: Number(plot.dataset.combinations), total: Number(plot.dataset.total),
                cap: Number(plot.dataset.cap), warning: !warning.hidden && warning.textContent,
                labels: [...plot.querySelectorAll('.parallel-axis')].map(axis => axis.dataset.label)};
    }""", anchor)


def _drawn(reader: Reader, anchor: str) -> set[str]:
    """The combinations the curves below draw: the label each curve's points carry."""
    return {text for trace in reader.page.evaluate("""anchor => document.getElementById(anchor)
        .querySelector('.figure-chart').data.map(trace => trace.text || [])""", anchor) for text in trace if text}


def test_parallel_coordinates_select_curves_by_computed_axes_and_cap_the_grid(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact, "sweeps", (STEP,))
    page = reader.page
    times = [10 * index / 240 for index in range(241)]
    zetas, ws = (0.2, 0.5, 0.8, 1.3), (1, 1.5, 2, 2.5, 3)
    combinations = {f"zeta = {zeta:g}, w = {w:g} 1/s": _step_response(zeta, w, times) for zeta in zetas for w in ws}
    settling = {label: _settling(times, values, 0.02) for label, values in combinations.items()}
    error = {label: _absolute_area(times, [1 - value for value in values]) for label, values in combinations.items()}

    # The fence shows the plot: the 20 combinations, below the cap, each drawn as a curve.
    shown = _plot(reader, STEP)
    rows = page.evaluate(f"obsEquations.parallelTable(document.getElementById('{STEP}'))")
    assert (shown["hidden"], shown["combinations"], shown["warning"]) == (False, 20, False)
    assert shown["labels"] == ["zeta", "w", "settling", "error area"]
    assert _drawn(reader, STEP) == set(combinations)
    # The computed axes hold each combination's settling time and error area.
    assert {row["label"]: row["values"][2] for row in rows} == pytest.approx(settling, abs=1e-9)
    assert {row["label"]: row["values"][3] for row in rows} == pytest.approx(error, rel=1e-6)
    # Every axis shows a histogram of the combinations' values.
    for label in shown["labels"]:
        assert sum(_axis(reader, STEP, label)["bins"]) == 20, label

    # Dragging along the settling axis from its bottom selects the shortest settling times.
    ordered = sorted(settling.values())
    gap = max(range(3, 11), key=lambda index: ordered[index] - ordered[index - 1])
    axis = _axis(reader, STEP, "settling")
    height = axis["bottom"] - axis["top"]
    threshold = (ordered[gap] + ordered[gap - 1]) / 2
    assert (ordered[gap] - ordered[gap - 1]) / (axis["max"] - axis["min"]) * height > 6
    draws = reader.draws(STEP)
    page.mouse.move(axis["x"], axis["bottom"] + 4)
    page.mouse.down()
    page.mouse.move(axis["x"], axis["bottom"] - (threshold - axis["min"]) / (axis["max"] - axis["min"]) * height,
                    steps=4)
    page.mouse.up()
    reader.wait_for_draw(STEP, draws)
    shortest = {label for label, value in settling.items() if value < threshold}
    assert len(shortest) == gap
    assert _drawn(reader, STEP) == shortest

    # Above the cap: 3 axes of 20 values; the plot opens from the menu and warns, thinning the rightmost axis.
    cap = json.loads(CFG.read_text(encoding="utf-8"))["artifact"]["figures"]["parallelCoordinatesCap"]
    assert _plot(reader, CAP)["hidden"] is True
    draws = reader.draws(CAP)
    page.evaluate(f"document.getElementById('{CAP}').scrollIntoView({{block: 'start'}})")
    reader.menu(CAP).get_by_role("button", name="Parallel coordinates").click()
    reader.wait_for_draw(CAP, draws)
    capped = _plot(reader, CAP)
    assert (capped["hidden"], capped["total"], capped["cap"]) == (False, 8000, cap)
    assert capped["warning"] and capped["combinations"] <= cap
    assert [_axis(reader, CAP, label)["distinct"] for label in "abc"] == [20, 20, cap // 400]
    for label in "abc":
        assert sum(_axis(reader, CAP, label)["bins"]) == capped["combinations"], label
    # Dragging axis a to the right of c makes a the axis the cap thins.
    page.keyboard.press("Escape")
    a, c = _axis(reader, CAP, "a"), _axis(reader, CAP, "c")
    draws = reader.draws(CAP)
    page.mouse.move(a["label"]["x"], a["label"]["y"])
    page.mouse.down()
    page.mouse.move(c["label"]["x"] + 40, a["label"]["y"], steps=6)
    page.mouse.up()
    reader.wait_for_draw(CAP, draws)
    assert _plot(reader, CAP)["labels"] == ["b", "c", "a"]
    assert [_axis(reader, CAP, label)["distinct"] for label in "abc"] == [cap // 400, 20, 20]
    assert reader.page.evaluate("JSON.stringify(Object.entries(localStorage).sort())").count("parallel") == 0
    reader.clean()
