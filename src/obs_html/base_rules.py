"""The build's copy of the rules base.js refuses in a Base table beyond base.schema.json.

base.js's ``validate`` and ``project`` are the page's check and stay its owner; this module repeats
the rules among them that the schema cannot hold as plain data and that need no other note's
values, so the build refuses a table the page would refuse (input-model.md, Compact declarative
table presentation). ``test/fixtures/base-rules.json`` is the one list of examples both checks run,
and test_base_rules.py fails on a throw of base.js's check that no rule there names.

Pure: :func:`breaches` takes a definition the schema accepted and yields each rule it breaks, in
the order base.js meets them, as a :class:`Breach`; it reads no rendering state, and the caller
(render.py, ``base_definition_error``) turns the first into its input error. A setting counts as
base.js reads it: a present key counts, ``showEmptyGroups`` only when ``true``.

Exported for the build and for later rules: :data:`UNSUPPORTED_PROPERTY` and
:func:`unsupported_property` (the schema's ``$defs.unsupportedProperty``, which the filter check
reads too), :func:`js_trim`, :data:`RULES` (each rule's key and the base.js function that throws
it), :class:`Breach`, :func:`breaches` and :func:`first_breach`.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from importlib.resources import files

UNSUPPORTED_PROPERTY = re.compile(json.loads(files("obs_html").joinpath("base.schema.json").read_text(
    encoding="utf-8"))["$defs"]["unsupportedProperty"]["pattern"])
"""base.schema.json's ``$defs.unsupportedProperty``: it owns the Bases property names obs-html
cannot read, for base.js and the build alike."""

FILE_PROPERTIES = ("file.name", "file.path", "file.folder", "file.ext")
"""The file properties obs-html reads; every other file property is unsupported (OBS_BASE_FENCES)."""

JS_WHITESPACE = ("\t\n\v\f\r              "
                 "    　﻿")
"""What JavaScript's ``String.prototype.trim`` removes: its WhiteSpace and LineTerminator code points
(ECMAScript, White Space), not Python's ``str.isspace`` set (which adds U+001C to U+001F and U+0085
and lacks U+FEFF)."""

OBS_BASE_FENCES = "obs's spec/design_input/input-model.md, Base fences"
TABLE_DEFINITION = "obs-html's generic-tables.md, Table definition"
GROUPING = "obs-html's generic-tables.md, Hierarchy, grouping, and sorting"
COLUMNS = "obs-html's generic-tables.md, Columns and cells"
PRESENTATION = "obs-html's input-model.md, Compact declarative table presentation"

RULES: dict[str, str] = {
    "unsupported-property": "supportedProperty",
    "group-order-without-group-by": "validate",
    "empty-groups-without-group-order": "validate",
    "column-size-with-equal-sizing": "validate",
    "leading-lines-with-presentation": "validate",
    "view-names": "validate",
    "expanded-column-not-ordered": "project",
}
"""Each rule by its key, with the base.js function that throws it; base-rules.json names the same."""

LEADING_LINES_CONFLICTS = ("icon", "icons", "reference", "editable")
"""The property options ``leadingLines`` cannot be combined with, in the order base.js names them."""


@dataclass(frozen=True)
class Breach:
    """One rule a definition breaks: its key in :data:`RULES`, the field parts of the value that
    breaks it (as errors.field_path writes them, without the fence's ``base.``), the problem and
    the remedy, which names the spec section that owns the rule."""

    rule: str
    field: tuple[str | int, ...]
    problem: str
    remedy: str


def js_trim(text: str) -> str:
    """``text`` as JavaScript's ``trim`` leaves it."""
    return text.strip(JS_WHITESPACE)


def unsupported_property(name: str) -> bool:
    """Whether ``name`` is a Bases property obs-html cannot read (``$defs.unsupportedProperty``)."""
    return UNSUPPORTED_PROPERTY.search(name) is not None


def _property(name: object, field: tuple[str | int, ...]) -> Iterator[Breach]:
    if isinstance(name, str) and unsupported_property(name):
        yield Breach("unsupported-property", field, f"is {json.dumps(name, ensure_ascii=False)}, a Bases property "
                     "obs-html cannot read", f"Use a frontmatter property or one of "
                     f"{', '.join(FILE_PROPERTIES)}; see {OBS_BASE_FENCES}")


def _mapping(value: object) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _view(view: Mapping, index: int) -> Iterator[Breach]:
    """A view's rules, in the order base.js's ``validate`` checks them."""
    at = ("views", index)
    for position, name in enumerate(view.get("order") or []):
        yield from _property(name, (*at, "order", position))
    options = _mapping(view.get("obsHtml"))
    if "groupOrder" in options and "groupBy" not in view:
        yield Breach("group-order-without-group-by", (*at, "obsHtml", "groupOrder"), "is set, but the view has no "
                     "groupBy", f"Add groupBy or remove obsHtml.groupOrder; see {GROUPING}")
    if options.get("showEmptyGroups") is True and "groupOrder" not in options:
        yield Breach("empty-groups-without-group-order", (*at, "obsHtml", "showEmptyGroups"), "is true, but the "
                     "view has no obsHtml.groupOrder", f"Add obsHtml.groupOrder or remove "
                     f"obsHtml.showEmptyGroups; see {GROUPING}")
    for key in _mapping(view.get("columnSize")):
        yield from _property(key, (*at, "columnSize", key))
    if "columnSize" in view and options.get("columnSizing") == "equal":
        yield Breach("column-size-with-equal-sizing", (*at, "columnSize"), "is set, but the view sets "
                     "obsHtml.columnSizing: equal", f"Remove columnSize or obsHtml.columnSizing; see {COLUMNS}")
    for key in ("groupBy", "sort"):
        directives = view.get(key) or []
        listed = isinstance(directives, list)
        for position, directive in enumerate(directives if listed else [directives]):
            place = (*at, key, position) if listed else (*at, key)
            yield from _property(_mapping(directive).get("property"), (*place, "property"))


def _view_names(views: list) -> Iterator[Breach]:
    """Several views need unique nonempty names once trimmed as JavaScript trims; the first view
    whose name is missing, blank or repeats an earlier one breaks the rule."""
    if len(views) < 2:
        return
    seen: dict[str, int] = {}
    for index, view in enumerate(views):
        authored = _mapping(view).get("name")
        name = js_trim(str(authored if authored is not None else ""))
        problem = ("is missing" if authored is None else "is blank" if not name
                   else f"repeats the name of views[{seen[name]}]" if name in seen else None)
        if problem is not None:
            yield Breach("view-names", ("views", index, "name"), f"{problem}, but each view of a Base of several "
                         "views needs a unique nonempty name", f"Give each view its own name; see {TABLE_DEFINITION}")
            return
        seen[name] = index


def breaches(definition: Mapping) -> Iterator[Breach]:
    """Each rule ``definition``, a Base definition base.schema.json accepted, breaks, in the order
    base.js's ``validate`` and then ``project`` meet them. Filters are the filter check's
    (render.py, ``_unsupported_filter``), icon names the asset catalogue's."""
    properties = _mapping(definition.get("properties"))
    for key in properties:
        yield from _property(key, ("properties", key))
    views = [view for view in definition.get("views") or [] if isinstance(view, Mapping)]
    for index, view in enumerate(views):
        yield from _view(view, index)
    for key, declaration in properties.items():
        options = _mapping(_mapping(declaration).get("obsHtml"))
        if "leadingLines" not in options:
            continue
        for position, name in enumerate(options["leadingLines"] or []):
            yield from _property(name, ("properties", key, "obsHtml", "leadingLines", position))
        conflict = next((option for option in LEADING_LINES_CONFLICTS if option in options), None)
        if conflict is not None:
            yield Breach("leading-lines-with-presentation", ("properties", key, "obsHtml", conflict), "is set "
                         "together with obsHtml.leadingLines", f"Remove one of the two; see {PRESENTATION}")
    yield from _view_names(views)
    for field in _mapping(_mapping(definition.get("obsHtml")).get("expandProperties")):
        if not any(field in (view.get("order") or []) for view in views):
            yield Breach("expanded-column-not-ordered", ("obsHtml", "expandProperties", field), "expands a "
                         "property that no view's order lists", f"Add {field} to a view's order or remove its "
                         f"expansion; see {OBS_BASE_FENCES}")


def first_breach(definition: Mapping) -> Breach | None:
    """The first rule ``definition`` breaks, as base.js would refuse it first, or None."""
    return next(breaches(definition), None)
