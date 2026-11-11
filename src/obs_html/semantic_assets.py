"""One typed semantic presentation index; DOM and CSS are projections, not registries."""
from __future__ import annotations

import base64
import copy
import functools
import hashlib
import json
import re
import stat
from html import escape
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree

from jsonschema import Draft202012Validator

from obs_html.errors import InputError, schema_error


ROOT = Path(str(files("obs_html")))
SCHEMA = json.loads((ROOT / "assets.schema.json").read_text(encoding="utf-8"))
NAME_VALIDATOR = Draft202012Validator(SCHEMA["$defs"]["name"])
NAME = SCHEMA["$defs"]["name"]["pattern"].removeprefix("^").removesuffix(r"(?![\s\S])")
PLACEHOLDER = re.compile(
    rf'<span class="resource-icon" data-icon="({NAME})" aria-hidden="true"></span>'
)


REFERENCE = "obs-html's assets.schema.json and obs semantic-assets"
REMEDY = f"Correct the asset in its index; see {REFERENCE}"


def asset_field(name: str) -> str:
    """A semantic ID as its field path in an index: ``mark.risk`` is ``assets.mark.children.risk``."""
    return "assets." + ".children.".join(name.split("."))


def markup(name: str) -> str:
    if not NAME_VALIDATOR.is_valid(name):
        raise InputError("obs-html (src/obs_html/semantic_assets.py)", "name", f"is {name!r}, not a semantic ID",
                         f"Name an icon by its semantic ID; see {REFERENCE}")
    return f'<span class="resource-icon" data-icon="{name}" aria-hidden="true"></span>'


def _local_file(name: str, owner: Path, boundary: Path, field: str) -> Path:
    """The icon file the index ``owner`` names at ``field``, inside ``boundary``."""
    relative = Path(name)
    if relative.is_absolute() or relative.drive or ":" in name or "\\" in name:
        raise InputError(owner, field, f"is {name!r}, not a local relative path", "Name a file beside the index")
    candidate = owner.parent / relative
    for part in (candidate, *candidate.parents):
        if not part.is_relative_to(boundary):
            continue
        try:
            attributes = getattr(part.lstat(), "st_file_attributes", 0)
        except FileNotFoundError:
            continue
        if part.is_symlink() or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise InputError(owner, field, f"is {name!r}, which passes a symbolic link",
                             "Name the file itself, not a link")
    path = candidate.resolve()
    if not path.is_relative_to(boundary.resolve()):
        raise InputError(owner, field, f"is {name!r}, outside the folder of the index", "Name a file in that folder")
    if not path.is_file():
        raise InputError(owner, field, f"is {name!r}, which does not exist", "Add the file or name an existing one")
    return path


def _image(path: Path, owner: Path, field: str) -> tuple[str, bytes]:
    """The media type and bytes of an icon file the index (``owner``) names at ``field``."""
    def refused(problem: str) -> InputError:
        return InputError(owner, field, f"names {path.name}, {problem}",
                          "Use a static SVG of shapes, or a PNG, JPEG, GIF or WebP image")

    raw = path.read_bytes()
    mime = {
        ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    }.get(path.suffix.lower())
    valid = False
    if mime == "image/svg+xml":
        if b"<!" in raw:
            raise refused("an SVG with a declaration (<!...>)")
        try:
            root = ElementTree.fromstring(raw)
        except ElementTree.ParseError as error:
            raise refused(f"which is no well-formed SVG ({error})") from error
        tags = {"svg", "g", "path", "polygon", "polyline", "rect", "circle", "ellipse", "line"}
        attributes = {
            "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy",
            "r", "rx", "ry", "d", "points", "fill", "fill-rule", "stroke", "stroke-width",
            "stroke-linecap", "stroke-linejoin", "opacity", "transform", "version",
        }
        for node in root.iter():
            if node.tag.removeprefix("{http://www.w3.org/2000/svg}") not in tags:
                raise refused(f"an SVG with the element {node.tag!r}, which an icon may not use")
            if node.text and node.text.strip():
                raise refused("an SVG with text, but an icon holds only static geometry")
            for key, value in node.attrib.items():
                if key not in attributes or re.search(r"url\s*\(|[<>]", value, re.I):
                    raise refused(f"an SVG with the attribute {key!r} or its value, which an icon may not use")
        valid = root.tag == "{http://www.w3.org/2000/svg}svg"
    elif mime == "image/png":
        valid = raw.startswith(b"\x89PNG\r\n\x1a\n")
    elif mime == "image/jpeg":
        valid = raw.startswith(b"\xff\xd8\xff")
    elif mime == "image/gif":
        valid = raw.startswith((b"GIF87a", b"GIF89a"))
    elif mime == "image/webp":
        valid = raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"
    if not valid:
        raise refused("which is no image of its suffix's type")
    return mime, raw


def _unique(pairs, path: Path):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(path, "assets", f"repeats the key {key!r} in one object", "Keep one definition per key")
        result[key] = value
    return result


def _merge(base, overlay):
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return overlay
    merged = dict(base)
    for key, value in overlay.items():
        merged[key] = _merge(base.get(key), value) if key != "value" else value
    return merged


def color_variable(name: str) -> str:
    return "--asset-" + name.encode("utf-8").hex()


def _read_index(path: Path) -> dict:
    """An index file as JSON, refusing a key it repeats."""
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=lambda pairs: _unique(pairs, path))
    except InputError:
        raise
    except (ValueError, UnicodeError, OSError) as error:
        raise InputError(path, "", f"is no UTF-8 JSON file ({error})", f"Write the index as JSON; see {REFERENCE}") \
            from error


def _checked_index(path: Path) -> dict:
    """An index file as JSON, refusing one its schema refuses."""
    data = _read_index(path)
    error = schema_error(list(Draft202012Validator(SCHEMA).iter_errors(data)), path, REFERENCE)
    if error is not None:
        raise error
    return data


@functools.cache
def _packaged_index() -> dict:
    """The packaged index, read and checked once per process: it is package data, which nothing
    changes while the process runs; a style module's index is read and checked at every render."""
    return _checked_index(ROOT / "assets.json")


class SemanticAssets:
    def __init__(self, selected: Path | None = None):
        """The packaged index, overlaid by a style module's assets.json when one is selected."""
        indexes = [(ROOT / "assets.json", ROOT)]
        if selected is not None:
            path = selected.resolve(strict=True)
            indexes.append((path, path.parent))
        self.nodes, self.origins, self.value_origins = {}, {}, {}
        self.resources, self.embedded_assets = {}, {}
        for index, (path, boundary) in enumerate(indexes):
            data = copy.deepcopy(_packaged_index()) if index == 0 else _checked_index(path)
            def overlay(nodes, prefix=""):
                for segment, node in nodes.items():
                    name = f"{prefix}.{segment}" if prefix else segment
                    if not NAME_VALIDATOR.is_valid(name):
                        raise InputError(path, asset_field(name), f"has the key {segment!r}, which makes "
                                         f"{name!r} no semantic ID", f"Rename it; see {REFERENCE}")
                    previous = self.nodes.get(name, {})
                    if "type" in node and "type" in previous and node["type"] != previous["type"]:
                        raise InputError(path, f"{asset_field(name)}.type", f"is {node['type']!r}, but the "
                                         f"index it overlays declares {previous['type']!r}",
                                         "Keep the overlaid type or name another semantic ID")
                    local = {key: value for key, value in node.items() if key != "children"}
                    self.nodes[name] = _merge(previous, local)
                    self.origins[name] = path
                    if "value" in node:
                        self.value_origins[name] = (path, boundary)
                    if "children" in node:
                        self.nodes[name]["group"] = True
                        overlay(node["children"], name)
            overlay(data["assets"])
        for name, node in self.nodes.items():
            if node.get("group"):
                if "ref" in node or "value" in node:
                    self.error(name, "group/template cannot contain a ref or concrete value")
                kind = None
                for ancestor in self._lineage(name):
                    explicit = self.nodes[ancestor].get("type")
                    if kind and explicit and explicit != kind:
                        self.error(name, f"incompatible inherited types {kind}/{explicit}", [ancestor])
                    kind = explicit or kind
                fields = {key: node[key] for key in ("icon", "color") if key in node}
                if kind in {"icon", "color"} and (fields or "states" in node or "defaultState" in node):
                    self.error(name, f"{kind} cannot contain appearance fields")
                for state, values in {"base": fields, **node.get("states", {})}.items():
                    for field, reference in values.items():
                        target = self._compile(reference["ref"], [name, f"state={state}"])
                        if target["type"] != field:
                            self.error(name, f"state={state}: {field} reference type mismatch")
            else:
                self._compile(name, [])

    def error(self, name, message, chain=()):
        """Refuse semantic asset ``name``, reached through ``chain``, naming its index and field."""
        known = name if name in self.origins else next((item for item in reversed(chain) if item in self.origins),
                                                       None)
        location = self.origins[known] if known else "obs-html's semantic assets (the packaged index and the style's)"
        route = " -> ".join([*chain, name])
        raise InputError(location, asset_field(known) if known else "assets",
                         f"{message} (semantic asset {name}, reached as {route})", REMEDY)

    def _lineage(self, name):
        parts = name.split(".")
        return [".".join(parts[:index]) for index in range(1, len(parts) + 1)]

    def _compile(self, name, chain):
        if name in chain:
            self.error(name, "reference cycle", chain)
        if name in self.resources:
            return self.resources[name]
        node = self.nodes.get(name)
        if node is None:
            self.error(name, "unknown reference", chain)
        if node.get("group"):
            self.error(name, "group/template is not a concrete asset", chain)
        kind, base, states, default = None, {}, {}, None
        for ancestor in self._lineage(name):
            inherited = self.nodes[ancestor]
            explicit = inherited.get("type")
            if explicit and kind and explicit != kind:
                self.error(name, f"incompatible inherited types {kind}/{explicit}", [ancestor])
            kind = explicit or kind
            base.update({field: inherited[field] for field in ("icon", "color") if field in inherited})
            states = _merge(states, inherited.get("states", {}))
            default = inherited.get("defaultState", default)
        route = [*chain, name]
        if "ref" in node:
            if set(node) - {"ref", "type"}:
                self.error(name, "an alias cannot add fields or children", chain)
            target = self._compile(node["ref"], route)
            if kind and kind != target["type"]:
                self.error(name, f"alias type mismatch: expected {kind}, got {target['type']}", route)
            result = {"type": target["type"], "ref": node["ref"]}
        elif kind in {"icon", "color"}:
            if base or states or default is not None:
                self.error(name, f"{kind} cannot contain appearance fields", chain)
            if "value" not in node:
                self.error(name, f"missing {kind} value", chain)
            value = node["value"]
            if kind == "color":
                if isinstance(value, dict) and "ref" in value:
                    target = self._compile(value["ref"], route)
                    if target["type"] != "color":
                        self.error(name, "color reference type mismatch", route)
                    result = {"type": "color", "ref": value["ref"]}
                elif isinstance(value, str) or isinstance(value, dict) and set(value) == {"light", "dark"}:
                    result = {"type": "color", "value": value}
                else:
                    self.error(name, "invalid color value", chain)
            else:
                if not isinstance(value, dict) or set(value) not in ({"glyph"}, {"asset"}, {"asset", "monochrome"}):
                    self.error(name, "icon requires one glyph or local image", chain)
                if "glyph" in value:
                    glyph = value["glyph"]
                    if any(ord(character) < 32 or 0xD800 <= ord(character) <= 0xDFFF for character in glyph):
                        self.error(name, "invalid UTF-8 glyph", chain)
                    resolved = value
                else:
                    path, boundary = self.value_origins[name]
                    field = f"{asset_field(name)}.value.asset"
                    image = _local_file(value["asset"], path, boundary, field)
                    try:
                        mime, raw = _image(image, path, field)
                    except OSError as error:
                        raise InputError(path, field, f"names {image.name}, which cannot be read ({error})",
                                         "Make the file readable") from error
                    if value.get("monochrome") and mime != "image/svg+xml":
                        raise InputError(path, f"{asset_field(name)}.value.monochrome", "is true, but the "
                                         "icon is no SVG", "Use an SVG or drop monochrome")
                    uri = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
                    key = hashlib.sha256(uri.encode("ascii")).hexdigest()
                    self.embedded_assets[key] = uri
                    resolved = {"asset": f"obs-asset:{key}"}
                    if value.get("monochrome"):
                        resolved["monochrome"] = True
                result = {"type": "icon", "value": resolved}
        elif kind == "appearance":
            if "value" in node:
                self.error(name, "appearance fields require typed references, not a value", chain)
            def fields(values, state):
                result = {}
                for field, reference in values.items():
                    target = self._compile(reference["ref"], [*route, f"state={state}"])
                    if target["type"] != field:
                        self.error(name, f"state={state}: {field} reference type mismatch", route)
                    result[field] = reference["ref"]
                return result
            result = {"type": "appearance", **fields(base, "base")}
            if states:
                result["states"] = {state: fields(values, state) for state, values in states.items()}
                for state, values in result["states"].items():
                    if not (set(base) | set(values)):
                        self.error(name, f"state={state}: incomplete concrete appearance", route)
                if default is not None:
                    if default not in states:
                        self.error(name, f"unknown default state {default}", route)
                    result["defaultState"] = default
            elif not base:
                self.error(name, "incomplete concrete appearance", route)
            elif default is not None:
                self.error(name, f"unknown default state {default}", route)
        else:
            self.error(name, "missing or unsupported concrete type", chain)
        self.resources[name] = result
        return result

    def entry(self, name):
        if name not in self.resources:
            self.error(name, "unknown reference")
        entry = self.resources[name]
        while "ref" in entry:
            entry = self.resources[entry["ref"]]
        return entry

    def icon(self, name, state=None):
        entry = self.entry(name)
        if entry["type"] == "icon":
            return entry["value"]
        if entry["type"] != "appearance":
            self.error(name, "expected icon or icon-bearing appearance")
        fields = {key: entry[key] for key in ("icon", "color") if key in entry}
        if entry.get("states"):
            chosen = state if state is not None else entry.get("defaultState")
            if chosen not in entry["states"]:
                self.error(name, f"unknown or missing state={chosen}")
            fields.update(entry["states"][chosen])
        if "icon" not in fields:
            self.error(name, f"state={state}: incomplete icon appearance")
        return self.entry(fields["icon"])["value"] | (
            {"color": fields["color"]} if "color" in fields else {})

    def css(self):
        declarations = []
        for name, entry in self.resources.items():
            if entry["type"] != "color":
                continue
            if "ref" in entry:
                value = f"var({color_variable(entry['ref'])})"
            else:
                literal = entry["value"]
                value = (f"light-dark({literal['light']},{literal['dark']})"
                         if isinstance(literal, dict) else literal)
            declarations.append(f"{color_variable(name)}:{value};")
            if name.startswith("color."):
                declarations.append(f"--color-{name[6:].replace('.', '-')}:" +
                                    f"var({color_variable(name)});")
        return ":root{" + "".join(declarations) + "}"

    def resolve_markup(self, text):
        def replace(match):
            entry = self.icon(match[1])
            body = escape(entry["glyph"]) if "glyph" in entry else (
                f'<img data-icon-asset="{escape(entry["asset"], quote=True)}" alt="">')
            opening = match[0]
            if entry.get("monochrome"):
                opening = opening.replace('class="resource-icon"', 'class="resource-icon resource-icon--monochrome"')
            if "color" in entry:
                opening = opening.replace(' aria-hidden=', f' style="color:var({color_variable(entry["color"])})" aria-hidden=')
            return opening.replace("</span>", f"{body}</span>")
        return PLACEHOLDER.sub(replace, text)

    def normalize_definition(self, definition, source):
        """Check each property's obsHtml icon against this catalogue; ``source`` names the note or
        .base file the Base definition comes from."""
        for property_name, declaration in definition.get("properties", {}).items():
            options = declaration.get("obsHtml", {})
            single = "icon" in options
            for index, icon in enumerate([options["icon"]] if single else options.get("icons", [])):
                try:
                    for state in ("active", "inactive"):
                        self.icon(icon["name"], state)
                except InputError as error:
                    field = f"properties.{property_name}.obsHtml.{'icon' if single else f'icons[{index}]'}.name"
                    raise InputError(source, field, f"names {icon['name']!r}, which is no icon of the style's "
                                     "semantic assets", "Name a packaged icon or one the style module's "
                                     "assets.json defines") from error
                if "linkProperty" in icon:
                    icon.setdefault("download", icon["name"] == "snapshot")
