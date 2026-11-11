"""The feature registry (obs_html.features): a reader feature ships only when used.

Each feature's inclusion condition decides whether its code, its page elements and, for a feature
that needs something of the host, its canary are in the HTML; no source of the artifact calls a
browser dialog (artifact-ui.md, notice center).
"""
import dataclasses
import json
import re
from importlib.resources import files

import pytest

import canaries
import library_fakes
from conftest import FIXTURE, PIXEL, ROOT
from documents import chapter, document, heading, node, paragraph
from obs_html import features
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.features import FEATURES, Feature, Part
from obs_html.figures import FIGURE_KINDS
from obs_html.render import render


CONFIG = load_config()
SOURCE = files("obs_html")
DIALOG_CALL = re.compile(r"\b(?:alert|confirm|prompt)\s*\(")


def _link(target: str, label: str) -> dict:
    return node("wikilinks", target=target, chapter=target, heading="", label=label)


def plain() -> dict:
    return document("Plain", chapter("one", "One", heading(1, "One"), paragraph("Text.")))


def with_bless() -> dict:
    """A chapter that asks for a bless (obs input-model, Bless requests), as the core carries it."""
    source = document("Bless", chapter("one", "One", heading(1, "One"), paragraph("Bless this.")),
                      chapter("two", "Two", heading(1, "Two"), paragraph("A record.")))
    source["chapters"][0]["bless"] = {"version": "0" * 64}
    return source


def deck() -> dict:
    """Every listed chapter asks for a bless, so the artifact opens in screens (artifact-ui.md, Screens)."""
    source = with_bless()
    source["chapters"][1]["bless"] = {"version": "1" * 64}
    return source


def declared(layout: str, source: dict) -> dict:
    """``source`` with its manifest declaring ``obsHtml.layout``."""
    source["manifest"]["metadata"]["obsHtml"] = {"layout": layout}
    return source


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


def with_figure(kind: str, body: dict) -> dict:
    """One figure of ``kind`` (figures.py, FIGURE_KINDS) whose body attrs are ``body``."""
    figure = {"type": "figures", "attrs": {"kind": kind}, "children": [node(kind, **body)]}
    return document(f"Figure {kind}", chapter("one", "One", heading(1, "One"), figure))


RESPONSE = json.loads(FIXTURE.read_text(encoding="utf-8"))
PLOT = next(item["children"][0]["attrs"] for chapter_ in RESPONSE["chapters"] for item in chapter_["content"]
            if item["type"] == "figures" and item["attrs"]["kind"] == "plot")
IMAGE = {"mediaType": "image/png", "data": PIXEL}
EQUATIONS = next(item["children"][0]["attrs"] for chapter_ in RESPONSE["chapters"] for item in chapter_["content"]
                 if item["type"] == "figures" and item["attrs"]["kind"] == "equations")
DECISIONS = json.loads((ROOT / "test" / "fixtures" / "documents" / "pugh.json").read_text(encoding="utf-8"))
PUGH = next(item["children"][0]["attrs"] for chapter_ in DECISIONS["chapters"] for item in chapter_["content"]
            if item["type"] == "figures" and item["attrs"]["kind"] == "pugh")
FIGURES = json.loads((ROOT / "test" / "fixtures" / "documents" / "figures.json").read_text(encoding="utf-8"))
SANKEY = next(item["children"][0]["attrs"] for chapter_ in FIGURES["chapters"] for item in chapter_["content"]
              if item["type"] == "figures" and item["attrs"]["kind"] == "sankey")


def fixture(name: str) -> dict:
    """A committed fixture Document (test/fixtures/documents/<name>.json)."""
    return json.loads((ROOT / "test" / "fixtures" / "documents" / f"{name}.json").read_text(encoding="utf-8"))


# Feature key -> Documents that meet its condition and Documents that do not.
CASES = {
    "history": ([plain()], []),
    "storage": ([plain()], []),
    "printing": ([plain()], []),
    "downloads": ([plain()], []),
    "clipboard": ([plain()], []),
    "answers": ([with_bless()], [plain()]),
    "bless": ([with_bless()], [plain(), with_figure("pugh", PUGH)]),
    "screens": ([deck(), declared("screens", plain())],
                [plain(), with_bless(), declared("paged", deck()), declared("scrolling", deck())]),
    "popups": ([with_context_note(), with_non_document_note(), with_guided_card()], [plain()]),
    "plotting": ([with_figure("plot", PLOT), with_figure("equations", EQUATIONS)],
                 [plain(), with_figure("image", IMAGE)]),
    "equations": ([with_figure("equations", EQUATIONS)], [plain(), with_figure("plot", PLOT)]),
    "pugh": ([with_figure("pugh", PUGH)], [plain(), with_figure("equations", EQUATIONS)]),
    "sankey": ([with_figure("sankey", SANKEY)], [plain(), with_figure("pugh", PUGH)]),
    "tables": ([with_guided_card()], [plain(), with_figure("pugh", PUGH)]),
    "options-menu": ([with_guided_card(), with_figure("image", IMAGE)], [plain(), with_bless()]),
    "figures": ([with_figure("image", IMAGE), with_figure("pugh", PUGH)], [plain(), with_guided_card()]),
    "cards": ([fixture("cards")], [plain(), with_figure("pugh", PUGH)]),
    "property-editor": ([fixture("property-editor-projection")], [plain(), with_guided_card()]),
}


def test_a_figure_kind_declares_what_it_needs_only_through_the_feature_registry() -> None:
    keys = {feature.key for feature in FEATURES}
    for kind, entry in FIGURE_KINDS.items():
        assert set(entry.features) <= keys, f"{kind}: declares features {entry.features} the registry lacks"
    plot, image = render(with_figure("plot", PLOT), CONFIG), render(with_figure("image", IMAGE), CONFIG)
    assert 'id="plotly-script"' in plot and 'id="canary-plotting"' in plot
    assert 'id="plotly-script"' not in image and 'id="canary-plotting"' not in image
    equations = render(with_figure("equations", EQUATIONS), CONFIG)
    assert 'id="maths-script"' in equations and 'id="plotly-script"' in equations
    assert 'id="maths-script"' not in plot and 'id="maths-script"' not in image
    pugh = render(with_figure("pugh", PUGH), CONFIG)
    assert 'id="pugh-engine-script"' in pugh and 'id="plotly-script"' not in pugh
    assert 'id="pugh-engine-script"' not in equations and 'id="pugh-engine-script"' not in image


def test_the_maths_library_ships_pinned_from_its_lockfile_with_its_licence() -> None:
    """math.js, pinned in maths/package-lock.json and packaged from it (hatch_build.py), is embedded
    whole in an artifact with an equation figure, with its licence; nothing loads it from elsewhere."""
    lock = json.loads((ROOT / "maths" / "package-lock.json").read_text(encoding="utf-8"))
    packaged = SOURCE.joinpath("vendor", "maths")
    library = packaged.joinpath("math.js").read_text(encoding="utf-8")
    with library_fakes.real():  # Its subject is the maths library's embedding (libraries.py).
        html = render(with_figure("equations", EQUATIONS), CONFIG)

    assert lock["packages"][""]["dependencies"] == {"mathjs": lock["packages"]["node_modules/mathjs"]["version"]}
    assert f"@version {lock['packages']['node_modules/mathjs']['version']}" in \
        packaged.joinpath("math.js.LICENSE.txt").read_text(encoding="utf-8")
    assert library.replace("</script", "<\\/script") in html
    assert packaged.joinpath("LICENSE").read_text(encoding="utf-8").strip() in html
    assert "cdn" not in html.split('id="maths-script"')[1].split("</script>")[0][:200].lower()


def test_every_feature_has_cases_and_its_canary_and_code_exist() -> None:
    assert sorted(feature.key for feature in FEATURES) == sorted(CASES), (
        "test_features.py: CASES names each feature of obs_html.features.FEATURES")
    for feature in FEATURES:
        assert (feature.canary is None) is (not feature.host), f"{feature.key}: a canary exactly where it needs the host"
        assert feature.canary is None or SOURCE.joinpath(feature.canary).is_file(), \
            f"{feature.key}: missing {feature.canary}"
        assert not SOURCE.joinpath(f"canaries/{feature.key}.js").is_file() or feature.host, \
            f"{feature.key}: canaries/{feature.key}.js ships with no feature that needs the host"
        assert feature.condition, f"{feature.key}: its condition names what puts it in the artifact"
        for name in (*feature.code, *feature.styles, *feature.base_styles):
            assert SOURCE.joinpath(name).is_file(), f"{feature.key}: missing {name}"
        for part in feature.parts:
            assert part.condition, f"{feature.key}/{part.key}: its condition names what ships the part"
            for name in part.code:
                assert SOURCE.joinpath(name).is_file(), f"{feature.key}/{part.key}: missing {name}"


def missing_from_the_feature_fixture(artifact: str, registry=FEATURES) -> list[str]:
    """Each registered feature, and each part of one, that the feature fixture's artifact does not
    carry by the registry's own conditions."""
    model = decode_artifact_data(artifact)
    return [f"{feature.key}{'/' + part.key if part else ''}" for feature in registry
            for part in (None, *feature.parts)
            if not (part or feature).included(model, False)]


def test_the_feature_fixture_carries_every_registered_feature_and_part(feature_artifact: str) -> None:
    """The browser tier tests every feature on the feature fixture (obs quality.md, Testing
    boundaries), so the fixture carries each one the registry declares."""
    missing = missing_from_the_feature_fixture(feature_artifact)
    assert not missing, (
        f"test/test_features.py: the feature fixture (test/fixtures/documents/features.json) lacks the "
        f"registered features {missing} (obs_html.features.FEATURES). Remedy: give the features vault of "
        "test/fixtures/build_documents.py what meets each condition, then rebuild it with "
        "`uv run python test/fixtures/build_documents.py <obs checkout> features`.")


def test_a_newly_registered_feature_or_part_must_appear_in_the_feature_fixture(feature_artifact: str) -> None:
    """The check is not vacuous: a feature or part added to the registry whose condition the
    fixture does not meet is named."""
    never = lambda _model, _trusted_runtime: False  # noqa: E731
    added = Feature("added", "a condition the feature fixture does not meet", never)
    part = Part("added-part", "a condition the feature fixture does not meet", never, ())
    registry = (*FEATURES, added, dataclasses.replace(FEATURES[0], parts=(part,)))
    assert missing_from_the_feature_fixture(feature_artifact, registry) == [
        *missing_from_the_feature_fixture(feature_artifact), "added", f"{FEATURES[0].key}/added-part"]


@pytest.mark.parametrize("feature", FEATURES, ids=lambda feature: feature.key)
def test_the_inclusion_condition_decides_whether_code_elements_and_canary_ship(feature) -> None:
    included, excluded = CASES[feature.key]
    canary = SOURCE.joinpath(feature.canary).read_text(encoding="utf-8").strip() if feature.canary else None
    code = [SOURCE.joinpath(name).read_text(encoding="utf-8").strip()
            for name in (*feature.code, *feature.styles, *feature.base_styles)]
    elements = [f'id="{element}"' for element in feature.elements]
    for source in included:
        html, title = render(source, CONFIG), source["manifest"]["title"]
        assert canary is None or f'id="canary-{feature.key}"' in html and canary in html, (
            f"{feature.key}: {title} meets '{feature.condition}' but lacks its canary")
        assert all(part in html for part in code), f"{feature.key}: code missing from {title}"
        assert all(element in html for element in elements), f"{feature.key}: elements missing from {title}"
    for source in excluded:
        html, title = render(source, CONFIG), source["manifest"]["title"]
        assert f'id="canary-{feature.key}"' not in html and (canary is None or canary not in html), (
            f"{feature.key}: {title} does not meet '{feature.condition}' but ships its canary")
        assert not any(part in html for part in code), f"{feature.key}: code shipped in {title}"
        assert not any(element in html for element in elements), f"{feature.key}: elements shipped in {title}"


def test_the_structural_styles_keep_base_css_order_then_the_features_then_the_style_module(
        feature_artifact: str) -> None:
    """A feature's share of the structural styles follows base.css in registry order and comes
    before the style module, so its rules keep the place in the cascade they had in base.css
    (architecture.md, Rendering and runtime)."""
    styles = feature_artifact.split('<style id="artifact-styles">', 1)[1].split("</style>", 1)[0]
    parts = [SOURCE.joinpath("base.css").read_text(encoding="utf-8"),
             *(SOURCE.joinpath(name).read_text(encoding="utf-8") for feature in FEATURES
               for name in feature.base_styles),
             SOURCE.joinpath("styles", "generic", "style.css").read_text(encoding="utf-8")]
    assert len(parts) > 2
    assert styles.strip() == "\n".join(parts).strip()


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


def test_a_feature_added_to_the_registry_is_expected_by_the_canary_tests(monkeypatch) -> None:
    """The browser tests of the canaries' results (test_sandboxed_preview_browser.py,
    test_features_browser.py) take their lists from test/canaries.py, which reads the registry and
    each canary, so a new feature's canary is expected there without a literal edit."""
    artifacts = [render(source, CONFIG) for source in (plain(), with_context_note())]
    before = [(canaries.canaries(html), canaries.undecided_where_flags_hidden(html)) for html in artifacts]
    fake = features.Feature("fake", "always", lambda _model, _trusted_runtime: True)
    shipped = canaries.canary_source
    monkeypatch.setattr(features, "FEATURES", (*features.FEATURES, fake))
    monkeypatch.setattr(canaries, "canary_source", lambda feature: (
        'probe: ({sandboxAllows}) => sandboxAllows("allow-fake")' if feature is fake else shipped(feature)))
    for html, (run, undecided) in zip(artifacts, before):
        assert canaries.canaries(html) == [*run, "fake"]
        assert canaries.undecided_where_flags_hidden(html) == [*undecided, "fake"]
