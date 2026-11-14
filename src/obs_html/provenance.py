"""The provenance check of a built artifact: built HTML in, findings out, each naming its place.

Reader: whoever changes what the provenance check looks for, how a build reacts to it, or its
exemption.

spec/architecture.md, Provenance check, owns the design. The module is pure: ``findings`` takes the
artifact's text and the local list's terms and returns what it found, and the CLI (cli.py,
``_write_artifact``) warns of each, or refuses the build where ``artifact.refuseProvenance`` is true.
A finding names its place (an HTML line, or a field path of the decoded data island, as the
exposure check names them: exposure.py, ``artifact_texts``) and the label of what it found, never the
matched text, as se's public check reports a hit.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from obs_html.errors import InputError
from obs_html.exposure import artifact_html, artifact_texts
from obs_html.libraries import LIBRARIES


SOURCE = "obs-html artifact"
"""The finished artifact, before it is written: a finding names where in it."""
REMEDY = ("Remove it from the source note it comes from, or from what wrote it there; "
          "architecture.md, Provenance check, says what the check finds and what it exempts")

LOCAL_FILE = ".public-check.local"
"""se's local list of private terms, at the root of a repository or vault, never checked in."""

GENERATION_TIMESTAMP = "artifact-data document.generation.timestamp"
"""The one place obs writes its own build time on purpose (render.py, the model's ``generation``)."""

EXEMPTIONS = {GENERATION_TIMESTAMP: "generation-timestamp"}
"""Place to the name of its documented exemption (architecture.md, Provenance check): a finding there
is reported under that name and never warns or refuses."""

VENDORED = (*(library.element for library in LIBRARIES.values()), "yaml-script")
"""The script elements that embed a third-party library as its release ships it (libraries.py, and
js-yaml in render.py): their own text, such as Plotly's example dates, says nothing of the build.
A finding on one of their lines is covered by the exemption ``vendored-library:<element id>``."""

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
    and ``exemption`` the name of the documented exemption that covers it, or None."""
    where: str
    label: str
    exemption: str | None = None

    def __str__(self) -> str:
        covered = f" (exempt: {self.exemption})" if self.exemption else ""
        return f"{self.where}: {self.label}{covered}"


def findings(artifact: str, local_terms: tuple[tuple[str, re.Pattern[str]], ...] = ()) -> list[Finding]:
    """Every provenance hit of the built ``artifact``: each detector's, then each local term's, per
    place. ``local_terms`` are labelled patterns, as ``local_terms`` reads them."""
    found: list[Finding] = []
    vendored = _vendored_lines(artifact_html(artifact))
    for where, text in artifact_texts(artifact):
        exemption = EXEMPTIONS.get(where) or vendored.get(where)
        detectors = tuple((label, pattern) for label, pattern in DETECTORS if _MAY_HOLD[label](text))
        for label, pattern in (*detectors, *local_terms):
            if pattern.search(text):
                found.append(Finding(where, label, exemption))
                if label == "session-url":  # its session id is the same hit
                    text = pattern.sub("", text)
    return found


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


def problem(finding: Finding) -> InputError:
    """A reported finding as the error a build warns of, or refuses with (cli.py)."""
    return InputError(SOURCE, finding.where, f"carries provenance ({finding.label})", REMEDY)


def local_list(start: Path) -> Path | None:
    """The local list nearest ``start``: in it or the first of its parents that has one."""
    for folder in (start, *start.parents):
        candidate = folder / LOCAL_FILE
        if candidate.is_file():
            return candidate
    return None


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
