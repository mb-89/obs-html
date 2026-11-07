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


_PAGE_GEOMETRY = re.compile(
    r"@page|--(?:paper|sheet)-|var\(--(?:paper|sheet)-|(?:^|[;{])\s*(?:size|orientation)\s*:",
    re.IGNORECASE,
)


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
    geometry = _PAGE_GEOMETRY.search(overlay)
    if geometry:
        declared = re.match(r"@?[-\w]+", overlay[geometry.start():].lstrip(";{ \t\r\n"))[0]
        raise InputError(stylesheet, declared, "declares page geometry, which the Document's profile owns",
                         "Remove it; a Document chooses its paper and margin in its manifest's obsHtml.print")
    return Style(
        directory=root,
        overlay=overlay,
        asset_index=asset_index if asset_index.is_file() else None,
    )
