"""The decision record of an answered chapter: its verdict, read-only, at the top of the chapter.

Reader: whoever changes how obs-html shows a reader's answer that obs-document --answers put into
the Document (obs input-model, Answers; spec/capabilities/bless.md).

A chapter whose bless request carries an ``answer`` shows it as answered; one whose request carries
an ``outdated`` answer asks again (bless.js) and shows the old answer as outdated. The record names
the verdict, the picked option, the comment and, per decision figure, the reader's weights, marks,
rulings with their tripwires and the winner they give. The figure itself shows the same changes
read-only (pugh-figure.js, from its spec's ``answered``).
"""
from __future__ import annotations

from html import escape

STATES = {"bless": "Blessed", "decline": "Declined", "ask": "Question", "pick": "Picked"}
SYMBOLS = {2: "++", 1: "+", 0: "S", -1: "−", -2: "−−"}
"""ctrl's mark symbols, as the decision figure shows them (vendor/pugh.js, SYMBOL)."""


def _matrices(nodes: list[dict]) -> list[dict]:
    """The bodies of the chapter's decision figures, in document order: each matrix and the short
    names the core resolved for its options (obs input-model, Pugh decision figures)."""
    found = []
    for node in nodes:
        if node["type"] == "figures" and node["attrs"].get("kind") == "pugh":
            found.append(node["children"][0]["attrs"])
        elif node["type"] != "figures":
            found.extend(_matrices(node.get("children", [])))
    return found


def _changes(figure: dict, criteria: dict[str, dict], names: dict[str, str]) -> list[str]:
    lines = []
    for key, weight in figure.get("weights", {}).items():
        criterion = criteria.get(key, {"label": key})
        was = f" (was {criterion['weight']:g})" if "weight" in criterion else ""
        lines.append(f"Weight of {criterion['label']}: {weight:g}{was}")
    for letter, marks in figure.get("marks", {}).items():
        for key, mark in marks.items():
            lines.append(f"Mark of {letter} on {criteria.get(key, {'label': key})['label']}: {SYMBOLS[mark]}")
    for letter, ruling in figure.get("rulings", {}).items():
        if ruling.get("ruling") == "could":
            watch = f"; watch for: {ruling['tripwire']}" if ruling.get("tripwire") else "; no sign to watch for yet"
            lines.append(f"{letter} winning could happen{watch}")
        elif ruling.get("ruling") == "nonsense":
            lines.append(f"{letter} winning is nonsense")
    if figure.get("winner"):
        winner = figure["winner"]
        lines.append(f"Winner with these changes: {winner}{f' · {names[winner]}' if names.get(winner) else ''}")
    return lines


def record_html(chapter: dict) -> str:
    """The record of the chapter's answer, or "" where it has none."""
    request = chapter.get("bless") or {}
    verdict = request.get("answer") or request.get("outdated")
    if verdict is None:
        return ""
    bodies = _matrices(chapter["content"])
    criteria = {criterion["key"]: criterion for body in bodies for criterion in body["matrix"]["criteria"]}
    names: dict[str, str | None] = {}
    for body in bodies:
        for index, short in enumerate(body["shortNames"]):
            names.setdefault(chr(65 + index), short)
    state = STATES[verdict["verdict"]]
    if verdict.get("pick"):
        letter = verdict["pick"]["option"]
        state += f" {letter}" + (f" · {names[letter]}" if names.get(letter) else "")
    outdated = "outdated" in request
    title = ("Outdated answer: the chapter changed after it was answered, so it asks again"
             if outdated else "Answer")
    parts = [f'<p class="bless-record-title"><strong>{escape(title)}</strong></p>',
             f'<p><strong>Verdict:</strong> <span data-bless-record-verdict>{escape(state)}</span></p>']
    if verdict.get("comment"):
        parts.append(f'<p><strong>Comment:</strong> <span data-bless-record-comment>{escape(verdict["comment"])}</span></p>')
    lines = [line for figure in verdict.get("figures", {}).values() for line in _changes(figure, criteria, names)]
    if lines:
        parts.append("<p><strong>The reader's changes:</strong></p><ul>"
                     + "".join(f"<li>{escape(line)}</li>" for line in lines) + "</ul>")
    kind = "outdated" if outdated else "answer"
    return (f'<aside class="bless-record bless-record-{kind}" data-bless-record="{kind}" '
            f'aria-label="{escape(title, quote=True)}">{"".join(parts)}</aside>')
