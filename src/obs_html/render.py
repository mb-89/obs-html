"""Render a JSON Document as one portable, interactive HTML artifact.

The Document is the only input: no vault, no core package. Each capability this adapter
renders registers one node renderer in ``CAPABILITIES``; ``adapter.json`` declares the same
identifiers. Chapters become the notes of the artifact-data island, which the embedded
runtime (artifact.js and its companions) reads to build the reader, the bars and the pages.
"""
from __future__ import annotations

import json
import math
import mimetypes
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape, unescape
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.parse import unquote

import yaml
from jsonschema import Draft202012Validator
from markdown_it import MarkdownIt

from obs_html.bars import BarDefinition, discover_bars
from obs_html.config import Config, paper
from obs_html.figures import FigureError, render_descriptor
from obs_html.artifact_data import encode_artifact_data, prepare_artifact_scripts, serialize_artifact_data
from obs_html.semantic_assets import SemanticAssets, markup
from obs_html.styles import load_style
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
}
COVER_FIELDS = ("authors", "reviewers", "approvers", "sap number", "legal entity")
HOME = "home"
DOCK_DIRECTIONS = (
    ("left", "left", "vertical"),
    ("right", "right", "vertical"),
    ("top", "up", "horizontal"),
    ("bottom", "down", "horizontal"),
)


class RenderError(ValueError):
    """Raised when a Document cannot be rendered."""


@dataclass
class Context:
    document: dict[str, object]
    command_runner: Callable[[str], str] | None
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
    aliases: dict[str, str | None] = field(default_factory=dict)
    records: dict[str, dict[str, object]] = field(default_factory=dict)
    editable: dict[str, dict[str, object]] = field(default_factory=dict)
    unknown: set[str] = field(default_factory=set)


Renderer = Callable[[dict[str, object], Context], str]


def _nothing(_node: dict[str, object], _context: Context) -> str:
    """A marker or data-only node: it states the source used the capability, nothing to show."""
    return ""


def _frontmatter(node: dict[str, object], context: Context) -> str:
    """A chapter's frontmatter feeds its frontmatter panel, filters and Base rows, not its body."""
    if context.chapter:
        context.frontmatter.update(node["attrs"]["metadata"])
    return ""


def _wikilink(node: dict[str, object], context: Context) -> str:
    attrs = node["attrs"]
    chapter = attrs["chapter"]
    if chapter is None:
        return (f'<span class="unresolved" title="{escape(attrs["target"], quote=True)}">'
                f'{escape(attrs["label"])}</span>')
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
    anchor = context.headings.get(f"{chapter}#{_identifier(heading)}") if heading else None
    href = f"#{chapter}/{anchor.removeprefix(f'{chapter}--')}" if anchor else f"#{chapter}"
    return f'<a class="internal-link" href="{href}">{escape(label or title)}</a>'


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


QUANTITY_ALIAS = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,39}")
NOTE_LINK = re.compile(r"!?\[\[[^\[\]]+\]\]")


def _quantity(node: dict[str, object], context: Context) -> str:
    """A quantity note's metadata, checked as the interim adapter checked it; its value shows
    where the note is linked (see _quantity_link), not in its own body."""
    metadata = node["attrs"]["metadata"]
    where = f"Chapter {context.chapter or HOME}: quantity"
    value, unit, aliases, source = (metadata.get(key) for key in ("value", "unit", "aliases", "source"))
    if ("value" in metadata) == ("query" in metadata):
        raise RenderError(f"{where} needs exactly one of value or query. Remedy: give the quantity note "
                          "either a numeric value or a count query, not both.")
    if "value" in metadata and (isinstance(value, bool) or not isinstance(value, (int, float))
                                or not math.isfinite(value)):
        raise RenderError(f"{where} value must be a finite number, not {value!r}. Remedy: write the value "
                          "as a number; put its unit into unit.")
    if "unit" in metadata and (not isinstance(unit, str) or not unit.strip()):
        raise RenderError(f"{where} unit must be a non-empty string when supplied. Remedy: write the unit "
                          "as text or remove unit.")
    aliases = [aliases] if isinstance(aliases, str) else aliases
    if not isinstance(aliases, list) or len(aliases) != 1 or not isinstance(aliases[0], str) \
            or not QUANTITY_ALIAS.fullmatch(aliases[0].strip()):
        raise RenderError(f"{where} needs one short variable-style alias, not {aliases!r}. Remedy: give the "
                          "note one alias of letters, digits and underscores, starting with a letter.")
    sources = [source] if isinstance(source, str) else source
    if not isinstance(sources, list) or not sources or not all(
            isinstance(item, str) and item.strip() for item in sources) \
            or not any(NOTE_LINK.search(item) for item in sources):
        raise RenderError(f"{where} source must be a non-empty string or list of them with a note link. "
                          "Remedy: cite the supporting note as a wikilink in source.")
    return ""


def _count_query(node: dict[str, object], context: Context) -> str:
    """A count query is data the runtime evaluates (cards.js) from the note's frontmatter."""
    if not isinstance(node["attrs"]["query"].get("where"), list):
        raise RenderError(f"Chapter {context.chapter or HOME}: count query has no where list; "
                          "regenerate the Document with the obs core.")
    return ""


CAPABILITY_FENCES = {"base", "cards", "cmd", "figure", "property-editor"}


def _cards(node: dict[str, object], context: Context) -> str:
    """Data-only cards: titled sections whose metric slots the runtime (cards.js) counts from the
    globally filtered records; only the metric declarations enter the browser."""
    place = f"Chapter {context.chapter or HOME}"
    cards = node["attrs"]["spec"].get("cards")
    if not isinstance(cards, list) or not all(
            isinstance(card, dict) and isinstance(card.get("title"), str) and isinstance(card.get("body"), str)
            and isinstance(card.get("metrics", []), list) for card in cards):
        raise RenderError(f"{place}: cards fence is not a list of cards with a title, a body and metrics; "
                          "regenerate the Document with the obs core.")
    rendered = []
    for card in cards:
        what = f"{place}: card {card['title']!r}"
        series = (card.get("obsHtml") or {}).get("metricsFrom")
        if series:
            _check_series(series, what, context)
        metrics = [dict(metric) for metric in card.get("metrics", [])]
        for metric in metrics:
            if "secondary" in metric:
                metric["valueHtml"] = _markdown(f'[[{metric["from"]}]] ([[{metric["secondary"]}]])', what, context)\
                    .strip().removeprefix("<p>").removesuffix("</p>")
        payload = escape(json.dumps(metrics, ensure_ascii=False), quote=True)
        slots = "".join(f'<div data-record-metric="{index}" role="status" aria-busy="true">Calculating…</div>'
                        for index in range(len(metrics)))
        style = f'record-metrics--{card["metricStyle"]}' if card.get("metricStyle") else ""
        series_data = f' data-record-series="{escape(json.dumps(series), quote=True)}"' if series else ""
        rendered.append(
            f'<section class="content-card record-card" data-record-card="{payload}"{series_data}>'
            f'<header class="content-card-title">{escape(card["title"])}</header>'
            + (f'<div class="record-metrics {style}">{slots}</div>' if metrics or series else "")
            + _markdown(card["body"], what, context) + "</section>")
    return '<div class="record-cards" data-record-cards>' + "".join(rendered) + "</div>\n"


def _check_series(series: dict[str, object], what: str, context: Context) -> None:
    """A metric series reads a list from a note's frontmatter: one metric per uniquely labelled item."""
    name = f"{what} metric series {series.get('sourceNote')}/{series.get('property')}"
    record = context.records.get(context.paths.get(str(series.get("sourceNote")), ""))
    value: object = record["fields"] if record else None
    for part in str(series.get("property")).split("."):
        value = value.get(part) if isinstance(value, dict) else None
    if not isinstance(value, list):
        raise RenderError(f"{name} is not a list. Remedy: name a note path and a frontmatter list property.")
    labels: set[object] = set()
    for item in value:
        fields = [item.get(str(series.get(key))) if isinstance(item, dict) else None
                  for key in ("labelProperty", "distinctProperty")]
        if any(not isinstance(field, str) or not field.strip() for field in fields) or fields[0] in labels:
            raise RenderError(f"{name} needs unique labels and non-empty distinct names. Remedy: give every "
                              "list item its own label and a distinct property value.")
        labels.add(fields[0])


BLOCK = MarkdownIt("commonmark", {"html": False})
CODE = re.compile(r"(<pre\b.*?</pre>|<code>.*?</code>)", re.DOTALL)


def _markdown(source: str, what: str, context: Context) -> str:
    """A card body: Markdown with wikilinks, raw HTML as text. The Document carries it as authored
    Markdown, not as nodes, so a capability fence in it cannot render here."""
    for token in BLOCK.parse(source):
        language = token.info.strip().split()[0] if token.type == "fence" and token.info.strip() else ""
        if language in CAPABILITY_FENCES:
            raise RenderError(f"{what} body holds a {language} fence, which obs-html cannot render inside a "
                              f"card. Remedy: move the {language} fence out of the card body.")
    parts = CODE.split(BLOCK.render(source))
    return "".join(part if index % 2 else WIKILINK.sub(lambda match: _frontmatter_link(match, context), part)
                   for index, part in enumerate(parts))


def _embed(node: dict[str, object], context: Context) -> str:
    """An embedded note links to its chapter, titled like an unaliased wikilink; an embedded
    file (a target with a non-note suffix, which no chapter resolves) renders like an attachment."""
    target, chapter = node["attrs"]["target"], node["attrs"]["chapter"]
    if chapter is None and PurePosixPath(target).suffix.lower() not in {"", ".md"}:
        media_type = mimetypes.guess_type(target)[0] or "application/octet-stream"
        return _file(target, "", media_type, f"embed {target!r}", context)
    if chapter is None:
        return f'<span class="unresolved embed" title="{escape(target, quote=True)}">{escape(target)}</span>'
    return f'<a class="internal-link embed" href="#{chapter}">{escape(_chapter_title(chapter, context))}</a>'


def _attachment(node: dict[str, object], context: Context) -> str:
    """An attachment names a Document asset: an image is document content, any other file is
    provenance text (its label and path), as the interim adapter rendered it without
    --embed-attachments; the adapter has only the Document, not the file's bytes."""
    identifier, label = node["attrs"]["asset"], node["attrs"]["label"]
    asset = context.files.get(identifier)
    if asset is None:
        raise RenderError(f"Chapter {context.chapter or HOME}: attachment names asset {identifier!r}, which "
                          "the Document's assets do not contain; regenerate the Document with the obs core.")
    return _file(asset["href"], label, asset["mediaType"], f"attachment {identifier!r}", context)


def _file(href: str, label: str, media_type: str, what: str, context: Context) -> str:
    if re.match(r"(?:file:|/|\\\\|[A-Za-z]:[\\/])", href):
        raise RenderError(f"Chapter {context.chapter or HOME}: {what} has the absolute path {href!r}, which "
                          "would expose the build machine; link the file by its vault-relative path.")
    if media_type.startswith("image/"):
        return f'<img src="{escape(href, quote=True)}" alt="{escape(label, quote=True)}">'
    if re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", href):
        return f'<a href="{escape(href, quote=True)}">{escape(label or href)}</a>'
    name = label or PurePosixPath(href).name
    return (f'<span class="source-reference" data-source-path="{escape(href, quote=True)}">{escape(name)}</span>'
            f' ({_code({"attrs": {}, "text": href})})')


# Canonical callout kind: its tone, the shared semantic card colour (obs artifact-ui.md).
CALLOUT_TONES = {
    "note": "accent", "abstract": "accent", "info": "accent", "todo": "accent", "tip": "accent",
    "success": "success", "question": "warning", "warning": "warning", "failure": "failure",
    "danger": "failure", "bug": "failure", "example": "accent", "quote": "neutral",
    "important": "accent",
}


def _callout(node: dict[str, object], context: Context) -> str:
    """A callout is a card titled by its authored title or, untitled, by its kind; ``important``
    is the untitled emphasis box."""
    kind, title = node["attrs"]["kind"], node["attrs"]["title"]
    if kind not in CALLOUT_TONES:
        raise RenderError(f"Chapter {context.chapter or HOME}: callout kind {kind!r} is not one of "
                          f"{', '.join(sorted(CALLOUT_TONES))}; regenerate the Document with the obs core.")
    name = kind.capitalize()
    if kind == "important":
        opening = f'<aside class="content-card content-emphasis" aria-label="{name}">\n'
    else:
        opening = (f'<aside class="content-card content-callout content-callout--{CALLOUT_TONES[kind]}" '
                   f'data-callout="{kind}" aria-label="{name}">\n')
        title = title or name
    header = f'<header class="content-card-title">{_inline(title, context)}</header>\n' if title else ""
    return f"{opening}{header}{_nodes(node['children'], context)}</aside>\n"


def _chapter_title(chapter: str, context: Context) -> str:
    if chapter not in context.chapters:
        raise RenderError(f"Chapter {context.chapter or HOME}: a link names chapter {chapter!r}, which the "
                          "Document does not contain; regenerate the Document with the obs core.")
    return context.chapters[chapter]


def _mark(node: dict[str, object], _context: Context) -> str:
    """Marks are collected by their paragraph, which carries the mark rail (see _paragraph)."""
    return ""


def _command(node: dict[str, object], context: Context) -> str:
    if node["attrs"].get("silent"):
        return ""
    if context.command_runner is None:
        raise RenderError("A command fence requires explicit command execution authorization "
                          "(--execute-commands).")
    output = context.command_runner(node["attrs"]["source"].strip())
    return f'<pre class="command-output">{escape(output)}</pre>\n'


def _base(node: dict[str, object], context: Context) -> str:
    """A Base view is a table placeholder; the runtime evaluates it over the island's notes."""
    definition = node["attrs"]["spec"]
    try:
        context.assets.normalize_definition(definition)
    except ValueError as error:
        raise RenderError(f"Base in chapter {context.chapter or HOME}: {error}") from error
    key = f"{context.chapter or HOME}-base-{len(context.tables) + 1}"
    for filters in [definition.get("filters"), *(view.get("filters") for view in definition.get("views", []))]:
        unsupported = _unsupported_filter(filters)
        if unsupported is not None:
            names = ", ".join(str(view.get("name", "")) for view in definition.get("views", []))
            raise RenderError(
                f'Base "{names}" ({key}) in chapter {context.chapter or HOME}: obs-html cannot evaluate '
                f"the filter: {unsupported}. Supported: comparisons PROPERTY == LITERAL or PROPERTY != LITERAL, "
                "where PROPERTY is a frontmatter property (dotted, or note[\"name with spaces\"]) or one of "
                f"{', '.join(FILE_PROPERTIES)}, and LITERAL is quoted text, a number, true, false or null; "
                "combined with and, or and not. Remedy: rewrite the filter in this subset.")
    context.tables.append({"key": key, "definition": definition})
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
    descriptor = node["attrs"]["descriptor"]
    try:
        return render_descriptor(descriptor, f"{context.chapter or HOME}--figure-{descriptor['id']}")
    except FigureError as error:
        raise RenderError(f"Chapter {context.chapter or HOME}: {error}") from error


def _references(node: dict[str, object], context: Context) -> str:
    """A glossary or reference note. Its metadata reaches the runtime as the note's frontmatter:
    hover cards and the glossary register read the definition (``definitionHtml``, see
    _definition_html) and a reference's ``url`` (obs references.md, input-model Reference notes)."""
    metadata = node["attrs"]["metadata"]
    place = f"Chapter {context.chapter or HOME}"
    if metadata.get("kind") == "glossary" and not isinstance(metadata.get("definition"), str):
        raise RenderError(f"{place}: glossary note has no text definition. Remedy: add "
                          "'definition: <text>' to the note's frontmatter.")
    url = metadata.get("url")
    if url is not None and not (isinstance(url, str) and re.match(r"https?://\S+$", url, re.IGNORECASE)):
        raise RenderError(f"{place}: reference url {url!r} is not an http(s) URL. Remedy: give the "
                          "reference note's url field the external address, such as https://example.org.")
    return ""


def _definition_html(frontmatter: dict[str, object], context: Context) -> str:
    """A glossary note's definition as inline HTML, for its hover card and register rows."""
    if frontmatter.get("kind") != "glossary" or "definition" not in frontmatter:
        return ""
    return _inline(frontmatter["definition"], context)


SYNTAX_EXTENSIONS = {"callout": "callouts"}


def _extension(node: dict[str, object], context: Context) -> str:
    """An Obsidian syntax extension the source used (obs extensions.md). It marks the syntax; the
    capability that owns the syntax renders its content, so the marker itself shows nothing.
    Trusted runtime extensions are another thing: artifact.js's ``obsArtifact.trustedExtension``."""
    syntax = node["attrs"].get("syntax")
    owner = SYNTAX_EXTENSIONS.get(syntax)
    if owner is None:
        raise RenderError(f"Chapter {context.chapter or HOME}: syntax extension {syntax!r} is not one obs-html "
                          f"renders; it renders {', '.join(sorted(SYNTAX_EXTENSIONS))}. Remedy: write the "
                          "content without that syntax, or extend obs-html's SYNTAX_EXTENSIONS.")
    if owner not in context.document["capabilities"]:
        raise RenderError(f"Chapter {context.chapter or HOME}: syntax extension {syntax!r} is used, but the "
                          f"Document does not use {owner!r}, which renders it; regenerate the Document with "
                          "the obs core.")
    return ""


PROPERTY_EDITOR_SCHEMA = json.loads(files("obs_html").joinpath("property-editor.schema.json")
                                    .read_text(encoding="utf-8"))
PROPERTY_EDITOR = Draft202012Validator(PROPERTY_EDITOR_SCHEMA)
PROTECTED_FIELDS = frozenset(PROPERTY_EDITOR_SCHEMA["$defs"]["editableField"]["not"]["enum"])


def _property_editor(node: dict[str, object], context: Context) -> str:
    """A ``property-editor`` fence: a text editor for one existing string field of an authored
    note; properties.js commits edits through artifact.js (``obsArtifact.commitProperty``), which
    checks the same declaration. The core has no capability for the fence (obs input-model,
    Reviewed copy), so the Document carries it as a code node in that language."""
    place = f"Chapter {context.chapter or HOME}: property editor"
    try:
        spec = yaml.safe_load(node.get("text", ""))
    except yaml.YAMLError as error:
        raise RenderError(f"{place} is not valid YAML: {error}. Remedy: fix the property-editor fence.") from error
    field = spec.get("field") if isinstance(spec, dict) else None
    if isinstance(field, str) and field.lower() in PROTECTED_FIELDS:
        raise RenderError(f"{place} cannot change the protected field {field!r}. Remedy: edit another field.")
    error = next(PROPERTY_EDITOR.iter_errors(spec), None)
    if error is not None:
        raise RenderError(f"{place}: {error.message[:180]}. Remedy: declare version: 1, field and label as "
                          "property-editor.schema.json says.")
    limit = spec.get("maxLength", PROPERTY_EDITOR_SCHEMA["properties"]["maxLength"]["default"])
    if not context.chapter or not isinstance(context.frontmatter.get(field), str):
        raise RenderError(f"{place} needs an existing text field {field!r} on an authored note. Remedy: add "
                          f"'{field}: <text>' to the note's frontmatter.")
    if len(context.frontmatter[field]) > limit:
        raise RenderError(f"{place}: the text of {field!r} is longer than maxLength {limit}. Remedy: shorten "
                          "it or raise maxLength.")
    if field in context.editable:
        raise RenderError(f"{place} declares {field!r} more than once. Remedy: keep one editor per field.")
    definition: dict[str, object] = {"label": spec["label"], "maxLength": limit}
    projection = spec.get("projection")
    if projection is not None:
        for branch in ("blank", "nonblank"):
            for name, value in projection[branch].items():
                if name == field or name.lower() in PROTECTED_FIELDS or name not in context.frontmatter \
                        or not _projection_matches(context.frontmatter[name], value):
                    raise RenderError(f"{place}: projection field {name!r} must be another existing, unprotected "
                                      "field of the same type. Remedy: project onto such a field.")
        definition["projection"] = projection
    context.editable[field] = definition
    label = escape(spec["label"])
    return ('<label class="property-editor">'
            f"<span>{label}</span>"
            f'<textarea data-property-editor data-property-note="{escape(context.chapter, quote=True)}" '
            f'data-property-field="{escape(field, quote=True)}" maxlength="{limit}" '
            f'aria-label="{escape(spec["label"], quote=True)}" rows="2"></textarea></label>\n')


def _projection_kind(value: object) -> str | None:
    """The kinds a projection may write, as artifact.js checks them: one primitive, or a list of one."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number" if math.isfinite(value) else None
    if isinstance(value, list):
        kinds = {_projection_kind(item) for item in value}
        return "array" if None not in kinds and len(kinds) <= 1 else None
    return None


def _projection_matches(existing: object, projected: object) -> bool:
    kind = _projection_kind(projected)
    if kind is None or _projection_kind(existing) != kind:
        return False
    if kind != "array" or not existing or not projected:
        return True
    return _projection_kind(existing[0]) == _projection_kind(projected[0])


CAPABILITIES: dict[str, Renderer] = {
    "artifact-presentation": _nothing,
    "attachments": _attachment,
    "bases": _base,
    "callouts": _callout,
    "cards-metrics": _cards,
    "chapter-inclusion": _nothing,
    "command-fences": _command,
    "count-query": _count_query,
    "embeds": _embed,
    "extensions": _extension,
    "figure-descriptor": _figure,
    "manifest": _nothing,
    "markdown": _nothing,
    "markdown-frontmatter": _frontmatter,
    "marks": _mark,
    "named-icons": _nothing,
    "profiles": _nothing,
    "quantities": _quantity,
    "queries": _nothing,
    "references": _references,
    "wikilinks": _wikilink,
}


@stage("render")
def render(document: dict[str, object], config: Config,
           command_runner: Callable[[str], str] | None = None,
           style_folder: Path | None = None,
           trusted_runtime: tuple[str, str] | None = None) -> str:
    if document.get("schemaVersion") != 1:
        raise RenderError(f"Unsupported Document schema version: {document.get('schemaVersion')!r}.")
    unsupported = sorted(set(document["capabilities"]) - set(CAPABILITIES))
    if unsupported:
        raise RenderError(f"Document uses capabilities this adapter does not render: "
                          f"{', '.join(unsupported)}.")
    style = load_style(style_folder)
    assets = SemanticAssets(style.asset_index)
    context = Context(
        document, command_runner, assets,
        links={item["id"]: item for item in document["links"]},
        files={item["id"]: item for item in document["assets"]},
        paths={record["path"].removesuffix(".md"): record["id"]
               for record in document["records"] if record.get("type") == "note"},
        records={record["id"]: record for record in document["records"] if record.get("type") == "note"},
    )
    for record in context.records.values():
        aliases = record["fields"].get("aliases")
        for alias in [aliases] if isinstance(aliases, str) else aliases if isinstance(aliases, list) else []:
            if isinstance(alias, str) and alias.strip():
                key = alias.strip().casefold()  # An alias two notes share resolves to neither.
                context.aliases[key] = record["id"] if key not in context.aliases else None
    _index(document["chapters"], context)
    _index_headings(HOME, document["manifest"].get("abstract", []), context)
    if HOME in context.chapters:
        raise RenderError(f"Chapter id {HOME!r} is reserved for the artifact's home page.")
    context.chapters[HOME] = document["manifest"]["title"]  # The core links the manifest as home.
    model = _resolve_icons(_model(document, config, context), assets)
    return prepare_artifact_scripts(assets.resolve_markup(
        _shell(model, style.stylesheet, assets, config, trusted_runtime)))


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
    declared = next((node["attrs"]["profile"] for node in manifest.get("abstract", [])
                     if node["type"] == "profiles"), {})
    resolved = {key: declared.get(key, value) for key, value in PROFILE_DEFAULTS.items()}
    resolved["figures"] = PROFILE_DEFAULTS["figures"] | resolved["figures"]
    resolved["print"] = declared.get("print") or {}
    return resolved


def _model(document: dict[str, object], config: Config, context: Context) -> dict[str, object]:
    """The artifact-data island: the runtime's only model of the artifact."""
    manifest = document["manifest"]
    profile = _profile(manifest)
    settings = config.artifact
    title = manifest["title"]
    metadata = {key: value for key, value in manifest["metadata"].items() if key != "obsHtml"}
    home_html = _cover(title, metadata, profile["heading"] == "compact") + _note_body(
        manifest.get("abstract", []), "", context)
    notes = [_note(0, title, HOME, HOME, {}, home_html, context)]
    notes.extend(_chapter_notes(document["chapters"], context, 0))
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
            "pages": profile["pages"],
            "generation": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "generator": {"name": "obs-html", "version": version("obs-html"), "commit": "unknown"},
                "target": {"name": title, "version": "unknown", "commit": "unknown"},
            },
        },
        "paper": paper({**config.print_default, **profile["print"]}, config),
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


def _chapter_notes(chapters: list[dict[str, object]], context: Context, depth: int) -> list[dict]:
    notes = []
    for chapter in chapters:
        context.frontmatter = dict(chapter.get("metadata") or {})
        body = _note_body(chapter["content"], chapter["id"], context)
        notes.append(_note(depth, chapter["title"], chapter["id"], "", context.frontmatter, body, context))
        notes.extend(_chapter_notes(chapter["children"], context, depth + 1))
    return notes


def _note_body(nodes: list[dict[str, object]], chapter: str, context: Context) -> str:
    context.chapter, context.tables, context.marks, context.editable = chapter, [], [], {}
    body = _nodes(nodes, context)
    context.chapter = ""
    return body


def _note(depth: int, title: str, slug: str, generated: str, frontmatter: dict[str, object],
          html: str, context: Context) -> dict[str, object]:
    return {
        "depth": depth, "title": title, "slug": slug, "sourcePath": f"{slug}.md",
        "generated": generated, "cssClasses": _css_classes(frontmatter, slug),
        "frontmatter": frontmatter, "editableProperties": context.editable,
        "frontmatterHtml": _frontmatter_html(frontmatter, context),
        "definitionHtml": _definition_html(frontmatter, context), "marks": context.marks, "tables": context.tables, "html": html,
    }


def _attach_records(records: list[dict[str, object]], notes: list[dict[str, object]],
                    context: Context) -> None:
    """Records join the queryable population: a chapter's own record adds to its frontmatter,
    any other record becomes a record-only note outside the reading order. A note record's
    path is its note's source path, which Bases read file.* properties from (obs bases.md)."""
    by_slug = {note["slug"]: note for note in notes}
    for record in records:
        fields = dict(record["fields"])
        note = by_slug.get(record["id"])
        source_path = record.get("path") or f"{record['id']}.md"
        if note is not None and record.get("ignored"):
            note["ignored"] = True  # Runtime selections skip it (artifact.js, selectable).
        if note is not None and not note["generated"]:
            note["frontmatter"] = {**fields, **note["frontmatter"]}
            note["frontmatterHtml"] = _frontmatter_html(note["frontmatter"], context)
            note["definitionHtml"] = _definition_html(note["frontmatter"], context)
            note["sourcePath"] = source_path
            continue
        if note is not None:
            raise RenderError(f"Record id {record['id']!r} is reserved for the artifact's home page.")
        fields["obsHtml"] = {**(fields.get("obsHtml") or {}), "document": False}
        notes.append({
            "depth": 0, "title": str(fields.get("title") or record["id"]), "slug": record["id"],
            "sourcePath": source_path, "generated": "", "cssClasses": [],
            "frontmatter": fields, "editableProperties": {},
            "frontmatterHtml": _frontmatter_html(fields, context),
            "definitionHtml": _definition_html(fields, context), "marks": [], "tables": [], "html": "", "record": True,
            **({"ignored": True} if record.get("ignored") else {}),
        })


def _cover(title: str, metadata: dict[str, object], compact: bool) -> str:
    def value(item: object) -> str:
        return escape(_text(item))

    product = metadata.get("product") if isinstance(metadata.get("product"), dict) else {}
    subtitle = _inline(metadata["subtitle"]) if metadata.get("subtitle") else ""
    if compact:
        product_text = " ".join(value(product[key]) for key in ("name", "version") if product.get(key))
        parts = [("cover-organization", value(metadata.get("organization", ""))),
                 ("cover-product", product_text), ("cover-type", value(metadata.get("document type", "")))]
        line = "".join(f'<span class="{name}">{text}</span>' for name, text in parts if text)
        line += f'<h1 class="document-title">{escape(title)}</h1>'
        if subtitle:
            line += f'<span class="document-subtitle">{subtitle}</span>'
        return ('<header class="document-heading document-heading--compact">'
                f'<div class="compact-heading">{line}</div></header>\n')
    product_html = "".join(f"<div>{value(product[key])}</div>" for key in ("name", "version") if product.get(key))
    band = (f'<span class="cover-template">{value(metadata.get("template", ""))}</span>'
            f'<span class="cover-organization">{value(metadata.get("organization", ""))}</span>')
    facts = "".join(f"<dt>{escape(key.title())}</dt><dd>{value(metadata[key])}</dd>"
                    for key in COVER_FIELDS if metadata.get(key))
    legal = "".join(f'<p class="cover-{key}">{value(metadata[key])}</p>'
                    for key in ("copyright", "confidentiality") if metadata.get(key))
    return (
        '<header class="document-heading">'
        + (f'<div class="cover-product">{product_html}</div>' if product_html else "")
        + f'<div class="cover-band">{band}</div><div class="cover-frame">'
        + f'<h1 class="document-title">{escape(title)}</h1>'
        + (f'<p class="cover-type">{value(metadata["document type"])}</p>' if metadata.get("document type") else "")
        + (f'<div class="document-subtitle">{subtitle}</div>' if subtitle else "")
        + legal + "</div>"
        + f'<div class="cover-facts-frame"><dl class="cover-facts">{facts}</dl></div></header>\n'
    )


def _nodes(nodes: list[dict[str, object]], context: Context) -> str:
    return "".join(_node(node, context) for node in nodes)


def _node(node: dict[str, object], context: Context) -> str:
    kind = node["type"]
    return (CAPABILITIES.get(kind) or STRUCTURAL_NODES.get(kind) or _unknown)(node, context)


def _code_node(node: dict[str, object], context: Context) -> str:
    if node["attrs"].get("language") == "property-editor":
        return _property_editor(node, context)
    return _code(node)


def _list(node: dict[str, object], context: Context) -> str:
    tag = "ol" if node["attrs"].get("ordered") else "ul"
    if _tight(node):
        items = "".join(f"<li>{_tight_item(item, context)}</li>\n" for item in node["children"])
        return f"<{tag}>\n{items}</{tag}>\n"
    return f"<{tag}>\n{_nodes(node['children'], context)}</{tag}>\n"


def _section(node: dict[str, object], context: Context) -> str:
    level = min(max(int(node["attrs"].get("level", 1)), 1), 6)
    anchor = context.headings.get(f"{context.chapter or HOME}#{_identifier(_plain(node))}", "")
    identifier = f' id="{anchor}"' if anchor else ""
    return f"<h{level}{identifier}>{_nodes(node['children'], context)}</h{level}>\n"


def _wrap(opening: str, closing: str) -> Renderer:
    """A node shown as its children inside one element."""
    return lambda node, context: f"{opening}{_nodes(node['children'], context)}{closing}"


def _unknown(node: dict[str, object], context: Context) -> str:
    """A node type this adapter does not know shows its text, never nothing, and warns once per type."""
    kind = node["type"]
    if kind not in context.unknown:
        context.unknown.add(kind)
        listed = "lists it as structural" if kind in STRUCTURAL else "does not list it"
        print(f"Warning: obs-html (src/obs_html/render.py): Document node type {kind!r} is not rendered by "
              f"this adapter, first in chapter {context.chapter or HOME!r}; its text is shown without its "
              f"formatting. The core's document.schema.json {listed}. Remedy: add a renderer for {kind!r} "
              "to src/obs_html/render.py.", file=sys.stderr)
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


def _tight(node: dict[str, object]) -> bool:
    """A list whose items each hold one paragraph (plus nested lists) renders tight, as
    Markdown's usual tight lists do; the Document does not say whether a list was loose."""
    return all(
        sum(child["type"] == "paragraph" for child in item["children"]) == 1
        and all(child["type"] in {"paragraph", "list"} for child in item["children"])
        for item in node["children"]
    )


def _tight_item(item: dict[str, object], context: Context) -> str:
    parts = []
    for child in item["children"]:
        if child["type"] == "paragraph" and not any(c["type"] == "marks" for c in child["children"]):
            parts.append(_nodes(child["children"], context))
        else:
            parts.append(("\n" if parts else "") + _node(child, context))
    return "".join(parts)


def _paragraph(node: dict[str, object], context: Context) -> str:
    inner = _nodes(node["children"], context)
    marks = [child["attrs"] for child in node["children"] if child["type"] == "marks"]
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
        f'aria-label="{escape(_mark_description(mark), quote=True)}">{_mark_icon(kind, context)}</a>'
        for kind, mark in zip(kinds, marks)
    )
    return (f'<p class="semantic-mark {classes}" data-mark-kind="{escape(" ".join(kinds), quote=True)}" '
            f'data-mark-label="{escape(" ".join(mark["id"] for mark in marks), quote=True)}" id="{anchor}">'
            f'<span class="semantic-mark-content">{inner.strip()}</span>'
            f'<span class="semantic-mark-rail" aria-label="Paragraph marks">{rail}</span></p>\n')


def _mark_icon(kind: str, context: Context) -> str:
    try:
        context.assets.icon(f"mark.{kind}")
    except ValueError as error:
        raise RenderError(f"Unknown paragraph mark kind {kind!r}: {error}") from error
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
            raise RenderError(f"Text links to an unknown link: {attrs['link']}.")
        chapter = _note_target(link["href"], context)
        if chapter is not None:
            return f'<a class="internal-link" href="#{chapter}">{text}</a>'
        return f'<a href="{escape(link["href"], quote=True)}">{text}</a>'
    if "asset" in attrs:
        asset = context.files.get(attrs["asset"])
        if asset is None:
            raise RenderError(f"Text names an unknown asset: {attrs['asset']}.")
        return f'<img src="{escape(asset["href"], quote=True)}" alt="{escape(node.get("text", ""), quote=True)}">'
    return text


STRUCTURAL_NODES: dict[str, Renderer] = {
    "document": _wrap('<div class="document">', "</div>\n"),
    "section": _section,
    "paragraph": _paragraph,
    "text": _text_node,
    "list": _list,
    "list-item": _wrap("<li>", "</li>\n"),
    "code": _code_node,
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


def _shell(model: dict[str, object], stylesheet: str, assets: SemanticAssets, config: Config,
           trusted_runtime: tuple[str, str] | None) -> str:
    package = files("obs_html")

    def read(*parts: str) -> str:
        return package.joinpath(*parts).read_text(encoding="utf-8")

    bars = discover_bars()
    bar_scripts = "\n".join(f"\n{bar.script}" for bar in bars if bar.script)
    data = serialize_artifact_data(model)
    title = model["document"]["title"]
    figure_assets = ""
    if "data-artifact-figure" in data:
        plotly = ""
        if 'data-figure-kind=\\"plot\\"' in data:
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
        figure_assets = (f'<style id="figure-styles">{read("figures.css")}</style>{plotly}'
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
    header_metadata = escape(serialize_artifact_data(model["document"]["metadata"]), quote=True)
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
  <div class="app-shell" inert>
    {_dock_region("top")}
    {_dock_region("left")}
    <main class="reader-shell">
      <div class="frontmatter-nav-zone">
        <button class="frontmatter-toggle" type="button" data-frontmatter-toggle
                aria-label="Show frontmatter" aria-expanded="false"
                aria-controls="frontmatter-panel" title="Show frontmatter" hidden>
          {markup("frontmatter")}
        </button>
      </div>
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
  <button class="icon-button menu-button" type="button" data-menu-button
          aria-label="Open bars menu" aria-expanded="false" title="Bars" disabled>{markup("menu")}</button>
  <section class="bars-menu" data-bars-menu aria-label="Bars" hidden>
    {''.join(_menu_row(bar) for bar in bars)}
  </section>

  <div class="bar-parking" data-bar-parking hidden>
    {''.join(_bar(bar) for bar in bars)}
  </div>

  {encode_artifact_data(model, config.artifact["dataCompression"])}
  <script id="obs-comments" type="application/json" data-comment-island>{_empty_comment_island()}</script>
  <script id="capabilities-script">
{read("capabilities.js")}
  </script>
  <script id="query-script">
{read("query.js")}
  </script>
  <script id="base-schema" type="application/json">{read("base.schema.json")}</script>
  <script type="application/json" data-json-schema="assets.schema.json">{read("assets.schema.json")}</script>
  <script id="property-editor-schema" type="application/json">{read("property-editor.schema.json")}</script>
  <script id="yaml-script">
/* {read("vendor", "js-yaml.LICENSE")} */
{read("vendor", "js-yaml.min.js")}
  </script>
  <script id="base-script">
{read("base.js")}
  </script>
  <script id="data-table-script">
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
  <script id="artifact-script">
{read("hover-card.js")}
{read("guided-card.js")}
{read("artifact.js")}
  </script>
  {figure_assets}
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


def _index(chapters: list[dict[str, object]], context: Context) -> None:
    """Record every chapter and heading anchor before rendering, so links can point forward."""
    for chapter in chapters:
        context.chapters[chapter["id"]] = chapter["title"]
        _index_headings(chapter["id"], chapter["content"], context)
        _index(chapter["children"], context)


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


def _css_classes(frontmatter: dict[str, object], slug: str) -> list[str]:
    """The note's Obsidian ``cssclasses``: one class name or a list of them."""
    value = frontmatter.get("cssclasses", [])
    classes = [value] if isinstance(value, str) else value
    if not isinstance(classes, list) or not all(
            isinstance(name, str) and CSS_CLASS.fullmatch(name) for name in classes):
        raise RenderError(f"cssclasses must be one CSS class name or a list of them in {slug}: {value!r}")
    return list(dict.fromkeys(classes))


INLINE = MarkdownIt("commonmark", {"html": False})


def _inline(value: object, context: Context | None = None) -> str:
    """Inline Markdown of a metadata string (bold, links, images such as badges); raw HTML stays text.

    The Document carries metadata values as authored strings, so their inline Markdown is
    rendered here, as the interim adapter did, until the core carries them as nodes. With a
    context, wikilinks link the chapter their note record names (see _frontmatter_link).
    """
    source = _text(value)
    if re.fullmatch(r"https?://[^\s<>]+", source, re.IGNORECASE):
        source = f"<{source}>"
    html = INLINE.renderInline(source)
    if context is None:
        return html
    html = NOTE_HREF.sub(lambda match: _note_href(match, context), html)
    return WIKILINK.sub(lambda match: _frontmatter_link(match, context), html)


NOTE_HREF = re.compile(r'<a href="([^"]*)">')


def _note_href(match: re.Match[str], context: Context) -> str:
    chapter = _note_target(unescape(match[1]), context)
    return f'<a class="internal-link" href="#{chapter}">' if chapter is not None else match[0]


WIKILINK = re.compile(r"\[\[([^\[\]|#]*)(?:#([^\[\]|]*))?(?:\|([^\[\]]*))?\]\]")


def _frontmatter_link(match: re.Match[str], context: Context) -> str:
    """A wikilink in authored text links like a body wikilink: to the chapter whose note record
    has the target's path, or, as Obsidian resolves it, the only path ending in the target, or
    the only note with the target as alias; any other target renders unresolved."""
    target, heading, label = (unescape(group).strip() if group else "" for group in match.groups())
    path = target.removesuffix(".md")
    chapter = context.paths.get(path)
    if chapter is None:
        candidates = [identifier for known, identifier in context.paths.items() if known.endswith(f"/{path}")]
        chapter = candidates[0] if path and len(candidates) == 1 else context.aliases.get(path.casefold())
    if chapter not in context.chapters:
        shown = label or target
        return f'<span class="unresolved" title="{escape(target, quote=True)}">{escape(shown)}</span>'
    return _internal_link(chapter, heading, label, context)


def _frontmatter_html(metadata: dict[str, object], context: Context) -> dict[str, str]:
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
                rendered[name] = ", ".join(_inline("null" if item is None else item, context)
                                           for item in value)
            else:
                for index, item in enumerate(value):
                    add(f"{name}.{index}", item)
        elif name:
            rendered[name] = _inline("null" if value is None else value, context)

    add("", metadata)
    return rendered


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
