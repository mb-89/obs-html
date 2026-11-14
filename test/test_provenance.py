"""The provenance check of a built artifact (src/obs_html/provenance.py; architecture.md, Provenance
check): built HTML in, findings out, each naming its place; the build warns of them by default and
refuses them with artifact.refuseProvenance."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from artifacts import artifact_html
from conftest import CORE_ROOT, ROOT
from documents import chapter, document, heading, paragraph
from obs_html import cli, provenance
from obs_html.errors import InputError
from obs_html.provenance import Finding, findings, local_list, local_terms, reported

OWNER = "architecture.md, Provenance check"
PLANTED = ("Built in /home/someone/vault, from https://claude.ai/code/session_PLANTEDabc123 "
           "and session_OTHERxyz789, at 2026-11-14T10:18:33Z, by Codename Kestrel.")
FIXTURES = ROOT / "test" / "fixtures" / "documents"
DECK = CORE_ROOT / "spec" / "examples" / "bless-deck" / "manifest.md"


def planted(text: str = PLANTED) -> dict:
    return document("Planted", chapter("one", "One", heading(1, "One"), paragraph(text)))


def test_it_finds_a_planted_path_session_and_date_each_naming_its_place() -> None:
    found = reported(findings(artifact_html(planted())))
    labels = {finding.label for finding in found}
    assert labels == {"absolute-path", "session-url", "session-id", "timestamp"}
    # Each is found where the chapter's text is: in the decoded data island, by its field path.
    assert all(finding.where.startswith("artifact-data ") for finding in found)
    assert all(finding.exemption is None for finding in found)


def test_a_session_url_is_one_finding_not_also_its_session_id() -> None:
    found = findings(artifact_html(planted("See https://claude.ai/code/session_ONLYurl12345 here.")))
    assert [finding.label for finding in reported(found)] == ["session-url"]


def test_a_term_of_the_local_list_is_found_by_its_line_never_by_its_text(tmp_path: Path) -> None:
    listing = tmp_path / provenance.LOCAL_FILE
    listing.write_text("# private terms\n\noff:some-public-label  # not this check's\nkestrel\n", encoding="utf-8")
    nested = tmp_path / "vault" / "notes"
    nested.mkdir(parents=True)
    assert local_list(nested) == listing  # the nearest one, up from the vault
    terms = local_terms(local_list(nested))
    assert [label for label, _ in terms] == ["local-term:4"]
    found = reported(findings(artifact_html(planted()), terms))
    assert "local-term:4" in {finding.label for finding in found}
    assert all("estrel" not in str(finding) for finding in found)


def test_an_invalid_local_term_names_its_line(tmp_path: Path) -> None:
    listing = tmp_path / provenance.LOCAL_FILE
    listing.write_text("fine\n(unclosed\n", encoding="utf-8")
    with pytest.raises(InputError) as caught:
        local_terms(listing)
    assert (caught.value.source, caught.value.field) == (str(listing), "line 2")


def test_without_a_local_list_there_are_no_local_terms() -> None:
    assert local_terms(None) == ()


@pytest.mark.parametrize("name", ["pugh", "decision-verdict", "features"])
def test_an_existing_deck_shows_only_the_documented_exemption(name: str, tmp_path: Path, capsys) -> None:
    """A committed fixture deck (its Document, as the core built it), built by the CLI: only obs's own
    build time, under its exemption, and no warning."""
    destination = tmp_path / f"{name}.html"
    assert cli.main([str(FIXTURES / f"{name}.json"), str(destination)]) == 0
    found = findings(destination.read_text(encoding="utf-8"))
    assert reported(found) == [] and "carries provenance" not in capsys.readouterr().err
    assert found == [Finding(provenance.GENERATION_TIMESTAMP, "timestamp", "generation-timestamp")]


def test_the_example_bless_deck_shows_only_the_documented_exemption(tmp_path: Path, capsys) -> None:
    """obs's example deck (spec/examples/bless-deck), its Document built by the core as
    test_bless_browser.py builds it, then the artifact by the CLI."""
    document = tmp_path / "deck.json"
    subprocess.run([sys.executable, "-m", "obs.document", "--source", str(DECK), "--document", str(document)],
                   check=True, capture_output=True)
    assert cli.main([str(document), str(tmp_path / "deck.html")]) == 0
    found = findings((tmp_path / "deck.html").read_text(encoding="utf-8"))
    assert "carries provenance" not in capsys.readouterr().err
    assert found == [Finding(provenance.GENERATION_TIMESTAMP, "timestamp", "generation-timestamp")]


def test_a_vendored_librarys_own_lines_are_exempt_by_name() -> None:
    html = artifact_html(planted()).replace(
        "<body>", '<body>\n<script id="plotly-script">var d = "2016-10-13 09:15:23";\n</script>', 1)
    vendored = [finding for finding in findings(html) if finding.exemption]
    assert {finding.exemption for finding in vendored} == {"generation-timestamp", "vendored-library:plotly-script"}


def build(tmp_path: Path, settings: dict, capsys) -> tuple[int, str]:
    source = tmp_path / "planted.json"
    source.write_text(json.dumps(planted()), encoding="utf-8")
    arguments = [str(source), str(tmp_path / "planted.html")]
    if settings:
        (tmp_path / "cfg.json").write_text(json.dumps({"artifact": settings}), encoding="utf-8")
        arguments = ["--config", str(tmp_path / "cfg.json"), *arguments]
    code = cli.main(arguments)
    return code, capsys.readouterr().err


def test_the_build_warns_of_each_finding_by_default_and_writes_the_artifact(tmp_path: Path, capsys) -> None:
    code, err = build(tmp_path, {}, capsys)
    assert code == 0 and (tmp_path / "planted.html").is_file()
    warnings = [line for line in err.splitlines() if line.startswith("Warning: obs-html artifact: ")]
    assert len(warnings) == 4 and all(OWNER in line for line in warnings)
    assert {re.search(r"\((\S+)\)", line)[1] for line in warnings} == {
        "absolute-path", "session-url", "session-id", "timestamp"}


def test_with_refuse_provenance_the_build_refuses_naming_each_place(tmp_path: Path, capsys) -> None:
    with pytest.raises(SystemExit) as stopped:
        build(tmp_path, {"refuseProvenance": True}, capsys)
    err = capsys.readouterr().err
    assert stopped.value.code != 0 and not (tmp_path / "planted.html").exists()
    assert "obs-html artifact: artifact-data " in err and OWNER in err
    assert err.count("carries provenance") == 4
