"""Byte-stable SVG export of the Document's FigureDescriptors."""
import copy
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ElementTree

import pytest

from obs_html.cli import main
from obs_html.figure_svg import document_figures, figure_svg
from obs_html.errors import InputError


SVG = "{http://www.w3.org/2000/svg}"


SOURCE = "appendix.md"
"""The note of the fixture's figure fences."""

def _descriptors(document) -> dict:
    return {descriptor["id"]: descriptor for _, descriptor, _ in document_figures(document)}


def _reordered(value):
    """The same JSON value with every object's keys in reverse order."""
    if isinstance(value, dict):
        return {key: _reordered(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reordered(item) for item in value]
    return value


@pytest.mark.parametrize("name", ["response", "flow"])
def test_the_same_descriptor_exports_identical_bytes(document, name) -> None:
    descriptor = _descriptors(document)[name]
    first = figure_svg(descriptor, SOURCE).encode("utf-8")
    assert figure_svg(copy.deepcopy(descriptor), SOURCE).encode("utf-8") == first
    assert figure_svg(_reordered(descriptor), SOURCE).encode("utf-8") == first


def test_exports_are_identical_across_processes_with_different_hash_seeds(document, tmp_path) -> None:
    path = tmp_path / "descriptors.json"
    path.write_text(json.dumps(list(_descriptors(document).values())), encoding="utf-8")
    script = ("import json, sys; from obs_html.figure_svg import figure_svg; "
              "sys.stdout.buffer.write(b''.join(figure_svg(d, 'appendix.md').encode() for d in "
              "json.load(open(sys.argv[1], encoding='utf-8'))))")
    outputs = {
        subprocess.run([sys.executable, "-c", script, str(path)], check=True, capture_output=True,
                       env={**os.environ, "PYTHONHASHSEED": seed}).stdout
        for seed in ("0", "1", "4242")
    }
    assert len(outputs) == 1


@pytest.mark.parametrize("name, change", [
    ("response", lambda d: d["data"]["traces"][0]["y"].__setitem__(1, 5)),
    ("response", lambda d: d["panels"][0]["axes"][0].__setitem__("label", "Seconds")),
    ("response", lambda d: d["panels"][0]["bounds"].__setitem__("width", 640)),
    ("flow", lambda d: d["data"]["sankey"]["links"][0].__setitem__("value", 7)),
    ("flow", lambda d: d["data"]["sankey"]["nodes"][0].__setitem__("label", "Supply")),
])
def test_a_changed_descriptor_changes_the_export(document, name, change) -> None:
    descriptor = _descriptors(document)[name]
    changed = copy.deepcopy(descriptor)
    change(changed)
    assert figure_svg(changed, SOURCE) != figure_svg(descriptor, SOURCE)


def test_trace_export_is_a_standalone_svg_of_the_panels(document) -> None:
    root = ElementTree.fromstring(figure_svg(_descriptors(document)["response"], SOURCE))
    assert root.tag == f"{SVG}svg"
    assert (root.get("width"), root.get("height"), root.get("viewBox")) == ("720", "320", "0 0 720 320")
    assert root.find(f"{SVG}title").text == "response"
    lines = root.findall(f".//{SVG}polyline")
    assert len(lines) == 2
    assert len(root.findall(f".//{SVG}circle")) == 3  # markers only for the lines+markers trace
    texts = [element.text for element in root.iter(f"{SVG}text")]
    assert "Time" in texts and "Value" in texts and "measured" in texts and "model" in texts
    # The log axis puts 1 at the bottom of the plot and 10 at its top.
    points = [tuple(map(float, point.split(","))) for point in lines[0].get("points").split()]
    assert points[0][1] > points[2][1]


def test_sankey_export_is_the_artifacts_static_drawing(document) -> None:
    root = ElementTree.fromstring(figure_svg(_descriptors(document)["flow"], SOURCE))
    assert root.tag == f"{SVG}svg"
    assert len(root.findall(f"{SVG}g[@class='sankey-node']")) == 3
    assert len(root.findall(f"{SVG}path[@class='sankey-link']")) == 2


def test_document_figures_are_named_like_their_artifact_anchors(document) -> None:
    assert [(name, source) for name, _, source in document_figures(document)] == [
        ("appendix--figure-response", SOURCE), ("appendix--figure-flow", SOURCE)]


def test_unsupported_descriptor_data_names_the_figure_and_the_remedy(document) -> None:
    descriptor = _descriptors(document)["response"]
    descriptor["data"] = {}
    with pytest.raises(InputError) as failure:
        figure_svg(descriptor, SOURCE)
    assert (failure.value.source, failure.value.field) == (SOURCE, "figure.data")


def test_cli_exports_every_figure_of_a_document(document, tmp_path, capsys) -> None:
    source = tmp_path / "document.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    folder = tmp_path / "figures"
    assert main([str(source), "--export-figures", str(folder)]) == 0
    first = {path.name: path.read_bytes() for path in folder.iterdir()}
    assert sorted(first) == ["appendix--figure-flow.svg", "appendix--figure-response.svg"]
    assert first["appendix--figure-response.svg"] == figure_svg(
        _descriptors(document)["response"], SOURCE).encode("utf-8")
    assert "Exported 2 figures" in capsys.readouterr().out
    assert main([str(source), "--export-figures", str(folder)]) == 0
    assert {path.name: path.read_bytes() for path in folder.iterdir()} == first


def test_cli_reports_a_document_without_figures(document, tmp_path, capsys) -> None:
    for chapter in document["chapters"]:
        chapter["content"] = [node for node in chapter["content"] if node["type"] != "figures"]
    source = tmp_path / "document.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(SystemExit):
        main([str(source), "--export-figures", str(tmp_path / "figures")])
    assert f"\n{source}: top level: " in f"\n{capsys.readouterr().err}"


def test_cli_refuses_export_figures_with_a_destination(document, tmp_path, capsys) -> None:
    source = tmp_path / "document.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(SystemExit):
        main([str(source), str(tmp_path / "out.html"), "--export-figures", str(tmp_path / "f")])
    assert "\nobs-html: DESTINATION: " in f"\n{capsys.readouterr().err}"
