"""The browser door's states, recordings and conformance (test/browser/browser-door.md, Recording and replay).

Reader: whoever records the browser door's states, opens a state in the fake browser, or reads why
the conformance check (test/test_browser_door.py) failed.

test/browser/expectations.yaml holds the expectations and the states. A state's artifact is built
with the library fakes and the build instant fixed (``build_artifact``); its SHA-256 is the
recording's ``artifactDigest``. ``record_state`` records a state: the fake browser first lists, by
step, each key and call the page asked (``listed``), then the one Chromium opens the state, runs
each step and, after it, every expectation's probe over those keys (``measure``). It writes
test/browser/recordings/<state>.yaml. ``open_state`` opens a state in the fake with its recording,
so the fake answers every supplied call from the latest step reached, and ``conformance`` compares
the fake's computed answers with the recording's, naming the state, the step, the key and both
answers where they differ.
"""
from __future__ import annotations

import contextlib
import functools
import hashlib
import importlib
import json
import os
from importlib import metadata
from pathlib import Path

import yaml

BROWSER = Path(__file__).parent
ROOT = BROWSER.parents[1]
EXPECTATIONS = BROWSER / "expectations.yaml"
RECORDINGS = BROWSER / "recordings"
DOOR_KEY = BROWSER / "door-key.js"
OWNER = "test/browser/door.py"
NOTE = "test/browser/browser-door.md"
# What records the states anew.
REMEDY = "uv run pytest -m hot --record"
# The build instant of every state's artifact (SOURCE_DATE_EPOCH), so that its digest changes
# exactly when the page does.
BUILD_EPOCH = "1700000000"
# The local themes the feature fixture carries (spec/configuration.md, Local themes), as
# test/conftest.py's feature_artifact builds it.
LOCAL_THEMES = ROOT / "test" / "fixtures" / "local-themes"
# A one-pixel image, the fixture Document's logo.
PIXEL = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
# The artifact's ready mark, in a top-level page and in a frame.
READY = "() => document.documentElement.dataset.artifactStatus === 'ready'"
# Two animation frames: what a page shows once the work a step started has been painted.
SETTLED = "() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
# The stylesheets' media rules, as the page states them: the media expectation asks each of them too.
MEDIA_RULES = """() => {
    const found = new Set();
    const walk = (rules) => {
        for (const rule of rules || []) {
            const text = rule.media?.mediaText || rule.conditionText || "";
            if (rule.constructor?.name === "CSSMediaRule" || rule.type === 4) { if (text) found.add(text); }
            if (rule.cssRules) walk(rule.cssRules);
        }
    };
    for (const sheet of document.styleSheets) {
        try { walk(sheet.cssRules); } catch (error) {}
    }
    return [...found];
}"""
# Every image of the page: the image-size expectation is asked of each, since a test reads an
# image's decoded size where the runtime does not (browser-door.md, The browser door's expectations).
IMAGES = "(door) => [...document.querySelectorAll('img')].map((image) => door.key(image))"
# A state's own reads (expectations.yaml, ``reads``) as cascade reads of the elements their selectors
# find now: ``<key>|<property>``, the form the runtime's own reads take.
READS = """(door) => door.asked.flatMap((read) => {
    const separator = read.lastIndexOf("|");
    const element = document.querySelector(read.slice(0, separator));
    return element ? [`${door.key(element)}|${read.slice(separator + 1)}`] : [];
})"""


@functools.cache
def _loaded() -> dict:
    return yaml.safe_load(EXPECTATIONS.read_text(encoding="utf-8"))


def states() -> dict[str, dict]:
    return _loaded()["states"]


def expectations() -> list[dict]:
    return _loaded()["expectations"]


def given(expectation: dict, state: dict, step: int | None = None) -> bool:
    """Whether the state's context, and after ``step`` (any step where None) the step, meet the
    expectation's given precondition; ``step: last`` is the state's last step."""
    precondition = dict(expectation.get("given") or {})
    last = precondition.pop("step", None)
    if last is not None and step is not None and step != len(state["steps"]) - 1:
        return False
    return all(state["context"].get(name) == value for name, value in precondition.items())


def asked_in(state: dict, kind: str | None = None, step: int | None = None) -> list[dict]:
    """The expectations the state asks (after ``step``, where given), of one kind where ``kind`` is
    given, in the file's order."""
    return [each for each in expectations() if given(each, state, step) and kind in (None, each["kind"])]


# ---- Artifacts

@contextlib.contextmanager
def _environment(**values: str):
    earlier = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in earlier.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def build_feature_file(document: Path, target: Path) -> None:
    """Build a Document file as the browser tier opens it: with its notes' way from the page, so the
    source file row is a link (spec/cli.md, Source file links), and with the fixture's local themes,
    so it carries the popups feature's style-sync part."""
    from obs_html import cli

    with _environment(OBS_HTML_LOCAL_FOLDER=str(LOCAL_THEMES)):
        built = cli.main([str(document), str(target), "--vault-link", "../vault"])
    assert built == 0, f"{OWNER}: obs-html could not render {document.relative_to(ROOT).as_posix()}"


def build_artifact(name: str, folder: Path) -> Path:
    """The state's artifact, built into ``folder`` with the library fakes this process embeds
    (test/library_fakes.py) and SOURCE_DATE_EPOCH fixed at BUILD_EPOCH: a Document file, or
    ``<module>::<function>``, a function of a test module that returns the Document to render or
    the artifact's HTML, which it builds in the current folder. It is built from ``folder``,
    outside this checkout: a build records the commit and version of the repository it runs in as
    its target (spec/artifact-ui.md, Generation provenance), which would change the digest with
    every commit of this one."""
    source = states()[name]["artifact"]
    folder = folder.resolve()
    target = folder / "artifact.html"
    with _environment(SOURCE_DATE_EPOCH=BUILD_EPOCH), contextlib.chdir(folder):
        if "::" in source:
            from obs_html import build_time
            from obs_html.config import load_config
            from obs_html.render import render

            module, function = source.split("::")
            built = getattr(importlib.import_module(Path(module).stem), function)()
            if isinstance(built, str):
                target.write_text(built, encoding="utf-8")
            else:
                target.write_text(render(built, load_config(), built=build_time.instant(os.environ), target_root=folder),
                                  encoding="utf-8")
        else:
            build_feature_file(ROOT / source, target)
    return target


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


# ---- Recordings

class _Dumper(yaml.SafeDumper):
    """Lists of numbers on one line, so a box reads as [x, y, width, height]; keys one per line."""


def _numbers(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _list(dumper: yaml.SafeDumper, value: list):
    flow = not value or all(map(_numbers, value)) or all(
        isinstance(each, list) and all(map(_numbers, each)) for each in value)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", value, flow_style=flow)


_Dumper.add_representer(list, _list)


# The fixture Document's printed PDF, the supplied answer of the print expectation that
# test_pdf.py records and the PDF inspection tools read (test_pdf_inspect.py).
PRINTED_PDF = RECORDINGS / "fixture-print.pdf"


def print_fixture(folder: Path) -> Path:
    """Print the fixture Document by this repository's own PDF path into ``folder``, with its image
    beside it and the build instant fixed at BUILD_EPOCH, so that two prints are equal."""
    import base64

    from obs_html import cli

    (folder / "images").mkdir(exist_ok=True)
    (folder / "images" / "logo.png").write_bytes(base64.b64decode(PIXEL))
    pdf = folder / "artifact.pdf"
    with _environment(SOURCE_DATE_EPOCH=BUILD_EPOCH):
        assert cli.main([str(ROOT / "test" / "fixtures" / "documents" / "document.json"), str(pdf)]) == 0, (
            f"{OWNER}: obs-html could not print the fixture Document")
    return pdf


def recording_path(name: str) -> Path:
    return RECORDINGS / f"{name}.yaml"


def load_recording(name: str) -> dict | None:
    path = recording_path(name)
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None


def write_recording(recording: dict) -> Path:
    path = recording_path(recording["state"])
    path.parent.mkdir(exist_ok=True)
    header = (f"# The browser door's recording of the state {recording['state']} (test/browser/expectations.yaml),\n"
              f"# written by `{REMEDY}` ({OWNER}); never edited by hand.\n")
    path.write_text(header + yaml.dump(recording, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=120),
                    encoding="utf-8")
    return path


# ---- Steps, in either engine: a Playwright Page or Frame, or a FakePage

def run_step(target, step: dict) -> None:
    """Take a state's step in the page: open the page (it waits for the artifact's ready mark) or
    open a chapter by its address."""
    if step.get("open") == "page":
        target.wait_for_function(READY)
    elif step.get("open") == "chapter":
        target.evaluate(f"() => {{ location.hash = {json.dumps('#' + step['id'])}; }}")
        target.wait_for_function(
            f"() => document.querySelector('[data-active-chapter]')?.dataset.chapter === {json.dumps(step['id'])}")
    else:
        raise ValueError(f"{OWNER}: the step {step!r} is none the door takes (open: page, or open: chapter with an id); "
                         f"see {EXPECTATIONS.relative_to(ROOT).as_posix()}")


def page_function(function: str) -> str:
    """A page function of ``door`` as a page function of its argument ``asked``, with door-key.js
    loaded beside it: ``door.asked``, ``door.key(element)`` and ``door.element(key)``."""
    return (f"async (asked) => {{\n{DOOR_KEY.read_text(encoding='utf-8')}\n"
            "const door = {asked, key: doorKey, element: (key) => doorElement(key, document)};\n"
            f"const probe = ({function.strip()});\nreturn await probe(door);\n}}")


def probe_function(expectation: dict) -> str:
    """The page function that asks the expectation's probe."""
    return page_function(expectation["probe"])


def measure(target, state: dict, step: int, asked: dict, kind: str | None = None) -> dict:
    """The answer of every expectation the state asks after ``step`` (of ``kind``, where given), in
    the page as it is now."""
    return {each["name"]: target.evaluate(probe_function(each), asked) for each in asked_in(state, kind, step)}


def fake_context(fake_page, state: dict) -> None:
    """The state's context as the fake browser takes it: its viewport, colour scheme, motion and media."""
    width, height = state["context"]["viewport"]
    fake_page.set_viewport_size({"width": width, "height": height})
    context = state["context"]
    fake_page.emulate_media(media=context.get("media", "screen"), color_scheme=context.get("scheme", "light"),
                            reduced_motion=context.get("motion", "no-preference"))


def open_state(fake_page, name: str, artifact: Path, recording: dict | None, through: int | None = None,
               after_step=None, url: str | None = None) -> None:
    """Open the state in the fake page with ``recording`` (None: the door's defaults) and take its
    steps up to ``through`` (every step where None). Each step is reached as it begins, so the page
    answers it from that step's recording; ``after_step(index)`` runs once each step has ended. ``url``,
    where given, is the address the page opens in place of the artifact's file."""
    state = states()[name]
    fake_page.replay(recording)
    fake_context(fake_page, state)
    steps = state["steps"] if through is None else state["steps"][:through + 1]
    for index, step in enumerate(steps):
        fake_page.reach(index)
        if index == 0:
            fake_page.goto(url or artifact.as_uri())
        run_step(fake_page, step)
        if after_step is not None:
            after_step(index)


def frame_answers(name: str) -> dict:
    """The recording of the viewer-frame state ``name`` with only what belongs to the frame, not to
    its artifact: its context and, at each step, the frame's refusals, ``document.fonts`` and the
    window's inner size. A page that opens another artifact in the viewer frame replays these, and
    the door's defaults for its own elements, whose keys the recording's artifact does not share."""
    recording = load_recording(name)
    if recording is None or recording["context"]["frame"] != "viewer":
        raise ValueError(f"{OWNER}: {name} is no recorded viewer-frame state; record it with `{REMEDY}`")
    frame = []
    for answer in recording["answers"]:
        kept = {"step": answer["step"], "asked": {}}
        for kind in ("viewer-frame", "fonts"):
            if kind in answer:
                kept[kind] = answer[kind]
        if "window" in (answer.get("sizes") or {}):
            kept["sizes"] = {"window": answer["sizes"]["window"]}
        frame.append(kept)
    return {**recording, "answers": frame}


def open_recorded(fake_page, name: str, artifact: Path, through: int | None = None, url: str | None = None) -> dict:
    """Open the state in the fake page as a logic test does, with its committed recording, and take its
    steps up to ``through``; ``url``, where given, is the address the page opens in place of the
    artifact's file (a served copy, a variant of the same page). Returns the recording."""
    recording = load_recording(name)
    assert recording is not None, (f"{OWNER}: the state {name} has no recording "
                                   f"{recording_path(name).relative_to(ROOT).as_posix()}. Remedy: run `{REMEDY}` "
                                   "and commit it")
    open_state(fake_page, name, artifact, recording, through, url=url)
    return recording


def listed(fake_page, name: str, artifact: Path, previous: dict | None) -> tuple[dict[int, dict[str, list[str]]], bool]:
    """What the page asks at each step of the state in the fake browser, by expectation and key: on
    the door's defaults, and with the previous recording where there is one, since its answers can
    send the runtime down other branches; with each step's stylesheet media rules and the state's
    own reads (``reads``: ``<selector>|<property>``, the computed values its hot tests check, such
    as an appearance's painted colours), each as the cascade read of the first element the
    selector finds at that step. Also whether the fake took every step on the last answers it had."""
    union: dict[int, dict[str, set[str]]] = {}
    reads = states()[name].get("reads") or []

    def collect(index: int) -> None:
        union.setdefault(index, {}).setdefault("media", set()).update(fake_page.evaluate(MEDIA_RULES))
        images = fake_page.evaluate(page_function(IMAGES), {})
        if images:
            union[index].setdefault("image-size", set()).update(images)
        union[index].setdefault("cascade", set()).update(fake_page.evaluate(page_function(READS), reads))

    opened = False
    for recording in ([None, previous] if previous else [None]):
        fake_page.asked()
        try:
            open_state(fake_page, name, artifact, recording, after_step=collect)
            opened = True
        except Exception:  # A page the door's defaults cannot open: what it asked so far still counts.
            opened = False
        for index, kinds in fake_page.asked().items():
            for kind, keys in kinds.items():
                union.setdefault(index, {}).setdefault(kind, set()).update(keys)
    return ({index: {kind: sorted(keys) for kind, keys in sorted(kinds.items())} for index, kinds in sorted(union.items())},
            opened)


def chromium_version(page) -> str:
    return f"{page.context.browser.version} (Playwright {metadata.version('playwright')})"


# How often the recorder lists a state again on the recording it just took, where the fake could not
# take every step on the answers it had (record_state).
ROUNDS = 3


def record_state(name: str, artifact: Path, fake_page, open_chromium) -> dict:
    """Record the state: the fake lists what the page asks, then ``open_chromium()`` opens it in the
    one Chromium and answers (page, target), the page and the page or frame the artifact runs in;
    after each step every expectation's probe runs there. Where the fake could not take every step
    on the answers it had (a page the door's defaults cannot lay out), it lists the state again on
    the recording just taken, up to ROUNDS times. Writes and returns the recording."""
    previous = load_recording(name)
    for _ in range(ROUNDS):
        recording, opened = _record_once(name, artifact, fake_page, open_chromium, previous)
        if opened:
            break
        previous = recording
    assert opened, (f"{OWNER}: the fake browser could not take every step of the state {name} on its "
                           f"recording after {ROUNDS} rounds; open it with door.open_state to see where it stops")
    write_recording(recording)
    return recording


def _record_once(name: str, artifact: Path, fake_page, open_chromium, previous: dict | None) -> tuple[dict, bool]:
    state = states()[name]
    asked, opened = listed(fake_page, name, artifact, previous)
    page, target = open_chromium()
    answers = []
    for index, step in enumerate(state["steps"]):
        run_step(target, step)
        target.evaluate(SETTLED)
        step_asked = asked.get(index, {})
        answers.append({"step": index, "asked": step_asked, **measure(target, state, index, step_asked)})
    recording = {
        "state": name,
        "artifact": state["artifact"],
        "context": state["context"],
        "steps": state["steps"],
        "artifactDigest": digest(artifact),
        "chromium": chromium_version(page),
        "answers": answers,
    }
    return recording, opened


# ---- Conformance

def _differences(name: str, step: int, expectation: str, fake, chromium) -> list[str]:
    where = f"state {name}, step {step}, {expectation}"
    if isinstance(fake, dict) and isinstance(chromium, dict):
        found = []
        for key in sorted(set(fake) | set(chromium)):
            if fake.get(key) != chromium.get(key):
                found.append(f"{where}, key {key}: the fake answers {json.dumps(fake.get(key))}, "
                             f"Chromium answered {json.dumps(chromium.get(key))}")
        return found
    if fake != chromium:
        return [f"{where}: the fake answers {json.dumps(fake)}, Chromium answered {json.dumps(chromium)}"]
    return []


def compare(name: str, recording: dict, computed: dict[int, dict]) -> list[str]:
    """Each computed answer of the fake (``computed``, by step and expectation) that differs from the
    recording's, naming the state, the step, the key and both answers."""
    found = []
    for answer in recording["answers"]:
        fake = computed.get(answer["step"], {})
        for expectation in asked_in(states()[name], "computed", answer["step"]):
            found += _differences(name, answer["step"], expectation["name"], fake.get(expectation["name"]),
                                  answer.get(expectation["name"]))
    return found


def conformance(fake_page, name: str, artifact: Path, recording: dict) -> list[str]:
    """Open the state in the fake with its recording and, after each step, ask every computed
    expectation with the keys the recording lists; each answer that differs from Chromium's."""
    state = states()[name]
    computed: dict[int, dict] = {}

    def ask(index: int) -> None:
        computed[index] = measure(fake_page, state, index, recording["answers"][index]["asked"], "computed")

    open_state(fake_page, name, artifact, recording, after_step=ask)
    return compare(name, recording, computed)


def stale(name: str, artifact: Path, recording: dict | None) -> str:
    """Why the state's recording no longer fits its artifact, or "" where it does."""
    if recording is None:
        return f"the state {name} has no recording {recording_path(name).relative_to(ROOT).as_posix()}"
    if recording["artifactDigest"] != digest(artifact):
        return (f"the recording of {name} was taken of an artifact with the digest {recording['artifactDigest']}; "
                f"its artifact now builds to {digest(artifact)}")
    return ""
