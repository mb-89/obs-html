"""Host-dependent reader features: the one place such a feature is declared.

Reader: whoever adds or changes a reader feature that needs something of the page showing the
HTML (artifact-ui.md, notice center).

Each entry names the feature's key, the condition that puts it in the artifact, the package
scripts that hold its own code and controls (beyond the reader's shared scripts), and its canary,
``canaries/<key>.js``, which declares the feature's name, why a host blocks it, the remedy and the
probe that capabilities.js runs. The renderer includes a feature's code and canary only when its
condition holds, so a feature the Document does not use has no code, control, canary or notice.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


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
        or (note["frontmatter"].get("obsHtml") or {}).get("document") is False
        for note in model["notes"])


FEATURES: tuple[Feature, ...] = (
    Feature("history", "always: every chapter has an address", _always),
    Feature("storage", "always: reader settings are kept", _always),
    Feature("printing", "always: Settings offers Print to PDF", _always),
    Feature("downloads", "always: Download HTML and Download source ZIP", _always),
    Feature("clipboard", "always: the Comments bar offers Copy comments", _always),
    Feature("popups", "a guided card, a note a link opens as context, or a trusted runtime",
            _floating_window, ("guided-card.js",)),
)


def included(model: dict, trusted_runtime: bool) -> tuple[Feature, ...]:
    """The features the artifact carries, in registry order."""
    return tuple(feature for feature in FEATURES if feature.included(model, trusted_runtime))
