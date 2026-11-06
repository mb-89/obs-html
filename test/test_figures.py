"""Plot figures drawn from the Document's FigureDescriptors."""
import copy
import html as html_module
import json
import re

import pytest

from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render
from obs_html.artifact_data import decode_artifact_data


CONFIG = load_config()


def _appendix(document) -> str:
    data = decode_artifact_data(render(document, CONFIG))
    return next(note for note in data["notes"] if note["slug"] == "appendix")["html"]


def _descriptors(document) -> dict:
    appendix = next(chapter for chapter in document["chapters"] if chapter["id"] == "appendix")
    descriptors = [node["children"][0]["attrs"]["descriptor"] for node in appendix["content"]
                   if node["type"] == "figures" and node["attrs"]["kind"] == "plot"]
    return {descriptor["id"]: descriptor for descriptor in descriptors}


def _spec(html: str, kind: str) -> dict:
    encoded = re.search(rf'data-figure-kind="{kind}"[^>]*? data-figure-spec="([^"]*)"', html).group(1)
    return json.loads(html_module.unescape(encoded))


def test_trace_descriptors_become_plotly_figures_on_their_panel_axes(document) -> None:
    html = _appendix(document)
    assert 'id="appendix--figure-response"' in html
    spec = _spec(html, "plot")
    assert [trace["name"] for trace in spec["data"]] == ["measured", "model"]
    assert spec["data"][1]["mode"] == "lines+markers"
    assert spec["data"][0]["x"] == [0, 1, 2] and spec["data"][0]["y"] == [1, 4, 9]
    assert spec["layout"]["xaxis"] == {"title": {"text": "Time"}, "type": "linear", "range": [0, 2],
                                       "domain": [0.0, 1.0]}
    assert spec["layout"]["yaxis"]["type"] == "log" and spec["layout"]["yaxis"]["range"] == [0.0, 1.0]


def test_plot_figures_embed_plotly_with_its_licence_only_when_needed(document) -> None:
    artifact = render(document, CONFIG)
    assert 'id="plotly-script"' in artifact and "Plotly" in artifact
    assert 'id="figure-script"' in artifact and 'id="figure-styles"' in artifact
    without = copy.deepcopy(document)
    appendix = next(chapter for chapter in without["chapters"] if chapter["id"] == "appendix")
    appendix["content"] = [node for node in appendix["content"] if node["type"] != "figures"]
    plain = render(without, CONFIG)
    assert 'id="plotly-script"' not in plain and 'id="figure-script"' not in plain


def test_multi_panel_descriptors_place_axes_by_grid(document) -> None:
    descriptor = _descriptors(document)["response"]
    second = copy.deepcopy(descriptor["panels"][0])
    second["id"] = "detail"
    second["grid"] = {"row": 1, "column": 0, "rowSpan": 1, "columnSpan": 1}
    descriptor["panels"].append(second)
    descriptor["data"]["traces"][1]["panel"] = "detail"
    spec = _spec(_appendix(document), "plot")
    assert spec["layout"]["yaxis"]["domain"] == [0.5, 1.0]
    assert spec["layout"]["yaxis2"]["domain"] == [0.0, 0.5]
    assert spec["layout"]["xaxis2"]["anchor"] == "y2"
    assert (spec["data"][1]["xaxis"], spec["data"][1]["yaxis"]) == ("x2", "y2")


def test_sankey_descriptors_render_a_static_svg_and_the_runtime_spec(document) -> None:
    html = _appendix(document)
    assert 'id="appendix--figure-flow"' in html
    assert html.count('class="sankey-node"') == 3
    assert 'aria-label="flow"' in html
    spec = _spec(html, "sankey")
    assert [link["value"] for link in spec["links"]] == [8, 2]


@pytest.mark.parametrize("change, field", [
    (lambda data: data.clear(), "figure.data"),
    (lambda data: data["traces"].append({"x": [1], "y": []}), "figure.data.traces[2]"),  # After its two traces.
    (lambda data: data["traces"][0].update(panel="nowhere"), "figure.data.traces[0].panel"),
])
def test_invalid_plot_data_fails_naming_the_note_and_the_descriptor_field(document, change, field) -> None:
    change(_descriptors(document)["response"]["data"])
    with pytest.raises(InputError) as failure:
        render(document, CONFIG)
    assert (failure.value.source, failure.value.field) == ("appendix.md", field)


def test_invalid_sankey_graphs_fail(document) -> None:
    _descriptors(document)["flow"]["data"]["sankey"]["links"][0]["target"] = "missing"
    with pytest.raises(InputError) as failure:
        render(document, CONFIG)
    assert (failure.value.source, failure.value.field) == ("appendix.md", "figure.data.sankey.links[0].target")


def test_log_axes_need_positive_limits(document) -> None:
    _descriptors(document)["response"]["panels"][0]["axes"][1]["limits"]["minimum"] = 0
    with pytest.raises(InputError) as failure:
        render(document, CONFIG)
    assert (failure.value.source, failure.value.field) == ("appendix.md", "figure.panels[0].axes[1].limits")
