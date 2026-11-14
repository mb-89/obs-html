"""The opt-in page shell parts (architecture.md, Opt-in page shell parts): the limited-host banner
(artifact.limitedHostNeeds) and the note for agents (artifact.agentNote) ship only where their option
asks for them, and with every option at its default an artifact is byte for byte what it was."""
import json
import re
from pathlib import Path

from documents import chapter, document, heading, paragraph
from obs_html.agent_note import agent_note_markup
from obs_html.artifact_data import same_artifact_content
from obs_html.config import load_config
from obs_html.limited_host import limited_host_markup
from obs_html.render import render

PAGE = document("Shell", chapter("one", "One", heading(1, "One"), paragraph("Text.")))
DEFAULTS = {"limitedHostNeeds": [], "refuseProvenance": False, "agentNote": False}


def built(tmp_path: Path, settings: dict) -> str:
    path = tmp_path / f"cfg-{len(list(tmp_path.iterdir()))}.json"
    path.write_text(json.dumps({"artifact": settings}), encoding="utf-8")
    return render(PAGE, load_config(path))


def test_every_option_at_its_declared_default_builds_what_the_packaged_settings_build(tmp_path: Path) -> None:
    plain = render(PAGE, load_config())
    assert same_artifact_content(built(tmp_path, DEFAULTS), plain)
    assert 'id="limited-host' not in plain and 'id="agent-note"' not in plain


def test_the_banner_ships_with_a_declared_need_its_table_and_a_script_that_runs_before_the_first_paint(
        tmp_path: Path) -> None:
    html = built(tmp_path, {"limitedHostNeeds": ["scripts", "storage"]})
    banner = re.search(r'<div id="limited-host" class="limited-host" role="alert">([^<]*)</div>', html)
    assert banner and banner[1].startswith("Limited viewer: this viewer runs no scripts")
    island = re.search(r'<script id="limited-host-needs" type="application/json">([^<]*)</script>', html)
    assert list(json.loads(island[1])) == ["storage"]  # scripts are the static line's, not the table's
    assert '<script id="limited-host-script">' in html  # not made inert (artifact_data.py)
    assert html.index('id="limited-host"') < html.index('class="top-band"')


def test_the_banner_markup_is_empty_without_needs() -> None:
    assert limited_host_markup([]) == ""


def test_the_agent_note_ships_only_with_its_option_and_names_answers_only_where_the_page_asks() -> None:
    assert agent_note_markup(False, True) == ""
    note, asking = agent_note_markup(True, False), agent_note_markup(True, True)
    assert note.startswith('<script id="agent-note" type="text/markdown">')
    assert "activateChapter" in note and "sendAnswers" not in note and "sendAnswers" in asking


def test_the_agent_note_option_puts_the_note_in_the_page(tmp_path: Path) -> None:
    html = built(tmp_path, {"agentNote": True})
    assert html.count('<script id="agent-note" type="text/markdown">') == 1
