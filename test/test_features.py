"""The feature registry (obs_html.features): a host-dependent reader feature ships only when used.

Each feature's inclusion condition decides whether its code and its canary are in the HTML; no
source of the artifact calls a browser dialog (artifact-ui.md, notice center).
"""
import re
from importlib.resources import files

import pytest

from documents import chapter, document, heading, node, paragraph
from obs_html.config import load_config
from obs_html.features import FEATURES
from obs_html.render import render


CONFIG = load_config()
SOURCE = files("obs_html")
DIALOG_CALL = re.compile(r"\b(?:alert|confirm|prompt)\s*\(")


def _link(target: str, label: str) -> dict:
    return node("wikilinks", target=target, chapter=target, heading="", label=label)


def plain() -> dict:
    return document("Plain", chapter("one", "One", heading(1, "One"), paragraph("Text.")))


def with_context_note() -> dict:
    """A note outside the reading order, which a link opens as context in the floating window."""
    source = document(
        "Context",
        chapter("one", "One", heading(1, "One"), paragraph("See ", _link("aside", "the aside"), ".")),
        chapter("aside", "Aside", heading(1, "Aside"), paragraph("Aside text.")),
    )
    source["chapters"][1]["toc"] = False
    return source


def with_non_document_note() -> dict:
    """A listed note marked as no document (obs.document: false), which a link opens as context."""
    return document(
        "Non-document",
        chapter("one", "One", heading(1, "One"), paragraph("See ", _link("term", "the term"), ".")),
        chapter("term", "Term", heading(1, "Term"), metadata={"obs": {"document": False}}),
    )


def with_guided_card() -> dict:
    """A table icon whose action opens a guided card in the floating window."""
    icon = {"name": "help", "label": "Collect evidence", "action": "collect",
            "card": {"title": "Collect evidence", "submit": "Save"}}
    base = node("bases", source="", spec={
        "properties": {"evidence": {"obsHtml": {"icon": icon}}},
        "views": [{"type": "table", "name": "Items", "order": ["file.name", "evidence"]}],
    })
    return document("Guided", chapter("one", "One", heading(1, "One"), base))


# Feature key -> Documents that meet its condition and Documents that do not.
CASES = {
    "history": ([plain()], []),
    "storage": ([plain()], []),
    "printing": ([plain()], []),
    "downloads": ([plain()], []),
    "clipboard": ([plain()], []),
    "popups": ([with_context_note(), with_non_document_note(), with_guided_card()], [plain()]),
}


def test_every_feature_has_cases_and_its_canary_and_code_exist() -> None:
    assert sorted(feature.key for feature in FEATURES) == sorted(CASES), (
        "test_features.py: CASES names each feature of obs_html.features.FEATURES")
    for feature in FEATURES:
        assert SOURCE.joinpath(feature.canary).is_file(), f"{feature.key}: missing {feature.canary}"
        assert feature.condition, f"{feature.key}: its condition names what puts it in the artifact"
        for name in feature.code:
            assert SOURCE.joinpath(name).is_file(), f"{feature.key}: missing {name}"


@pytest.mark.parametrize("feature", FEATURES, ids=lambda feature: feature.key)
def test_the_inclusion_condition_decides_whether_code_and_canary_ship(feature) -> None:
    included, excluded = CASES[feature.key]
    canary = SOURCE.joinpath(feature.canary).read_text(encoding="utf-8").strip()
    code = [SOURCE.joinpath(name).read_text(encoding="utf-8").strip() for name in feature.code]
    for source in included:
        html = render(source, CONFIG)
        assert f'id="canary-{feature.key}"' in html and canary in html, (
            f"{feature.key}: {source['manifest']['title']} meets '{feature.condition}' but lacks its canary")
        assert all(part in html for part in code), f"{feature.key}: code missing from {source['manifest']['title']}"
    for source in excluded:
        html = render(source, CONFIG)
        assert f'id="canary-{feature.key}"' not in html and canary not in html, (
            f"{feature.key}: {source['manifest']['title']} does not meet '{feature.condition}' but ships its canary")
        assert not any(part in html for part in code), (
            f"{feature.key}: code shipped in {source['manifest']['title']}")


def test_an_artifact_without_a_floating_window_ships_no_popup_code() -> None:
    html = render(plain(), CONFIG)
    for marker in ("window.open", "documentPictureInPicture", "Separate windows", "canary-popups"):
        assert marker not in html, f"popup code shipped without a guided card or context note: {marker}"


def test_no_source_calls_a_browser_dialog_and_no_dialogs_canary_ships() -> None:
    callers = [f"{path.name}:{number}" for path in _sources() for number, line in
               enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if DIALOG_CALL.search(line)]
    assert callers == [], f"adapters/html/src/obs_html: browser dialog calls at {callers}; use obsCapabilities.note"
    for source in (plain(), with_context_note(), with_guided_card()):
        html = render(source, CONFIG)
        assert 'id="canary-dialogs"' not in html and '"Dialogs"' not in html


def _sources():
    root = SOURCE.joinpath("")
    return [path for path in sorted(root.rglob("*")) if path.suffix in {".js", ".py"}
            and "vendor" not in path.relative_to(root).parts and "__pycache__" not in path.parts]
