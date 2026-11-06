import re
from pathlib import Path

from structure.naming import says_document_presentation

ROOT = Path(__file__).parents[2]


def test_artifact_ui_alone_owns_what_counts_as_a_change() -> None:
    design = ROOT / "spec"
    artifact_ui = (design / "artifact-ui.md").read_text(encoding="utf-8")
    input_model = (design / "input-model.md").read_text(encoding="utf-8")
    rule = artifact_ui.split("## What counts as a change", 1)[1].split("\n## ", 1)[0]

    for reader_state in ("filters", "view selections", "table columns", "sorting", "open or closed panels"):
        assert reader_state in rule
    assert "Reader state is never a change" in rule
    assert "persisted reader-state changes all participate" not in artifact_ui
    assert "[[artifact-ui#What counts as a change" in input_model
    for restatement in ("Persisted reader-state changes do", "changed-HTML state", "as changed.", "or an artifact change"):
        assert restatement not in input_model


def test_width_rule_has_one_owner() -> None:
    design = ROOT / "spec"
    input_model = (design / "input-model.md").read_text(encoding="utf-8")

    assert "column or width changes" not in input_model

    generic_tables = (design / "generic-tables.md").read_text(encoding="utf-8")
    assert "never mark the" not in generic_tables
    assert "never show the change notice" not in generic_tables
    assert "[[artifact-ui#What counts as a change" in generic_tables


WIDTH_CLASSIFICATION = re.compile(r"widths?\b[^.]*session-only|session-only[^.]*\bwidths?\b", re.IGNORECASE)


def test_exactly_one_note_classifies_resized_widths() -> None:
    notes = sorted(path for path in (ROOT / "spec").rglob("*.md") if "design_output" not in path.parts)
    classifying = [path.relative_to(ROOT).as_posix() for path in notes
                   if WIDTH_CLASSIFICATION.search(" ".join(path.read_text(encoding="utf-8").split()))]
    assert classifying == ["spec/artifact-ui.md"], (
        f"{classifying}: state the width classification only in artifact-ui#What counts as a change "
        "and link [[artifact-ui#What counts as a change]] elsewhere"
    )

    design = ROOT / "spec"
    artifact_ui = (design / "artifact-ui.md").read_text(encoding="utf-8")
    rule = artifact_ui.split("## What counts as a change", 1)[1].split("\n## ", 1)[0]
    assert "table columns and their widths" not in rule
    flat = " ".join(artifact_ui.split())
    assert flat.count("session-only view state") == 1
    assert "resized widths are session-only" not in flat
    assert " a artifact" not in flat
    assert "session-only view state" in " ".join(rule.split())
    for note in ("input-model.md", "generic-tables.md"):
        assert "[[artifact-ui#What counts as a change" in (design / note).read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    return text.split(f"\n{heading}\n", 1)[1].split("\n## ", 1)[0]


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_top_band_is_one_row_of_equal_squares() -> None:
    artifact_ui = (ROOT / "spec" / "artifact-ui.md").read_text(encoding="utf-8")
    shell = _flat(_section(artifact_ui, "## Reading shell"))

    assert "The top band is one row and holds every top control: Home, the breadcrumbs, " \
        "the frontmatter chevron, the notice icons and the menu." in shell
    assert "Home, the breadcrumbs, the chapter controls," not in shell, (
        "artifact-ui.md, Reading shell: the top band names the frontmatter chevron, not 'the chapter controls'")
    assert "The notice icons sit directly left of the menu." in shell
    assert "Every control in the band is a square of one size." in shell
    assert "No control takes a row of its own." in shell
    for replaced in ("A compact menu button floats at the top-right", "Breadcrumbs occupy that same top band"):
        assert replaced not in _flat(artifact_ui), f"artifact-ui.md: replace '{replaced}' with the one-row top band"


def test_notice_icons_point_to_the_top_band() -> None:
    artifact_ui = _flat((ROOT / "spec" / "artifact-ui.md").read_text(encoding="utf-8"))

    assert "The icon row never covers the menu or chapter controls." not in artifact_ui
    assert "The icons sit in the [[#Reading shell|top band]]." in artifact_ui


def test_no_text_appears_twice_in_one_view_is_stated_once() -> None:
    artifact_ui = _flat((ROOT / "spec" / "artifact-ui.md").read_text(encoding="utf-8"))
    rule = "No text appears twice in one view."

    assert artifact_ui.count(rule) == 1
    after = artifact_ui.split(rule, 1)[1]
    assert after.startswith(" The title page shows the document type once, under the title; "
                            "it has no running header that repeats it. "
                            "A chapter's running header never repeats its own visible heading.")


def test_only_used_features_ship_and_canaries_decide_or_stay_silent() -> None:
    artifact_ui = _flat((ROOT / "spec" / "artifact-ui.md").read_text(encoding="utf-8"))
    notice_center = _flat(_section((ROOT / "spec" / "artifact-ui.md").read_text(encoding="utf-8"),
                                   "## Dock menu"))

    for replaced in ("a refused or unknown result counts as limited",
                     "Each capability canary that reports limited raises its own warning entry",
                     "(history updates, storage, printing, modal dialogs, downloads, clipboard, popups)",
                     "run before any feature is used"):
        assert replaced not in artifact_ui, (
            f"artifact-ui.md: replace '{replaced}' with the feature model and canary rule of the notice center")
    for rule in (
        "The artifact includes a host-dependent feature, with its code, controls and canary, only when "
        "its Document uses it or the artifact always offers it. A feature that is not included raises nothing.",
        "A canary decides or stays silent.",
        "A canary that observes a refusal raises one warning entry: the feature, why the host refuses it, "
        "what was observed and the remedy,",
        "A canary that cannot decide raises nothing at load. The feature is tried on use, and an observed "
        "failure then shows the reason and remedy inline and raises the warning.",
        "Where a failure cannot be observed even on use, there is no notice; the control's help text "
        "names the remedy.",
        "No feature uses a browser dialog; its messages are inline.",
        "The registry and its entries are owned by obs-html's `features.py`; the list of abilities "
        "is not repeated here.",
    ):
        assert rule in notice_center, f"artifact-ui.md, Dock menu: state '{rule}' in the notice center"


def test_no_heading_or_link_says_document_presentation() -> None:
    assert says_document_presentation("spec/artifact-ui.md") == []


READER_TEXT_RULE = "Reader-facing text names no kind"
ERROR_RULE = "An error message the artifact shows names its source and a remedy"


def test_reader_facing_text_and_error_rules_are_stated_once() -> None:
    flat = " ".join((ROOT / "spec" / "artifact-ui.md").read_text(encoding="utf-8").split())
    section = flat.split("## Reader-facing text", 1)[1].split(" ## ", 1)[0]

    for rule in (READER_TEXT_RULE, ERROR_RULE):
        assert rule in section
        assert flat.count(rule) == 1
    for label in ('"Search"', '"Filter"', '"Untitled"'):
        assert label in section


def test_artifact_ui_names_the_runtime_selection_resolver() -> None:
    """obs's quality note leaves the runtime's selection resolver to the adapter's specification."""
    artifact_ui = (ROOT / "spec" / "artifact-ui.md").read_text(encoding="utf-8")
    rule = next(paragraph for paragraph in artifact_ui.split("\n\n") if "selection resolver" in paragraph)
    assert "`obsQuery.propertyTexts`" in rule
    for consumer in ("count", "distinct", "drill-down"):
        assert consumer in rule
