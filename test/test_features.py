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
from conftest import FIXTURE, LOCAL_THEMES, PIXEL, ROOT
from documents import chapter, document, heading, node, paragraph
from obs_html import features
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.features import FEATURES, PART_REGION, Feature, Part, feature_source
from obs_html.figures import FIGURE_KINDS
from obs_html.render import render
from obs_html.style_choice import local_style_choice


CONFIG = load_config()
SOURCE_FILES_OFF = dataclasses.replace(CONFIG, artifact={**CONFIG.artifact, "sourceFileLinks": False})
ROWS_OFF = dataclasses.replace(CONFIG, artifact={**CONFIG.artifact, "tableRowsOneLine": False})
"""The packaged settings with artifact.tableRowsOneLine false: a page built so is byte for byte as before it."""
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


def _cell(value: str, header: bool = False) -> dict:
    return {"type": "table-cell", "attrs": {"header": True} if header else {}, "children": [
        {"type": "text", "attrs": {}, "children": [], "text": value}]}


def with_pipe_table() -> dict:
    """A note with a pipe table (render.py, _table): a header row and a body row."""
    table = {"type": "table", "attrs": {}, "children": [
        {"type": "table-row", "attrs": {}, "children": [_cell("Key", True), _cell("Meaning", True)]},
        {"type": "table-row", "attrs": {}, "children": [_cell("pipe"), _cell("A long meaning.")]}]}
    return document("Pipe", chapter("one", "One", heading(1, "One"), table))


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
TIMELINE = next(item["children"][0]["attrs"] for chapter_ in FIGURES["chapters"] for item in chapter_["content"]
                if item["type"] == "figures" and item["attrs"]["kind"] == "timeline")


def fixture(name: str) -> dict:
    """A committed fixture Document (test/fixtures/documents/<name>.json)."""
    return json.loads((ROOT / "test" / "fixtures" / "documents" / f"{name}.json").read_text(encoding="utf-8"))


# Feature key -> Documents that meet its condition and Documents that do not; a case is a Document,
# rendered with the packaged settings, or a Document and the settings it is rendered with.
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
    "timeline": ([with_figure("timeline", TIMELINE)], [plain(), with_figure("sankey", SANKEY)]),
    "tables": ([with_guided_card()], [plain(), with_figure("pugh", PUGH)]),
    "pipe-tables": ([with_pipe_table()], [plain(), with_guided_card()]),
    "options-menu": ([with_guided_card(), with_figure("image", IMAGE)], [plain(), with_bless()]),
    "figures": ([with_figure("image", IMAGE), with_figure("pugh", PUGH)], [plain(), with_guided_card()]),
    "cards": ([fixture("cards")], [plain(), with_figure("pugh", PUGH)]),
    "property-editor": ([fixture("property-editor-projection")], [plain(), with_guided_card()]),
    "columns": ([fixture("columns")], [plain(), fixture("cards")]),
    "source-file": ([plain()], [(plain(), SOURCE_FILES_OFF)]),
    "style-choice": ([plain()], [plain()]),
}
# Feature key -> the render options its included Documents are rendered with: the fixture's local themes.
OPTIONS = {"style-choice": {"style_choice": local_style_choice({"OBS_HTML_LOCAL_FOLDER": str(LOCAL_THEMES)})}}


def _case(case: dict | tuple[dict, object]) -> tuple[dict, object]:
    """A case's Document and the settings it is rendered with."""
    return case if isinstance(case, tuple) else (case, CONFIG)


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


def test_the_style_sync_part_ships_only_with_local_themes() -> None:
    """A guided card's window follows the page's theme only on a page that carries local themes
    (artifact-ui.md, Styling); elsewhere guided-card.js ships as it is without the part."""
    from obs_html.style_choice import local_style_choice

    plain_page = render(with_context_note(), load_config())
    assert feature_source("guided-card.js") in plain_page and "dataset.style" not in plain_page
    choice = local_style_choice({"OBS_HTML_LOCAL_FOLDER": str(ROOT / "test" / "fixtures" / "local-themes")})
    themed = render(with_context_note(), load_config(), style_choice=choice)
    assert feature_source("guided-card.js", ["style-sync"]) in themed
    assert "dataset.style" in themed and '"data-style"' in themed


def test_the_style_refit_part_ships_only_with_local_themes() -> None:
    """A table's columns are measured again when the reader chooses a theme only on a page that carries
    local themes (artifact-ui.md, Styling); elsewhere table.js ships as it is without the part."""
    listener = 'window.addEventListener("resize"'
    plain_page = render(with_guided_card(), ROWS_OFF)
    assert feature_source("table.js") in plain_page and listener not in feature_source("table.js")
    themed = render(with_guided_card(), ROWS_OFF, **OPTIONS["style-choice"])
    shipped = feature_source("table.js", ["style-refit"])
    assert shipped in themed and listener in shipped


@pytest.mark.parametrize("feature", FEATURES, ids=lambda feature: feature.key)
def test_the_inclusion_condition_decides_whether_code_elements_and_canary_ship(feature) -> None:
    included, excluded = CASES[feature.key]
    canary = SOURCE.joinpath(feature.canary).read_text(encoding="utf-8").strip() if feature.canary else None
    names = (*feature.code, *feature.styles, *feature.base_styles)
    elements = [f'id="{element}"' for element in feature.elements]

    def code(html: str, config) -> list[str]:
        """Each script as the case ships it (features.py, feature_source): with the parts the case
        carries (Feature.shipped), as the packaged settings turn an option's parts on."""
        shipped = [part.key for part in feature.shipped(decode_artifact_data(html), False, config.artifact)]
        return [feature_source(name, shipped).strip() for name in names]

    for source, config in map(_case, included):
        html, title = render(source, config, **OPTIONS.get(feature.key, {})), source["manifest"]["title"]
        assert canary is None or f'id="canary-{feature.key}"' in html and canary in html, (
            f"{feature.key}: {title} meets '{feature.condition}' but lacks its canary")
        assert all(part in html for part in code(html, config)), f"{feature.key}: code missing from {title}"
        assert all(element in html for element in elements), f"{feature.key}: elements missing from {title}"
    for source, config in map(_case, excluded):
        html, title = render(source, config), source["manifest"]["title"]
        assert f'id="canary-{feature.key}"' not in html and (canary is None or canary not in html), (
            f"{feature.key}: {title} does not meet '{feature.condition}' but ships its canary")
        assert not any(part in html for part in code(html, config)), f"{feature.key}: code shipped in {title}"
        assert not any(element in html for element in elements), f"{feature.key}: elements shipped in {title}"


def test_the_structural_styles_keep_base_css_order_then_the_features_then_the_style_module(
        feature_artifact: str) -> None:
    """A feature's share of the structural styles follows base.css in registry order and comes
    before the style module, so its rules keep the place in the cascade they had in base.css
    (architecture.md, Rendering and runtime)."""
    styles = feature_artifact.split('<style id="artifact-styles">', 1)[1].split("</style>", 1)[0]
    # Each stylesheet as it ships (features.py, feature_source): the fixture carries every part, and
    # the packaged settings turn no option's part on.
    shipped = [part.key for feature in FEATURES for part in feature.parts if part.enabled(CONFIG.artifact)]
    parts = [feature_source("base.css", shipped),
             *(feature_source(name, shipped) for feature in FEATURES for name in feature.base_styles),
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


def test_a_part_an_option_turns_on_ships_only_with_it_and_its_regions_strip_without_it() -> None:
    """features.py, Part.option and feature_source: the decision figure's verdict part ships only where
    artifact.figures.decisionVerdict is true, and without it the figure script carries none of its regions."""
    part = next(part for feature in FEATURES if feature.key == "pugh" for part in feature.parts if part.key == "verdict")
    assert part.option == ("figures", "decisionVerdict")
    assert [part.enabled(config) for config in ({}, {"figures": {}}, {"figures": {"decisionVerdict": False}},
                                                {"figures": {"decisionVerdict": True}})] == [False, False, False, True]
    plain, kept = feature_source("pugh-figure.js"), feature_source("pugh-figure.js", ["verdict"])
    assert "part verdict" not in plain and "obsPughVerdict" not in plain
    assert kept == SOURCE.joinpath("pugh-figure.js").read_text(encoding="utf-8")
    regions = kept.count("// part verdict {") + kept.count("/* part verdict { */")
    assert regions == kept.count("// } part verdict") + kept.count("/* } part verdict */") > 0


BRIEF_NOTICE_FILES = ("notices.js", "bless.js", "bless.css")
"""The files that hold the passing line's regions (features.py, the bless feature's part brief-notice)."""


def _brief_config(tmp_path, reading: dict | None):
    """The packaged settings, with a --config file that sets ``reading`` where it is given."""
    if reading is None:
        return CONFIG
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"artifact": {"reading": reading}}), encoding="utf-8")
    return load_config(path)


def test_the_brief_notice_part_turns_on_with_a_positive_setting_and_strips_without_it() -> None:
    """features.py, the bless feature's part brief-notice: artifact.reading.briefNoticeMilliseconds above 0
    turns it on, left out or 0 it is off; without it the files that hold its regions carry none of them."""
    bless = next(feature for feature in FEATURES if feature.key == "bless")
    part = next(part for part in bless.parts if part.key == "brief-notice")
    assert part.option == ("reading", "briefNoticeMilliseconds")
    assert "briefNoticeMilliseconds" in part.condition and "passing line" in part.condition
    assert part.included is bless.included
    assert [part.enabled(config) for config in (
        {}, {"reading": {}}, {"reading": {"briefNoticeMilliseconds": 0}},
        {"reading": {"briefNoticeMilliseconds": 4000}})] == [False, False, False, True]
    for name in BRIEF_NOTICE_FILES:
        stripped, kept = feature_source(name), feature_source(name, ["brief-notice"])
        assert "brief-notice" not in stripped and "obsNoticeBrief" not in stripped, name
        assert kept == SOURCE.joinpath(name).read_text(encoding="utf-8") != stripped, name
        assert kept.count("// part brief-notice {") + kept.count("/* part brief-notice { */") == (
            kept.count("// } part brief-notice") + kept.count("/* } part brief-notice */")) > 0, name


@pytest.mark.parametrize(("reading", "bless", "ships"), [
    (None, True, False), ({"briefNoticeMilliseconds": 0}, True, False),
    ({"briefNoticeMilliseconds": 4000}, True, True), ({"briefNoticeMilliseconds": 4000}, False, False)],
    ids=["absent", "zero", "on", "on-without-send"])
def test_the_passing_line_ships_only_on_a_page_with_send_and_a_positive_setting(
        tmp_path, reading: dict | None, bless: bool, ships: bool) -> None:
    """features.py, the brief-notice part, and cfg.schema.json, artifact.reading.briefNoticeMilliseconds:
    left out of the packaged settings, the page carries none of the line and its data no setting; a
    setting given, 0 included, is the page's data."""
    html = render(with_bless() if bless else plain(), _brief_config(tmp_path, reading))
    assert ("obsNoticeBrief" in html, "brief-notice" in html) == (ships, ships)
    data = decode_artifact_data(html)["reading"]
    if reading is None:
        assert "briefNoticeMilliseconds" not in data
    else:
        assert data["briefNoticeMilliseconds"] == reading["briefNoticeMilliseconds"]


EMPTY_GROUPS_FILES = ("table.js", "tables.js", "base.js", "tables.css", "base.schema.json")
TABLES_PARTS = [part.key for feature in FEATURES if feature.key == "tables" for part in feature.parts]


def _grouped_table(**options: object) -> dict:
    view = {"type": "table", "name": "Items", "order": ["file.name", "phase"], "groupBy": {"property": "phase"},
            "obsHtml": {"groupOrder": ["design", "build"], **options}}
    base = node("bases", source="", spec={"views": [{"type": "table", "name": "All", "order": ["file.name"]}, view]})
    return document("Grouped", chapter("one", "One", heading(1, "One"), base))


def test_the_empty_groups_part_ships_only_where_a_view_sets_the_option_and_strips_without_it() -> None:
    """features.py, the tables feature's part empty-groups: it ships where any view of a Base sets
    obsHtml.showEmptyGroups, to any value, so base.js holds a false one to the schema line it
    embeds, and without it the files the renderer embeds carry none of its regions (the JSON line
    region of the schema included), so such an artifact is what it was."""
    part = next(part for feature in FEATURES if feature.key == "tables" for part in feature.parts
                if part.key == "empty-groups")
    assert part.option == ()
    for name in EMPTY_GROUPS_FILES:
        plain_source, kept = feature_source(name), feature_source(name, ["empty-groups"])
        assert "empty-groups" not in plain_source and "showEmptyGroups" not in plain_source, name
        assert kept != plain_source, name
        assert feature_source(name, TABLES_PARTS) == SOURCE.joinpath(name).read_text(encoding="utf-8"), name
    assert "showEmptyGroups" not in json.dumps(json.loads(feature_source("base.schema.json")))
    shipped = {}
    for label, source in (("off", _grouped_table()), ("false", _grouped_table(showEmptyGroups=False)),
                          ("on", _grouped_table(showEmptyGroups=True))):
        html = render(source, ROWS_OFF)
        shipped[label] = [name for name in EMPTY_GROUPS_FILES if feature_source(name, ["empty-groups"]) in html]
        assert not any(feature_source(name) in html for name in EMPTY_GROUPS_FILES) or label != "on", label
    assert shipped == {"off": [], "false": list(EMPTY_GROUPS_FILES), "on": list(EMPTY_GROUPS_FILES)}


PASSING_ROWS_FILES = ("table.js", "tables.js", "base.js", "tables.css", "base.schema.json")


def test_the_passing_rows_part_ships_only_where_a_view_sets_the_option_and_strips_without_it() -> None:
    """features.py, the tables feature's part passing-rows: it ships where any view of a Base sets
    obsHtml.passing, and without it the files the renderer embeds carry none of its regions (the JSON
    line region of the schema included), so such an artifact is what it was."""
    part = next(part for feature in FEATURES if feature.key == "tables" for part in feature.parts
                if part.key == "passing-rows")
    assert part.option == ()
    for name in PASSING_ROWS_FILES:
        plain_source, kept = feature_source(name), feature_source(name, ["passing-rows"])
        assert "passing" not in plain_source.lower(), name
        assert kept != plain_source and "showEmptyGroups" not in kept, name
    assert "passing" not in json.dumps(json.loads(feature_source("base.schema.json")))
    passing = {"filters": 'status == "verified"', "label": "verified"}
    shipped = {}
    for label, source in (("off", _grouped_table()), ("on", _grouped_table(passing=passing))):
        html = render(source, ROWS_OFF)
        shipped[label] = [name for name in PASSING_ROWS_FILES if feature_source(name, ["passing-rows"]) in html]
    assert shipped == {"off": [], "on": list(PASSING_ROWS_FILES)}


DETAIL_FIELDS_FILES = ("table.js", "tables.js", "base.schema.json")


@pytest.mark.parametrize("detail_fields", [[], ["date"]])
def test_the_detail_fields_part_ships_where_a_view_sets_the_option_and_strips_without_it(detail_fields) -> None:
    """features.py, the tables feature's part detail-fields: it ships where any view of a Base sets
    obsHtml.detailFields (an empty list too), and without it the files the renderer embeds carry
    none of its regions, so such an artifact is what it was. A value its schema line refuses fails
    the build (test_a_detail_fields_value_its_schema_line_refuses_fails_the_build)."""
    part = next(part for feature in FEATURES if feature.key == "tables" for part in feature.parts
                if part.key == "detail-fields")
    assert part.option == ()
    for name in DETAIL_FIELDS_FILES:
        plain_source, kept = feature_source(name), feature_source(name, ["detail-fields"])
        assert "detail-fields" not in plain_source and "detailFields" not in plain_source, name
        assert "chosenDetailEntries" not in plain_source, name
        assert kept != plain_source and "showEmptyGroups" not in kept and "passing" not in kept.lower(), name
    shipped = {}
    for label, source in (("off", _grouped_table()), ("on", _grouped_table(detailFields=detail_fields))):
        html = render(source, ROWS_OFF)
        shipped[label] = [name for name in DETAIL_FIELDS_FILES if feature_source(name, ["detail-fields"]) in html]
    assert shipped == {"off": [], "on": list(DETAIL_FIELDS_FILES)}


def test_a_detail_fields_value_its_schema_line_refuses_fails_the_build() -> None:
    """The build holds obsHtml.detailFields to its schema line, as the browser does (input-model.md,
    Compact declarative table presentation)."""
    with pytest.raises(InputError) as failure:
        render(_grouped_table(detailFields="date"), CONFIG)
    assert (failure.value.source, failure.value.field) == ("chapter one", "base.views[1].obsHtml.detailFields")


LIVE_DECLARATION = __import__("yaml").safe_load(re.search(r"```yaml\n(.*?)```", (
    ROOT / "spec" / "capabilities" / "live-data.md").read_text(encoding="utf-8"), re.S)[1])["obsHtml"]["liveSource"]
"""The live-data capability note's example declaration."""


def test_the_live_source_part_ships_only_where_a_base_declares_it_and_strips_without_it() -> None:
    """features.py, the tables feature's part live-source: it ships live-data.js and tables.js's
    live-source region where a Base declares obsHtml.liveSource, and without it the HTML holds
    neither, so a Base without the option renders as it did (generic-tables.md, Current data)."""
    part = next(part for feature in FEATURES if feature.key == "tables" for part in feature.parts
                if part.key == "live-source")
    assert (part.option, part.code) == ((), ("live-data.js",))
    assert next(feature for feature in FEATURES if feature.key == "tables").canary is None
    plain_source, kept = feature_source("tables.js"), feature_source("tables.js", ["live-source"])
    assert "live-source" not in plain_source and "obsLiveData" not in plain_source and "liveTables" not in plain_source
    assert kept != plain_source and "showEmptyGroups" not in kept and "passing" not in kept.lower()
    assert feature_source("tables.js", TABLES_PARTS) == SOURCE.joinpath("tables.js").read_text(encoding="utf-8")
    pure = feature_source("live-data.js")
    live = _grouped_table()
    live["chapters"][0]["content"][1]["attrs"]["spec"]["obsHtml"] = {"liveSource": LIVE_DECLARATION}
    off, on = render(_grouped_table(), ROWS_OFF), render(live, ROWS_OFF)
    assert "obsLiveData" not in off and "live-source" not in off and plain_source in off
    assert pure in on and kept in on and plain_source not in on


LIVE_FILES = ("tables.js", "table.js", "artifact.js", "pages.js", "bars/comments.js", "tables.css")
"""The files whose live-source regions the part ships: the table code, the page's own scripts that
listen to a table's rows and the status line's styles (generic-tables.md, Projection)."""


def test_the_live_source_part_strips_from_every_file_that_holds_its_regions() -> None:
    """Without obsHtml.liveSource the page ships no live-source region, artifact.js included: each
    file as feature_source gives it, which is the file with the part's regions removed, holds none of
    the part's names, and the rendered page holds each file exactly so (features.py, Part)."""
    names = ("part live-source", "ownerOf", "obs-table-rows-change", "liveRevision", "data-table-live-status",
             "liveNoteRow", "tableRowsChange")
    plain, live = _grouped_table(), _grouped_table()
    live["chapters"][0]["content"][1]["attrs"]["spec"]["obsHtml"] = {"liveSource": LIVE_DECLARATION}
    off, on = render(plain, ROWS_OFF), render(live, ROWS_OFF)
    for name in LIVE_FILES:
        source = SOURCE.joinpath(*name.split("/")).read_text(encoding="utf-8")
        stripped, kept = feature_source(name), feature_source(name, ["live-source"])
        assert "part live-source" in source, name
        others = sorted({key for match in PART_REGION.finditer(source)
                         for key in [match["line"] or match["inline"] or match["json"]]} - {"live-source"})
        assert feature_source(name, others) == PART_REGION.sub(lambda region: region[0] if (
            region["line"] or region["inline"] or region["json"]) != "live-source" else "", source), name
        assert not [word for word in names if word in stripped], name
        assert kept != stripped and "part live-source" in kept, name
        assert stripped in off and stripped not in on and kept in on, name
    assert "obs-table-rows-change" not in off


def test_every_row_owner_site_of_the_tables_reads_through_owner_of() -> None:
    """generic-tables.md, Projection, One owner lookup: with the part shipped, every lookup of a
    row's canonical note in tables.js is the canonical argument of ownerOf, so a live table's
    projected note wins wherever its row is read. The two exceptions read the build's own rows on
    purpose: livePopulation, the check of a declaration, and savedLiveRows, the rows a read is laid over."""
    source = feature_source("tables.js", TABLES_PARTS)
    canonical = [re.search(rf"const {name} = \(?\)?.*?\n    \}}\)?\)?;\n", source, re.S).span()
                 for name in ("livePopulation", "savedLiveRows")]
    lookups = [match.start() for match in re.finditer(re.escape("recordsBySlug.get(row.noteId)"), source)]
    outside = [source.count("\n", 0, start) + 1 for start in lookups
               if not re.search(r"ownerOf\(row, [\w.]+, (?:/\* \} part live-source \*/)?$", source[:start])
               and not any(begin <= start < end for begin, end in canonical)]
    assert len(lookups) >= 14 and outside == []


ROWS_PARTS = {"table-rows-one-line": (("table.js", "tables.js", "tables.css"), with_guided_card),
              "pipe-table-rows-one-line": (("pipe-tables.js", "base.css", "artifact.js", "bars/comments.js"),
                                           with_pipe_table)}
"""Each part artifact.tableRowsOneLine turns on, the files that hold its code or regions and a page with its kind
of table (generic-tables.md, Columns and cells, One line per row; Pipe tables)."""


@pytest.mark.parametrize("key", sorted(ROWS_PARTS))
def test_a_one_line_part_ships_as_packaged_with_its_kind_of_table_and_strips_with_the_option_false(key) -> None:
    """features.py: artifact.tableRowsOneLine, on in the packaged cfg.json by the owner's decision of 17 Nov
    2026, ships each part on a page with its kind of table; false, the page carries none of its regions
    (pipe-tables.js not at all), and a page with neither kind of table ships neither part."""
    part = next(part for feature in FEATURES for part in feature.parts if part.key == key)
    assert part.option == ("tableRowsOneLine",)
    assert CONFIG.artifact["tableRowsOneLine"] is True and part.enabled(CONFIG.artifact)
    assert not part.enabled(ROWS_OFF.artifact)
    names, source = ROWS_PARTS[key]
    on, off, neither = render(source(), CONFIG), render(source(), ROWS_OFF), render(plain(), CONFIG)
    model = decode_artifact_data(on)
    shipped = [item.key for feature in FEATURES for item in feature.shipped(model, False, CONFIG.artifact)]
    assert key in shipped
    for name in names:
        whole, stripped = feature_source(name, shipped), feature_source(name, [item for item in shipped if item != key])
        assert f"part {key}" in SOURCE.joinpath(*name.split("/")).read_text(encoding="utf-8") or part.code == (name,)
        assert whole != stripped or name in part.code, name
        assert whole in on, name
        if name in part.code:
            assert whole not in off and whole not in neither, name
        else:
            assert stripped in off and whole not in off and f"part {key}" not in off, name
    assert f"part {key}" not in neither and "obsPipeTables" not in neither and "data-rows-one-line" not in neither
