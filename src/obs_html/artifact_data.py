"""The standalone canonical-data transport and ordered runtime boundary."""
from __future__ import annotations

import base64
import gzip
import json
import re
from html.parser import HTMLParser
from importlib.resources import files
from zlib import error as ZlibError

from obs_html.errors import InputError


ARTIFACT_PATTERN = re.compile(r'(<script id="artifact-data"[^>]*>)(.*?)(</script>)', re.DOTALL)
# A script element: its opening tag, then its body up to the first closing tag. Found as two
# searches, not one pattern with a lazy body, which costs a step per character of a megabyte body.
_SCRIPT_OPENING = re.compile(r"<script\b[^>]*>", re.IGNORECASE)
_SCRIPT_CLOSING = re.compile(r"</script>", re.IGNORECASE)
_INERT_TYPE = "application/x-obs-html-script"


class _Attributes(HTMLParser):
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.attrs = dict(attrs)


def _attributes(opening: str) -> dict[str, str | None]:
    parser = _Attributes()
    parser.feed(opening)
    return parser.attrs


def serialize_artifact_data(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def encode_artifact_data(data: dict, compression: str | None = None) -> str:
    if compression is None:
        compression = json.loads(files("obs_html").joinpath("cfg.json").read_text(encoding="utf-8"))["artifact"]["dataCompression"]
    if compression not in {"gzip", "none"}:
        raise InputError("obs-html (src/obs_html/artifact_data.py)", "compression", f"is {compression!r}, not "
                         "gzip or none", "Pass artifact.dataCompression as cfg.schema.json allows it")
    text = serialize_artifact_data(data)
    raw = text.encode("utf-8")
    plain = (f'<script id="artifact-data" type="application/json" data-artifact-data '
             f'data-compression="{compression}">{text}</script>')
    encoded = base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii") if compression == "gzip" else ""
    if encoded:
        compressed = (f'<script id="artifact-data" type="application/octet-stream" data-artifact-data '
                      f'data-compression="{compression}" data-encoding="gzip">{encoded}</script>')
        if len(compressed) < len(plain.encode("utf-8")):
            return compressed
    return plain


ISLAND = "artifact HTML"
"""An artifact as a message names it: its data island is read from the HTML text, not a file."""
REGENERATE = "Regenerate the HTML with obs-html"


def decode_artifact_data(artifact: str) -> dict:
    match = ARTIFACT_PATTERN.search(artifact)
    if not match:
        raise InputError(ISLAND, "script#artifact-data", "is missing", REGENERATE)
    text = _island_text(match)
    try:
        data = json.loads(text)
    except ValueError as error:
        raise InputError(ISLAND, "script#artifact-data", f"is not JSON ({error})", REGENERATE) from error
    if not isinstance(data, dict):
        raise InputError(ISLAND, "script#artifact-data", "is no JSON object", REGENERATE)
    return data


def chapter_html(artifact: str, chapter: str) -> str:
    """The HTML the artifact stores for ``chapter``: the note whose id (slug) it is, else the one
    note whose title it is. An unknown or shared title names the chapter and the ids to choose from."""
    notes = decode_artifact_data(artifact).get("notes", [])
    for note in notes:
        if note.get("slug") == chapter:
            return note.get("html", "")
    titled = [note for note in notes if note.get("title") == chapter]
    if len(titled) == 1:
        return titled[0].get("html", "")
    if titled:
        ids = ", ".join(note.get("slug", "") for note in titled)
        raise InputError(ISLAND, "--print-chapter", f"names {chapter!r}, the title of the chapters {ids}",
                         "Give one of these ids instead")
    ids = ", ".join(note.get("slug", "") for note in notes) or "none"
    raise InputError(ISLAND, "--print-chapter", f"names no chapter {chapter!r}; the available ids are {ids}",
                     "Give one of these ids, or a chapter's title")


_BLOCKS = {"address", "article", "aside", "blockquote", "br", "dd", "details", "div", "dl", "dt",
           "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr",
           "li", "main", "nav", "ol", "p", "pre", "section", "summary", "table", "td", "th", "tr",
           "ul"}


_TEXTLESS = frozenset({"style", "script"})


class _Text(HTMLParser):
    """Collects plain text, one line per block element; text inside <pre> keeps its lines, and
    a style or script element (an inline figure's SVG has one) has none."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.current: list[str] = []
        self.pre = 0
        self.hidden = 0

    def end_line(self) -> None:
        line = "".join(self.current)
        if not self.pre:
            line = " ".join(line.split())
        if line.strip():
            self.lines.append(line)
        self.current = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _BLOCKS:
            self.end_line()
        if tag == "pre":
            self.pre += 1
        if tag in _TEXTLESS:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCKS:
            self.end_line()
        if tag == "pre" and self.pre:
            self.pre -= 1
        if tag in _TEXTLESS and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if self.hidden:
            return
        if self.pre:
            self.lines.extend(data.strip("\n").splitlines())
        else:
            self.current.append(data)


def html_text(html: str) -> str:
    """Plain text of HTML: one line per block, inline markup dropped."""
    parser = _Text()
    parser.feed(html)
    parser.close()
    parser.end_line()
    return "".join(f"{line}\n" for line in parser.lines)


def _island_text(match: re.Match[str]) -> str:
    attrs = _attributes(match[1])
    encoding = attrs.get("data-encoding")
    if encoding == "gzip":
        if attrs.get("type") != "application/octet-stream":
            raise InputError(ISLAND, "script#artifact-data.type", f"is {attrs.get('type')!r}, not "
                             "application/octet-stream, the type of a gzip island", REGENERATE)
        try:
            raw = base64.b64decode(re.sub(r"\s", "", match[2]), validate=True)
            return gzip.decompress(raw).decode("utf-8")
        except (ValueError, OSError, EOFError, ZlibError) as error:
            raise InputError(ISLAND, "script#artifact-data", f"is no base64 gzip of UTF-8 text ({error})",
                             REGENERATE) from error
    if encoding is None and attrs.get("type") == "application/json":
        return match[2]
    raise InputError(ISLAND, "script#artifact-data.data-encoding", f"is {encoding or attrs.get('type')!r}, "
                     "neither gzip nor plain JSON", REGENERATE)


def same_artifact_content(artifact: str, existing: str) -> bool:
    """Whether two artifacts differ at most in their generation timestamp.

    The timestamp records the last content change, so an unchanged rebuild keeps the
    existing artifact instead of rewriting it with a new build time.
    """
    new, old = ARTIFACT_PATTERN.search(artifact), ARTIFACT_PATTERN.search(existing)
    if (not new or not old or new[1] != old[1] or artifact[:new.start()] != existing[:old.start()]
            or artifact[new.end():] != existing[old.end():]):
        return False
    try:
        previous_text = _island_text(old)
        data, previous = json.loads(_island_text(new)), json.loads(previous_text)
        data["document"]["generation"]["timestamp"] = previous["document"]["generation"]["timestamp"]
        return serialize_artifact_data(data) == previous_text
    except (ValueError, TypeError, KeyError, OSError, EOFError, ZlibError):
        return False


def prepare_artifact_scripts(artifact: str) -> str:
    """Make every model consumer inert, including scripts added by later stages."""
    def prepare(opening: str) -> str:
        attrs = _attributes(opening)
        if attrs.get("id") in {"reader-startup-script", "running-header-script", "artifact-bootstrap-script"}:
            return opening
        kind = attrs.get("type", "")
        if kind not in {"", "text/javascript", "application/javascript"}:
            return opening
        opening = re.sub(r"""\s+type\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)""", "", opening, flags=re.IGNORECASE)
        return opening[:-1] + f' type="{_INERT_TYPE}" data-obs-runtime>'

    parts, done = [], 0
    while (opening := _SCRIPT_OPENING.search(artifact, done)) and (
            closing := _SCRIPT_CLOSING.search(artifact, opening.end())):
        parts += [artifact[done:opening.start()], prepare(opening[0]), artifact[opening.end():closing.end()]]
        done = closing.end()
    artifact = "".join(parts) + artifact[done:]
    if 'id="artifact-bootstrap-script"' not in artifact:
        runtime = files("obs_html").joinpath("artifact-data.js").read_text(encoding="utf-8")
        artifact = artifact.replace('<script id="artifact-data"',
                                f'<script id="artifact-bootstrap-script">{runtime}</script>\n'
                                '<script id="artifact-data"', 1)
    return artifact
