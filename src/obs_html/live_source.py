"""A Base's live source, ``obsHtml.liveSource``: the build's shape checks of its declaration.

Reader: whoever changes what a Base may declare about where newer values of its rows are read
(generic-tables.md, Current data). The declaration's keys are owned by live-source.schema.json;
this module adds the refusals a schema cannot state. The adapter imports no core module, so these
are shape checks only: whether the declaration fits the rows is checked in the page
(live-data.js, check).
"""
from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Iterator
from urllib.parse import parse_qsl, urlsplit

from jsonschema import Draft202012Validator

from .errors import InputError, field_path, schema_error

SCHEMA = json.loads(files("obs_html").joinpath("live-source.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)
OWNER = "obs-html's live-source.schema.json and its generic-tables.md, Current data"
"""The owner every refusal names."""

PLAIN_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_ .-]{0,63}$")
PROTOTYPE_NAMES = frozenset({"__proto__", "constructor", "prototype"})
RESERVED_NAMES = frozenset({"title", "slug", "text", "content", "body", "depth", "chapter", "sourcePath",
                            "recordType", "frontmatter", "mark", "obs"})
RESERVED_PREFIXES = ("frontmatter.", "file.", "mark.", "obs.")
ADAPTER_NAMESPACE = re.compile(r"^obs[A-Z]")
"""A name the runtime or the core reserves: the runtime's own row fields, the core's file and mark
fields, and the core's and the adapters' namespaces (obs's input model, Core and adapter namespaces)."""
TEMPLATE = re.compile(r"\{([^{}]*)\}")
SECRET_NAME = re.compile(r"token|key|secret|password|auth|sig|code", re.IGNORECASE)
PATH_STEPS = 8


def _steps(path: str) -> int:
    """A path's steps: each key and each ``[]`` is one."""
    return sum(1 + part.endswith("[]") for part in path.split("."))


def _field(name: str) -> str:
    """A Base property key as the field it names: without ``note.`` or ``note["..."]``."""
    return name[6:-2] if name.startswith('note["') and name.endswith('"]') else name.removeprefix("note.")


def _target_problem(name: str) -> str | None:
    if not PLAIN_NAME.fullmatch(name):
        return f"is {name!r}, which is not a plain name ({PLAIN_NAME.pattern})"
    if name in PROTOTYPE_NAMES:
        return f"is {name!r}, a name a page's objects reserve"
    if name in RESERVED_NAMES or name.startswith(RESERVED_PREFIXES) or ADAPTER_NAMESPACE.match(name):
        return f"is {name!r}, a name the reader or the obs core reserves"
    return None


def _conditions(declaration: dict) -> Iterator[tuple[list[object], dict]]:
    """Each condition of the declaration with its place."""
    for name in ("exclude", "accept"):
        for index, condition in enumerate(declaration.get(name) or []):
            yield [name, index], condition
    for target, cases in (declaration.get("derive") or {}).items():
        for index, case in enumerate(cases):
            for position, condition in enumerate(case.get("where") or []):
                yield ["derive", target, index, "where", position], condition


def _paths(declaration: dict) -> Iterator[tuple[list[object], str]]:
    """Each path of the declaration with its place."""
    for target, spec in declaration["fields"].items():
        yield (["fields", target], spec) if isinstance(spec, str) else (["fields", target, "path"], spec["path"])
    for target, cases in (declaration.get("derive") or {}).items():
        for index, case in enumerate(cases):
            if "path" in case:
                yield ["derive", target, index, "path"], case["path"]
    for target, path in (declaration.get("fillNew") or {}).items():
        yield ["fillNew", target], path
    if "bodyPath" in declaration:
        yield ["bodyPath"], declaration["bodyPath"]
    for index, route in enumerate(declaration["changes"]):
        if "rows" in route:
            yield ["changes", index, "rows"], route["rows"]
        if isinstance(route.get("next"), dict):
            for name in ("cursor", "more"):
                yield ["changes", index, "next", name], route["next"][name]
        for target, path in (route.get("fields") or {}).items():
            yield ["changes", index, "fields", target], path


def _templates(declaration: dict) -> Iterator[tuple[list[object], str]]:
    """Each template of a route with its place: a request's url and its input's text values."""
    for index, route in enumerate(declaration["changes"]):
        for position, request in enumerate(route["requests"]):
            if "url" in request:
                yield ["changes", index, "requests", position, "url"], request["url"]
            for name, value in (request.get("input") or {}).items():
                for item in value if isinstance(value, list) else [value]:
                    if isinstance(item, str):
                        yield ["changes", index, "requests", position, "input", name], item


def _template_names(template: str) -> list[str] | None:
    """The names a template fills, or None where it holds braces that are no ``{name}``."""
    if "{" in TEMPLATE.sub("", template) or "}" in TEMPLATE.sub("", template):
        return None
    return TEMPLATE.findall(template)


def live_source_error(definition: dict, source: str, views: list[int] | None = None) -> InputError | None:
    """The input error of the first refusal of the Base ``definition``'s ``obsHtml.liveSource``, or
    None (generic-tables.md, Current data, Build refusals). ``source`` names the note of a fence,
    whose fields sit under ``base.``, or the .base file; ``views`` maps a one-view table's views to
    their index in that file."""
    def view_index(index: int) -> int:
        return index if views is None else views[index]

    prefix = "obsHtml.liveSource" if source.endswith(".base") else "base.obsHtml.liveSource"
    declaration = (definition.get("obsHtml") or {})["liveSource"]

    def refused(parts: list[object], problem: str, remedy: str) -> InputError:
        return InputError(source, field_path(parts, prefix), problem, f"{remedy}; see {OWNER}")

    error = schema_error(list(VALIDATOR.iter_errors(declaration)), source, OWNER, prefix=prefix)
    if error is not None:
        return error
    for target, cases in (declaration.get("derive") or {}).items():
        default = next((index for index, case in enumerate(cases) if "where" not in case), None)
        if default is not None and default != len(cases) - 1:
            return refused(["derive", target, default], "has no where but is not the last case",
                           "Move the default case to the end")

    for index, view in enumerate(definition.get("views") or []):
        core = view.get("obs") or {}
        if "members" in core:
            return refused([], f"is declared on a Base whose views[{view_index(index)}] lists obs.members, whose rows "
                           "follow no note path", "Remove obs.members or the live source")
        if core.get("records", "note") != "note":
            return refused([], f"is declared on a Base whose views[{view_index(index)}] selects {core['records']} "
                           "records; a live source updates note rows only", "Select note records")
    records = (definition.get("obs") or {}).get("records", "note")
    if records != "note":
        return refused([], f"is declared on a Base that selects {records} records; a live source updates "
                       "note rows only", "Select note records")

    routes = declaration["changes"]
    targets: list[tuple[list[object], str]] = [
        *((["fields", name], name) for name in declaration["fields"]),
        *((["derive", name], name) for name in declaration.get("derive") or {}),
        *((["fillNew", name], name) for name in declaration.get("fillNew") or {}),
        *((["changes", index, "requests", position, "set", name], name)
          for index, route in enumerate(routes) for position, request in enumerate(route["requests"])
          for name in request["set"])]
    for parts, name in targets:
        problem = _target_problem(name)
        if problem is not None:
            return refused(parts, problem, "Map the value to a property name of your own")

    protected: dict[str, str] = {}
    for key, prop in (definition.get("properties") or {}).items():
        options = prop.get("obsHtml") or {}
        if options.get("editable") is True:
            protected.setdefault(_field(key), f"properties[{key!r}] declares it editable")
        reference = options.get("reference")
        if isinstance(reference, dict):
            protected.setdefault(_field(key), f"properties[{key!r}] declares it a reference")
            for format_spec in (reference.get("metadataFormats") or {}).values():
                if isinstance(format_spec, dict) and "source" in format_spec:
                    protected.setdefault(_field(format_spec["source"]),
                                         f"properties[{key!r}] reads it as a metadataFormats source")
            if "linkProperty" in reference:
                protected.setdefault(_field(reference["linkProperty"]), f"properties[{key!r}] links through it")
        if "linkProperty" in options:
            protected.setdefault(_field(options["linkProperty"]), f"properties[{key!r}] links through it")
    for parts, name in targets:
        if name in protected:
            return refused(parts, f"is {name!r}, which {protected[name]}; a live value would overwrite "
                           "what the Base presents or edits as its own", "Map the value to another property")

    mapped = {name for parts, name in targets if parts[0] in {"fields", "changes"}}
    for index, name in enumerate(declaration["key"]):
        if name not in mapped:
            return refused(["key", index], f"is {name!r}, which no fields or set target maps", f"Map {name}")
    for parts, condition in _conditions(declaration):
        if condition["field"] not in mapped:
            return refused([*parts, "field"], f"is {condition['field']!r}, which no fields or set target maps",
                           f"Map {condition['field']} or name a mapped field")

    names = _template_names(declaration["notePath"])
    outside = None if names is None else next((name for name in names if name not in declaration["key"]), None)
    if names is None or not names or outside is not None:
        return refused(["notePath"], f"names {outside!r}, which is not a key property" if outside is not None
                       else "is no template of {name} over the key properties alone",
                       "Write the note path as a template over the key properties alone")
    for parts, template in _templates(declaration):
        names = _template_names(template)
        unknown = None if names is None else next(
            (name for name in names if name not in mapped and name != "since"), None)
        if names is None or unknown is not None:
            return refused(parts, "holds braces that are no {name}" if names is None else
                           f"names {unknown!r}, which is neither a key property, a mapped field nor since",
                           "Name a key property, a mapped field or since")

    for parts, path in _paths(declaration):
        if _steps(path) > PATH_STEPS:
            return refused(parts, f"has {_steps(path)} steps, more than {PATH_STEPS}", "Shorten the path")

    for index, route in enumerate(routes):
        if isinstance(route.get("next"), dict) and SECRET_NAME.search(route["next"]["input"]):
            return refused(["changes", index, "next", "input"], f"is {route['next']['input']!r}, which reads "
                           "as a credential; a live source carries none", "Name a cursor input")
        for position, request in enumerate(route["requests"]):
            place = ["changes", index, "requests", position]
            for name in request.get("input") or {}:
                if SECRET_NAME.search(name):
                    return refused([*place, "input", name], "reads as a credential; a live source carries none",
                                   "Remove the input")
            if "url" in request:
                problem = _url_problem(request["url"])
                if problem is not None:
                    return refused([*place, "url"], problem, "Write an https URL without credentials")

    for index, view in enumerate(definition.get("views") or []):
        group = view.get("groupBy")
        order = (view.get("obsHtml") or {}).get("groupOrder")
        if not isinstance(group, dict) or not isinstance(order, list):
            continue
        target = _field(str(group.get("property", "")))
        cases = (declaration.get("derive") or {}).get(target)
        if cases is None or any(case.get("keep") for case in cases):
            continue
        produced = {str(case["value"]) for case in cases if "value" in case}
        missing = next((value for value in order if value not in produced), None)
        if missing is not None:
            return refused(["derive", target], f"produces no {missing!r}, which views[{view_index(index)}].obsHtml.groupOrder "
                           "lists", f"Add a case whose value is {missing}, or a keep case")
    return None


def _url_problem(url: str) -> str | None:
    """Why a request's url is refused, or None: it is https, carries no user name or password and
    no query name that reads as a credential."""
    parts = urlsplit(TEMPLATE.sub("x", url))
    if parts.scheme != "https" or not parts.hostname:
        return "is no https URL"
    if parts.username is not None or parts.password is not None:
        return "carries a user name or password; a live source carries no credentials"
    secret = next((name for name, _ in parse_qsl(parts.query, keep_blank_values=True) if SECRET_NAME.search(name)),
                  None)
    if secret is not None:
        return f"has the query name {secret!r}, which reads as a credential; a live source carries none"
    return None


def _declarations(value: object) -> Iterator[dict]:
    """Every live-source declaration a Document's Bases carry, in document order."""
    if isinstance(value, dict):
        options = value.get("obsHtml")
        if isinstance(options, dict) and isinstance(options.get("liveSource"), dict):
            yield options["liveSource"]
        for item in value.values():
            yield from _declarations(item)
    elif isinstance(value, list):
        for item in value:
            yield from _declarations(item)


def live_publish(document: dict) -> dict | None:
    """The capability declaration a page with a connector route is published with in Claude's
    artifact viewer (live-data.md, Reading in Claude's artifact viewer): each route's server once,
    with every tool its routes call, or None where no Base reads through a connector."""
    servers: dict[str, list[str]] = {}
    for declaration in _declarations(document):
        for route in declaration.get("changes") or []:
            if isinstance(route, dict) and route.get("provider") == "connector":
                tools = servers.setdefault(route["server"], [])
                if route["tool"] not in tools:
                    tools.append(route["tool"])
    return {"mcp": {"servers": [{"server": server, "tools": tools} for server, tools in servers.items()]}} if servers else None
