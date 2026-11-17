"""Local themes: the build machine's own themes and its start theme, from obs-html's local folder.

Reader: whoever changes where a build finds its local themes, what one may hold, or how a page
carries them. spec/configuration.md, "Local themes", owns the behaviour; spec/artifact-ui.md,
Styling, what a theme is in the page.

``local_style_choice(environ)`` is the one door to the folder: ``read_local`` lists it, and
``choose``, which reads no file, checks what was listed and returns the ``StyleChoice``, or None
where there is no theme. ``render()`` takes the choice and reads no folder itself. Every refusal
names its file from the local folder (``obs-html local folder: themes/<name>/assets.json``),
never an absolute path, so no message names where the folder is.
"""
from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator

from obs_html.errors import InputError, schema_error
from obs_html.semantic_assets import SCHEMA as ASSETS_SCHEMA, asset_field, color_variable

VARIABLE = "OBS_HTML_LOCAL_FOLDER"
"""Names obs-html's local folder instead of the one in the user's configuration folder."""
SOURCE = "obs-html local folder"
OWNER = "obs-html spec/configuration.md (Local themes)"
DEFAULT = "default"
"""The theme Default: the build's style module, with no local layer over it."""
ASSETS = "assets.json"
LOCAL = "local.json"
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
LOCAL_SCHEMA = json.loads(files("obs_html").joinpath("local.schema.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Theme:
    """One local theme: its name and, for each colour it sets, the semantic ID and its light and dark values."""
    name: str
    colors: tuple[tuple[str, str, str], ...] = ()

    def css(self) -> str:
        """Its colours, scoped to a root that names it, with the specificity of the semantic asset styles' ``:root``."""
        declarations = "".join(f"{color_variable(name)}:light-dark({light},{dark});"
                               for name, light, dark in self.colors)
        return f':root:where([data-style="{self.name}"]){{{declarations}}}'


@dataclass(frozen=True)
class StyleChoice:
    """The machine's themes, sorted by name (``extras``), and the one every opening starts in."""
    extras: tuple[Theme, ...]
    start: str = DEFAULT

    @property
    def names(self) -> list[str]:
        """Every theme a page carries, Default first: its ``reading.styles``."""
        return [DEFAULT, *(theme.name for theme in self.extras)]

    def css(self) -> str:
        """The page's ``style-choice-styles``: each theme's colour rule, in name order."""
        return "".join(theme.css() for theme in self.extras)


@dataclass(frozen=True)
class ThemeFolder:
    """A folder of ``themes`` as listed: its name, its entries but dot-named ones, and its assets.json's text."""
    name: str
    entries: tuple[str, ...] = ()
    assets: str | None = None


def local_folder(environ: Mapping[str, str]) -> Path:
    """obs-html's local folder: ``OBS_HTML_LOCAL_FOLDER`` where set and not empty, else ``obs-html`` in
    the user's configuration folder."""
    if environ.get(VARIABLE):
        return Path(environ[VARIABLE])
    if sys.platform == "win32":
        base = Path(environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "obs-html"


def local_style_choice(environ: Mapping[str, str]) -> StyleChoice | None:
    """The themes and start theme of the local folder ``environ`` names, or None without a theme."""
    return choose(*read_local(local_folder(environ)))


def read_local(folder: Path) -> tuple[tuple[ThemeFolder, ...], str | None]:
    """The theme folders of ``folder``'s ``themes``, by name, and the text of its local.json, or None
    without it. Files and dot-named entries of ``themes`` are no theme."""
    try:
        themes = folder / "themes"
        listed = []
        if themes.is_dir():
            for entry in sorted(themes.iterdir(), key=lambda path: path.name):
                if entry.name.startswith(".") or not entry.is_dir():
                    continue
                inside = sorted(item.name for item in entry.iterdir() if not item.name.startswith("."))
                assets = entry / ASSETS
                if assets.exists() and not assets.is_file():
                    raise InputError(f"{SOURCE}: themes/{entry.name}", ASSETS, "is no file",
                                     f"Make {ASSETS} a file of the theme's colours; see {OWNER}")
                listed.append(ThemeFolder(entry.name, tuple(inside), _text(assets, f"themes/{entry.name}/{ASSETS}")))
        local = folder / LOCAL
        if local.exists() and not local.is_file():
            raise InputError(f"{SOURCE}: {LOCAL}", "", "is no file", f"Make {LOCAL} a file; see {OWNER}")
        return tuple(listed), _text(local, LOCAL)
    except OSError as error:  # Its message would name the folder; the reason alone does not.
        raise InputError(SOURCE, "", f"cannot be read ({error.strerror or type(error).__name__})",
                         f"Make the local folder readable, or set {VARIABLE} to an empty folder; see {OWNER}") \
            from error


def _text(path: Path, name: str) -> str | None:
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise InputError(f"{SOURCE}: {name}", "", f"is no UTF-8 text ({error.reason})",
                         f"Save it as UTF-8 JSON; see {OWNER}") from error


def choose(folders: Iterable[ThemeFolder], local_json: str | None) -> StyleChoice | None:
    """The style choice of the listed theme ``folders`` and the text of local.json (None without it):
    each theme checked, then the start theme; None where there is no theme."""
    extras = tuple(sorted((_theme(folder) for folder in folders), key=lambda theme: theme.name))
    start = _start(local_json, [theme.name for theme in extras])
    return StyleChoice(extras, start) if extras else None


def _theme(folder: ThemeFolder) -> Theme:
    source = f"{SOURCE}: themes/{folder.name}"
    if not NAME.fullmatch(folder.name) or folder.name == DEFAULT:
        raise InputError(source, "name", f"is {folder.name!r}, which is no theme name", "Name the folder with 1 to "
                         "32 lowercase letters, digits and dashes, starting with a letter or digit, and not "
                         f"{DEFAULT!r}; see {OWNER}")
    for entry in folder.entries:
        if entry != ASSETS:
            raise InputError(source, entry, "is no part of a theme, which holds only assets.json",
                             f"Move it out of the theme's folder; see {OWNER}")
    if folder.assets is None:
        return Theme(folder.name)
    return Theme(folder.name, _colors(folder.assets, f"{source}/{ASSETS}"))


REMEDY = ('Give only colours the packaged assets.json declares, each with a value '
          '{"light": "#rrggbb", "dark": "#rrggbb"}; see ' + OWNER)


def _colors(text: str, source: str) -> tuple[tuple[str, str, str], ...]:
    """The colours a theme's assets.json sets, by semantic ID, each with its light and dark value."""
    try:
        data = json.loads(text)
    except ValueError as error:
        raise InputError(source, "", f"is no JSON ({error})", REMEDY) from error
    error = schema_error(list(Draft202012Validator(ASSETS_SCHEMA).iter_errors(data)), source,
                         f"obs-html's assets.schema.json and {OWNER}")
    if error is not None:
        raise error
    for key in data["assets"]:
        if key != "color":
            raise InputError(source, f"assets.{key}", "is no colour: a theme holds only children of color", REMEDY)
    group = data["assets"].get("color", {})
    for key in group:
        if key not in ("children", "type") or key == "type" and group[key] != "color":
            raise InputError(source, f"assets.color.{key}", "is not allowed: a theme holds only children of color",
                             REMEDY)
    declared = _declared_colors()
    colors = []
    for segment, node in group.get("children", {}).items():
        name = f"color.{segment}"
        field = asset_field(name)
        if name not in declared:
            raise InputError(source, field, "is no colour the packaged assets.json declares", REMEDY)
        value = node.get("value")
        if set(node) - {"value", "type"} or node.get("type", "color") != "color" or not (
                isinstance(value, dict) and set(value) == {"light", "dark"}):
            raise InputError(source, field, "is no light and dark pair of colour values", REMEDY)
        colors.append((name, value["light"], value["dark"]))
    return tuple(sorted(colors))


def _declared_colors() -> set[str]:
    """The semantic IDs of the colours the packaged index declares."""
    index = json.loads(files("obs_html").joinpath(ASSETS).read_text(encoding="utf-8"))

    def walk(nodes: dict, prefix: str):
        for segment, node in nodes.items():
            name = f"{prefix}.{segment}"
            if "children" in node:
                yield from walk(node["children"], name)
            else:
                yield name
    return set(walk(index["assets"]["color"].get("children", {}), "color"))


def _start(text: str | None, names: list[str]) -> str:
    """The start theme local.json names, ``default`` without one."""
    source = f"{SOURCE}: {LOCAL}"
    listed = ", ".join([DEFAULT, *names])
    if text is None:
        return DEFAULT
    try:
        data = json.loads(text)
    except ValueError as error:
        raise InputError(source, "", f"is no JSON ({error})",
                         f'Write {{"startTheme": "<name>"}}, the name one of {listed}; see {OWNER}') from error
    error = schema_error(list(Draft202012Validator(LOCAL_SCHEMA).iter_errors(data)), source,
                         f"obs-html's local.schema.json and {OWNER}")
    if error is not None:
        raise error
    start = data.get("startTheme", DEFAULT)
    if start != DEFAULT and start not in names:
        raise InputError(source, "startTheme", f"is {start!r}, neither {DEFAULT!r} nor a theme there",
                         f"Name one of the themes there: {listed}; see {OWNER}")
    return start
