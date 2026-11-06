"""DOM tier: the embedded artifact runtime, run in Node over linkedom (test/browser)."""
import os
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest

from conftest import ROOT
from documents import chapter, document, heading, node, paragraph
from obs_html.config import load_config
from obs_html.render import render


pytestmark = pytest.mark.dom
CONFIG = load_config()
RUNNER = ROOT / "test" / "browser" / "artifact-ui.cjs"


def write_artifact(path: Path, source: dict) -> Path:
    path.write_text(render(source, CONFIG), encoding="utf-8")
    return path


def run_artifact_dom_contract(artifact: Path, mode: str, *runtimes: Path, arguments: tuple[str, ...] = ()) -> str:
    """Run one mode of artifact-ui.cjs; the runtimes are loaded into the page in the given order."""
    module = os.environ.get("OBS_HTML_TEST_DOM_MODULE") or str(
        ROOT / "test" / "browser" / "node_modules" / "linkedom")
    node = shutil.which("node")
    if not node or not Path(module).is_dir():
        pytest.fail("The DOM tier needs Node and linkedom: npm --prefix test/browser ci")
    paths = [str(path) for path in runtimes]
    paths.extend([""] * (3 - len(paths)))
    result = subprocess.run(
        [node, str(RUNNER), str(artifact), module, *paths, *([mode] if mode else []), *arguments],
        text=True, encoding="utf-8", capture_output=True, cwd=ROOT, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_comment_export_dom_contract(tmp_path: Path) -> None:
    artifact = write_artifact(tmp_path / "artifact.html", document(
        "Comments",
        chapter("parent", "Parent", heading(1, "Parent"), heading(2, "Context"),
                paragraph("Quote Ω on the first line.\nSecond line.")),
        chapter("child", "Child", heading(1, "Child"), paragraph("Inactive paragraph.")),
    ))
    package = files("obs_html")
    run_artifact_dom_contract(artifact, "--comments-only", package / "bars" / "comments.js",
                            package / "bars" / "settings.js", package / "storage.js")


def test_filter_and_search_are_separate_discovered_bars(tmp_path: Path) -> None:
    names = [f"chapter-{index}" for index in range(6)]
    artifact = write_artifact(tmp_path / "artifact.html", document("Query controls", *(
        chapter(name, name, heading(1, name), paragraph(f"{'Draft' if index < 3 else 'Final'} prose."),
                metadata={"status": "draft" if index < 3 else "final"})
        for index, name in enumerate(names))))
    bars = files("obs_html.bars")
    run_artifact_dom_contract(artifact, "--discovered-query-controls-only", bars / "filter.js", bars / "search.js")


def test_table_reference_contract_covers_headers_groups_and_footer(tmp_path: Path) -> None:
    # A Base table ships the data-table runtime (features.py, tables) that the contract drives.
    base = node("bases", source="", spec={"views": [{"type": "table", "name": "Items", "order": ["file.name"]}]})
    artifact = write_artifact(tmp_path / "artifact.html", document(
        "Tables", chapter("chapter", "Chapter", heading(1, "Chapter"), base)))
    run_artifact_dom_contract(artifact, "--table-controls-only")

