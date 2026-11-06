"""Equation figures, plotted live in the reader (figures.py, the equations kind; equations.js;
artifact-ui.md, Equation figures).

Reader: whoever changes how an equation figure is evaluated, sampled, solved or explored.

One artifact of the equations fixture Document (fixtures/build_documents.py, equations) serves
every test: the torque family over a quantity note's range with a second axis, the saturated
oscillator the core leaves as a differential system, and the quintic it leaves for Newton's
method. Every page runs with every request outside the artifact refused and recorded.
"""
import json
import math
from pathlib import Path

import pytest

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

    return built_once(tmp_path_factory, "equations-artifact", build) / "artifact.html"


class Reader:
    """A page of the artifact whose requests beyond the file itself are refused and recorded."""

    def __init__(self, reader_browser, artifact: Path):
        context = reader_browser.new_context(viewport={"width": 1200, "height": 1000})
        self.requests: list[str] = []

        def refuse(route):
            self.requests.append(route.request.url)
            route.abort()

        context.route("**/*", lambda route: route.continue_()
                      if route.request.url.startswith(("file:", "data:", "blob:")) else refuse(route))
        self.page = context.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(artifact.as_uri())
        self.page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
        self.page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('curves')")
        for anchor in (TORQUE, SATURATED, QUINTIC):
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


def _torque(speed_rpm: float, throttle: float) -> float:
    return 250 * throttle * (1 - (speed_rpm / 6000) ** 2)


def test_the_torque_family_renders_from_the_document_with_the_network_blocked(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact)

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


def test_the_numeric_systems_plot_through_the_integrator_and_newtons_method(artifact, reader_browser) -> None:
    reader = Reader(reader_browser, artifact)

    [oscillator] = reader.traces(SATURATED)
    [quintic] = reader.traces(QUINTIC)

    assert oscillator["x"][0] == 0 and oscillator["x"][-1] == pytest.approx(10)
    assert oscillator["y"] == pytest.approx(_saturated(oscillator["x"]), abs=1e-6)
    assert max(oscillator["y"]) > 1  # The saturation lets the response overshoot past y = 1.
    assert len(quintic["x"]) == 241 and None not in quintic["y"]
    for a, y in zip(quintic["x"], quintic["y"]):
        assert y ** 5 + y == pytest.approx(a, abs=1e-9)
    reader.clean()


def test_the_shared_test_vectors_pass_in_the_browser(artifact, reader_browser) -> None:
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
    reader = Reader(reader_browser, artifact)

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
