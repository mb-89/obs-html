"""What an artifact's bytes are made of: its HTML element by element, and its PDF stream by stream.

Reader: whoever decides whether, or where, obs-html makes its artifacts smaller (architecture.md,
Rendering and runtime): which scripts, styles, libraries, data and assets a page carries, and
what its printed PDF holds.

    uv run python adapters/html/test/measure/artifact_bytes.py [NAME ...] [--output DIRECTORY]

It builds, with this checkout's core and adapter, each committed deck through the core as a deck
is built (``obs-document --source <manifest> --adapter html``): ``bless-deck``
(spec/examples/bless-deck) and ``phone-deck`` (test/fixtures/phone-deck); and each committed
fixture report, every Document in test/fixtures/documents, with ``obs-html DOCUMENT``. Each is
also printed to PDF (``obs-html DOCUMENT out.pdf``). NAME limits the run to those artifacts.

For each artifact it prints one Markdown table of the HTML and one of the PDF:

- HTML: every top-level ``<script>`` and ``<style>`` element, whole, by its id: each runtime
  script; each vendored library (a script that holds a file of the package's ``vendor/``); each
  style; the data island (``artifact-data``), its packed bytes and, beside them, its decoded JSON
  with the ``assets`` and ``embeddedAssets`` it carries; the other JSON data; the source archive;
  then the ``data:`` URIs of the markup and the rest of the markup.
- PDF: each stream kind (page content, font files, ToUnicode maps, images, forms, embedded files,
  metadata, other) with its count and its stored bytes, then what is no stream's data (objects,
  cross-reference table, trailer).

Every row of the Bytes column is a disjoint part of the file, so the Total row is a sum, and it
states the file's size beside it; the decoded sizes are no part of the sum. It also writes the
tables to DIRECTORY (default ``data/data_output/artifact-bytes``, ignored) as ``artifact-bytes.md``,
beside the artifacts it measured, in ``built/``. Nothing in the suite or the build runs it.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import gzip
import io
import json
import re
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import DictionaryObject, IndirectObject, StreamObject

from obs_html import cli
from obs_html.artifact_data import ARTIFACT_PATTERN, decode_artifact_data

ADAPTER = Path(__file__).resolve().parents[2]
ROOT = ADAPTER.parents[1]
DOCUMENTS = ADAPTER / "test" / "fixtures" / "documents"
DECKS = {"bless-deck": ROOT / "spec" / "examples" / "bless-deck", "phone-deck": ADAPTER / "test" / "fixtures" / "phone-deck"}
ELEMENT = re.compile(r"<(script|style)\b([^>]*)>", re.IGNORECASE)
DATA_URI = re.compile(r"""data:[^"'\s)>]+""")
ISLAND_ASSETS = ("assets", "embeddedAssets")
"""The data island's keys that carry assets (render.py): the icons and the embedded files."""
JSON_TYPES = {"application/json"}
BINARY_TYPES = {"application/octet-stream"}


@dataclass(frozen=True)
class Part:
    """One row: what it is, its kind, its bytes in the file (None for a row that is no part of the
    sum) and, where it has one, its decoded size."""
    name: str
    kind: str
    size: int | None
    decoded: int | None = None


def vendored_sources() -> dict[str, str]:
    """Each JavaScript file the package vendors, by its path below ``vendor/``: a line of it that
    identifies it (its longest line, cut to 200 characters)."""
    vendor = files("obs_html").joinpath("vendor")
    found = {}

    def walk(folder, prefix: str) -> None:
        for entry in folder.iterdir():
            if entry.is_dir():
                walk(entry, f"{prefix}{entry.name}/")
            elif entry.name.endswith(".js"):
                lines = entry.read_text(encoding="utf-8").splitlines()
                found[f"{prefix}{entry.name}"] = max(lines, key=len)[:200]
    walk(vendor, "")
    return found


def _attribute(attributes: str, name: str) -> str | None:
    match = re.search(rf'\b{name}="([^"]*)"', attributes)
    return match[1] if match else None


def _island(element: str) -> tuple[int, list[Part]]:
    """The data island's decoded size and the decoded size of each asset key it carries."""
    data = decode_artifact_data(element)
    text = ARTIFACT_PATTERN.search(element)[2]
    decoded = len(gzip.decompress(base64.b64decode(text))) if 'data-encoding="gzip"' in element else len(text.encode())
    return decoded, [Part(f"artifact-data: {key}", "assets (decoded, in the island)", None,
                          len(json.dumps(data[key], ensure_ascii=False, separators=(",", ":")).encode()))
                     for key in ISLAND_ASSETS if key in data]


def html_parts(html: str, vendored: dict[str, str]) -> list[Part]:
    """``html`` as disjoint parts whose sizes add up to its bytes, plus the island's decoded rows."""
    parts, markup, at = [], [], 0
    while match := ELEMENT.search(html, at):
        markup.append(html[at:match.start()])
        tag, attributes = match[1].lower(), match[2]
        close = html.lower().find(f"</{tag}", match.end())
        end = html.find(">", close) + 1
        element, content = html[match.start():end], html[match.end():close]
        name, kind = _attribute(attributes, "id") or f"(unnamed {tag})", _attribute(attributes, "type") or ""
        size = len(element.encode("utf-8"))
        if tag == "style":
            parts.append(Part(name, "style", size))
        elif name == "artifact-data":
            decoded, assets = _island(element)
            parts.append(Part(name, "data island (packed; decoded beside)", size, decoded))
            parts.extend(assets)
        elif kind in JSON_TYPES:
            parts.append(Part(name, "JSON data", size))
        elif kind in BINARY_TYPES:
            parts.append(Part(name, "embedded asset", size))
        else:
            library = next((path for path, line in vendored.items() if line in content), None)
            parts.append(Part(name, f"vendored library ({library})" if library else "runtime script", size))
        at = end
    markup.append(html[at:])
    rest = "".join(markup)
    uris = sum(len(uri.encode("utf-8")) for uri in DATA_URI.findall(rest))
    if uris:
        parts.append(Part("data: URIs in the markup", "embedded asset", uris))
    parts.append(Part("markup", "markup", len(rest.encode("utf-8")) - uris))
    return parts


def _objects(reader: PdfReader) -> Iterator[tuple[int, object]]:
    """Each object of the PDF's cross-reference table by its number; a free entry gives none."""
    for number in range(1, int(reader.trailer["/Size"])):
        value = reader.get_object(IndirectObject(number, 0, reader))
        if value is not None:
            yield number, value


def _roles(reader: PdfReader) -> dict[int, str]:
    """The stream kind that the objects referring to a stream give it, by object number."""
    roles: dict[int, str] = {}

    def mark(reference, role: str) -> None:
        for item in reference if isinstance(reference, list) else [reference]:
            if isinstance(item, IndirectObject):
                roles[item.idnum] = role

    for page in reader.pages:
        mark(page.get("/Contents"), "page content")
    for _, value in _objects(reader):
        if not isinstance(value, DictionaryObject):
            continue
        for key in ("/FontFile", "/FontFile2", "/FontFile3"):
            if key in value:
                mark(value.raw_get(key), "font file")
        if "/ToUnicode" in value:
            mark(value.raw_get("/ToUnicode"), "ToUnicode map")
    return roles


def pdf_parts(path: Path) -> list[Part]:
    """The PDF's stream data by kind, with its count, and what is no stream's data; the sizes add up."""
    reader = PdfReader(path)
    roles, kinds = _roles(reader), {}
    for number, stream in _objects(reader):
        if not isinstance(stream, StreamObject):
            continue
        kind = roles.get(number) or {"/Image": "image", "/Form": "form"}.get(stream.get("/Subtype"), "") or {
            "/EmbeddedFile": "embedded file", "/Metadata": "metadata", "/ObjStm": "object stream",
            "/XRef": "cross-reference stream"}.get(stream.get("/Type"), "other")
        count, size, decoded = kinds.get(kind, (0, 0, 0))
        kinds[kind] = (count + 1, size + len(stream._data), decoded + len(stream.get_data()))
    parts = [Part(f"{kind} ({count})", "stream", size, decoded) for kind, (count, size, decoded) in sorted(kinds.items())]
    parts.append(Part("objects, cross-reference table, trailer", "no stream data",
                      path.stat().st_size - sum(part.size for part in parts)))
    return parts


def table(title: str, parts: list[Part], size: int) -> str:
    """``parts`` as a Markdown table whose Total row is their sum, beside the file's ``size``."""
    total = sum(part.size for part in parts if part.size is not None)
    rows = [f"### {title}", "", "| Part | Kind | Bytes | Share | Decoded |", "|---|---|---:|---:|---:|"]
    for part in parts:
        bytes_ = "—" if part.size is None else f"{part.size:,}"
        share = "—" if part.size is None else f"{100 * part.size / size:.1f} %"
        decoded = "" if part.decoded is None else f"{part.decoded:,}"
        rows.append(f"| {part.name} | {part.kind} | {bytes_} | {share} | {decoded} |")
    rows.append(f"| **Total** | sum of the rows | **{total:,}** | | file: {size:,} bytes, "
                f"{'equal' if total == size else 'DIFFERENT'} |")
    if total != size:
        raise SystemExit(f"artifact_bytes.py: {title}: the parts add up to {total} bytes, the file has {size}")
    return "\n".join(rows) + "\n"


def build(folder: Path, names: list[str]) -> dict[str, tuple[Path, Path]]:
    """Each committed deck and fixture report, in ``folder``, as its HTML and its PDF."""
    sources = {name: None for name in DECKS} | {path.stem: path for path in sorted(DOCUMENTS.glob("*.json"))}
    unknown = sorted(set(names) - sources.keys())
    if unknown:
        raise SystemExit(f"artifact_bytes.py: no deck or fixture report {', '.join(unknown)}; "
                         f"choose from {', '.join(sources)}")
    built = {}
    for name, document in sources.items():
        if names and name not in names:
            continue
        html, pdf = folder / f"{name}.html", folder / f"{name}.pdf"
        if document is None:
            document = folder / f"{name}.json"
            subprocess.run([sys.executable, "-m", "obs.document", "--source", str(DECKS[name] / "manifest.md"),
                            "--document", str(document), "--adapter", "html", "--destination", str(html)],
                           check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
        elif cli.main([str(document), str(html)]) != 0:
            raise SystemExit(f"artifact_bytes.py: obs-html could not build {document}")
        if cli.main([str(document), str(pdf)]) != 0:
            raise SystemExit(f"artifact_bytes.py: obs-html could not print {document} to PDF")
        built[name] = html, pdf
    return built


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("names", nargs="*", metavar="NAME", help="only these decks and fixture reports")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "data_output" / "artifact-bytes")
    options = parser.parse_args(argv)
    vendored = vendored_sources()
    folder = options.output / "built"
    folder.mkdir(parents=True, exist_ok=True)
    with contextlib.redirect_stdout(io.StringIO()):
        built = build(folder, options.names)
    out = []
    for name, (html, pdf) in built.items():
        out.append(table(f"{name}.html", html_parts(html.read_bytes().decode("utf-8"), vendored), html.stat().st_size))
        out.append(table(f"{name}.pdf", pdf_parts(pdf), pdf.stat().st_size))
    text = "\n".join(out)
    sys.stdout.write(text)
    (options.output / "artifact-bytes.md").write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
