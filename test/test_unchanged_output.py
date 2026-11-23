"""The check that a change leaves obs's reference pages as they were, test/unchanged_output.py:
issue unchanged-output-check."""
import json
from pathlib import Path, PurePosixPath

import pytest

import conftest
import unchanged_output
from artifacts import artifact_html
from compare_builds import compare
from documents import chapter, document, paragraph
from unchanged_output import (CORE, SIDE, BuildError, Page, build, check, core_files, machine_folder, paired,
                              reference_set, report, side_files)

# This checkout's root, as test/unchanged_output.py takes a side's root.
CHECKOUT = Path(__file__).resolve().parents[1]
FIXTURES = unchanged_output.DOCUMENTS
DECK = unchanged_output.CORE_DECKS["bless-deck"]


def page(name: str) -> Page:
    return next(item for item in reference_set(side_files(CHECKOUT)) if item.name == name)


@pytest.fixture(scope="module")
def artifact() -> str:
    return artifact_html(document("Pages", chapter("alpha", "Alpha", paragraph("One."))))


def test_the_core_is_the_checkout_the_tests_read():
    assert unchanged_output.CORE_ROOT == conftest.CORE_ROOT


def test_the_set_is_every_fixture_document_both_decks_and_both_specs():
    pages = reference_set(side_files(CHECKOUT), core_files(unchanged_output.CORE_ROOT))
    documents = {path.stem: ("document", FIXTURES / path.name, SIDE)
                 for path in (CHECKOUT / "test" / "fixtures" / "documents").glob("*.json")}
    assert documents and "structural" in documents
    assert {item.name: (item.kind, item.source, item.origin) for item in pages} == {
        "bless-deck": ("deck", PurePosixPath("spec/examples/bless-deck/manifest.md"), CORE),
        "phone-deck": ("deck", PurePosixPath("test/fixtures/phone-deck/manifest.md"), SIDE),
        **documents,
        "obs-spec": ("spec", PurePosixPath("spec/manifest.md"), CORE),
        "adapter-spec": ("adapter-spec", PurePosixPath("spec/manifest.md"), SIDE)}
    assert [item.name for item in pages][:2] == ["bless-deck", "phone-deck"]
    assert [item.name for item in pages][-2:] == ["obs-spec", "adapter-spec"]
    roots = {SIDE: CHECKOUT, CORE: unchanged_output.CORE_ROOT}
    assert all((roots[item.origin] / item.source).is_file() for item in pages)


def test_the_set_holds_only_what_a_side_and_the_core_have():
    files = [FIXTURES / "only.json", FIXTURES / "notes.txt", unchanged_output.ADAPTER_SPEC_SOURCE, DECK]
    assert [(item.name, item.kind, item.origin) for item in reference_set(files)] == [
        ("only", "document", SIDE), (unchanged_output.ADAPTER_SPEC, "adapter-spec", SIDE)]
    assert [(item.name, item.kind, item.origin) for item in reference_set([], [unchanged_output.OBS_SPEC_SOURCE])] == [
        (unchanged_output.OBS_SPEC, "spec", CORE)]
    assert reference_set([]) == []


def test_every_page_the_same_exits_0():
    assert report([("alpha", "<p>a</p>", "<p>a</p>"), ("beta", "<p>b</p>", "<p>b</p>")]) == (
        ["same alpha", "same beta", "2 same, 0 differ"], 0)


def test_a_page_that_differs_carries_compares_report_indented(artifact):
    after = artifact.replace("</body>", "<p>added</p>\n</body>", 1)
    lines, code = report([("alpha", artifact, after), ("beta", "b", "b")])
    shown = compare(artifact, after, names=("base/alpha.html", "head/alpha.html"))
    assert lines == ["differs alpha", *(f"  {line}" for line in shown), "same beta", "1 same, 1 differ"]
    assert "  +<p>added</p>" in lines
    assert code == 1


def test_a_page_only_one_side_has_is_added_or_removed():
    assert report([("new", None, "<p>n</p>"), ("old", "<p>o</p>", None), ("kept", "k", "k")]) == (
        ["added new", "removed old", "same kept", "1 same, 2 differ"], 1)


def test_the_pairs_follow_the_sets_order():
    core = [unchanged_output.OBS_SPEC_SOURCE]
    base = reference_set([FIXTURES / "a.json", FIXTURES / "c.json"], core)
    head = reference_set([FIXTURES / "b.json", FIXTURES / "c.json"], core)
    assert [(name, before is not None, after is not None) for name, before, after in paired(base, head)] == [
        ("a", True, False), ("b", False, True), ("c", True, True), (unchanged_output.OBS_SPEC, True, True)]


def fake_sides(tmp_path: Path, base: list[PurePosixPath], head: list[PurePosixPath],
               core: list[PurePosixPath] = ()) -> dict[str, Path]:
    """Each side's root with ``base``'s and ``head``'s files, and the core with ``core``'s, which
    unchanged_output reads as CORE_ROOT until the test ends."""
    sides = {}
    for side, files in (("base", base), ("head", head), ("core", core)):
        (tmp_path / side).mkdir()
        for file in files:
            (tmp_path / side / file).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / side / file).write_text("{}", encoding="utf-8")
        sides[side] = tmp_path / side
    return sides


@pytest.fixture
def fake_core(tmp_path, monkeypatch) -> Path:
    """An empty core of the test's own as unchanged_output's CORE_ROOT; fake_sides fills it."""
    monkeypatch.setattr(unchanged_output, "CORE_ROOT", tmp_path / "core")
    return tmp_path / "core"


def test_check_builds_each_side_from_its_root_and_reports(tmp_path, artifact, fake_core):
    sides = fake_sides(tmp_path, [FIXTURES / "a.json", FIXTURES / "b.json"], [FIXTURES / "a.json", FIXTURES / "c.json"],
                       [DECK])
    built = []

    def fake_build(page: Page, root: Path, folder: Path, side: str) -> Path:
        built.append((page.name, root, side))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{page.name}.html").write_text(artifact, encoding="utf-8")
        return folder / f"{page.name}.html"

    lines, code = check({side: sides[side] for side in ("base", "head")}, tmp_path / "out", fake_build)
    assert lines == ["same bless-deck", "same a", "removed b", "added c", "2 same, 2 differ"]
    assert code == 1
    assert sorted(built) == [("a", sides["base"], "base"), ("a", sides["head"], "head"),
                             ("b", sides["base"], "base"), ("bless-deck", sides["base"], "base"),
                             ("bless-deck", sides["head"], "head"), ("c", sides["head"], "head")]
    assert (tmp_path / "out" / "base" / "a.html").is_file() and (tmp_path / "out" / "head" / "a.html").is_file()


def test_a_failed_build_exits_2_naming_the_page_and_the_side(tmp_path, fake_core):
    sides = fake_sides(tmp_path, [FIXTURES / "a.json"], [FIXTURES / "a.json"])

    def failing(page: Page, root: Path, folder: Path, side: str) -> Path:
        raise BuildError(page.name, side, "the last line")

    lines, code = check({side: sides[side] for side in ("base", "head")}, tmp_path / "out", failing)
    assert code == 2
    [line] = lines
    assert all(part in line for part in ("a", "base", "the last line"))


def test_a_build_that_fails_names_the_page_the_side_and_its_last_error_line(tmp_path):
    (tmp_path / "no-project").mkdir()
    with pytest.raises(BuildError) as raised:
        build(page("structural"), tmp_path / "no-project", tmp_path / "out", "base")
    assert (raised.value.page, raised.value.side) == ("structural", "base")
    assert raised.value.detail and "\n" not in raised.value.detail


def test_the_build_step_builds_one_document_twice_alike(tmp_path):
    first, second = (build(page("structural"), CHECKOUT, tmp_path / side, "head").read_text(encoding="utf-8")
                     for side in ("first", "second"))
    assert report([("structural", first, second)]) == (["same structural", "1 same, 0 differ"], 0)


def test_a_side_builds_with_its_checkout_installed_as_obs_html_as_the_tests_install_it(tmp_path):
    machine = machine_folder(CHECKOUT, tmp_path / "head")
    assert machine == tmp_path / "head" / unchanged_output.MACHINE
    assert sorted(path.name for path in (machine / "components").iterdir()) == ["obs-html", "obs-html-style-generic"]
    assert (machine / "components" / "obs-html").resolve() == CHECKOUT.resolve()
    listed = json.loads((machine / "components.json").read_text(encoding="utf-8"))
    assert listed == json.loads((conftest.MACHINE / "components.json").read_text(encoding="utf-8"))
    assert machine_folder(CHECKOUT, tmp_path / "head") == machine
    assert unchanged_output._environment(CHECKOUT, machine)["OBS_LOCAL_FOLDER"] == str(machine)


def test_a_side_from_before_the_rename_is_installed_as_the_component_its_adapter_json_names(tmp_path):
    """A base from before the component took its repository's name declares html; it is installed,
    and built, as html, so the comparison still builds it."""
    old = tmp_path / "old-side"
    old.mkdir()
    (old / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    (old / "adapter.json").write_text(json.dumps({"name": "html"}), encoding="utf-8")
    machine = machine_folder(old, tmp_path / "base")
    assert sorted(path.name for path in (machine / "components").iterdir()) == ["html", "obs-html-style-generic"]
    [entry, _style] = json.loads((machine / "components.json").read_text(encoding="utf-8"))["components"]
    assert entry["name"] == unchanged_output.component(old) == "html"


def test_a_side_without_a_project_version_fails_naming_its_pyproject(tmp_path):
    (tmp_path / "no-project").mkdir()
    with pytest.raises(BuildError) as raised:
        build(page("phone-deck"), tmp_path / "no-project", tmp_path / "out", "head")
    assert "pyproject.toml" in raised.value.detail and raised.value.side == "head"


def test_a_deck_builds_through_the_core_with_the_sides_checkout(tmp_path):
    html = build(page("phone-deck"), CHECKOUT, tmp_path / "head", "head").read_text(encoding="utf-8")
    assert "<html" in html
