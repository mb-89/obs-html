"""Render a JSON Document as one portable, interactive HTML artifact.

The Document is the only input: no vault, no core package. Each capability this adapter
renders registers one node renderer in ``CAPABILITIES``; ``adapter.json`` declares the same
identifiers. Chapters become the notes of the artifact-data island, which the embedded
runtime (artifact.js and its companions) reads to build the reader, the bars and the pages.
"""
from __future__ import annotations

import base64
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape, unescape
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator
from urllib.parse import unquote

from jsonschema import Draft202012Validator
from latex2mathml import exceptions as math_exceptions
from latex2mathml.converter import convert as mathml

from obs_html.bars import BarDefinition, discover_bars
from obs_html.config import Config, paper
from obs_html.errors import DOCUMENT_OF, InputError, field_path, schema_error, warn
from obs_html.features import included as included_features, maths_library, maths_library_licence
from obs_html.figure_links import FigureLink
from obs_html.figures import FIGURE_KINDS, render_figure
from obs_html.artifact_data import encode_artifact_data, prepare_artifact_scripts, serialize_artifact_data
from obs_html.semantic_assets import SemanticAssets, markup
from obs_html.declared_style import DeclaredStyles, GitFetcher, user_cache
from obs_html.styles import load_style
from obs_html import source_archive
from obs_html.timings import stage


STRUCTURAL = frozenset(json.loads(files("obs").joinpath("document.schema.json").read_text(encoding="utf-8"))
                       ["$defs"]["structuralType"]["enum"])
"""The node types every adapter renders, as the core's Document schema lists them (structuralType)."""
PROFILE_DEFAULTS = {
    "layout": "paged",
    "heading": "cover",
    "pages": [{"page": "cover"}, {"page": "abstract", "title": "Abstract"},
              {"page": "contents", "title": "Contents"}],
    "figures": {"numbering": "none", "label": "Figure", "labelPlural": "Figures"},
    "query": {"scope": "chapters"},
    "cssSnippets": [],
}
COVER_FIELDS = ("authors", "reviewers", "approvers", "document number", "legal entity")
HOME = "home"
DOCK_DIRECTIONS = (
    ("left", "left", "vertical"),
    ("right", "right", "vertical"),
    ("top", "up", "horizontal"),
    ("bottom", "down", "horizontal"),
)


@dataclass
class Context:
    document: dict[str, object]
    assets: SemanticAssets
    chapter: str = ""
    links: dict[str, dict[str, str]] = field(default_factory=dict)
    files: dict[str, dict[str, str]] = field(default_factory=dict)
    chapters: dict[str, str] = field(default_factory=dict)
    headings: dict[str, str] = field(default_factory=dict)
    tables: list[dict[str, object]] = field(default_factory=list)
    marks: list[dict[str, object]] = field(default_factory=list)
    frontmatter: dict[str, object] = field(default_factory=dict)
    paths: dict[str, str] = field(default_factory=dict)
    records: dict[str, dict[str, object]] = field(default_factory=dict)
    editable: dict[str, dict[str, object]] = field(default_factory=dict)
    unknown: dict[str, dict[str, str]] = field(default_factory=dict)
    fields: dict[str, dict[str, str]] = field(default_factory=dict)
    row_keys: dict[str, str] = field(default_factory=dict)
    embed_attachments: bool = False
    """The evidence edition (obs-html --embed-attachments): a marked attachment is a download of
    its asset's bytes; otherwise (the light edition) it is provenance text."""
    phrasing: bool = False
    """Whether the node being rendered sits where HTML allows only phrasing content (inside a
    paragraph or a heading), so it may write no block element."""
    where: list[object] = field(default_factory=list)
    """The path of the node being rendered in the Document, as an error names it."""
    figure_position: int = 0
    """The current note's figures so far, which name an anchor where nothing else does."""
    figures: dict[str, object] = field(default_factory=lambda: dict(PROFILE_DEFAULTS["figures"]))
    """The manifest's obsHtml.figures (numbering, label, labelPlural)."""
    figure_numbers: dict[str, list[str]] = field(default_factory=dict)
    """Each chapter's figure numbers in document order, "" for a figure without one (_number_figures)."""
    figure_blocks: dict[tuple[str, str], str] = field(default_factory=dict)
    """The number of each figure with a block id, by chapter and block id, "" for none."""
    conjunctions: tuple[str, ...] = ()
    """The words that may separate merged figure references (cfg.json artifact.figureReferences)."""
    bordered_tags: tuple[str, ...] = ()
    """The tag kinds whose paragraphs a shared card encloses (cfg.json artifact.borderedTags)."""


def _source(document: dict[str, object]) -> str:
    """The Document as a message names it: by the manifest note it was built from."""
    return f"{DOCUMENT_OF}{document['manifest']['path']}"


def _rebuild(document: dict[str, object], option: str = "") -> str:
    """Build the Document again from its manifest note, whose path is vault-relative."""
    return (f"Rebuild the Document from the vault's {document['manifest']['path']} with the current obs core "
            f"(obs-document --source{option})")


def _stale(context: Context, parts: list[object], problem: str, remedy: str = "") -> InputError:
    """A Document the current core does not write, at the node being rendered: it is stale or not
    the core's (the core validates what it writes, obs-document)."""
    return InputError(_source(context.document), field_path(parts, field_path(context.where)), problem,
                      remedy or _rebuild(context.document))


@contextmanager
def _at(context: Context, *parts: object) -> Iterator[None]:
    """Render below ``parts`` of the current node path."""
    context.where.extend(parts)
    try:
        yield
    finally:
        del context.where[len(context.where) - len(parts):]


Renderer = Callable[[dict[str, object], Context], str]


def _nothing(_node: dict[str, object], _context: Context) -> str:
    """A marker or data-only node: it states the source used the capability, nothing to show."""
    return ""


def _frontmatter(node: dict[str, object], context: Context) -> str:
    """A note's frontmatter feeds its frontmatter panel, filters and Base rows, not its body; its
    field nodes are its display HTML, by dotted path: a chapter's panel, and the manifest's cover,
    title page and running header (the manifest's abstract renders with no chapter)."""
    if context.chapter:
        context.frontmatter.update(node["attrs"]["metadata"])
    fields = context.fields[context.chapter or HOME] = {}
    for index, child in enumerate(node["children"]):
        if child["type"] == "field":
            with _at(context, "children", index):
                fields[child["attrs"]["name"]] = _nodes(child["children"], context)
    return ""


def _wikilink(node: dict[str, object], context: Context) -> str:
    attrs = node["attrs"]
    chapter = attrs["chapter"]
    if chapter is None:
        return (f'<span class="unresolved" title="{escape(attrs["target"], quote=True)}">'
                f'{escape(attrs["label"])}</span>')
    if "figure" in attrs:
        return _figure_reference(node, context)
    label = "" if attrs["label"] == attrs["target"] else attrs["label"]  # Unaliased: the note's title.
    return _internal_link(chapter, attrs["heading"], label, context)


def _internal_link(chapter: str, heading: str, label: str, context: Context) -> str:
    """A link to a chapter, titled by its label or, unaliased, by the chapter; an unaliased
    link to a quantity note without a heading shows the quantity (obs quantities.md)."""
    title = _chapter_title(chapter, context)
    if not label and not heading:
        quantity = _quantity_link(chapter, context)
        if quantity:
            return quantity
    return f'<a class="internal-link" href="{_internal_href(chapter, heading, context)}">{escape(label or title)}</a>'


def _link_href(attrs: dict[str, object], context: Context) -> str | None:
    """The href of a wikilink: its figure's for a block link, else its chapter's at its heading;
    None for a missing note."""
    chapter = attrs["chapter"]
    if chapter is None:
        return None
    if "figure" in attrs:
        return f"#{chapter}/block-{escape(attrs['figure'], quote=True)}"
    return _internal_href(chapter, attrs["heading"], context)


def _internal_href(chapter: str, heading: str, context: Context) -> str:
    """The href of a link to a chapter, at its heading where it names one."""
    anchor = context.headings.get(f"{chapter}#{_identifier(heading)}") if heading else None
    return f"#{chapter}/{anchor.removeprefix(f'{chapter}--')}" if anchor else f"#{chapter}"


def _quantity_link(chapter: str, context: Context) -> str:
    """A static quantity shows its value and unit; a query quantity is a pending count that the
    runtime (cards.js) fills from the current filter, naming only its owner's source path."""
    record = context.records.get(chapter)
    fields = record["fields"] if record else {}
    if fields.get("kind") != "quantity":
        return ""
    if "query" in fields:
        return (f'<a class="internal-link" href="#{chapter}" '
                f'data-quantity-reference="{escape(str(record["path"]), quote=True)}" '
                'aria-busy="true" role="status">Calculating…</a>')
    return f'<a class="internal-link" href="#{chapter}">{escape(_quantity_label(fields))}</a>'


def _quantity_label(metadata: dict[str, object]) -> str:
    value = metadata.get("value", 0)
    number = str(int(value)) if isinstance(value, float) and value.is_integer() and value != 0 else str(value)
    unit = metadata.get("unit")
    return f"{number} {unit.strip()}" if isinstance(unit, str) else number


def _cards(node: dict[str, object], context: Context) -> str:
    """Data-only cards: titled sections whose metric slots the runtime (cards.js) counts from the
    globally filtered records; only the metric declarations enter the browser. Each card's body is
    its ``document`` child node, rendered like chapter content (nested cards included). The core
    validated the fence (obs capabilities/cards-metrics); one body follows each card."""
    cards, bodies = node["attrs"]["spec"]["cards"], node["children"]
    rendered = []
    for index, (card, body) in enumerate(zip(cards, bodies)):
        series = (card.get("obs") or {}).get("metricsFrom")
        if series:
            _check_series(series, context)
        metrics = [dict(metric) for metric in card.get("metrics", [])]
        with _at(context, "children", index, "attrs"):
            title = _attr_nodes(body["attrs"]["title"], context, "title")
            for position, metric in enumerate(metrics):
                metric["labelHtml"] = _attr_nodes(body["attrs"]["labels"][position], context, "labels", position)
        for metric in metrics:
            if "secondary" in metric:
                metric["valueHtml"] = (f'{_metric_quantity(metric["from"], context)} '
                                       f'({_metric_quantity(metric["secondary"], context)})')
        payload = escape(json.dumps(metrics, ensure_ascii=False), quote=True)
        slots = "".join(f'<div data-record-metric="{index}" role="status" aria-busy="true">Calculating…</div>'
                        for index in range(len(metrics)))
        style = f'record-metrics--{card["metricStyle"]}' if card.get("metricStyle") else ""
        series_data = f' data-record-series="{escape(json.dumps(series), quote=True)}"' if series else ""
        rendered.append(
            f'<section class="content-card record-card" data-record-card="{payload}"{series_data}>'
            f'<header class="content-card-title">{title}</header>'
            + (f'<div class="record-metrics {style}">{slots}</div>' if metrics or series else "")
            + _body(body, index, context) + "</section>")
    return '<div class="record-cards" data-record-cards>' + "".join(rendered) + "</div>\n"


def _attr_nodes(nodes: list[dict[str, object]], context: Context, *parts: object) -> str:
    """The HTML of inline nodes an attribute of the current node holds at ``parts``: a callout
    title, a card title, a metric label (obs capabilities/markdown#Document nodes)."""
    with _at(context, *parts):
        return _nodes(nodes, context)


def _metric_quantity(path: str, context: Context) -> str:
    """The pending count of the query quantity a metric's ``from`` or ``secondary`` names by its
    note path (obs capabilities/cards-metrics); the core resolved it."""
    link = _quantity_link(context.paths.get(path, ""), context)
    if not link:
        raise _stale(context, ["attrs", "spec"], f"names {path!r} in a metric, which is no quantity note "
                     "of the Document")
    return link


def _body(body: dict[str, object], index: int, context: Context) -> str:
    with _at(context, "children", index):
        return _nodes(body["children"], context)


def _check_series(series: dict[str, object], context: Context) -> None:
    """A metric series reads a list from a note's frontmatter: one metric per uniquely labelled item.
    The cards fence's ``obs.metricsFrom`` names the note and its property."""
    record = context.records.get(context.paths.get(str(series.get("sourceNote")), ""))
    source, prefix = (record["path"], "") if record else (_note_source(context), "cards.obs.metricsFrom")
    value: object = record["fields"] if record else None
    for part in str(series.get("property")).split("."):
        value = value.get(part) if isinstance(value, dict) else None
    if not isinstance(value, list):
        raise InputError(source, field_path(["sourceNote" if not record else series.get("property")], prefix),
                         f"is no list a cards fence's metric series can read (obs.metricsFrom names "
                         f"{series.get('sourceNote')}/{series.get('property')})",
                         "Name a note path and a frontmatter list property in obs.metricsFrom")
    labels: set[object] = set()
    for index, item in enumerate(value):
        fields = [item.get(str(series.get(key))) if isinstance(item, dict) else None
                  for key in ("labelProperty", "distinctProperty")]
        if any(not isinstance(field, str) or not field.strip() for field in fields) or fields[0] in labels:
            raise InputError(source, field_path([index], str(series.get("property"))),
                             "needs a label no other item has and a non-empty distinct name for the cards "
                             "fence's metric series", "Give every list item its own label and a distinct "
                             "property value")
        labels.add(fields[0])


def _embed(node: dict[str, object], context: Context) -> str:
    """An embedded note links to its chapter, titled like an unaliased wikilink; an embedded
    file (one that names a Document asset) renders like an attachment."""
    target, chapter = node["attrs"]["target"], node["attrs"]["chapter"]
    if "asset" in node["attrs"]:
        identifier = node["attrs"]["asset"]
        return _file(_document_asset(identifier, context), "", context)
    if chapter is None:
        return f'<span class="unresolved embed" title="{escape(target, quote=True)}">{escape(target)}</span>'
    return f'<a class="internal-link embed" href="#{chapter}">{escape(_chapter_title(chapter, context))}</a>'


def _attachment(node: dict[str, object], context: Context) -> str:
    """An attachment names a Document asset: an image is document content, any other file is a
    download in the evidence edition and provenance text (its label and path) in the light one."""
    identifier, label = node["attrs"]["asset"], node["attrs"]["label"]
    return _file(_document_asset(identifier, context), label, context)


def _document_asset(identifier: str, context: Context) -> dict[str, str]:
    """The asset a node's ``attrs.asset`` names."""
    asset = context.files.get(identifier)
    if asset is None:
        raise _stale(context, ["attrs", "asset"], f"names asset {identifier!r}, which the Document's assets do "
                     "not contain")
    return asset


def _image(asset: dict[str, str], alt: str) -> str:
    """An image from its asset's bytes, never from the vault or the network; without bytes (a
    remote image the build could not fetch), its alt text is a visible label in its place."""
    if "data" in asset:
        return (f'<img src="data:{escape(asset["mediaType"], quote=True)};base64,{asset["data"]}" '
                f'alt="{escape(alt, quote=True)}">')
    shown = escape(alt or asset["href"], quote=True)
    return f'<span class="image-unavailable" role="img" aria-label="{shown}">{shown}</span>'


def _file(asset: dict[str, str], label: str, context: Context) -> str:
    """The core checked that a vault file exists inside the vault; its provenance is its
    vault-relative path, never the reference as authored. An asset without a path is a URL."""
    if asset["mediaType"].startswith("image/"):
        return _image(asset, label)
    if "path" not in asset:
        return f'<a href="{escape(asset["href"], quote=True)}">{escape(label or asset["href"])}</a>'
    path = asset["path"]
    name = label or PurePosixPath(path).name
    if context.embed_attachments:
        return _download(asset, label)
    return (f'<span class="source-reference" data-source-path="{escape(path, quote=True)}">{escape(name)}</span>'
            f' ({_code({"attrs": {}, "text": path})})')


def _download(asset: dict[str, str], label: str) -> str:
    """The evidence edition's attachment: a download of the asset's embedded bytes, named like the
    vault file and showing its type and size. Its help on use is the downloads feature's
    (features.py, downloads: attachment-download.js)."""
    filename = PurePosixPath(asset["path"]).name
    size = len(base64.b64decode(asset["data"]))
    kind = PurePosixPath(filename).suffix.removeprefix(".").upper() or asset["mediaType"]
    details = ", ".join(([filename] if label else []) + [kind, _size(size)])
    return (f'<a class="attachment-download" href="data:{escape(asset["mediaType"], quote=True)};base64,'
            f'{asset["data"]}" download="{escape(filename, quote=True)}" data-attachment-download>'
            f'<span class="attachment-name">{escape(label or filename)}</span> '
            f'<span class="attachment-details">({escape(details)})</span></a>')


def _size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    return f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"


# Canonical callout kind: its tone, the shared semantic card colour (obs artifact-ui.md).
CALLOUT_TONES = {
    "note": "accent", "abstract": "accent", "info": "accent", "todo": "accent", "tip": "accent",
    "success": "success", "question": "warning", "warning": "warning", "failure": "failure",
    "danger": "failure", "bug": "failure", "example": "accent", "quote": "neutral",
    "important": "accent",
}


def _callout(node: dict[str, object], context: Context) -> str:
    """A callout is a card titled by the inline nodes of ``attrs.title`` exactly as the core gives
    them (the core resolves an untitled callout's title); ``important`` is the emphasis box."""
    kind, title = node["attrs"]["kind"], node["attrs"]["title"]
    if kind not in CALLOUT_TONES:
        raise _stale(context, ["attrs", "kind"], f"is {kind!r}, not one of the callout kinds "
                     f"{', '.join(sorted(CALLOUT_TONES))}")
    name = kind.capitalize()
    if kind == "important":
        opening = f'<aside class="content-card content-emphasis" aria-label="{name}">\n'
    else:
        opening = (f'<aside class="content-card content-callout content-callout--{CALLOUT_TONES[kind]}" '
                   f'data-callout="{kind}" aria-label="{name}">\n')
    header = f'<header class="content-card-title">{_attr_nodes(title, context, "attrs", "title")}</header>\n' \
        if title else ""
    return f"{opening}{header}{_nodes(node['children'], context)}</aside>\n"


def _chapter_title(chapter: str, context: Context) -> str:
    """The title of the chapter a link node's ``attrs.chapter`` names."""
    if chapter not in context.chapters:
        raise _stale(context, ["attrs", "chapter"], f"names chapter {chapter!r}, which the Document does not "
                     "contain")
    return context.chapters[chapter]


def _mark(node: dict[str, object], _context: Context) -> str:
    """Marks are collected by their paragraph, which carries the mark rail (see _paragraph)."""
    return ""


def _command(node: dict[str, object], context: Context) -> str:
    """The output the core captured; the adapter never runs a command (capabilities/command-fences)."""
    if node["attrs"].get("silent"):
        return ""
    output = node["attrs"].get("output")
    if not isinstance(output, str):
        raise _stale(context, ["attrs", "output"], "is missing: the core captures a command fence's output only "
                     "when it runs the fences", _rebuild(context.document, " ... --execute-commands"))
    return f'<pre class="command-output"><code>{escape(output)}</code></pre>\n'


def _base(node: dict[str, object], context: Context) -> str:
    """A Base fence is a table placeholder; the runtime evaluates its views over the island's rows.
    Members need the core's rows, which only a register carries."""
    definition = node["attrs"]["spec"]
    for index, view in enumerate(definition.get("views", [])):
        if "members" in (view.get("obs") or {}):
            raise InputError(_note_source(context), f"base.views[{index}].obs.members", "is in a Base fence, "
                             "but obs-html shows members only in a register, whose rows the obs core selects",
                             "Move the Base into a .base file and embed it with ![[<file>.base]]")
    return _data_table(definition, None, context, _note_source(context))


def _register(node: dict[str, object], context: Context) -> str:
    """A register is a table placeholder whose rows are the core's: per view, the row keys of the
    records it selects (obs capabilities/registers, Document node). The adapter selects nothing; a
    heading embeds its one view, no heading every view with the selector."""
    attrs = node["attrs"]
    rows = []
    for index, identifiers in enumerate(attrs["rows"]):
        missing = next((identifier for identifier in identifiers if identifier not in context.row_keys), None)
        if missing is not None:
            raise _stale(context, ["attrs", "rows", index], f"names record {missing!r}, which the Document's "
                         f"records do not contain (register {attrs['target']})")
        rows.append([context.row_keys[identifier] for identifier in identifiers])
    definition, view = attrs["base"], attrs["view"]
    if view is not None:
        definition, rows = {**definition, "views": [definition["views"][view]]}, [rows[view]]
    return _data_table(definition, rows, context, attrs["target"])


def _row_keys(records: list[dict[str, object]]) -> dict[str, str]:
    """Each record's key among the runtime's table rows, by record id: the keys artifact.js gives
    the rows it builds per record type (noteTableRows, chapterTableRows, tagTableRows,
    glossaryTableRows, documentMetadataRows, documentHistoryRows)."""
    history = [record["id"] for record in records if record["type"] == "documentHistory"]
    keys = {
        "note": lambda record: f"note:{record['id']}",
        "chapter": lambda record: record["fields"]["slug"],
        "tag": lambda record: f"{record['note']}:{record['fields']['type']}:{record['fields']['label']}",
        "glossary": lambda record: f"glossary:{record['note']}",
        "documentMetadata": lambda record: f"metadata:{record['fields']['key']}",
        "documentHistory": lambda record: f"history:{history.index(record['id'])}",
    }
    return {record["id"]: keys[record["type"]](record) for record in records}


def _note_source(context: Context) -> str:
    """The note the current chapter's content comes from, as messages name it."""
    return _slug_source(context.chapter or HOME, context)


def _slug_source(slug: str, context: Context) -> str:
    """The note of a chapter, or of the home page, as messages name it: its vault-relative path."""
    record = context.records.get(slug)
    return str(record["path"]) if record else context.document["manifest"]["path"] if slug == HOME \
        else f"chapter {slug}"


def _data_table(definition: dict[str, object], rows: list[list[str]] | None, context: Context,
                source: str) -> str:
    context.assets.normalize_definition(definition, source)
    key = f"{context.chapter or HOME}-base-{len(context.tables) + 1}"
    places = [("filters", definition.get("filters")),
              *((f"views[{index}].filters", view.get("filters")) for index, view in enumerate(definition.get("views", [])))]
    for place, filters in places:
        unsupported = _unsupported_filter(filters)
        if unsupported is not None:
            raise InputError(
                source, place if source.endswith(".base") else f"base.{place}",
                f"holds {unsupported}, which obs-html cannot evaluate. It evaluates comparisons PROPERTY == "
                "LITERAL or PROPERTY != LITERAL, where PROPERTY is a frontmatter property (dotted, or "
                f"note[\"name with spaces\"]) or one of {', '.join(FILE_PROPERTIES)}, and LITERAL is quoted "
                "text, a number, true, false or null; combined with and, or and not",
                "Rewrite the filter in this subset")
    context.tables.append({"key": key, "definition": definition, **({"rows": rows} if rows is not None else {})})
    return f'<div class="data-table-placeholder" data-base-table="{escape(key, quote=True)}"></div>\n'


FILE_PROPERTIES = ("file.name", "file.path", "file.folder", "file.ext")
COMPARISON = re.compile(json.loads(files("obs_html").joinpath("base.schema.json").read_text(encoding="utf-8"))
                        ["$defs"]["comparison"]["pattern"])


def _unsupported_filter(filters: object) -> str | None:
    """The first filter expression base.js cannot evaluate, as authored, or None.

    The schema's comparison pattern owns the comparison syntax (generic-tables, Bases filter
    grammar); base.js evaluates the same subset at runtime.
    """
    if filters is None:
        return None
    if isinstance(filters, str):
        match = COMPARISON.fullmatch(filters)
        if not match or match[1] == "recordType" or (match[2] or "").startswith("file."):
            return filters
        name = (match[1] or "").removeprefix("note.")
        if name.startswith(("formula.", "this.", "file.")) and (match[1] != name or name not in FILE_PROPERTIES):
            return filters
        return None
    if isinstance(filters, dict) and len(filters) == 1:
        [(operator, operands)] = filters.items()
        operands = operands if isinstance(operands, list) else [operands]
        if operator in {"and", "or", "not"} and operands and all(item is not None for item in operands):
            return next((found for found in map(_unsupported_filter, operands) if found is not None), None)
    return json.dumps(filters, ensure_ascii=False)


def _figure(node: dict[str, object], context: Context) -> str:
    """A figure of any kind in the one figure frame (figures.py); an error names the note and the
    figure's field. Its number follows the manifest's obsHtml.figures numbering."""
    if node["attrs"]["kind"] not in FIGURE_KINDS:
        raise _stale(context, ["attrs", "kind"], f"is {node['attrs']['kind']!r}, a figure kind obs-html "
                     "(src/obs_html/figures.py, FIGURE_KINDS) does not render", "Use one of "
                     f"{', '.join(sorted(FIGURE_KINDS))}, or build the Document for an adapter that renders it")
    context.figure_position += 1
    paragraphs = []
    for index, paragraph in enumerate(node["attrs"].get("caption", [])):
        with _at(context, "attrs", "caption", index):
            paragraphs.append(_phrasing(paragraph["children"], context))
    caption_text = " ".join(_plain_text(paragraph) for paragraph in paragraphs)
    links = {  # The links the core resolved in the figure's SVG (obs capabilities/wikilinks).
        link["attrs"]["svg"]: FigureLink(_link_href(link["attrs"], context), link["attrs"]["label"])
        for link in node["children"][0]["children"]
    }
    return render_figure(node, context.chapter or HOME, context.figure_position, paragraphs, caption_text,
                         _note_source(context), _figure_number(context), links)


def _figure_number(context: Context) -> str:
    """The current figure's label and number, or "" for a figure without a number."""
    numbers = context.figure_numbers.get(context.chapter or HOME, [])
    number = numbers[context.figure_position - 1] if context.figure_position <= len(numbers) else ""
    return f"{context.figures['label']} {number}" if number else ""


def _number_figures(chapters: list[dict[str, object]], context: Context) -> None:
    """Number the captioned figures of the contents chapters in reading order, before any note
    renders, so a reference shows the number of a figure further on (obs input-model, Figure
    captions and references): `document` counts through the document, `chapter` restarts at each
    top-level contents chapter and prefixes its position; a note outside the contents, and the
    home page, number none."""
    numbering = context.figures["numbering"]
    count = top = 0

    def figures(nodes: list[dict[str, object]]) -> Iterator[dict[str, object]]:
        for node in nodes:
            if node["type"] == "figures":
                yield node
            yield from figures(node.get("children", []))

    def walk(items: list[dict[str, object]], depth: int, section: int) -> None:
        nonlocal count, top
        for chapter in items:
            if depth == 0:  # A top-level contents chapter opens a numbering section; a note outside none.
                in_contents = chapter.get("toc", True)
                top += in_contents
                section = top if in_contents else 0
                count = 0 if numbering == "chapter" else count
            numbers = context.figure_numbers[chapter["id"]] = []
            for figure in figures(chapter["content"]):
                number = ""
                if section and numbering != "none" and figure["attrs"].get("caption"):
                    count += 1
                    number = str(count) if numbering == "document" else f"{section}.{count}"
                numbers.append(number)
                if "block" in figure["attrs"]:
                    context.figure_blocks[(chapter["id"], figure["attrs"]["block"])] = number
            walk(chapter["children"], depth + 1, section)

    walk(chapters, 0, 0)


def _figure_reference(node: dict[str, object], context: Context, number_only: bool = False) -> str:
    """A block link to a figure: its label as written or, unlabelled, the figure's label and
    number (obs input-model, Figure captions and references); ``number_only`` in a merged group."""
    attrs = node["attrs"]
    chapter, block = attrs["chapter"], attrs["figure"]
    number = context.figure_blocks.get((chapter, block), "")
    text = attrs["label"]
    if _unlabelled(attrs, context):
        if not number:
            raise InputError(
                _source(context.document), field_path(context.where),
                f"is the unlabelled reference [[{attrs['target']}#{attrs['heading']}]] to a figure without a "
                f"number (^{block} in {chapter})",
                "Caption the figure in a contents chapter and number figures with the manifest's "
                "obsHtml.figures.numbering, or give the link a label ([[note#^name|label]]); see obs "
                "input-model#Figure captions and references")
        text = number if number_only else f"{context.figures['label']} {number}"
    return f'<a class="internal-link" href="#{chapter}/block-{escape(block, quote=True)}">{escape(text)}</a>'


def _unlabelled(attrs: dict[str, object], context: Context) -> bool:
    """Whether a resolved wikilink has no |label: its label is the one the core gives an unaliased
    link (obs capabilities/wikilinks#Link text)."""
    target, heading = attrs["target"], attrs["heading"]
    if heading and target:
        return attrs["label"] == f"{_chapter_title(attrs['chapter'], context)} > {heading}"
    return attrs["label"] == (heading or target)


def _numbered_reference(node: dict[str, object], context: Context) -> str:
    """The number of an unlabelled reference to a numbered figure, else ""."""
    attrs = node["attrs"]
    if node["type"] != "wikilinks" or "figure" not in attrs or attrs["chapter"] is None or not _unlabelled(attrs, context):
        return ""
    return context.figure_blocks.get((attrs["chapter"], attrs["figure"]), "")


def _merged_references(nodes: list[dict[str, object]], context: Context) -> str:
    """Phrasing nodes with each run of adjacent unlabelled references to numbered figures as one
    plural reference: Figures 2.4 and 2.5, Figures 2.4–2.6 (obs input-model, Figure captions and
    references). Adjacent means separated only by whitespace, a comma or a configured conjunction;
    the author's order and separators stay, the plural label replaces the singular once and a run
    of three or more consecutive numbers shows its ends."""
    def rendered(index: int, number_only: bool = False) -> str:
        with _at(context, "children", index):
            if number_only:
                return _figure_reference(nodes[index], context, number_only=True)
            return _node(nodes[index], context)

    units = [index for index, node in enumerate(nodes) if _numbered_reference(node, context)]
    words = "|".join(re.escape(word) for word in sorted(context.conjunctions, key=len, reverse=True))
    separator = re.compile(rf"\s*(?:,\s*)?(?:(?:{words})\s+)?" if words else r"\s*(?:,\s*)?", re.IGNORECASE)
    groups: list[list[int]] = []
    for index in units:
        between = nodes[groups[-1][-1] + 1:index] if groups else None
        if between is not None and all(node["type"] == "text" and not node["attrs"] for node in between) \
                and separator.fullmatch("".join(node.get("text", "") for node in between)):
            groups[-1].append(index)
        else:
            groups.append([index])

    def consecutive(first: int, second: int) -> bool:
        head, _, last = _numbered_reference(nodes[first], context).rpartition(".")
        next_head, _, next_last = _numbered_reference(nodes[second], context).rpartition(".")
        return head == next_head and int(next_last) == int(last) + 1

    html: list[str] = []
    position = 0
    for group in (group for group in groups if len(group) > 1):
        html.extend(rendered(index) for index in range(position, group[0]))
        html.append(f"{escape(context.figures['labelPlural'])} ")
        start = 0
        while start < len(group):
            end = start
            while end + 1 < len(group) and consecutive(group[end], group[end + 1]):
                end += 1
            if end - start >= 2:
                html.extend([rendered(group[start], True), "–", rendered(group[end], True)])
            else:
                end = start
                html.append(rendered(group[start], True))
            if end + 1 < len(group):
                html.extend(rendered(index) for index in range(group[end] + 1, group[end + 1]))
            start = end + 1
        position = group[-1] + 1
    html.extend(rendered(index) for index in range(position, len(nodes)))
    return "".join(html)


def _plain_text(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", "", html))).strip()


def _references(node: dict[str, object], context: Context) -> str:
    """A glossary or reference note. Its metadata reaches the runtime as the note's frontmatter:
    hover cards and the glossary register read the definition (``definitionHtml``, see
    _definition_html) and a reference's ``url`` (obs references.md, input-model Reference notes)."""
    metadata = node["attrs"]["metadata"]
    if metadata.get("kind") == "glossary" and not isinstance(metadata.get("definition"), str):
        raise InputError(_note_source(context), "definition", "is missing or not text, and a glossary note "
                         "needs one", "Add 'definition: <text>' to the note's frontmatter")
    url = metadata.get("url")
    if url is not None and not (isinstance(url, str) and re.match(r"https?://\S+$", url, re.IGNORECASE)):
        raise InputError(_note_source(context), "url", f"is {url!r}, not an http(s) URL",
                         "Give the reference note's url the external address, such as https://example.org")
    return ""


def _definition_html(frontmatter: dict[str, object], slug: str, context: Context) -> str:
    """A glossary note's definition as inline HTML, for its hover card and register rows."""
    if frontmatter.get("kind") != "glossary" or "definition" not in frontmatter:
        return ""
    return _field_html(slug, "definition", frontmatter["definition"], context)


def _extension(node: dict[str, object], context: Context) -> str:
    """An Obsidian syntax extension the source used (obs extensions.md). None has an input-model
    contract yet, so the core emits none and obs-html renders none; a callout is a ``callouts``
    node. Trusted runtime extensions are another thing: artifact.js's ``obsArtifact.trustedExtension``."""
    raise _stale(context, ["attrs", "syntax"], f"is {node['attrs'].get('syntax')!r}, a syntax extension obs-html "
                 "(src/obs_html/render.py) does not render: no syntax extension has an input-model contract yet "
                 "(obs spec/capabilities/extensions.md), and a callout is a callouts node")


PROPERTY_EDITOR_SCHEMA = json.loads(files("obs_html").joinpath("property-editor.schema.json")
                                    .read_text(encoding="utf-8"))
PROPERTY_EDITOR = Draft202012Validator(PROPERTY_EDITOR_SCHEMA)


def _property_editor(node: dict[str, object], context: Context) -> str:
    """A ``property-editors`` node: a text editor for one existing string field of an authored
    note; properties.js commits edits through artifact.js (``obsArtifact.commitProperty``), which
    checks the same declaration. ``attrs.spec`` is the fence's mapping and ``attrs.writes`` the
    fields the core let it write (obs capabilities/property-editors); the runtime writes no other."""
    source, fence = _note_source(context), "property-editor"
    spec = node["attrs"]["spec"]
    field = spec.get("field") if isinstance(spec, dict) else None
    writes = node["attrs"].get("writes")
    if not isinstance(writes, list) or not writes or not all(isinstance(name, str) for name in writes):
        raise _stale(context, ["attrs", "writes"], "is missing or not a list of field names; the core "
                     "writes the fields a property editor may write there (obs capabilities/property-editors)")
    error = schema_error(list(PROPERTY_EDITOR.iter_errors(spec)), source, "obs-html's "
                         "property-editor.schema.json and obs capabilities/property-editors", prefix=fence)
    if error is not None:
        raise error
    limit = spec.get("maxLength", PROPERTY_EDITOR_SCHEMA["properties"]["maxLength"]["default"])
    if not context.chapter or not isinstance(context.frontmatter.get(field), str):
        raise InputError(source, f"{fence}.field", f"names {field!r}, which is no text field of an authored "
                         "note", f"Add '{field}: <text>' to the note's frontmatter")
    if len(context.frontmatter[field]) > limit:
        raise InputError(source, field, f"is longer than the property editor's maxLength {limit}",
                         "Shorten it or raise maxLength")
    if field in context.editable:
        raise InputError(source, f"{fence}.field", f"names {field!r}, which another property editor of the "
                         "note edits", "Keep one editor per field")
    definition: dict[str, object] = {"label": spec["label"], "maxLength": limit, "writes": writes}
    if "projection" in spec:  # The core enforces its rules (obs capabilities/property-editors).
        definition["projection"] = spec["projection"]
    context.editable[field] = definition
    label = escape(spec["label"])
    return ('<label class="property-editor">'
            f"<span>{label}</span>"
            f'<textarea data-property-editor data-property-note="{escape(context.chapter, quote=True)}" '
            f'data-property-field="{escape(field, quote=True)}" maxlength="{limit}" '
            f'aria-label="{escape(spec["label"], quote=True)}" rows="2"></textarea></label>\n')


CAPABILITIES: dict[str, Renderer] = {
    "artifact-presentation": _nothing,
    "attachments": _attachment,
    "bases": _base,
    "callouts": _callout,
    "cards-metrics": _cards,
    "chapter-inclusion": _nothing,
    "command-fences": _command,
    "count-query": _nothing,
    "embeds": _embed,
    "equation-figures": _nothing,  # A figure kind: figures.py draws its body.
    "extensions": _extension,
    "figure-descriptor": _nothing,
    "figures": _figure,
    "manifest": _nothing,
    "markdown": _nothing,
    "markdown-frontmatter": _frontmatter,
    "marks": _mark,
    "mermaid": _nothing,  # A figure kind: figures.py draws its body.
    "named-icons": _nothing,
    "plantuml": _nothing,  # A figure kind: figures.py draws its body.
    "profiles": _nothing,
    "property-editors": _property_editor,
    "quantities": _nothing,
    "queries": _nothing,
    "references": _references,
    "registers": _register,
    "wikilinks": _wikilink,
}


@stage("render")
def render(document: dict[str, object], config: Config,
           style_folder: Path | None = None,
           trusted_runtime: tuple[str, str] | None = None,
           embed_attachments: bool = False,
           styles: DeclaredStyles | None = None) -> str:
    """The artifact of ``document``, styled by ``style_folder``, else by the style the Document
    declares (fetched through ``styles``, by default git into the user's cache), else by the packaged
    generic module (spec/configuration.md, Declared style)."""
    if document.get("schemaVersion") != 1:
        raise InputError("Document", "schemaVersion", f"is {document.get('schemaVersion')!r}, not 1, the "
                         "version obs-html renders", "Build the Document with an obs core of schema version 1")
    if "path" not in document["manifest"]:
        raise InputError("Document", "manifest.path", "is missing, so the Document is older than this adapter",
                         "Rebuild the Document with the current obs core (obs-document)")
    unsupported = sorted(set(document["capabilities"]) - set(CAPABILITIES))
    if unsupported:
        raise InputError(_source(document), "capabilities", f"lists {', '.join(unsupported)}, which obs-html "
                         "does not render", "Build the Document for an adapter that declares them, or drop "
                         "their syntax from the notes")
    if style_folder is None and "style" in document:
        styles = styles or DeclaredStyles(GitFetcher(), user_cache())
        style_folder = styles.folder(document["style"], _source(document))
    style = load_style(style_folder)
    assets = SemanticAssets(style.asset_index)
    context = Context(
        document, assets,
        links={item["id"]: item for item in document["links"]},
        files={item["id"]: item for item in document["assets"]},
        paths={record["path"].removesuffix(".md"): record["id"]
               for record in document["records"] if record.get("type") == "note"},
        records={record["id"]: record for record in document["records"] if record.get("type") == "note"},
        row_keys=_row_keys(document["records"]),
        embed_attachments=embed_attachments,
    )
    _index(document["chapters"], context)
    _index_headings(HOME, document["manifest"].get("abstract", []), context)
    context.chapters[HOME] = document["manifest"]["title"]  # The core links the manifest as home.
    model = _resolve_icons(_model(document, config, context), assets)
    archive = source_archive.package(document, embed_attachments)
    if archive is not None:
        model = source_archive.share(model, archive)
    return prepare_artifact_scripts(assets.resolve_markup(
        _shell(model, list(context.unknown.values()), style.stylesheet, assets, config, trusted_runtime,
               snippets=_css_snippets(document), archive=archive)))


def _css_snippets(document: dict[str, object]) -> str:
    """The style elements of the CSS snippets the manifest's obsHtml.cssSnippets lists, in its
    order, from the Document's cssSnippets (the vault's snippet folder, which the core reads)."""
    manifest = document["manifest"]
    available = {snippet["name"]: snippet for snippet in document["cssSnippets"]}
    styles = []
    for index, name in enumerate(_profile(manifest)["cssSnippets"]):
        snippet = available.get(name)
        if snippet is None:
            listed = ", ".join(sorted(available)) or "none"
            raise InputError(manifest["path"], f"obsHtml.cssSnippets[{index}]", f"names {name!r}, which the "
                             "vault's snippet folder does not hold", f"Name one of its snippets ({listed}) or add "
                             f"{name}.css to the snippet folder (obs configuration input.cssSnippetFolder)")
        if re.search(r"</style", snippet["text"], re.IGNORECASE):
            raise InputError(snippet["path"], "", "contains '</style', which would end its style element",
                             "Remove it from the snippet")
        styles.append(f'<style data-css-snippet="{escape(name, quote=True)}">{snippet["text"]}</style>')
    return "".join(styles)


def _resolve_icons(value: object, assets: SemanticAssets) -> object:
    """Named icon placeholders become their glyphs or images everywhere in the island."""
    if isinstance(value, str):
        return assets.resolve_markup(value)
    if isinstance(value, list):
        return [_resolve_icons(item, assets) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_icons(item, assets) for key, item in value.items()}
    return value


def _profile(manifest: dict[str, object]) -> dict[str, object]:
    """The manifest frontmatter's obsHtml mapping, the adapter's own namespace, which the obs core
    passes on without reading (obs input-model#Core and adapter namespaces); this adapter checks it."""
    declared = manifest["metadata"].get("obsHtml", {})
    schema = json.loads(files("obs_html").joinpath("profile.schema.json").read_text(encoding="utf-8"))
    error = schema_error(list(Draft202012Validator(schema).iter_errors(declared)), manifest["path"], "obs-html's "
                         "profile.schema.json and obs capabilities/artifact-presentation", prefix="obsHtml")
    if error is not None:
        raise error
    resolved = {key: declared.get(key, value) for key, value in PROFILE_DEFAULTS.items()}
    resolved["figures"] = PROFILE_DEFAULTS["figures"] | resolved["figures"]
    resolved["print"] = declared.get("print") or {}
    return resolved


def _model(document: dict[str, object], config: Config, context: Context) -> dict[str, object]:
    """The artifact-data island: the runtime's only model of the artifact."""
    manifest = document["manifest"]
    profile = _profile(manifest)
    context.figures = profile["figures"]
    context.conjunctions = tuple(config.artifact["figureReferences"]["conjunctions"])
    _number_figures(document["chapters"], context)
    settings = config.artifact
    context.bordered_tags = tuple(settings["borderedTags"])
    title = manifest["title"]
    metadata = {key: value for key, value in manifest["metadata"].items() if key not in {"obs", "obsHtml"}}
    abstract = _note_body(manifest.get("abstract", []), "", ["manifest", "abstract"], context)  # It holds the metadata's field nodes.
    # The display HTML of each value that shows: an empty value leaves its cover and header line out.
    metadata_html = _frontmatter_html({key: value for key, value in metadata.items() if value}, HOME, context)
    home_html = _cover(title, metadata, metadata_html, profile["heading"] == "compact") + abstract
    notes = [_note(0, title, HOME, HOME, {}, home_html, context)]
    notes.extend(_chapter_notes(document["chapters"], context, 0, ["chapters"]))
    _attach_records(document["records"], notes, context)
    for note in notes:
        if note["frontmatter"].get("kind") == "quantity" and "value" in note["frontmatter"]:
            note["valueLabel"] = _quantity_label(note["frontmatter"])  # Its hover card shows it.
    return {
        "assets": context.assets.resources,
        "embeddedAssets": context.assets.embedded_assets,
        "document": {
            "title": title,
            "metadata": metadata,
            "metadataHtml": metadata_html,
            "pages": profile["pages"],
            "generation": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "generator": {"name": "obs-html", "version": version("obs-html"), "commit": "unknown"},
                "target": {"name": title, "version": "unknown", "commit": "unknown"},
            },
        },
        "paper": paper({**config.print_default, **profile["print"]}, config, lambda key: (
            (manifest["path"], f"obsHtml.print.{key}") if key in profile["print"]
            else (config.source("artifact", "print", "default", key), f"artifact.print.default.{key}"))),
        "reading": {"theme": "light", "paged": profile["layout"] == "paged", **settings["reading"]},
        "figures": settings["figures"],
        "printReadyTimeoutMilliseconds": settings["printReadyTimeoutMilliseconds"],
        "hoverCard": settings["hoverCard"],
        "tablePageSize": settings["tablePageSize"],
        "inactiveIconOpacity": settings["inactiveIconOpacity"],
        "tableColumnMinimumPixels": settings["tableColumnMinimumPixels"],
        "tableCompactColumnMinimumPixels": settings["tableCompactColumnMinimumPixels"],
        "dockPaneMinimumPixels": settings["dockPaneMinimumPixels"],
        "guidedCard": settings["guidedCard"],
        "tableIconWidthPixels": settings["tableIconWidthPixels"],
        "tableDetailFontSizePoints": settings["tableDetailFontSizePoints"],
        "facetDistinctRatio": settings["facetDistinctRatio"],
        "query": profile["query"],
        "filterPresets": settings["filterPresets"],
        "toc": [HOME, *_listed(document["chapters"])],
        "notes": [{key: value for key, value in note.items() if key != "record"} for note in notes],
    }


def _listed(chapters: list[dict[str, object]]) -> list[str]:
    """The reading order: Contents and previous/next. A `toc: false` chapter, an included note
    the manifest does not list, stays a note outside it (obs input-model, Chapter content)."""
    return [slug for chapter in chapters if chapter.get("toc", True)
            for slug in (chapter["id"], *_listed(chapter["children"]))]


def _chapter_notes(chapters: list[dict[str, object]], context: Context, depth: int,
                   where: list[object]) -> list[dict]:
    notes = []
    for index, chapter in enumerate(chapters):
        context.frontmatter = dict(chapter.get("metadata") or {})
        body = _note_body(chapter["content"], chapter["id"], [*where, index, "content"], context)
        notes.append(_note(depth, chapter["title"], chapter["id"], "", context.frontmatter, body, context))
        notes.extend(_chapter_notes(chapter["children"], context, depth + 1, [*where, index, "children"]))
    return notes


def _note_body(nodes: list[dict[str, object]], chapter: str, where: list[object], context: Context) -> str:
    """A note's nodes, which sit at ``where`` in the Document."""
    context.chapter, context.tables, context.marks, context.editable = chapter, [], [], {}
    context.figure_position = 0
    context.where = where[:-1]
    body = _nodes(nodes, context, where[-1])
    context.chapter, context.where = "", []
    return body


def _note(depth: int, title: str, slug: str, generated: str, frontmatter: dict[str, object],
          html: str, context: Context) -> dict[str, object]:
    return {
        "depth": depth, "title": title, "slug": slug, "sourcePath": f"{slug}.md",
        "generated": generated, "cssClasses": _css_classes(frontmatter, slug, context),
        "frontmatter": frontmatter, "editableProperties": context.editable,
        "frontmatterHtml": _frontmatter_html(frontmatter, slug, context),
        "definitionHtml": _definition_html(frontmatter, slug, context), "marks": context.marks, "tables": context.tables, "html": html,
    }


def _attach_records(records: list[dict[str, object]], notes: list[dict[str, object]],
                    context: Context) -> None:
    """Note records join the queryable population: a chapter's own record adds to its frontmatter,
    any other note record becomes a record-only note outside the reading order. A note record's
    path is its note's source path, which Bases read file.* properties from (obs bases.md)."""
    by_slug = {note["slug"]: note for note in notes}
    for position, record in enumerate(records):
        if record["type"] != "note":
            continue  # A projected row reaches a register through its rows (_register), not as a note.
        fields = dict(record["fields"])
        note = by_slug.get(record["id"])
        rendered = context.fields.setdefault(record["id"], {})  # A chapter's frontmatter node rendered first.
        for index, child in enumerate(record.get("fieldNodes", [])):
            if child["attrs"]["name"] not in rendered:
                with _at(context, "records", position, "fieldNodes", index):
                    rendered[child["attrs"]["name"]] = _nodes(child["children"], context)
        source_path = record.get("path") or f"{record['id']}.md"
        if note is not None and record.get("ignored"):
            note["ignored"] = True  # Runtime selections skip it (artifact.js, selectable).
        if note is not None and not note["generated"]:
            note["frontmatter"] = {**fields, **note["frontmatter"]}
            note["frontmatterHtml"] = _frontmatter_html(note["frontmatter"], note["slug"], context)
            note["definitionHtml"] = _definition_html(note["frontmatter"], note["slug"], context)
            note["sourcePath"] = source_path
            continue
        if note is not None:
            raise InputError(_source(context.document), f"records[{position}].id", f"is {record['id']!r}, which "
                             "obs-html reserves for the artifact's home page", "Rename the note, so the core "
                             "gives its record another id")
        fields["obs"] = {**(fields.get("obs") or {}), "document": False}
        notes.append({
            "depth": 0, "title": str(fields.get("title") or record["id"]), "slug": record["id"],
            "sourcePath": source_path, "generated": "", "cssClasses": [],
            "frontmatter": fields, "editableProperties": {},
            "frontmatterHtml": _frontmatter_html(fields, record["id"], context),
            "definitionHtml": _definition_html(fields, record["id"], context), "marks": [], "tables": [], "html": "", "record": True,
            **({"ignored": True} if record.get("ignored") else {}),
        })


def _cover(title: str, metadata: dict[str, object], html: dict[str, str], compact: bool) -> str:
    """The cover or compact heading: each metadata value as its display HTML (_frontmatter_html)."""
    def value(key: str) -> str:
        return html.get(key, "") if metadata.get(key) else ""

    product = metadata.get("product") if isinstance(metadata.get("product"), dict) else {}
    products = [html.get(f"product.{key}", "") for key in ("name", "version") if product.get(key)]
    subtitle = value("subtitle")
    if compact:
        parts = [("cover-organization", value("organization")),
                 ("cover-product", " ".join(products)), ("cover-type", value("document type"))]
        line = "".join(f'<span class="{name}">{text}</span>' for name, text in parts if text)
        line += f'<h1 class="document-title">{escape(title)}</h1>'
        if subtitle:
            line += f'<span class="document-subtitle">{subtitle}</span>'
        return ('<header class="document-heading document-heading--compact">'
                f'<div class="compact-heading">{line}</div></header>\n')
    product_html = "".join(f"<div>{item}</div>" for item in products)
    band = (f'<span class="cover-template">{value("template")}</span>'
            f'<span class="cover-organization">{value("organization")}</span>')
    facts = "".join(f"<dt>{escape(key.title())}</dt><dd>{value(key)}</dd>"
                    for key in COVER_FIELDS if metadata.get(key))
    legal = "".join(f'<p class="cover-{key}">{value(key)}</p>'
                    for key in ("copyright", "confidentiality") if metadata.get(key))
    return (
        '<header class="document-heading">'
        + (f'<div class="cover-product">{product_html}</div>' if product_html else "")
        + f'<div class="cover-band">{band}</div><div class="cover-frame">'
        + f'<h1 class="document-title">{escape(title)}</h1>'
        + (f'<p class="cover-type">{value("document type")}</p>' if metadata.get("document type") else "")
        + (f'<div class="document-subtitle">{subtitle}</div>' if subtitle else "")
        + legal + "</div>"
        + f'<div class="cover-facts-frame"><dl class="cover-facts">{facts}</dl></div></header>\n'
    )


def _nodes(nodes: list[dict[str, object]], context: Context, key: str = "children") -> str:
    """The nodes of the current node's ``key`` list."""
    html = []
    for index, node in enumerate(nodes):
        with _at(context, key, index):
            html.append(_node(node, context))
    return "".join(html)


def _node(node: dict[str, object], context: Context) -> str:
    kind = node["type"]
    return (CAPABILITIES.get(kind) or STRUCTURAL_NODES.get(kind) or _unknown)(node, context)


def _phrasing(nodes: list[dict[str, object]], context: Context) -> str:
    """The children of an element that allows only phrasing content (a paragraph, a heading)."""
    outer, context.phrasing = context.phrasing, True
    try:
        return _merged_references(nodes, context)
    finally:
        context.phrasing = outer


def _list(node: dict[str, object], context: Context) -> str:
    tag = "ol" if node["attrs"].get("ordered") else "ul"
    if node["attrs"]["tight"]:
        items = "".join(_child(context, index, lambda: f"<li>{_tight_item(item, context)}</li>\n"
                                       if item["type"] == "list-item" else _node(item, context))
                        for index, item in enumerate(node["children"]))
        return f"<{tag}>\n{items}</{tag}>\n"
    return f"<{tag}>\n{_nodes(node['children'], context)}</{tag}>\n"


def _child(context: Context, index: int, rendered: Callable[[], str]) -> str:
    """What ``rendered`` writes for the current node's child at ``index``."""
    with _at(context, "children", index):
        return rendered()


def _section(node: dict[str, object], context: Context) -> str:
    level = min(max(int(node["attrs"].get("level", 1)), 1), 6)
    anchor = context.headings.get(f"{context.chapter or HOME}#{_identifier(_plain(node))}", "")
    identifier = f' id="{anchor}"' if anchor else ""
    return f"<h{level}{identifier}>{_phrasing(node['children'], context)}</h{level}>\n"


def _wrap(opening: str, closing: str) -> Renderer:
    """A node shown as its children inside one element."""
    return lambda node, context: f"{opening}{_nodes(node['children'], context)}{closing}"


def _table(node: dict[str, object], context: Context) -> str:
    """A pipe table: its header rows (every cell a header) in the head, the other rows in the body."""
    def header(row: dict[str, object]) -> bool:
        return bool(row["children"]) and all(cell["attrs"].get("header") for cell in row["children"])

    def rows(head: bool) -> str:
        return "".join(_child(context, index, lambda: _node(row, context))
                       for index, row in enumerate(node["children"]) if header(row) == head)

    head, body = rows(True), rows(False)
    return ("<table>\n" + (f"<thead>\n{head}</thead>\n" if head else "")
            + (f"<tbody>\n{body}</tbody>\n" if body else "") + "</table>\n")


def _table_cell(node: dict[str, object], context: Context) -> str:
    tag = "th" if node["attrs"].get("header") else "td"
    align = node["attrs"].get("align")
    style = f' style="text-align:{escape(str(align), quote=True)}"' if align else ""
    return f"<{tag}{style}>{_nodes(node['children'], context)}</{tag}>"


MATH_ERRORS = tuple(error for error in vars(math_exceptions).values()
                    if isinstance(error, type) and issubclass(error, Exception))


def _math(node: dict[str, object], context: Context) -> str:
    """TeX math as MathML: display math on its own is a block; display math inside a paragraph
    or heading is phrasing content, a span the stylesheet shows as a block; inline math a span."""
    display = bool(node["attrs"].get("display"))
    formula = node.get("text", "")
    try:
        markup = mathml(formula, display="block" if display else "inline")
    except MATH_ERRORS as error:
        raise InputError(_note_source(context), "body", f"has the math formula {formula!r}, which is not valid "
                         f"TeX ({type(error).__name__})", "Correct the formula in the note") from error
    if not display:
        return f'<span class="math inline">{markup}</span>'
    return f'<span class="math block">{markup}</span>' if context.phrasing else f'<div class="math block">{markup}</div>\n'


def _field(node: dict[str, object], context: Context) -> str:
    """A frontmatter field outside its frontmatter node (which renders it in the panel): its text."""
    return (f'<span class="frontmatter-field" data-field="{escape(node["attrs"]["name"], quote=True)}">'
            f"{_nodes(node['children'], context)}</span>")


def _unknown(node: dict[str, object], context: Context) -> str:
    """A node type this adapter does not know shows its text plain, never nothing, and raises one
    limited-function warning per type: on stderr and in the artifact's notice center."""
    kind = node["type"]
    if kind not in context.unknown:
        listed = "lists it as structural" if kind in STRUCTURAL else "does not list it"
        limit = context.unknown[kind] = {
            "key": f"node-{kind}", "feature": f'Node type "{kind}"',
            "reason": f"obs-html (src/obs_html/render.py) does not render node type {kind!r}; its text is "
                      f"shown plain, without its formatting. The core's document.schema.json {listed}.",
            "observation": f"first in chapter {context.chapter or HOME!r}",
            "remedy": f"Add a renderer for {kind!r} to src/obs_html/render.py.",
        }
        warn(InputError("obs-html (src/obs_html/render.py)", "limited function",
                        f"{limit['reason']} Seen {limit['observation']}", limit["remedy"].removesuffix(".")))
    return (f'<span class="unknown-node" data-node-type="{escape(kind, quote=True)}">'
            f"{escape(_plain(node))}</span>")


# A separator run inside a code span is a break opportunity only between word characters,
# so a leading `/root`, trailing `trail.` or bare `--flag` never strand a lone mark.
CODE_BREAK = re.compile(r"(?<=[^\s/\\._:\-])[/\\._:\-]+(?=[^\s/\\._:\-])")


def _code(node: dict[str, object]) -> str:
    """A fence (it names a language, possibly empty) is a block; any other code is inline."""
    text = node.get("text", "")
    language = node["attrs"].get("language")
    if language is not None:
        css = f' class="language-{escape(language, quote=True)}"' if language else ""
        return f"<pre><code{css}>{escape(text)}</code></pre>\n"
    pieces, position = [], 0
    for separator in CODE_BREAK.finditer(text):
        pieces.append(escape(text[position:separator.end()]))
        position = separator.end()
    pieces.append(escape(text[position:]))
    return f"<code>{'<wbr>'.join(pieces)}</code>"


def _tight_item(item: dict[str, object], context: Context) -> str:
    parts = []
    for index, child in enumerate(item["children"]):
        with _at(context, "children", index):
            if child["type"] == "paragraph" and not any(c["type"] == "marks" for c in child["children"]):
                parts.append(_nodes(child["children"], context))
            else:
                parts.append(("\n" if parts else "") + _node(child, context))
    return "".join(parts)


def _paragraph(node: dict[str, object], context: Context) -> str:
    """A paragraph; the core places no block node inside one (obs capabilities/markdown)."""
    inner = _phrasing(node["children"], context)
    positions = [index for index, child in enumerate(node["children"]) if child["type"] == "marks"]
    marks = [node["children"][index]["attrs"] for index in positions]
    if not marks:
        return f"<p>{inner}</p>\n"
    slug = context.chapter or HOME
    anchor = f"mark-{slug}-{_mark_slug(marks[0])}"
    text = " ".join(_plain(node).split())
    for mark in marks:
        context.marks.append({"kind": mark["category"], "label": mark["id"], "text": text,
                              "html": escape(text), "anchor": anchor, "backlinks": []})
    kinds = [mark["category"] for mark in marks]
    classes = " ".join(f"semantic-mark--{kind.replace('_', '-')}" for kind in kinds)
    rail = "".join(
        f'<a class="semantic-mark-icon semantic-mark-icon--{kind.replace("_", "-")}" href="#tags" '
        f'data-tag-kind="{escape(kind, quote=True)}" data-tag-label="{escape(mark["id"], quote=True)}" '
        f'aria-label="{escape(_mark_description(mark), quote=True)}">{_mark_icon(kind, index, context)}</a>'
        for kind, mark, index in zip(kinds, marks, positions)
    )
    marked = (f'<p class="semantic-mark {classes}" data-mark-kind="{escape(" ".join(kinds), quote=True)}" '
              f'data-mark-label="{escape(" ".join(mark["id"] for mark in marks), quote=True)}" id="{anchor}">'
              f'<span class="semantic-mark-content">{inner.strip()}</span>'
              f'<span class="semantic-mark-rail" aria-label="Paragraph marks">{rail}</span></p>\n')
    bordered = [kind for kind in dict.fromkeys(kinds) if kind in context.bordered_tags]
    if not bordered:
        return marked
    # One shared card encloses the paragraph and its rail, titled by the opted-in kinds
    # (artifact-ui, Content sections).
    title = " / ".join(kind.replace("_", " ").title() for kind in bordered)
    return (f'<section class="content-card"><header class="content-card-title">{escape(title)}</header>\n'
            f'{marked}</section>\n')


def _mark_icon(kind: str, index: int, context: Context) -> str:
    """The icon of the paragraph's mark node at ``index``."""
    try:
        context.assets.icon(f"mark.{kind}")
    except InputError as error:
        raise _stale(context, ["children", index, "attrs", "category"], f"is {kind!r}, a mark kind the style's "
                     f"semantic assets have no icon for ({error.problem})") from error
    return markup(f"mark.{kind}")


def _mark_slug(mark: dict[str, str]) -> str:
    return f"{mark['category'].replace('_', '-')}-{mark['id'].replace('_', '-')}"


def _mark_description(mark: dict[str, str]) -> str:
    return f"{mark['category'].replace('_', ' ').title()}: {mark['id'].replace('_', ' ')}"


def _text_node(node: dict[str, object], context: Context) -> str:
    text = escape(node.get("text", ""))
    attrs = node["attrs"]
    if "link" in attrs:
        link = context.links.get(attrs["link"])
        if link is None:
            raise _stale(context, ["attrs", "link"], f"names link {attrs['link']!r}, which the Document's links do "
                         "not contain")
        chapter = _note_target(link["href"], context)
        if chapter is not None:
            return f'<a class="internal-link" href="#{chapter}">{text}</a>'
        return f'<a href="{escape(link["href"], quote=True)}">{text}</a>'
    if "asset" in attrs:
        asset = _document_asset(attrs["asset"], context)
        return _image(asset, node.get("text", ""))
    return text


STRUCTURAL_NODES: dict[str, Renderer] = {
    "document": _wrap('<div class="document">', "</div>\n"),
    "section": _section,
    "paragraph": _paragraph,
    "text": _text_node,
    "list": _list,
    "list-item": _wrap("<li>", "</li>\n"),
    "code": lambda node, _context: _code(node),
    "quote": _wrap("<blockquote>\n", "</blockquote>\n"),
    "table": _table,
    "table-row": _wrap("<tr>", "</tr>\n"),
    "table-cell": _table_cell,
    "emphasis": _wrap("<em>", "</em>"),
    "strong": _wrap("<strong>", "</strong>"),
    "strikethrough": _wrap("<s>", "</s>"),
    "math": _math,
    "field": _field,
    "rule": lambda _node, _context: "<hr>\n",
}
"""One renderer per structural type (STRUCTURAL); a type without one renders as an unknown node."""


def _note_target(href: str, context: Context) -> str | None:
    """The chapter a Markdown link to a vault note (``[1](reference.md)``) shows, such as a
    citation of a reference note (obs input-model, Reference notes and link text), or None for
    an external or unresolved target, which stays an ordinary link."""
    if re.match(r"[A-Za-z][A-Za-z0-9+.-]*:|#", href):
        return None
    path = unquote(href.split("#", 1)[0])
    if not path.endswith(".md"):
        return None
    chapter = context.paths.get(path.removeprefix("./").removesuffix(".md"))
    return chapter if chapter in context.chapters else None


def _shell(model: dict[str, object], limits: list[dict[str, str]], stylesheet: str, assets: SemanticAssets,
           config: Config, trusted_runtime: tuple[str, str] | None, snippets: str = "",
           archive: bytes | None = None) -> str:
    """The artifact page; ``limits`` are the Document's limited functions (capabilities.js warns of each).
    ``snippets`` are the author's style elements, which follow every packaged style; ``archive`` is
    the source ZIP (source_archive.py)."""
    package = files("obs_html")

    def read(*parts: str) -> str:
        return package.joinpath(*parts).read_text(encoding="utf-8")

    bars = discover_bars()
    features = included_features(model, trusted_runtime is not None)
    canaries = "".join(f'\n  <script id="canary-{feature.key}">\n{read(feature.canary)}  </script>'
                       for feature in features)
    parts = [part for feature in features for part in feature.shipped(model, trusted_runtime is not None)]
    feature_code = "".join(f"{read(name)}\n" for feature in features for name in feature.code)
    feature_code += "".join(f"{read(name)}\n" for part in parts for name in part.code)
    pdf_library = ""
    if any(part.key == "source-archive" for part in parts):
        pdf_library = ('<script id="pdf-library-script">/* ' + read("vendor", "pdf-lib.LICENSE") + " */\n"
                       + read("vendor", "pdf-lib.min.js").replace("</script", "<\\/script") + "</script>")
    bar_scripts = "\n".join(f"\n{bar.script}" for bar in bars if bar.script)
    data = serialize_artifact_data(model)
    title = model["document"]["title"]
    figure_assets = ""
    if "data-artifact-figure" in data:
        plotly = ""
        if any(feature.key == "plotting" for feature in features):
            figures = config.artifact["figures"]
            if figures["plotlyDelivery"] == "cdn":
                plotly = (f'<script id="plotly-script" src="{figures["plotlyCdnUrl"]}" '
                          f'integrity="{figures["plotlyCdnIntegrity"]}" crossorigin="anonymous" '
                          "data-optional-runtime></script>")
            else:
                plotly = ('<script id="plotly-script">/* ' + read("vendor", "plotly.LICENSE") + " */\n"
                          + read("vendor", "plotly-basic.min.js.LICENSE.txt") + "\n"
                          + read("vendor", "plotly-basic.min.js").replace("</script", "<\\/script")
                          + "</script>")
        maths = ""
        if any(feature.key == "equations" for feature in features):
            maths = ('<script id="maths-script">/* ' + maths_library_licence() + " */\n"
                     + maths_library().replace("</script", "<\\/script") + "</script>")
        figure_assets = (f'<style id="figure-styles">{read("figures.css")}</style>{plotly}{maths}'
                         f'<script id="figure-script">{read("figures.js")}</script>')
    card_assets = ""
    if "data-record-cards" in data or any(note["frontmatter"].get("kind") == "quantity"
                                          and "query" in note["frontmatter"] for note in model["notes"]):
        card_assets = f'<script id="cards-script">{read("cards.js")}</script>'
    property_assets = ""
    if "data-property-editor" in data:
        property_assets = f'<script id="property-editor-script">{read("properties.js")}</script>'
    startup = model["reading"]
    reader_startup = "".join(
        f"    {line}\n" for line in read("reader-startup.js")
        .replace("READER_THEME", json.dumps(startup["theme"]))
        .replace("READER_PAGED", json.dumps(startup["paged"])).splitlines()
    )
    runtime_head = runtime_script = ""
    if trusted_runtime:
        runtime_id, runtime_source = trusted_runtime
        runtime_head = f'<meta name="obs-trusted-runtime" content="{escape(runtime_id, quote=True)}">'
        runtime_script = (f'<script id="trusted-application-runtime" '
                          f'data-runtime-bundle="{escape(runtime_id, quote=True)}">'
                          + re.sub(r"</script", r"<\\/script", runtime_source, flags=re.IGNORECASE)
                          + "</script>")
    header_metadata = escape(serialize_artifact_data(model["document"]["metadataHtml"]), quote=True)
    return f"""<!doctype html>
<html lang="en" data-theme="{escape(startup['theme'])}">
<head>
  <meta charset="utf-8">
  {runtime_head}
  <script id="reader-startup-script">
{reader_startup}  </script>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style id="artifact-styles">
{stylesheet}
  </style>
  <style id="semantic-asset-styles">{assets.css()}</style>
</head>
<body>
  <header class="top-band" data-top-band>
    <div class="top-band-path" data-top-band-path data-transient-content></div>
    <button class="icon-button frontmatter-toggle" type="button" data-frontmatter-toggle
            aria-label="Show frontmatter" aria-expanded="false"
            aria-controls="frontmatter-panel" title="Show frontmatter" hidden>
      {markup("frontmatter")}
    </button>
    <div class="top-band-end" data-top-band-end>
      <button class="icon-button menu-button" type="button" data-menu-button
              aria-label="Open bars menu" aria-expanded="false" title="Bars" disabled>{markup("menu")}</button>
    </div>
  </header>
  <div class="app-shell" inert>
    {_dock_region("top")}
    {_dock_region("left")}
    <main class="reader-shell">
      <div class="chapter-scroll" data-chapter-scroll tabindex="-1">
        <section class="frontmatter-panel" id="frontmatter-panel" data-frontmatter-panel
                 aria-label="Frontmatter" hidden>
          <table>
            <thead><tr><th scope="col">Field</th><th scope="col">Value</th></tr></thead>
            <tbody data-frontmatter-body data-transient-content></tbody>
          </table>
        </section>
        <article class="chapter" data-active-chapter>
          <div class="chapter-body" data-chapter-body data-transient-content>
          </div>
        </article>
      </div>
      <div class="chapter-nav-zone chapter-nav-zone--previous">
        <button class="icon-button chapter-nav" type="button" data-step="-1"
                aria-label="Previous chapter" title="Previous chapter"></button>
      </div>
      <div class="chapter-nav-zone chapter-nav-zone--next">
        <button class="icon-button chapter-nav" type="button" data-step="1"
                aria-label="Next chapter" title="Next chapter"></button>
      </div>
    </main>
    {_dock_region("right")}
    {_dock_region("bottom")}
  </div>

  <script id="running-header-script" data-header-metadata="{header_metadata}">
{read("running-header.js")}
  </script>
  <section class="bars-menu" data-bars-menu aria-label="Bars" hidden>
    {''.join(_menu_row(bar) for bar in bars)}
  </section>

  <div class="bar-parking" data-bar-parking hidden>
    {''.join(_bar(bar) for bar in bars)}
  </div>

  {encode_artifact_data(model, config.artifact["dataCompression"])}
  {source_archive.island(archive) if archive is not None else ""}
  <script id="obs-comments" type="application/json" data-comment-island>{_empty_comment_island()}</script>
  <script id="document-limits" type="application/json">{_json_island(limits)}</script>
  <script id="capabilities-script">
{read("capabilities.js")}
  </script>{canaries}
  <script id="query-script">
{read("query.js")}
  </script>
  <script id="base-schema" type="application/json">{read("base.schema.json")}</script>
  <script id="case-folding" type="application/json">{files("obs").joinpath("case-folding.json").read_text(encoding="utf-8")}</script>
  <script type="application/json" data-json-schema="assets.schema.json">{read("assets.schema.json")}</script>
  <script id="yaml-script">
/* {read("vendor", "js-yaml.LICENSE")} */
{read("vendor", "js-yaml.min.js")}
  </script>
  <script id="base-script">
{read("base.js")}
  </script>
  <script id="data-table-script">
{read("options-menu.js")}
{read("table.js")}
  </script>
  <script id="zip-rewrite-script">{read("zip-rewrite.js")}</script>
  <script id="payload-script">{read("payloads.js")}</script>
  <script id="assets-script">{read("assets.js")}</script>
  <script id="notices-script">{read("notices.js")}</script>
  <script id="canonical-transaction-script">
{read("canonical-transaction.js")}
{read("attachment-replacement.js")}
  </script>
  {pdf_library}
  <script id="artifact-script">
{read("hover-card.js")}
{feature_code}{read("artifact.js")}
  </script>
  {figure_assets}
  {snippets}
  {card_assets}
  {property_assets}
  <script id="pages-script">
{read("pages.js")}
  </script>
  <script id="storage-script">

{read("storage.js")}
  </script>
  <script id="bar-scripts">
{bar_scripts}
  </script>
  {runtime_script}
</body>
</html>
"""


def _json_island(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")


def _empty_comment_island() -> str:
    return json.dumps({"version": 2, "annotations": [], "reviewers": [], "reviews": []},
                      ensure_ascii=True, separators=(",", ":"))


def _bar(bar: BarDefinition) -> str:
    key, label = escape(bar.key), escape(bar.label)
    return (
        f'<aside class="dock-bar bar--{key}" data-bar="{key}" aria-label="{label}" hidden>'
        '<header class="dock-bar-header">'
        f'<span class="bar-icon bar-icon--{key}" aria-hidden="true">{markup(bar.icon)}</span>'
        f"<h2>{label}</h2>{bar.header_actions}"
        f'<button type="button" class="icon-button dock-bar-close" data-bar-close="{key}" '
        f'aria-label="Close {label}" title="Close {label}">{markup("close")}</button>'
        f'</header><div class="dock-bar-content">{bar.render()}</div></aside>'
    )


def _menu_row(bar: BarDefinition) -> str:
    key, label = escape(bar.key), escape(bar.label)
    buttons = "".join(
        f'<button class="icon-button dock-button" type="button" data-dock-bar="{key}" '
        f'data-dock-direction="{direction}" aria-label="Dock {label} {direction}" aria-pressed="false" '
        f'title="Dock {label} {direction}">{markup(icon)}</button>'
        for direction, icon, _orientation in DOCK_DIRECTIONS
    )
    return (
        '<div class="bars-menu-row">'
        f'<span class="bar-identity" data-hover-help="{escape(bar.help)}">'
        f'<span class="bar-icon bar-icon--{key}" aria-hidden="true">{markup(bar.icon)}</span>'
        f"<span>{label}</span></span>"
        f'<div class="dock-controls" role="group" aria-label="Dock {label}">{buttons}</div></div>'
    )


def _dock_region(direction: str) -> str:
    orientation = next(item for candidate, _icon, item in DOCK_DIRECTIONS if candidate == direction)
    return (
        f'<div class="dock-region dock-region--{direction}" data-dock-region="{direction}">'
        f'<div class="dock-resize-handle" data-dock-resize="{direction}" role="separator" '
        f'aria-label="Resize {direction} bars" aria-orientation="{orientation}" tabindex="0" '
        f'data-hover-help="Drag to resize {direction} bars; double-click to reset"></div></div>'
    )


def _index(chapters: list[dict[str, object]], context: Context, where: str = "chapters") -> None:
    """Record every chapter and heading anchor before rendering, so links can point forward."""
    for index, chapter in enumerate(chapters):
        if chapter["id"] == HOME:
            raise InputError(_source(context.document), f"{where}[{index}].id", f"is {HOME!r}, which obs-html "
                             "reserves for the artifact's home page", "Rename the note, so the core gives "
                             "its chapter another id")
        context.chapters[chapter["id"]] = chapter["title"]
        _index_headings(chapter["id"], chapter["content"], context)
        _index(chapter["children"], context, f"{where}[{index}].children")


def _index_headings(chapter: str, nodes: list[dict[str, object]], context: Context) -> None:
    """A heading's anchor is ``<chapter>--<slug>``; the home page's second-level headings also
    name its front-page groups (pages.js, the abstract's ``@<slug>`` sections)."""
    seen: set[str] = set()
    for node in nodes:
        if node["type"] == "section":
            slug = _identifier(_plain(node))
            if slug not in seen:
                seen.add(slug)
                context.headings[f"{chapter}#{slug}"] = f"{chapter}--{slug}"


CSS_CLASS = re.compile(r"-?[_A-Za-z][_A-Za-z0-9-]*")


def _css_classes(frontmatter: dict[str, object], slug: str, context: Context) -> list[str]:
    """The note's Obsidian ``cssclasses``: one class name or a list of them."""
    value = frontmatter.get("cssclasses", [])
    classes = [value] if isinstance(value, str) else value
    if not isinstance(classes, list) or not all(
            isinstance(name, str) and CSS_CLASS.fullmatch(name) for name in classes):
        raise InputError(_slug_source(slug, context), "cssclasses", f"is {value!r}, not one CSS class name or "
                         "a list of them", "Write class names of letters, digits, hyphens and underscores")
    return list(dict.fromkeys(classes))


def _frontmatter_html(metadata: dict[str, object], slug: str, context: Context) -> dict[str, str]:
    """Each flattened frontmatter field's display HTML, as the frontmatter panel shows it."""
    rendered: dict[str, str] = {}

    def add(name: str, value: object) -> None:
        if isinstance(value, dict):
            if value:
                for key, item in value.items():
                    add(f"{name}.{key}" if name else key, item)
            elif name:
                rendered[name] = "{}"
        elif isinstance(value, list):
            if not value:
                rendered[name] = "[]"
            elif all(not isinstance(item, (dict, list)) for item in value):
                rendered[name] = ", ".join(_field_html(slug, f"{name}.{index}", item, context)
                                           for index, item in enumerate(value))
            else:
                for index, item in enumerate(value):
                    add(f"{name}.{index}", item)
        elif name:
            rendered[name] = _field_html(slug, name, value, context)

    add("", metadata)
    return rendered


def _field_html(slug: str, name: str, value: object, context: Context) -> str:
    """A field's display HTML: its field node where the note's frontmatter or record carries one (a
    nonempty string), else its value as text. A value without a field node (a number, a boolean) is
    not Markdown: nothing here parses a metadata string."""
    fields = context.fields.get(slug, {})
    return fields[name] if name in fields else escape("null" if value is None else _text(value))


def _flatten(value: object, prefix: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _flatten(item, f"{prefix}.{key}" if prefix else str(key))
    elif prefix:
        yield prefix, _text(value)


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(_text(item) for item in value)
    return str(value)


def _plain(node: dict[str, object]) -> str:
    return node.get("text", "") + "".join(
        _plain(child) if child["type"] != "wikilinks" else child["attrs"]["label"]
        for child in node["children"]
    )


def _identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
