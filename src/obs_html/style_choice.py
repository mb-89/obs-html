"""Local themes: the build machine's own themes and its start theme, from obs-html's local folder.

Reader: whoever changes where a build finds its local themes, what one may hold, or how a page
carries them. spec/configuration.md, "Local themes", owns the behaviour; spec/artifact-ui.md,
Styling, what a theme is in the page.

``local_style_choice(environ)`` is the one door to the folder: ``read_local`` lists it, and
``choose``, which reads no file, checks what was listed and returns the ``StyleChoice``, or None
where there is no theme. ``render()`` takes the choice and reads no folder itself. Every refusal
names its file from the local folder (``obs-html local folder: themes/<name>/assets.json``),
never an absolute path, so no message names where the folder is.

``theme_rules`` checks a theme's style.css, CSS text in, and returns its rules scoped to the
theme's name, without its comments, or raises the first break as an ``InputError``; it reads no
file. The scoping shares css_scope.py's helpers with figure_styles.py.
"""
from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

import tinycss2
from jsonschema import Draft202012Validator
from tinycss2.ast import (AtRule, Declaration, FunctionBlock, HashToken, IdentToken, ParseError, QualifiedRule,
                          StringToken, URLToken, WhitespaceToken)

from obs_html.css_scope import leading_root, rule_list, split
from obs_html.errors import InputError, schema_error
from obs_html.semantic_assets import SCHEMA as ASSETS_SCHEMA, asset_field, color_variable
from obs_html.styles import GEOMETRY_PROBLEM, page_geometry

VARIABLE = "OBS_HTML_LOCAL_FOLDER"
"""Names obs-html's local folder instead of the one in the user's configuration folder."""
SOURCE = "obs-html local folder"
OWNER = "obs-html spec/configuration.md (Local themes)"
DEFAULT = "default"
"""The theme Default: the build's style module, with no local layer over it."""
ASSETS = "assets.json"
STYLE = "style.css"
LOCAL = "local.json"
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
LOCAL_SCHEMA = json.loads(files("obs_html").joinpath("local.schema.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Theme:
    """One local theme: its name, for each colour it sets the semantic ID and its light and dark
    values, and its style.css's rules scoped to its name (``theme_rules``)."""
    name: str
    colors: tuple[tuple[str, str, str], ...] = ()
    rules: str = ""

    def css(self) -> str:
        """Its colours, scoped to a root that names it, with the specificity of the semantic asset
        styles' ``:root``, then its rules."""
        declarations = "".join(f"{color_variable(name)}:light-dark({light},{dark});"
                               for name, light, dark in self.colors)
        return f':root:where([data-style="{self.name}"]){{{declarations}}}{self.rules}'


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
        """The page's ``style-choice-styles``: each theme's colour rule and rules, in name order."""
        return "".join(theme.css() for theme in self.extras)


@dataclass(frozen=True)
class ThemeFolder:
    """A folder of ``themes`` as listed: its name, its entries but dot-named ones, and the text of
    its assets.json and its style.css."""
    name: str
    entries: tuple[str, ...] = ()
    assets: str | None = None
    style: str | None = None


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
                texts = []
                for part, holds, kind in ((ASSETS, "colours", "JSON"), (STYLE, "rules", "CSS")):
                    path = entry / part
                    if path.exists() and not path.is_file():
                        raise InputError(f"{SOURCE}: themes/{entry.name}", part, "is no file",
                                         f"Make {part} a file of the theme's {holds}; see {OWNER}")
                    texts.append(_text(path, f"themes/{entry.name}/{part}", kind))
                listed.append(ThemeFolder(entry.name, tuple(inside), *texts))
        local = folder / LOCAL
        if local.exists() and not local.is_file():
            raise InputError(f"{SOURCE}: {LOCAL}", "", "is no file", f"Make {LOCAL} a file; see {OWNER}")
        return tuple(listed), _text(local, LOCAL, "JSON")
    except OSError as error:  # Its message would name the folder; the reason alone does not.
        raise InputError(SOURCE, "", f"cannot be read ({error.strerror or type(error).__name__})",
                         f"Make the local folder readable, or set {VARIABLE} to an empty folder; see {OWNER}") \
            from error


def _text(path: Path, name: str, kind: str) -> str | None:
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise InputError(f"{SOURCE}: {name}", "", f"is no UTF-8 text ({error.reason})",
                         f"Save it as UTF-8 {kind}; see {OWNER}") from error


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
        if entry not in (ASSETS, STYLE):
            raise InputError(source, entry, f"is no part of a theme, which holds only {ASSETS} and {STYLE}",
                             f"Move it out of the theme's folder; see {OWNER}")
    colors = () if folder.assets is None else _colors(folder.assets, f"{source}/{ASSETS}")
    rules = "" if folder.style is None else theme_rules(folder.style, folder.name)
    return Theme(folder.name, colors, rules)


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


AT_RULES = frozenset({"media", "supports"})
"""The at-rules a theme's style.css may hold: conditions whose rules are scoped one by one."""
URLS = frozenset({"url", "src"})
IMAGE_SETS = frozenset({"image-set", "-webkit-image-set"})
DATA_IMAGE = "data:image/"
PAIR = "light-dark"
COLOUR_FUNCTIONS = frozenset({"rgb", "rgba", "hsl", "hsla", "hwb", "lab", "lch", "oklab", "oklch", "color"})
NAMED_COLOURS = frozenset("""
aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown burlywood
cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray
darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen
darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue
firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew
hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan
lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray
lightslategrey lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue
mediumorchid mediumpurple mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred
midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid
palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple
rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue
slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke
yellow yellowgreen
""".split())
"""The CSS named colours: each is one value in both appearances."""
COLOUR_REMEDY = ("Give a colour as var(--color-...), light-dark(<light>, <dark>), currentcolor or transparent, "
                 "and quote a font name that is a colour's name; see " + OWNER)


def theme_rules(css: str, name: str) -> str:
    """The rules of theme ``name``'s style.css text ``css``, checked as spec/configuration.md (Local
    themes) says and scoped to the theme as spec/artifact-ui.md (Styling) says, without comments."""
    source = f"{SOURCE}: themes/{name}/{STYLE}"
    end = re.search(r"</style", css, re.IGNORECASE)
    if end:
        raise InputError(source, f"line {css.count(chr(10), 0, end.start()) + 1}",
                         "holds '</style', which would end the page's style element", f"Remove it; see {OWNER}")
    geometry = page_geometry(css)
    if geometry:
        raise InputError(source, geometry, GEOMETRY_PROBLEM,
                         f"Remove it; a theme sets no paper or margin, as no style module does; see {OWNER}")
    rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
    _check_rules(rules, source, nested=False)
    return "".join(_scoped(rule, name) for rule in rules)


def _check_rules(rules: list, source: str, nested: bool) -> None:
    """Refuse the first break of ``rules``; ``nested`` rules are inside a style rule's block."""
    for rule in rules:
        if isinstance(rule, ParseError):
            _parse_error(rule, source)
        if isinstance(rule, Declaration):
            if rule.lower_name == "color-scheme":
                raise InputError(source, "color-scheme", f"is set on line {rule.source_line}, but the appearance "
                                 "is the reader's", f"Remove it; a theme sets colours for both appearances; see {OWNER}")
            _check_tokens(rule.value, source, colours=True)
            continue
        if isinstance(rule, AtRule):
            if rule.lower_at_keyword not in AT_RULES:
                raise InputError(source, f"@{rule.at_keyword}", f"is an at-rule a theme cannot hold, on line "
                                 f"{rule.source_line}", "Use only @media and @supports; name fonts installed on the "
                                 f"reader's machine instead of @font-face; see {OWNER}")
            if _names_feature(rule.prelude, "prefers-color-scheme"):
                raise InputError(source, "prefers-color-scheme", f"is queried on line {rule.source_line}, but the "
                                 "appearance is the reader's, not the system's", "Give each colour as "
                                 f"light-dark(<light>, <dark>), which follows the reader's appearance; see {OWNER}")
            _check_tokens(rule.prelude, source, colours=False)
            if rule.content is None:
                raise InputError(source, f"line {rule.source_line}", f"has @{rule.at_keyword} without a block",
                                 f"Give its rules in braces; see {OWNER}")
            _check_rules(_blocks(rule.content) if nested else rule_list(rule.content), source, nested)
            continue
        if isinstance(rule, QualifiedRule):
            if any(not tinycss2.serialize(selector).strip() for selector in split(rule.prelude)):
                raise InputError(source, f"line {rule.source_line}", "has an empty selector",
                                 f"Remove the stray comma; see {OWNER}")
            _check_tokens(rule.prelude, source, colours=False)
            _check_rules(_blocks(rule.content), source, nested=True)


def _blocks(tokens: list) -> list:
    """A style rule's block: its declarations and nested rules."""
    return tinycss2.parse_blocks_contents(tokens, skip_comments=True, skip_whitespace=True)


def _parse_error(error: ParseError, source: str) -> None:
    raise InputError(source, f"line {error.source_line}", f"is no CSS ({error.message})",
                     f"Correct the CSS there; see {OWNER}")


def _check_tokens(tokens: list, source: str, colours: bool) -> None:
    """Refuse a parse error, a URL that is no ``data:image/`` URI and, where ``colours``, a colour
    literal outside ``light-dark()``, in ``tokens`` and the blocks inside them."""
    for token in tokens:
        if isinstance(token, ParseError):
            _parse_error(token, source)
        if isinstance(token, URLToken):
            _check_url(token.value, token, source)
        elif isinstance(token, FunctionBlock):
            if token.lower_name in IMAGE_SETS:
                raise InputError(source, "url", f"has {token.name}() on line {token.source_line}, which a theme "
                                 "cannot hold", f"Give one data:image/ URI in url(); see {OWNER}")
            if token.lower_name in URLS:
                given = [part for part in token.arguments if not isinstance(part, WhitespaceToken)]
                _check_url(given[0].value if given and isinstance(given[0], StringToken) else "", token, source)
            elif colours and token.lower_name in COLOUR_FUNCTIONS:
                _colour(token, source)
            _check_tokens(token.arguments, source, colours and token.lower_name != PAIR)
        elif colours and isinstance(token, HashToken):
            _colour(token, source)
        elif colours and isinstance(token, IdentToken) and token.lower_value in NAMED_COLOURS:
            _colour(token, source)
        elif getattr(token, "content", None) is not None:
            _check_tokens(token.content, source, colours)


def _check_url(value: str, token, source: str) -> None:
    if not value.lower().startswith(DATA_IMAGE):
        raise InputError(source, "url", f"on line {token.source_line} is no data:image/ URI, so the page would "
                         "fetch it", f"Embed the image as a data:image/ URI, such as an SVG logo; see {OWNER}")


def _colour(token, source: str) -> None:
    raise InputError(source, f"line {token.source_line}", f"has the colour {tinycss2.serialize([token])}, "
                     "which is one value in both appearances", COLOUR_REMEDY)


def _names_feature(tokens: list, feature: str) -> bool:
    """Whether ``tokens``, an at-rule's prelude, name the media feature ``feature``."""
    for token in tokens:
        if isinstance(token, IdentToken) and token.lower_value == feature:
            return True
        inner = getattr(token, "content", None) or getattr(token, "arguments", None)
        if isinstance(inner, list) and _names_feature(inner, feature):
            return True
    return False


def _scoped(rule, name: str) -> str:
    """``rule``, checked, scoped to theme ``name``: a selector that starts with ``:root`` or
    ``html`` takes ``:where([data-style])`` right after it, any other ``:where(:root[data-style])``
    before it, so each keeps its specificity; the rules of ``@media`` and ``@supports`` alike."""
    if isinstance(rule, AtRule):
        inner = "".join(_scoped(child, name) for child in rule_list(rule.content))
        return f"@{rule.at_keyword} {tinycss2.serialize(_stripped(rule.prelude))}{{{inner}}}"
    where = f':where([data-style="{name}"])'
    selectors = []
    for selector in split(rule.prelude):
        tokens = _stripped(selector)
        root = leading_root(tokens)
        if root:
            selectors.append(tinycss2.serialize(tokens[:root]) + where + tinycss2.serialize(tokens[root:]))
        else:
            selectors.append(f':where(:root[data-style="{name}"]) ' + tinycss2.serialize(tokens))
    return f"{','.join(selectors)}{{{tinycss2.serialize(rule.content)}}}"


def _stripped(tokens: list) -> list:
    start, end = 0, len(tokens)
    while start < end and isinstance(tokens[start], WhitespaceToken):
        start += 1
    while end > start and isinstance(tokens[end - 1], WhitespaceToken):
        end -= 1
    return tokens[start:end]
