"""The check that a change leaves obs's reference pages as they were, test/unchanged_output.py:
issue unchanged-output-check."""
from pathlib import Path, PurePosixPath

import pytest

import unchanged_output
from artifacts import artifact_html
from compare_builds import compare
from documents import chapter, document, paragraph
from measure import artifact_bytes
from unchanged_output import BuildError, Page, build, check, paired, reference_set, report, side_files

# This checkout's root, as test/unchanged_output.py takes a side's root.
CHECKOUT = Path(__file__).resolve().parents[3]
FIXTURES = PurePosixPath(artifact_bytes.DOCUMENTS.relative_to(artifact_bytes.ROOT).as_posix())
SPECS = {unchanged_output.OBS_SPEC: unchanged_output.OBS_SPEC_SOURCE,
         unchanged_output.ADAPTER_SPEC: unchanged_output.ADAPTER_SPEC_SOURCE}


def page(name: str) -> Page:
    return next(item for item in reference_set(side_files(CHECKOUT)) if item.name == name)


@pytest.fixture(scope="module")
def artifact() -> str:
    return artifact_html(document("Pages", chapter("alpha", "Alpha", paragraph("One."))))


def test_the_set_is_every_fixture_document_both_decks_and_both_specs():
    pages = reference_set(side_files(CHECKOUT))
    documents = {path.stem: FIXTURES / path.name for path in artifact_bytes.DOCUMENTS.glob("*.json")}
    decks = {name: PurePosixPath((folder / "manifest.md").relative_to(artifact_bytes.ROOT).as_posix())
             for name, folder in artifact_bytes.DECKS.items()}
    assert {item.name: item.source for item in pages} == decks | documents | SPECS
    assert len(pages) == len(decks) + len(documents) + len(SPECS)


def test_the_set_holds_only_what_a_side_has():
    files = [FIXTURES / "only.json", FIXTURES / "notes.txt", unchanged_output.OBS_SPEC_SOURCE]
    assert [(item.name, item.kind) for item in reference_set(files)] == [
        ("only", "document"), (unchanged_output.OBS_SPEC, "spec")]
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
    base = reference_set([FIXTURES / "a.json", FIXTURES / "c.json", unchanged_output.OBS_SPEC_SOURCE])
    head = reference_set([FIXTURES / "b.json", FIXTURES / "c.json", unchanged_output.OBS_SPEC_SOURCE])
    assert [(name, before is not None, after is not None) for name, before, after in paired(base, head)] == [
        ("a", True, False), ("b", False, True), ("c", True, True), (unchanged_output.OBS_SPEC, True, True)]


def fake_sides(tmp_path: Path, base: list[PurePosixPath], head: list[PurePosixPath]) -> dict[str, Path]:
    sides = {}
    for side, files in (("base", base), ("head", head)):
        for file in files:
            (tmp_path / side / file).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / side / file).write_text("{}", encoding="utf-8")
        sides[side] = tmp_path / side
    return sides


def test_check_builds_each_side_from_its_root_and_reports(tmp_path, artifact):
    sides = fake_sides(tmp_path, [FIXTURES / "a.json", FIXTURES / "b.json"], [FIXTURES / "a.json", FIXTURES / "c.json"])
    built = []

    def fake_build(page: Page, root: Path, folder: Path, side: str) -> Path:
        built.append((page.name, root, side))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{page.name}.html").write_text(artifact, encoding="utf-8")
        return folder / f"{page.name}.html"

    lines, code = check(sides, tmp_path / "out", fake_build)
    assert lines == ["same a", "removed b", "added c", "1 same, 2 differ"]
    assert code == 1
    assert sorted(built) == [("a", sides["base"], "base"), ("a", sides["head"], "head"),
                             ("b", sides["base"], "base"), ("c", sides["head"], "head")]
    assert (tmp_path / "out" / "base" / "a.html").is_file() and (tmp_path / "out" / "head" / "a.html").is_file()


def test_a_failed_build_exits_2_naming_the_page_and_the_side(tmp_path):
    sides = fake_sides(tmp_path, [FIXTURES / "a.json"], [FIXTURES / "a.json"])

    def failing(page: Page, root: Path, folder: Path, side: str) -> Path:
        raise BuildError(page.name, side, "the last line")

    lines, code = check(sides, tmp_path / "out", failing)
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
