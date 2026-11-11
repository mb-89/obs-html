"""The one figure frame: every figure kind is framed alike (figures.py, artifact-ui.md One figure
frame). The fixture Document has one figure of each kind (fixtures/build_documents.py, figures).

Reader: whoever changes the frame or adds a figure kind.
"""
import json
import re
from html import unescape
from pathlib import Path

import pytest

import library_fakes
from conftest import ROOT, built_once
from obs_html import cli
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.figures import FIGURE_KINDS
from obs_html.render import render


FIGURES = ROOT / "test" / "fixtures" / "documents" / "figures.json"
KINDS = ("image", "svg", "sankey", "plot", "mermaid", "plantuml", "equations", "pugh")
FIGURE = re.compile(r'<figure class="obs-figure figure-(\w+)" data-artifact-figure data-figure-kind="\1"'
                    r' id="([^"]+)"[^>]*>(.*?)</figure>', re.S)


def _gallery() -> str:
    document = json.loads(FIGURES.read_text(encoding="utf-8"))
    data = decode_artifact_data(render(document, load_config()))
    return next(note for note in data["notes"] if note["slug"] == "gallery")["html"]


def test_every_kind_has_the_one_frame_with_its_caption_last_and_numbered() -> None:
    figures = FIGURE.findall(_gallery())

    assert [kind for kind, _, _ in figures] == list(KINDS)
    assert set(FIGURE_KINDS) == set(KINDS)
    for index, (kind, anchor, inner) in enumerate(figures, start=1):
        assert anchor == f"gallery--block-{kind}-figure"
        assert inner.count("<figcaption>") == 1 and inner.endswith("</figcaption>"), kind
        caption = inner[inner.index("<figcaption>"):]
        assert caption.startswith(f'<figcaption><span class="figure-number">Figure 1.{index}:</span> '
                                  f"The {kind} figure, see "), kind
        assert 'data-chapter-link="gallery"' in caption or "gallery" in caption


@pytest.fixture(scope="module")
def figures_artifact(tmp_path_factory) -> Path:
    def build(folder: Path) -> None:
        assert cli.main([str(FIGURES), str(folder / "artifact.html")]) == 0

    with library_fakes.real():  # Its subject is the legend Plotly lays out and draws.
        return built_once(tmp_path_factory, "figures-artifact", build) / "artifact.html"


def _open(reader_browser, artifact: Path):
    page = reader_browser.new_page(viewport={"width": 1200, "height": 1000})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('gallery')")
    page.wait_for_selector(".obs-figure[data-figure-kind='plot'].figure-plot-ready")
    page.wait_for_selector(".obs-figure[data-figure-kind='equations'].figure-plot-ready")
    return page, errors


FRAME = """() => [...document.querySelectorAll('.obs-figure')].map(figure => {
    const style = getComputedStyle(figure);
    const caption = figure.querySelector(':scope > figcaption');
    const body = caption.previousElementSibling;  // The kind's body comes before its caption.
    return {
        kind: figure.dataset.figureKind,
        tag: figure.tagName,
        captions: figure.querySelectorAll('figcaption').length,
        captionBelow: caption.getBoundingClientRect().top >= body.getBoundingClientRect().bottom - 1,
        captionAlign: getComputedStyle(caption).textAlign,
        expand: figure.querySelectorAll(':scope > .figure-expand').length,
        frame: [style.borderTopStyle, style.borderTopWidth, style.borderBottomStyle, style.paddingTop,
                style.width],
        left: style.borderLeftWidth + ' ' + style.borderLeftStyle + ' ' + style.borderLeftColor,
    };
})"""


@pytest.mark.browser
def test_every_kind_shows_the_same_frame_caption_position_and_expand_button(
    figures_artifact, reader_browser,
) -> None:
    page, errors = _open(reader_browser, figures_artifact)

    frames = page.evaluate(FRAME)

    assert [frame["kind"] for frame in frames] == list(KINDS)
    assert {frame["tag"] for frame in frames} == {"FIGURE"}
    assert [frame["captions"] for frame in frames] == [1] * len(KINDS)
    assert all(frame["captionBelow"] for frame in frames), frames
    assert {frame["captionAlign"] for frame in frames} == {"center"}
    assert [frame["expand"] for frame in frames] == [1] * len(KINDS)
    assert len({json.dumps(frame["frame"]) for frame in frames}) == 1, frames
    assert errors == []


@pytest.mark.browser
def test_a_border_token_set_once_frames_every_kind(figures_artifact, reader_browser) -> None:
    page, errors = _open(reader_browser, figures_artifact)

    page.evaluate("document.documentElement.style.setProperty("
                  "'--figure-frame-border-inline', '3px solid rgb(200, 0, 0)')")
    frames = page.evaluate(FRAME)

    assert [frame["left"] for frame in frames] == ["3px solid rgb(200, 0, 0)"] * len(KINDS)
    assert errors == []


@pytest.mark.browser
def test_only_kinds_with_options_show_the_tables_options_menu_whose_changes_stay_in_the_view(
    figures_artifact, reader_browser,
) -> None:
    page, errors = _open(reader_browser, figures_artifact)
    menus = page.evaluate("""() => [...document.querySelectorAll('.obs-figure')].map(figure => [
        figure.dataset.figureKind,
        figure.querySelectorAll(':scope > .figure-expand').length,
        figure.querySelectorAll(':scope > .options-menu-toggle').length])""")
    stored = page.evaluate("JSON.stringify(Object.entries(localStorage).sort())")

    plot = page.locator(".obs-figure[data-figure-kind='plot']")
    plot.locator(":scope > .options-menu-toggle").click()
    plot.locator(".options-menu").get_by_role("button", name="Legend").click()
    page.wait_for_function("!document.querySelector(\".obs-figure[data-figure-kind='plot'] g.legend\")")

    assert menus == [[kind, 1, int(FIGURE_KINDS[kind].options != ())] for kind in KINDS]
    assert [kind for kind in KINDS if FIGURE_KINDS[kind].options] == ["plot", "equations", "pugh"]
    assert plot.locator(".options-menu").get_by_role("button", name="Legend").get_attribute("aria-pressed") == "false"
    assert page.evaluate("JSON.stringify(Object.entries(localStorage).sort())") == stored  # Nothing is saved.
    assert errors == []


def test_tables_and_figures_build_their_options_menu_from_one_component() -> None:
    package = ROOT / "src" / "obs_html"
    for script in ("table.js", "figures.js"):
        assert "globalThis.obsOptionsMenu({" in (package / script).read_text(encoding="utf-8"), script


def test_an_equation_figure_is_framed_with_its_live_body_and_spec() -> None:
    """The core's equations kind (capability equation-figures) renders in the one frame: a live
    body whose spec is the Document's body, which equations.js plots."""
    [(kind, anchor, inner)] = [figure for figure in FIGURE.findall(_gallery()) if figure[0] == "equations"]
    document = json.loads(FIGURES.read_text(encoding="utf-8"))
    [body] = [item["children"][0]["attrs"] for chapter in document["chapters"] for item in chapter["content"]
              if item["type"] == "figures" and item["attrs"]["kind"] == "equations"]
    spec = re.search(r'data-figure-spec="([^"]+)"', _gallery().split(f'id="{anchor}"')[1]).group(1)

    assert inner.startswith('<div class="figure-live" aria-label="Interactive figure"></div>')
    assert json.loads(unescape(spec)) == {"kind": "equations", "alt": "The equations figure, see Gallery.", **body}


PLOT = ".obs-figure[data-figure-kind='plot'] .js-plotly-plot"
# The plot's legend box and its chart's box, as [left, top, right, bottom] each.
LEGEND_AND_CHART = f"""() => {{
    const chart = document.querySelector("{PLOT}");
    const box = element => {{ const r = element.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }};
    return [box(chart.querySelector("g.legend")), box(chart)];
}}"""
LEGEND_INSIDE = f"""() => {{
    const chart = document.querySelector("{PLOT}");
    const legend = chart.querySelector("g.legend").getBoundingClientRect(), bounds = chart.getBoundingClientRect();
    return legend.left >= bounds.left - 1 && legend.right <= bounds.right + 1
        && legend.top >= bounds.top - 1 && legend.bottom <= bounds.bottom + 1;
}}"""


@pytest.mark.browser
def test_a_legend_laid_out_past_the_plot_is_moved_back_inside_again_after_a_resize(
    figures_artifact, reader_browser,
) -> None:
    page, errors = _open(reader_browser, figures_artifact)
    page.locator(PLOT).scroll_into_view_if_needed()

    page.evaluate(f"Plotly.relayout(document.querySelector(\"{PLOT}\"), {{'legend.x': 3, 'legend.y': 1}})")
    page.wait_for_function(LEGEND_INSIDE, timeout=3000)
    page.set_viewport_size({"width": 900, "height": 900})
    page.wait_for_function(f"document.querySelector(\"{PLOT}\")._fullLayout.width < 900")
    page.evaluate(f"Plotly.relayout(document.querySelector(\"{PLOT}\"), {{'legend.x': -2, 'legend.y': 1}})")
    page.wait_for_function(LEGEND_INSIDE, timeout=3000)

    assert errors == [], page.evaluate(LEGEND_AND_CHART)


# Resolves, with the afterplot count so far, after a few timer turns and frames.
FRAMES_LATER = """() => new Promise(resolve => setTimeout(() => requestAnimationFrame(() =>
    requestAnimationFrame(() => setTimeout(() => resolve(globalThis.legendRelayouts), 100))), 100))"""


@pytest.mark.browser
def test_a_legend_whose_box_never_moves_leaves_the_page_answering(figures_artifact, reader_browser) -> None:
    page, errors = _open(reader_browser, figures_artifact)
    page.locator(PLOT).scroll_into_view_if_needed()
    # The legend's box reads the same, out of the chart's bounds, whatever the correction does:
    # every relayout re-runs the correction, which must notice that it changed nothing.
    page.evaluate(f"""() => {{
        const chart = document.querySelector("{PLOT}");
        const bounds = chart.getBoundingClientRect();
        SVGGElement.prototype.getBoundingClientRect = function () {{
            return new DOMRect(bounds.left - 400, bounds.top - 300, 100, 60);
        }};
        globalThis.legendRelayouts = 0;
        chart.on("plotly_afterplot", () => globalThis.legendRelayouts++);
        setTimeout(() => Plotly.relayout(chart, {{"legend.x": 0.5}}));
    }}""")

    # A page whose main thread locks never answers: the test then runs past its tier's timeout
    # (test/bounds.py), which fails it and ends the pool's browser (test/conftest.py, PagePool).
    settled = page.evaluate(FRAMES_LATER)
    page.evaluate(FRAMES_LATER)

    assert settled <= 3 and page.evaluate("legendRelayouts") == settled, settled
    assert errors == []
