"""The note for agents a page may carry (spec/architecture.md, Agent note).

Reader: whoever changes what the note tells an agent or when a page carries it.

Pure: whether the option ``artifact.agentNote`` is on and whether the page asks for answers in, the
note's element out, or nothing where the option is off, so a page without it is byte for byte what it
was. The note's text is agent-note.md, and agent-note-answers.md where the page asks for answers.
"""
from __future__ import annotations

from importlib.resources import files


def agent_note_markup(enabled: bool, answers: bool) -> str:
    """The ``<script type="text/markdown" id="agent-note">`` element; "" where the option is off."""
    if not enabled:
        return ""
    package = files("obs_html")
    note = package.joinpath("agent-note.md").read_text(encoding="utf-8")
    if answers:
        note += package.joinpath("agent-note-answers.md").read_text(encoding="utf-8")
    return '<script id="agent-note" type="text/markdown">\n' + note.replace("</", "<\\/") + "  </script>\n  "
