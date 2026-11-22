"""Style module loading for self-contained artifact output."""
from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
import re

from obs_html.errors import InputError


@dataclass(frozen=True)
class Style:
    directory: Path
    overlay: str
    """The module's style.css, which follows the structural styles (render.py, _shell)."""
    asset_index: Path | None
    cover: str | None = None
    """The module's cover.html, checked by ``cover_placeholders``; None keeps the packaged cover."""

    def render_cover(self, title: str, metadata: dict[str, str]) -> str | None:
        """The module's cover with ``{{ title }}`` as ``title`` and each ``{{ metadata.<path> }}`` as
        ``metadata[<path>]``, both display HTML, empty where the path is absent; None without one."""
        if self.cover is None:
            return None
        return _COVER_PLACEHOLDER.sub(
            lambda match: title if match[1].strip() == "title"
            else metadata.get(match[1].strip().removeprefix("metadata."), ""), self.cover)


_COVER_PLACEHOLDER = re.compile(r"{{(.*?)}}", re.DOTALL)
_COVER_NAME = re.compile(r"title|metadata\.[\w -]+(?:\.[\w -]+)*")
COVER_REMEDY = "Use only {{ title }} and {{ metadata.<field path> }}, a path of letters, digits, spaces, '_' and '-'"


def cover_placeholders(template: str) -> str | None:
    """The first placeholder of a style module's cover.html that is no cover placeholder, as written,
    or None: ``{{ title }}`` and ``{{ metadata.<path> }}`` are the only ones, with no expression."""
    for match in _COVER_PLACEHOLDER.finditer(template):
        if not _COVER_NAME.fullmatch(match[1].strip()):
            return match[0]
    rest = _COVER_PLACEHOLDER.sub("", template)
    return next((mark for mark in ("{{", "}}") if mark in rest), None)


_PAGE_GEOMETRY = re.compile(
    r"@page|--(?:paper|sheet)-|var\(--(?:paper|sheet)-|(?:^|[;{])\s*(?:size|orientation)\s*:",
    re.IGNORECASE,
)


GEOMETRY_PROBLEM = "declares page geometry, which the Document's profile owns"
GEOMETRY_REMEDY = "Remove it; a Document chooses its paper and margin in its manifest's obsHtml.print"


def page_geometry(css: str) -> str | None:
    """The first page geometry ``css`` declares, as its at-rule or property (``@page``, ``size``,
    ``--paper-width``), or None: what a style module's style.css must not hold."""
    geometry = _PAGE_GEOMETRY.search(css)
    if not geometry:
        return None
    return re.match(r"@?[-\w]+", css[geometry.start():].lstrip(";{ \t\r\n"))[0]


def load_style(directory: Path | None = None) -> Style:
    """Load a style module folder, using the packaged generic module by default."""
    root = Path(directory) if directory is not None else Path(
        str(files("obs_html").joinpath("styles", "generic"))
    )
    root = root.resolve()
    stylesheet = root / "style.css"
    if not root.is_dir():
        raise InputError(root, "", "is no folder", "Give --style a style module folder that holds style.css")
    if not stylesheet.is_file():
        raise InputError(root, "style.css", "is missing", "Add the module's stylesheet as style.css")
    asset_index = root / "assets.json"
    overlay = stylesheet.read_text(encoding="utf-8")
    declared = page_geometry(overlay)
    if declared:
        raise InputError(stylesheet, declared, GEOMETRY_PROBLEM, GEOMETRY_REMEDY)
    cover_file = root / "cover.html"
    cover = cover_file.read_text(encoding="utf-8") if cover_file.is_file() else None
    if cover is not None and (placeholder := cover_placeholders(cover)):
        raise InputError(cover_file, placeholder, "is no cover placeholder", COVER_REMEDY)
    return Style(
        directory=root,
        overlay=overlay,
        asset_index=asset_index if asset_index.is_file() else None,
        cover=cover,
    )
