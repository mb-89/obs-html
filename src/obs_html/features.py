"""Host-dependent reader features: the one place such a feature is declared.

Reader: whoever adds or changes a reader feature that needs something of the page showing the
HTML (artifact-ui.md, notice center).

Each entry names the feature's key, the condition that puts it in the artifact, the package
scripts that hold its own code and controls (beyond the reader's shared scripts), and its canary,
``canaries/<key>.js``, which declares the feature's name, why a host blocks it, the remedy and the
probe that capabilities.js runs. The renderer includes a feature's code and canary only when its
condition holds, so a feature the Document does not use has no code, control, canary or notice.
A figure kind that needs a host ability or a library names the feature's key in its
FigureKind.features (figures.py); the feature's condition reads those declarations, so the kind
registry has no inclusion mechanism of its own. A library the renderer delivers itself (the
plotting library, by artifact.figures.plotlyDelivery) ships exactly where its feature is included.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

from .figures import FIGURE_KINDS


@dataclass(frozen=True)
class Feature:
    key: str
    condition: str
    """What puts the feature in the artifact, in words."""
    included: Callable[[dict, bool], bool]
    """Whether the artifact meets the condition, given its model (render.py's artifact-data
    island) and whether it bundles a trusted application runtime."""
    code: tuple[str, ...] = ()

    @property
    def canary(self) -> str:
        return f"canaries/{self.key}.js"


def _always(_model: dict, _trusted_runtime: bool) -> bool:
    return True


def _icons(value: object):
    """Every table icon of a Base definition, wherever its property presentation names one."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "icon" and isinstance(item, dict):
                yield item
            elif key == "icons" and isinstance(item, list):
                yield from (icon for icon in item if isinstance(icon, dict))
            else:
                yield from _icons(item)
    elif isinstance(value, list):
        for item in value:
            yield from _icons(item)


def _floating_window(model: dict, trusted_runtime: bool) -> bool:
    """A guided card (a table icon's card), a note a link opens as context (one outside the
    reading order or not a document: artifact.js, followNoteLink), or a trusted runtime, which
    may open the window (obsArtifact.openFloatingWindow)."""
    toc = set(model["toc"])
    return trusted_runtime or any(
        any("card" in icon for table in note["tables"] for icon in _icons(table["definition"]))
        or note["slug"] not in toc
        or (note["frontmatter"].get("obs") or {}).get("document") is False
        for note in model["notes"])


FIGURE_KIND = re.compile(r'data-figure-kind="([a-z][a-z0-9-]*)"')


def _figures_need(key: str) -> Callable[[dict, bool], bool]:
    """Whether a figure of the artifact is of a kind that declares the feature ``key`` (figures.py,
    FigureKind.features): a figure kind needs a host ability or a library only through here."""
    def included(model: dict, _trusted_runtime: bool) -> bool:
        kinds = {kind for note in model["notes"] for kind in FIGURE_KIND.findall(note["html"])}
        return any(key in FIGURE_KINDS[kind].features for kind in kinds if kind in FIGURE_KINDS)
    return included


FEATURES: tuple[Feature, ...] = (
    Feature("history", "always: every chapter has an address", _always),
    Feature("storage", "always: reader settings are kept", _always),
    Feature("printing", "always: Settings offers Print to PDF", _always),
    Feature("downloads", "always: Download HTML, Download source ZIP and, in the evidence edition, "
            "attachment downloads", _always, ("attachment-download.js",)),
    Feature("clipboard", "always: the Comments bar offers Copy comments", _always),
    Feature("popups", "a guided card, a note a link opens as context, or a trusted runtime",
            _floating_window, ("guided-card.js",)),
    Feature("plotting", "a figure of a kind that needs the plotting library (figures.py, FIGURE_KINDS): "
            "a stored-data plot", _figures_need("plotting")),
)


def included(model: dict, trusted_runtime: bool) -> tuple[Feature, ...]:
    """The features the artifact carries, in registry order."""
    return tuple(feature for feature in FEATURES if feature.included(model, trusted_runtime))
