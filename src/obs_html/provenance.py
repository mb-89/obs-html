"""The provenance check of a built artifact: built HTML in, findings out, each naming its place.

Reader: whoever changes what the provenance check looks for, how a build reacts to it, its
exemptions, or its exceptions and the files that hold them.

spec/architecture.md, Provenance check, owns the design, and its Exceptions the exceptions. The
module is pure where it can be: ``findings`` takes the artifact's text, the local list's terms and
the exceptions and returns what it found, each finding covered or not, and the CLI (cli.py,
``_check_provenance``) warns of the uncovered ones, or refuses the build where
``artifact.refuseProvenance`` is true. A finding names its place (an HTML line, or a field path of
the decoded data island, as the exposure check names them: exposure.py, ``artifact_texts``, or of
the comment island where it has the shape the build writes: ``comment_island``), the
label of what it found and the digest of the text it matched, never the text, as se's public check
reports a hit. The readers of files, ``local_terms`` and ``local_exceptions``, find their file as
``local_list`` finds se's local list.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator

from obs_html.comments import ISLAND, _resolved
from obs_html.config import SCHEMA_PATH
from obs_html.errors import InputError, schema_error
from obs_html.exposure import _strings, artifact_html, artifact_texts
from obs_html.libraries import LIBRARIES


SOURCE = "obs-html artifact"
"""The finished artifact, before it is written: a finding names where in it."""
REMEDY = ("Remove it from the source note it comes from, or from what wrote it there; "
          "architecture.md, Provenance check, says what the check finds and what it exempts")

LOCAL_FILE = ".public-check.local"
"""se's local list of private terms, at the root of a repository or vault, never checked in."""

EXCEPTIONS_FILE = ".check-exceptions.local.json"
"""The local file of exceptions, found as the local list is and never checked in (architecture.md,
Exceptions)."""
EXCEPTIONS_OWNER = "architecture.md, Exceptions"
LOCAL_ONLY = ("timestamp", "absolute-path", "local-term")
"""The labels an exception of the committed layer may not take: a digest of a date, a path or a
name can be found by trying candidates, and a local term is private by definition."""

GENERATION_TIMESTAMP = "artifact-data document.generation.timestamp"
"""The one place obs writes its own build time on purpose (render.py, the model's ``generation``)."""

EXEMPTIONS = {GENERATION_TIMESTAMP: "generation-timestamp"}
"""Place to the name of its documented exemption (architecture.md, Provenance check): a finding there
is reported under that name and never warns or refuses."""

VENDORED = (*(library.element for library in LIBRARIES.values()), "yaml-script")
"""The script elements that embed a third-party library as its release ships it (libraries.py, and
js-yaml in render.py): their own text, such as Plotly's example dates, says nothing of the build.
A finding on one of their lines is covered by the exemption ``vendored-library:<element id>``."""

ISLAND_TAG = '<script id="obs-comments" type="application/json" data-comment-island>'
"""The comment island's start tag exactly as the build writes it (render.py)."""
REVIEW_TIME = "review-time"
_REVIEW_TIMES = re.compile(
    rf"{re.escape(ISLAND)}\.(?:comments\[\d+\]\.(?:created|modified)|(?:decisions|states)\[\d+\]\.created)")
"""The comment island's places the exemption ``review-time`` covers: the time each review entry was
made, which the core's schema allows to be an RFC 3339 time and nothing else (``$defs/time``)."""
_ISLAND_ID = re.compile(r"""<script\b[^>]*?\sid\s*=\s*(?:"obs-comments"|'obs-comments'|obs-comments(?=[\s/>]))""",
                        re.IGNORECASE)

_SEGMENT = r"""[^\s/\\:*?"'<>|`,;()\[\]{}=]+"""
_URL_CHARACTERS = r"""[^\s"'<>()\\]"""
_SESSION_ID = r"session_[0-9A-Za-z]{6,}"
DETECTORS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # A URL that carries a session id; its id is not reported a second time.
    ("session-url", re.compile(rf"https?://{_URL_CHARACTERS}*?{_SESSION_ID}{_URL_CHARACTERS}*")),
    ("session-id", re.compile(rf"(?<![0-9A-Za-z]){_SESSION_ID}")),
    # A path below a person's home folder or an agent's scratch folder, on any of the systems a
    # build runs on; JSON or JavaScript text may double its backslashes.
    ("absolute-path", re.compile(
        rf"(?<![\w.~/\\:-])(?:/home/{_SEGMENT}|/Users/{_SEGMENT}|/root/{_SEGMENT}|/tmp/claude"
        rf"|/(?:private/)?var/folders/{_SEGMENT}|[A-Za-z]:(?:\\\\|\\|/)Users(?:\\\\|\\|/){_SEGMENT})")),
    # A date with a time of day, as a build writes its time: 2026-11-14T10:18:33Z, 2026-11-14 10:18.
    ("timestamp", re.compile(r"(?<!\d)\d{4}-[01]\d-[0-3]\d[T ][0-2]\d:[0-5]\d")),
)
"""Each kind of provenance the check finds, by its label, in the order it looks."""
_TIME = re.compile(r"\d-[01]\d-[0-3]\d[T ][0-2]\d:")
_PATH_MARKS = ("home/", "Users", "root/", "tmp/claude", "var/folders/")
_MAY_HOLD = {
    "session-url": lambda text: "session_" in text,
    "session-id": lambda text: "session_" in text,
    "absolute-path": lambda text: any(mark in text for mark in _PATH_MARKS),
    "timestamp": lambda text: _TIME.search(text) is not None,
}
"""Per detector, whether a text may hold what it finds: a text without the detector's literal part
holds none, and plain substring tests read most places far faster than the detectors would."""


@dataclass(frozen=True)
class Finding:
    """One provenance hit: ``where`` in the artifact, ``label`` what (a detector or ``local-term:N``),
    ``digest`` the digest of the text it matched, and ``exemption`` the name of the documented
    exemption or of the exception that covers it, or None."""
    where: str
    label: str
    digest: str
    exemption: str | None = None

    def __str__(self) -> str:
        covered = f" (exempt: {self.exemption})" if self.exemption else ""
        return f"{self.where}: {self.label}{covered}"


@dataclass(frozen=True)
class CheckException:
    """An exception of the provenance check: the ``label`` (a detector's, or ``local-term`` for a
    local term on any line) and ``digest`` of the findings it covers, the ``layer`` that holds it
    (``settings`` or ``local``) and, where it names one, the one place ``where`` it covers them."""
    label: str
    digest: str
    layer: str
    where: str | None = None


def digest(text: str) -> str:
    """The digest of a matched text: ``sha256:`` and SHA-256 over its UTF-8 bytes in lowercase hex."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def findings(artifact: str, local_terms: tuple[tuple[str, re.Pattern[str]], ...] = (),
             exceptions: tuple[CheckException, ...] = ()) -> list[Finding]:
    """Every provenance hit of the built ``artifact``: each detector's, then each local term's, per
    place, one per place, label and digest, each covered as ``excepted`` says. ``local_terms`` are
    labelled patterns, as ``local_terms`` reads them."""
    found: list[Finding] = []
    html = artifact_html(artifact)
    vendored = _vendored_lines(html)
    island = comment_island(html)
    texts = artifact_texts(artifact)
    if island:
        place, line, model = island
        texts = (*((where, line if where == place else text) for where, text in texts), *_strings(model, ISLAND))
    for where, text in texts:
        exemption = EXEMPTIONS.get(where) or vendored.get(where) or review_time(where)
        found += (Finding(where, label, hashed, exemption) for label, hashed in _hits(text, local_terms))
    return excepted(found, exceptions)


def review_time(where: str) -> str | None:
    """``review-time`` where ``where`` is a review entry's time in the comment island, else None."""
    return REVIEW_TIME if _REVIEW_TIMES.fullmatch(where) else None


def comment_island(html: str) -> tuple[str, str, object] | None:
    """The comment island of ``html`` (the artifact without the data island's content) where it has
    the shape the build writes: its place as an HTML line, that line without the island's JSON, and
    the JSON's value. None for an island of any other shape, whose line is then read as it is: not
    exactly one script element with the id, another start tag, JSON past its line, a key twice, or
    JSON the core's schema of a resolved model refuses."""
    start = html.find(ISLAND_TAG)
    if start < 0 or len(_ISLAND_ID.findall(html)) != 1 or html.count(ISLAND_TAG) != 1:
        return None
    body = start + len(ISLAND_TAG)
    end = html.find("</script>", body)
    if end < 0 or len(html[start:end + len("</script>")].splitlines()) != 1:
        return None
    model = _unique_json(html[body:end])
    if model is None or not _resolved().is_valid(model):
        return None
    # Numbered as artifact_texts numbers them, by str.splitlines.
    number = len((html[:start] + "<").splitlines())
    return f"HTML line {number}", (html[:body] + html[end:]).splitlines()[number - 1], model


def _unique_json(text: str) -> object | None:
    """The JSON value of ``text``, or None where it is not JSON or an object holds a key twice, which
    would hide its first value from the check."""
    twice = False

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        nonlocal twice
        twice = twice or len({key for key, _ in pairs}) != len(pairs)
        return dict(pairs)

    try:
        value = json.loads(text, object_pairs_hook=unique)
    except ValueError:
        return None
    return None if twice else value


def _hits(text: str, local_terms: tuple[tuple[str, re.Pattern[str]], ...]) -> list[tuple[str, str]]:
    """Each label and digest the detectors, then the local terms, find in one ``text``, in the order
    the text first holds each."""
    hits: dict[tuple[str, str], None] = {}
    detectors = tuple((label, pattern) for label, pattern in DETECTORS if _MAY_HOLD[label](text))
    for label, pattern in (*detectors, *local_terms):
        for match in pattern.finditer(text):
            hits[label, digest(match[0])] = None
        if label == "session-url":  # its session id is the same hit
            text = pattern.sub("", text)
    return list(hits)


def excepted(found: list[Finding], exceptions: tuple[CheckException, ...]) -> list[Finding]:
    """``found``, each finding no exemption covers marked ``exception:<layer>`` where an exception
    has its label (``local-term`` covering every ``local-term:N``), its digest and, where it names
    one, its place; the committed layer's (``settings``) where both cover it."""
    def covering(finding: Finding) -> str | None:
        label = "local-term" if finding.label.startswith("local-term:") else finding.label
        layers = {exception.layer for exception in exceptions
                  if (exception.label, exception.digest) == (label, finding.digest)
                  and exception.where in (None, finding.where)}
        return next((f"exception:{layer}" for layer in ("settings", "local") if layer in layers), None)

    return [finding if finding.exemption else replace(finding, exemption=covering(finding))
            for finding in found]


def _vendored_lines(html: str) -> dict[str, str]:
    """The places (``HTML line N``) inside a vendored library's script element, to its exemption."""
    places = {}
    for element in VENDORED:
        match = re.search(rf'<script id="{re.escape(element)}"[^>]*>.*?</script>', html, re.S)
        if match:
            # Numbered as artifact_texts numbers them, by str.splitlines.
            first, last = len((html[:match.start()] + "<").splitlines()), len(html[:match.end()].splitlines())
            for number in range(first, last + 1):
                places[f"HTML line {number}"] = f"vendored-library:{element}"
    return places


def reported(found: list[Finding]) -> list[Finding]:
    """The findings no exemption covers: those a build warns of, or refuses."""
    return [finding for finding in found if finding.exemption is None]


def problems(found: list[Finding], digests: bool = False) -> list[InputError]:
    """The errors a build warns of, or refuses with (cli.py): one per place and label among the
    findings nothing covers, naming every digest of them there with ``digests`` (--finding-digests)."""
    places: dict[tuple[str, str], list[str]] = {}
    for finding in reported(found):
        places.setdefault((finding.where, finding.label), []).append(finding.digest)
    return [problem(where, label, named if digests else []) for (where, label), named in places.items()]


def problem(where: str, label: str, digests: list[str]) -> InputError:
    """The error of the findings of ``label`` at ``where``, naming ``digests``."""
    return InputError(SOURCE, where, f"carries provenance ({', '.join([label, *digests])})", REMEDY)


def check_exceptions(entries: list[dict], layer: str) -> tuple[CheckException, ...]:
    """The exceptions of one layer's valid ``entries`` (cfg.schema.json, ``checkException``)."""
    return tuple(CheckException(entry["label"], entry["digest"], layer, entry.get("where"))
                 for entry in entries if entry["check"] == "provenance")


def committed_problems(entries: list[dict], source: object,
                       local_terms: tuple[tuple[str, re.Pattern[str]], ...]) -> list[InputError]:
    """What fails the committed layer's ``entries`` (``artifact.checkExceptions`` of ``source``): an
    exception of a label only the local file takes, and a ``reason`` or ``where`` that carries
    provenance or a local term; each named by its field path, never by its text."""
    failed = []
    for number, entry in enumerate(entries):
        field = f"artifact.checkExceptions[{number}]"
        if entry["label"] in LOCAL_ONLY:
            failed.append(committed_problem(source, field, f"is a {entry['label']} exception, which the "
                                            "committed settings may not hold", "Move the entry"))
            continue
        failed += (committed_problem(source, f"{field}.{key}", "carries provenance", "Reword it, or move the entry")
                   for key in ("reason", "where") if key in entry and _hits(entry[key], local_terms))
    return failed


def committed_problem(source: object, field: str, issue: str, remedy: str) -> InputError:
    return InputError(source, field, issue, f"{remedy} to the local file {EXCEPTIONS_FILE}, which is never "
                      f"checked in; {EXCEPTIONS_OWNER}, says why")


def local_list(start: Path, name: str = LOCAL_FILE) -> Path | None:
    """The local list nearest ``start``, or the local file ``name``: in it or the first of its parents
    that has one."""
    for folder in (start, *start.parents):
        candidate = folder / name
        if candidate.is_file():
            return candidate
    return None


def local_exceptions(path: Path | None) -> tuple[CheckException, ...]:
    """The exceptions of the local file at ``path``, ``{"checkExceptions": [...]}``, every label
    allowed; one that is not JSON or breaks that form fails naming the file and the field path."""
    if path is None:
        return ()
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InputError(path, "", f"is not JSON ({error.msg} at line {error.lineno}, column {error.colno})",
                         f"Correct the JSON there; {EXCEPTIONS_OWNER}, says what the file holds") from None
    error = schema_error(list(_local_validator().iter_errors(content)), path, EXCEPTIONS_OWNER)
    if error:
        raise error
    return check_exceptions(content["checkExceptions"], "local")


def _local_validator() -> Draft202012Validator:
    """The local file's form: the settings' exceptions (cfg.schema.json, ``checkException``)."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator({
        "$defs": schema["$defs"], "type": "object", "additionalProperties": False,
        "required": ["checkExceptions"],
        "properties": {"checkExceptions": {"type": "array", "items": {"$ref": "#/$defs/checkException"}}}})


def local_terms(path: Path | None) -> tuple[tuple[str, re.Pattern[str]], ...]:
    """The private terms of se's local list at ``path``, read as se's public check reads it: one
    case-insensitive regex a line, blank lines, ``#`` comments and ``off:<label>`` entries (which
    switch se's public entries off, and this check has none) skipped; each labelled by its line."""
    if path is None:
        return ()
    terms = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = raw.strip()
        if not text or text.startswith("#") or text.startswith("off:"):
            continue
        try:
            terms.append((f"local-term:{number}", re.compile(text, re.IGNORECASE)))
        except re.error as error:
            raise InputError(path, f"line {number}", f"is not a valid regex ({error.msg})",
                             "Correct the entry; se's README leads to the rules of the local list") from None
    return tuple(terms)
