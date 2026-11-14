"""obs-html DOCUMENT --print-verdicts (cli.md, Printing the verdicts): the computed verdict of each
decision of a Document, as text or JSON, without a page.

Reader: whoever changes the print, its door to Node.js (verdicts.py, run_node) or the bottom line's
wording (pugh-verdict.js). One test runs the real door; every other test runs the door's fake.
"""
import json
from pathlib import Path

import pytest

from conftest import ROOT
from obs_html import cli, verdicts


DOCUMENTS = ROOT / "test" / "fixtures" / "documents"
VERDICT = DOCUMENTS / "decision-verdict.json"
"""Its vault turns artifact.figures.decisionVerdict on; pugh.json's leaves it off."""
PAGE_LINES = {
    "Which option": [
        "The choice holds: C · Quick wins 96.0 % of the weight draws within ±1.",
        "B · Precise ties if Speed goes 2 → 0.5: not a reasonable change.",
        "No single weight makes D · Middling tie.",
        "No single weight makes A · What runs today tie."],
    "Many options": [
        "The choice depends on the weights: G wins 88.3 % of the weight draws within ±1.",
        "H ties it now.",
        "C ties if Speed goes 2 → 1: a reasonable change.",
        "D ties if Speed goes 2 → 1: a reasonable change."],
    "Which option within budget": [
        "The choice holds: C · Quick wins 100.0 % of the weight draws within ±1.",
        "No single weight makes D · Middling tie.",
        "No single weight makes A · What runs today tie.",
        "B · Precise is out: over budget: Cost of ownership 19 above 15."],
}
"""What the page draws for decision-verdict.json (test_pugh_figures_browser.py,
test_with_the_option_on_the_proposed_winner_states_the_verdict_each_runner_ups_tie_and_each_veto,
asserts OPTION's lines, WIDE's first three and GATED's last)."""


def _print(capsys, *arguments) -> tuple[int, str, str]:
    try:
        code = cli.main([str(argument) for argument in arguments])
    except SystemExit as exit_info:
        code = exit_info.code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _fake(answer: list[dict] | None):
    """The door's fake: answers the program with ``answer`` as Node.js would print it, or, with None,
    reports no runtime as the door does; it records each program it was handed."""
    programs = []

    def run(program: str) -> str:
        programs.append(program)
        if answer is None:
            raise verdicts.RuntimeMissing(*verdicts.NO_RUNTIME)
        return json.dumps(answer)

    run.programs = programs
    return run


@pytest.mark.dom
def test_the_print_states_what_the_page_draws_and_two_runs_give_the_same_bytes(capsys) -> None:
    """The real door: the lines equal the page's, the JSON holds the same lines with the engine's
    data, and two runs of each format print the same bytes."""
    text = [_print(capsys, VERDICT, "--print-verdicts") for _ in range(2)]
    data = [_print(capsys, VERDICT, "--print-verdicts", "--verdict-format", "json") for _ in range(2)]
    assert text[0] == text[1] and data[0] == data[1]
    assert text[0][0] == 0 and data[0][0] == 0 and text[0][2] == ""
    blocks = [block.splitlines() for block in text[0][1].split("\n\n")]
    assert {block[0]: block[1:] for block in blocks} == PAGE_LINES
    decided = json.loads(data[0][1])["decisions"]
    assert [[decision["title"], [line["text"] for line in decision["lines"]]] for decision in decided] == \
        [[block[0], block[1:]] for block in blocks]
    gated = decided[2]
    assert (gated["anchor"], gated["suggestion"]["name"], gated["lines"][-1]["part"]) == \
        ("decisions--block-gated", "C · Quick", "veto")
    assert [entry["fits"] for entry in gated["ranking"]][-1] is False
    assert decided[0]["sensitivity"]["runnersUp"][0]["tie"] | {"from": None} == \
        {"criterion": "speed", "label": "Speed", "from": None, "to": 0.5, "reasonable": False, "now": False}
    # Independent of artifact.figures.decisionVerdict: pugh.json's vault leaves it off.
    code, out, _ = _print(capsys, DOCUMENTS / "pugh.json", "--print-verdicts")
    assert code == 0 and "The choice" in out


def test_a_document_without_a_decision_prints_one_line_and_never_reaches_the_door(capsys, monkeypatch) -> None:
    door = _fake(None)
    monkeypatch.setattr(verdicts, "run_node", door)
    document = DOCUMENTS / "callouts.json"
    assert _print(capsys, document, "--print-verdicts") == (0, f"No decision in {document}.\n", "")
    assert _print(capsys, document, "--print-verdicts", "--verdict-format", "json") == (0, '{"decisions": []}\n', "")
    assert door.programs == []


def test_without_a_runtime_the_print_says_so_in_one_line_and_exits_2(capsys, monkeypatch) -> None:
    monkeypatch.setattr(verdicts, "run_node", _fake(None))
    code, out, err = _print(capsys, VERDICT, "--print-verdicts")
    assert (code, out, len(err.splitlines())) == (2, "", 1)
    assert err.startswith("obs-html: --print-verdicts: ")


def test_the_door_gets_each_figure_spec_and_the_print_writes_what_it_answered(capsys, monkeypatch) -> None:
    """The program carries ctrl's engine and the three scripts, each unchanged, and the specs the
    page's figures get; text and JSON write the door's answer, title first."""
    answer = [{"lines": [{"part": "verdict", "text": f"Line of {index}."}]} for index in range(3)]
    door = _fake(answer)
    monkeypatch.setattr(verdicts, "run_node", door)
    code, out, _ = _print(capsys, VERDICT, "--print-verdicts")
    assert code == 0
    assert out == "Which option\nLine of 0.\n\nMany options\nLine of 1.\n\nWhich option within budget\nLine of 2.\n"
    program = door.programs[0]
    package = ROOT / "src" / "obs_html"
    for name in verdicts.SCRIPTS:
        assert (package / name).read_text(encoding="utf-8") in program
    assert "globalThis.obsPughEngine = pughEngine();" in program
    document = json.loads(VERDICT.read_text(encoding="utf-8"))
    matrices = [node["children"][0]["attrs"]["matrix"] for node in document["chapters"][0]["content"]
                if node["type"] == "figures"]
    assert [decision["spec"]["matrix"] for decision in verdicts.decisions(document)] == matrices
    code, out, _ = _print(capsys, VERDICT, "--print-verdicts", "--verdict-format", "json")
    assert [decision["anchor"] for decision in json.loads(out)["decisions"]] == \
        ["decisions--block-option", "decisions--block-wide", "decisions--block-gated"]


def test_a_decision_without_a_block_is_named_by_its_place_and_an_answer_decides_it() -> None:
    """The anchor is the artifact's (figures.py, render_figure): a block id, else the figure's place
    in its note; a chapter's answer reaches its figure's spec, as the page's figure gets it."""
    document = json.loads(VERDICT.read_text(encoding="utf-8"))
    chapter = document["chapters"][0]
    del next(node for node in chapter["content"] if node["type"] == "figures")["attrs"]["block"]
    chapter["bless"] = {"answer": {"figures": {"decisions--block-wide": {"weights": {"speed": 1}}}}}
    found = verdicts.decisions(document)
    assert [decision["anchor"] for decision in found] == \
        ["decisions--figure-1", "decisions--block-wide", "decisions--block-gated"]
    assert [decision["spec"].get("answered") for decision in found] == [None, {"weights": {"speed": 1}}, None]


@pytest.mark.parametrize(("arguments", "field"), [
    (["--verdict-format", "json"], "--verdict-format"),
    (["--print-verdicts", "out.html"], "DESTINATION"),
    (["--print-verdicts", "--check"], "--check"),
], ids=["format-alone", "destination", "check"])
def test_the_print_writes_no_artifact_and_its_format_needs_it(capsys, monkeypatch, arguments, field) -> None:
    monkeypatch.setattr(verdicts, "run_node", _fake(None))
    code, out, err = _print(capsys, VERDICT, *arguments)
    assert (code, out) == (2, "") and f"obs-html: {field}: " in err
