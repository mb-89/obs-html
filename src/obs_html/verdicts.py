"""The computed verdict of each decision of a Document, as text or JSON, without a page
(cli.md, Printing the verdicts): what ``obs-html DOCUMENT --print-verdicts`` prints.

Pure but for one door. ``decisions`` finds each decision figure's spec as the page's figure gets
it (figures.py, the pugh kind), ``program`` is the JavaScript that decides them, ``run_node`` the
one door to a JavaScript runtime, Node.js, and ``text_of`` and ``json_of`` write what it answered.
The decision and its wording stay JavaScript, run unchanged: ctrl's engine (vendor/pugh.js), the
figure's mapping (pugh-figure.js, obsPugh.decide), the bottom line's pure layer (pugh-verdict.js,
bottomLineOf) and the text module that calls them (pugh-text.js). No rule is copied here.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Iterator
from importlib.resources import files

from obs_html.errors import InputError
from obs_html.features import pugh_engine
from obs_html.figures import FIGURE_KINDS
from obs_html.render import HOME
SCRIPTS = ("pugh-figure.js", "pugh-verdict.js", "pugh-text.js")
"""The package's scripts the decision runs, after ctrl's engine, in this order."""
NO_PAGE = "globalThis.document = {addEventListener() {}};\n"
"""What pugh-figure.js reaches of a page while it loads: it listens for the bless band's pick,
which never comes here. Deciding needs no page."""
OPTION = "--print-verdicts"


class RuntimeMissing(InputError):
    """No JavaScript runtime to decide with: the call prints this one line and exits 2."""


NO_RUNTIME = ("obs-html", OPTION, "needs Node.js, and no node is on PATH",
              "Install Node.js 18 or newer (nodejs.org) and put node on PATH")
"""The RuntimeMissing the door raises without Node.js; its fake raises the same."""


def run_node(program: str) -> str:
    """The one door to Node.js: runs ``program`` and gives its stdout; RuntimeMissing without node."""
    node = shutil.which("node")
    if node is None:
        raise RuntimeMissing(*NO_RUNTIME)
    done = subprocess.run([node, "-"], input=program, capture_output=True, text=True, encoding="utf-8")
    if done.returncode:
        raise InputError("obs-html", OPTION, f"failed in Node.js ({done.stderr.strip().splitlines()[-1:]})",
                         "Use Node.js 18 or newer")
    return done.stdout


def decisions(document: dict) -> list[dict]:
    """Each decision figure of ``document`` in Document order: its anchor in the artifact (figures.py,
    render_figure), its title and the spec its figure decides, with its chapter's answer where one is."""
    found = []

    def walk(nodes: list[dict], chapter: str, answered: dict, position: list[int]) -> Iterator[dict]:
        for node in nodes:
            if node["type"] == "figures":
                position[0] += 1  # Every figure counts, as render.py numbers them.
                if node["attrs"]["kind"] == "pugh":
                    attrs = node["attrs"]
                    anchor = f"{chapter}--block-{attrs['block']}" if "block" in attrs else f"{chapter}--figure-{position[0]}"
                    spec = FIGURE_KINDS["pugh"].body(node["children"][0]["attrs"], "", "", {}).spec
                    if anchor in answered:
                        spec = {**spec, "answered": answered[anchor]}
                    yield {"anchor": anchor, "title": spec["matrix"].get("title", "Decision"), "spec": spec}
                continue
            yield from walk(node.get("children", []), chapter, answered, position)

    found.extend(walk(document["manifest"]["abstract"], HOME, {}, [0]))
    stack = list(reversed(document["chapters"]))
    while stack:
        chapter = stack.pop()
        answered = ((chapter.get("bless") or {}).get("answer") or {}).get("figures", {})
        found.extend(walk(chapter["content"], chapter["id"], answered, [0]))
        stack.extend(reversed(chapter["children"]))
    return found


def program(found: list[dict]) -> str:
    """The JavaScript that decides ``found`` and writes their verdicts to stdout as one JSON array."""
    package = files("obs_html")
    scripts = "".join(package.joinpath(name).read_text(encoding="utf-8") + "\n" for name in SCRIPTS)
    specs = json.dumps([decision["spec"] for decision in found], ensure_ascii=False)
    return (f"{NO_PAGE}{pugh_engine()}\n{scripts}"
            f"process.stdout.write(JSON.stringify({specs}.map(spec => globalThis.obsPughText.verdictOf(spec))));\n")


def verdicts(document: dict, run: Callable[[str], str] | None = None) -> list[dict]:
    """Each decision of ``document`` with its verdict, decided through ``run`` (by default the door,
    run_node, looked up at the call); a Document without a decision never reaches the door."""
    found = decisions(document)
    if not found:
        return []
    answered = json.loads((run or run_node)(program(found)))
    return [{"anchor": decision["anchor"], "title": decision["title"], "answered": "answered" in decision["spec"], **verdict}
            for decision, verdict in zip(found, answered, strict=True)]


def text_of(decided: list[dict], source: str) -> str:
    """The verdicts as text: each decision's title, then its lines, a blank line between decisions."""
    if not decided:
        return f"No decision in {source}.\n"
    return "\n".join(f"{decision['title']}\n" + "".join(f"{line['text']}\n" for line in decision["lines"])
                     for decision in decided)


def json_of(decided: list[dict]) -> str:
    """The verdicts as one JSON object, ``{"decisions": [...]}``; without a decision, on one line."""
    if not decided:
        return '{"decisions": []}\n'
    return json.dumps({"decisions": decided}, ensure_ascii=False, indent=2) + "\n"
