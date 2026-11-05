"""DOM tier: the report verification harness (test/browser/report-harness.cjs) on a rendered report."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import ROOT
from documents import chapter, document, heading, node, paragraph
from obs_html.config import load_config
from obs_html.render import render


pytestmark = pytest.mark.dom
HARNESS = ROOT / "test" / "browser" / "report-harness.cjs"
TABLE = "items-base-1"
LETTER = {"widthMillimeters": 215.9, "heightMillimeters": 279.4, "marginMillimeters": 15}


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A report with two chapters, one Base table over three records, printed on Letter paper."""
    records = tuple({"id": name, "type": "note", "path": f"{name}.md", "fields": {"kind": "item", "rank": rank}}
                    for rank, name in enumerate(["alpha", "beta", "gamma"], 1))
    base = node("bases", source="filters: ...\n", spec={
        "filters": {"and": ['kind == "item"']},
        "views": [{"type": "table", "name": "Items", "order": ["file.name", "rank"],
                   "sort": [{"property": "rank", "direction": "DESC"}]}],
    })
    source = document(
        "Harness",
        chapter("intro", "Intro", heading(1, "Intro"), paragraph("Intro prose.")),
        chapter("items", "Items", heading(1, "Items"), paragraph("Items prose."), base),
        abstract=(node("profiles", profile={"print": {"paper": "Letter", "margin": "15mm"}}),),
        records=records,
    )
    path = tmp_path_factory.mktemp("harness") / "report.html"
    path.write_text(render(source, load_config()), encoding="utf-8")
    return path


def run_harness(report: Path, tmp_path: Path, *steps: dict, check: bool = True) -> list | str:
    """Run the harness's steps on the report; returns each step's result, or stderr when failing."""
    module = os.environ.get("OBS_HTML_TEST_DOM_MODULE") or str(
        ROOT / "test" / "browser" / "node_modules" / "linkedom")
    node_program = shutil.which("node")
    if not node_program or not Path(module).is_dir():
        pytest.fail("The DOM tier needs Node and linkedom: npm --prefix test/browser ci")
    script = tmp_path / "steps.json"
    script.write_text(json.dumps(list(steps)), encoding="utf-8")
    result = subprocess.run([node_program, str(HARNESS), str(report), module, str(script)],
                            text=True, encoding="utf-8", capture_output=True, cwd=ROOT, timeout=60)
    if not check:
        assert result.returncode == 1, result.stdout
        return result.stderr
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_harness_loads_the_report_data(report: Path, tmp_path: Path) -> None:
    [data] = run_harness(report, tmp_path, {"step": "data"})
    assert data["status"] == "ready"
    assert [note["slug"] for note in data["notes"]][:3] == ["home", "intro", "items"]
    assert data["tables"] == [{"note": "items", "key": TABLE}]
    assert data["paper"] == LETTER


def test_harness_activates_a_chapter(report: Path, tmp_path: Path) -> None:
    [active] = run_harness(report, tmp_path, {"step": "activate", "chapter": "intro"})
    assert active == {"chapter": "intro", "hash": "#intro", "title": "Intro"}
    error = run_harness(report, tmp_path, {"step": "activate", "chapter": "missing"}, check=False)
    assert 'report-harness.cjs: activate: the report has no chapter "missing".' in error
    assert "Remedy:" in error


def test_harness_mounts_a_table(report: Path, tmp_path: Path) -> None:
    _, table = run_harness(report, tmp_path, {"step": "activate", "chapter": "items"},
                           {"step": "table", "key": TABLE})
    assert [column["key"] for column in table["columns"]] == ["file.name", "rank"]
    assert table["rows"] == ["note:gamma", "note:beta", "note:alpha"]
    assert table["count"] == "3 of 3 items"
    error = run_harness(report, tmp_path, {"step": "table", "key": TABLE}, check=False)
    assert f'table: the active chapter "home" mounted no table "{TABLE}".' in error


def test_harness_switches_page_mode(report: Path, tmp_path: Path) -> None:
    _, off, on = run_harness(report, tmp_path, {"step": "activate", "chapter": "items"},
                             {"step": "paged", "enabled": False}, {"step": "paged", "enabled": True})
    assert off == {"paged": False, "reader": False, "chapter": "items", "sheets": 0}
    assert on["paged"] is True and on["reader"] is True and on["chapter"] == "items"
    assert on["sheets"] >= 1


def test_harness_reports_print_and_presentation_geometry(report: Path, tmp_path: Path) -> None:
    _, _, paged, _, flowing = run_harness(
        report, tmp_path, {"step": "activate", "chapter": "items"}, {"step": "paged", "enabled": True},
        {"step": "geometry"}, {"step": "paged", "enabled": False}, {"step": "geometry"})
    portrait = {"orientation": "portrait", **LETTER}
    assert [sheet["chapter"] for sheet in paged["presentation"]] == ["items"]
    assert all(sheet.items() >= portrait.items() for sheet in paged["presentation"])
    printed = paged["print"]["sheets"]
    assert [sheet["chapter"] for sheet in printed] == ["home", "@abstract", "@contents", "intro", "items"]
    assert [sheet["page"] for sheet in printed] == [1, 2, 3, 4, 5]
    assert all(sheet.items() >= portrait.items() for sheet in printed)
    assert paged["print"]["mediaBoxes"] == [
        {"widthMillimeters": 215.9, "heightMillimeters": 279.4}] * len(printed)
    assert paged["presentation"][0]["page"] == printed[-1]["page"]
    assert flowing["presentation"] is None
    assert flowing["print"] == paged["print"]
