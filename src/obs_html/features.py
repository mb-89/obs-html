"""Reader features that not every artifact needs: the one place such a feature is declared.

Reader: whoever adds or changes a reader feature whose code, styles or page elements ship only
with the Documents that use it, or one that needs something of the page showing the HTML
(artifact-ui.md, notice center).

Each entry names the feature's key, the condition that puts it in the artifact, the package
scripts that hold its own code and controls (beyond the reader's shared scripts), the page
elements the renderer writes only for it (by id), and, for a feature that needs something of the
page showing the HTML (``host``), its canary, ``canaries/<key>.js``, which declares the feature's
name, why a host blocks it, the remedy and the probe that capabilities.js runs. The renderer
includes a feature's code, elements and canary only when its condition holds, so a feature the
Document does not use has no code, control, element, canary or notice.
A figure kind that needs a host ability, a library or a script of its own names the feature's key in its
FigureKind.features (figures.py); the feature's condition reads those declarations, so the kind
registry has no inclusion mechanism of its own. A feature's part ships code only where its own condition holds as
well, under the feature's canary: the downloads feature's source-archive part attaches the source
ZIP to a PDF only in an artifact that has one. A library the renderer delivers itself (the
plotting library, by artifact.figures.plotlyDelivery, the maths library, packaged from its
npm lockfile ``maths/package-lock.json`` by hatch_build.py, ctrl's decision engine ``vendor/pugh.js``, and the PDF
library ``vendor/pdf-lib.min.js`` of the source-archive part) ships exactly where its feature or part is included.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
import re
from typing import Callable

from .artifact_data import serialize_artifact_data
from .errors import InputError
from .figures import FIGURE_KINDS


def maths_library() -> str:
    """The maths library (math.js) the equations feature embeds, packaged from its lockfile (hatch_build.py)."""
    return files("obs_html").joinpath("vendor", "maths", "math.js").read_text(encoding="utf-8")


def maths_library_licence() -> str:
    """The maths library's licence and its bundled licences, which ship with it."""
    maths = files("obs_html").joinpath("vendor", "maths")
    return (maths.joinpath("LICENSE").read_text(encoding="utf-8") + "\n"
            + maths.joinpath("math.js.LICENSE.txt").read_text(encoding="utf-8")).replace("*/", "* /")


ENGINE_EXPORT = re.compile(r"^export const \{[^}]*\} = pughEngine\(\);\s*\Z", re.M)
"""The last line of ctrl's engine module (vendor/pugh.js), which a classic script cannot hold."""


def pugh_engine() -> str:
    """ctrl's Pugh engine (vendor/pugh.js, its header naming ctrl's commit) as the classic script the
    pugh feature embeds: the file as it is, its module export replaced by ``globalThis.obsPughEngine``."""
    source = files("obs_html").joinpath("vendor", "pugh.js").read_text(encoding="utf-8")
    if not ENGINE_EXPORT.search(source):
        raise InputError("obs_html/vendor/pugh.js", "last line", "is not ctrl's export of pughEngine()",
                         "Copy ctrl's src/core/pugh.js again unchanged under its header; see features.py, pugh_engine")
    return ENGINE_EXPORT.sub("globalThis.obsPughEngine = pughEngine();\n", source)


@dataclass(frozen=True)
class Part:
    """Code of a feature that ships only where the part's own condition holds as well."""
    key: str
    condition: str
    included: Callable[[dict, bool], bool]
    code: tuple[str, ...]


@dataclass(frozen=True)
class Feature:
    key: str
    condition: str
    """What puts the feature in the artifact, in words."""
    included: Callable[[dict, bool], bool]
    """Whether the artifact meets the condition, given its model (render.py's artifact-data
    island) and whether it bundles a trusted application runtime."""
    code: tuple[str, ...] = ()
    parts: tuple[Part, ...] = ()
    styles: tuple[str, ...] = ()
    """Package stylesheets that ship with the feature, after the packaged styles."""
    base_styles: tuple[str, ...] = ()
    """Package stylesheets of the feature's share of the structural styles: they follow base.css inside
    the artifact styles, in registry order and before the style module, so each rule keeps the place in
    the cascade it had in base.css (architecture.md, Rendering and runtime)."""
    elements: tuple[str, ...] = ()
    """Ids of the page elements (render.py, _shell) the renderer writes only with the feature."""
    host: bool = True
    """Whether the feature needs something of the page showing the HTML, so it has a canary."""

    def shipped(self, model: dict, trusted_runtime: bool) -> tuple[Part, ...]:
        """The parts the artifact carries along with the feature."""
        return tuple(part for part in self.parts if part.included(model, trusted_runtime))

    @property
    def canary(self) -> str | None:
        return f"canaries/{self.key}.js" if self.host else None


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
    FigureKind.features): a figure kind needs a host ability, a library or a script of its own only through here."""
    def included(model: dict, _trusted_runtime: bool) -> bool:
        kinds = {kind for note in model["notes"] for kind in FIGURE_KIND.findall(note["html"])}
        return any(key in FIGURE_KINDS[kind].features for kind in kinds if kind in FIGURE_KINDS)
    return included


def _bless(model: dict, _trusted_runtime: bool) -> bool:
    """A chapter of the Document asks for a bless (obs input-model, Bless requests)."""
    return any("bless" in note for note in model["notes"])


def _screens(model: dict, _trusted_runtime: bool) -> bool:
    """The artifact opens in screens (artifact-ui.md, Screens; render.py, _layout)."""
    return model["reading"]["layout"] == "screens"


def _source_archive(model: dict, _trusted_runtime: bool) -> bool:
    """The Document carries its sources (obs-document --embed-source; source_archive.py)."""
    return model.get("sourceArchiveComplete") is True


def _tables(model: dict, _trusted_runtime: bool) -> bool:
    """A note holds a Base table (render.py, the bases renderer; artifact.js, renderChapterTables)."""
    return any(note["tables"] for note in model["notes"])


def _marked(marker: str) -> Callable[[dict, bool], bool]:
    """Whether the artifact's model holds ``marker``, the attribute the renderer writes on the
    element a feature's script finds (a figure, a record card, a property editor)."""
    def included(model: dict, _trusted_runtime: bool) -> bool:
        return marker in serialize_artifact_data(model)
    return included


def _figures(model: dict, trusted_runtime: bool) -> bool:
    """A figure (figures.py): its frame, styles and script."""
    return _marked("data-artifact-figure")(model, trusted_runtime)


def _options_menu(model: dict, trusted_runtime: bool) -> bool:
    """A Base table or a figure, which share the one options menu (artifact-ui.md, Interactive engineering figures)."""
    return _tables(model, trusted_runtime) or _figures(model, trusted_runtime)


def _cards(model: dict, trusted_runtime: bool) -> bool:
    """Record cards, or a quantity note that counts by a query (cards.js)."""
    return _marked("data-record-cards")(model, trusted_runtime) or any(
        note["frontmatter"].get("kind") == "quantity" and "query" in note["frontmatter"]
        for note in model["notes"])


FEATURES: tuple[Feature, ...] = (
    Feature("history", "always: every chapter has an address", _always),
    Feature("storage", "always: reader settings are kept", _always),
    Feature("printing", "always: Settings offers Print to PDF", _always),
    Feature("downloads", "always: Download HTML, Download source ZIP and, in the evidence edition, "
            "attachment downloads", _always, ("attachment-download.js",), parts=(
                Part("source-archive", "a source archive (obs-document --embed-source): Download source ZIP "
                     "and Attach source ZIP to PDF, with the PDF library", _source_archive, ("archive.js",)),)),
    Feature("clipboard", "always: the Comments bar offers Copy comments", _always),
    Feature("answers", "a chapter that asks for a bless: the page hands a reader's answers to a sink "
            "(obsArtifact.sendAnswers; spec/capabilities/answers.md)", _bless, ("answers.js",)),
    Feature("bless", "a chapter that asks for a bless: the top band's verdict pill and keys, and Send "
            "(spec/capabilities/bless.md)", _bless, ("bless.js",), base_styles=("bless.css",)),
    Feature("screens", "an artifact that opens in screens (obsHtml.layout, or a deck whose chapters all ask "
            "for a bless): the band's title and position (artifact-ui.md, Screens)", _screens, ("screens.js",),
            styles=("screens.css",)),
    Feature("popups", "a guided card, a note a link opens as context, or a trusted runtime",
            _floating_window, ("guided-card.js",), base_styles=("popups.css",)),
    Feature("plotting", "a figure of a kind that needs the plotting library (figures.py, FIGURE_KINDS): "
            "a stored-data plot or an equation figure", _figures_need("plotting"),
            elements=("plotly-script",)),
    Feature("equations", "a figure of a kind that needs the maths library (figures.py, FIGURE_KINDS): "
            "an equation figure", _figures_need("equations"), ("equations.js",),
            elements=("maths-script",)),
    Feature("pugh", "a figure of a kind that needs the decision engine (figures.py, FIGURE_KINDS): "
            "a decision figure", _figures_need("pugh"), ("pugh-figure.js",),
            elements=("pugh-engine-script",), base_styles=("pugh.css",)),
    Feature("sankey", "a figure of a kind drawn by the Sankey script (figures.py, FIGURE_KINDS): a Sankey "
            "figure", _figures_need("sankey"), ("sankey-figure.js",), host=False),
    Feature("tables", "a note with a Base table: the reader's table code, the data table, the Bases schema "
            "and the YAML library its definition editor reads", _tables, ("tables.js",),
            elements=("data-table-script", "base-schema", "yaml-script"), host=False,
            base_styles=("tables.css",)),
    Feature("options-menu", "a Base table or a figure: their one options menu (options-menu.js)",
            _options_menu, ("options-menu.js",), host=False, base_styles=("options-menu.css",)),
    Feature("figures", "a figure: its frame's styles and script", _figures,
            elements=("figure-styles", "figure-script"), host=False),
    Feature("cards", "record cards, or a quantity note that counts by a query", _cards,
            elements=("cards-script",), host=False, base_styles=("cards.css",)),
    Feature("property-editor", "a property editor", _marked("data-property-editor"),
            elements=("property-editor-script",), host=False),
)


def included(model: dict, trusted_runtime: bool) -> tuple[Feature, ...]:
    """The features the artifact carries, in registry order."""
    return tuple(feature for feature in FEATURES if feature.included(model, trusted_runtime))
