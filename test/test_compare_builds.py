"""The comparison of two builds of an artifact, test/compare_builds.py: issue compare-two-builds."""
import pytest

from artifacts import artifact_html
from compare_builds import compare, main
from documents import chapter, document, paragraph
from obs_html.artifact_data import ARTIFACT_PATTERN, decode_artifact_data, encode_artifact_data
from obs_html.errors import InputError

ISLAND = "script#artifact-data"


@pytest.fixture(scope="module")
def built() -> str:
    return artifact_html(document("Builds", chapter("alpha", "Alpha", paragraph("One.")),
                                  chapter("beta", "Beta", paragraph("Two.")),
                                  chapter("gamma", "Gamma", paragraph("Three."))))


def stored(artifact: str, data: dict, compression: str) -> str:
    """``artifact`` with ``data`` as its island, stored as ``compression`` says."""
    island = encode_artifact_data(data, compression)
    return ARTIFACT_PATTERN.sub(lambda _: island, artifact, count=1)


def edited(artifact: str, edit, compression: str = "gzip") -> tuple[str, str]:
    """The artifact before and after ``edit`` changes its decoded data, both stored as ``compression``."""
    data = decode_artifact_data(artifact)
    before = stored(artifact, data, compression)
    edit(data)
    return before, stored(artifact, data, compression)


def note(data: dict, slug: str) -> dict:
    return next(item for item in data["notes"] if item["slug"] == slug)


def test_equal_builds_are_identical(built, tmp_path):
    assert compare(built, built) == ["identical"]
    (tmp_path / "a.html").write_text(built, encoding="utf-8")
    (tmp_path / "b.html").write_text(built, encoding="utf-8")
    assert main([str(tmp_path / "a.html"), str(tmp_path / "b.html")]) == 0


def test_a_page_change_outside_the_data_is_a_diff(built, tmp_path):
    after = built.replace("</body>", "<p>added</p>\n</body>", 1)
    lines = compare(built, after)
    assert lines[0] == "page:"
    assert "+<p>added</p>" in lines
    assert lines[-1] == "data: same"
    (tmp_path / "a.html").write_text(built, encoding="utf-8")
    (tmp_path / "b.html").write_text(after, encoding="utf-8")
    assert main([str(tmp_path / "a.html"), str(tmp_path / "b.html")]) == 1


@pytest.mark.parametrize("compression", ["gzip", "none"])
def test_a_changed_note_names_its_slug_and_fields(built, compression):
    before, after = edited(built, lambda data: note(data, "beta").update(html="<p>Changed.</p>"), compression)
    assert f'data-compression="{compression}"' in ARTIFACT_PATTERN.search(after)[1]
    assert compare(before, after) == ["page: same", "data:", "  notes: changed", "    beta: changed: html"]


def test_added_and_removed_notes_follow_after_then_before(built):
    def edit(data):
        removed = note(data, "alpha")
        data["notes"].remove(removed)
        data["notes"].append({**note(data, "gamma"), "slug": "delta"})
    before, after = edited(built, edit)
    assert compare(before, after)[3:] == ["    delta: added", "    alpha: removed"]


def test_top_level_keys_added_removed_and_changed_in_sorted_order(built):
    def edit(data):
        data["zzz"] = 1
        del data["notes"]
        data["document"] = {**data["document"], "extra": True}
    before, after = edited(built, edit)
    assert compare(before, after) == ["page: same", "data:", "  document: changed", "  notes: removed",
                                      "  zzz: added"]


def test_unreadable_data_names_its_artifact(built, tmp_path, capsys):
    without = ARTIFACT_PATTERN.sub("", built, count=1)
    with pytest.raises(InputError) as raised:
        compare(built, without, ("old.html", "new.html"))
    assert (raised.value.source, raised.value.field) == ("new.html", ISLAND)
    (tmp_path / "a.html").write_text(built, encoding="utf-8")
    (tmp_path / "b.html").write_text(without, encoding="utf-8")
    assert main([str(tmp_path / "a.html"), str(tmp_path / "b.html")]) == 2
    error = capsys.readouterr().err.splitlines()
    assert len(error) == 1 and error[0].startswith(f"{tmp_path / 'b.html'}: {ISLAND}: ")
    assert main([str(tmp_path / "a.html"), str(tmp_path / "missing.html")]) == 2
    error = capsys.readouterr().err.splitlines()
    assert len(error) == 1 and error[0].startswith(f"{tmp_path / 'missing.html'}: ")
