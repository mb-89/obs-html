"""The provenance check of a built artifact (src/obs_html/provenance.py; architecture.md, Provenance
check): built HTML in, findings out, each naming its place; the build warns of them by default and
refuses them with artifact.refuseProvenance. An exception (architecture.md, Exceptions) names a
finding by its label and digest, never by its text."""
import hashlib
import json
import os
import re
import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from types import SimpleNamespace

import pytest

from artifacts import artifact_html
from conftest import CORE_ROOT, ROOT, spec_build
from documents import chapter, document, heading, paragraph
from obs_html import artifact_data, cli, exposure, provenance, render as renderer
from obs_html.errors import InputError
from obs_html.provenance import CheckException, excepted, findings, local_list, local_terms, reported

OWNER = "architecture.md, Provenance check"
PLANTED = ("Built in /home/someone/vault, from https://claude.ai/code/session_PLANTEDabc123 "
           "and session_OTHERxyz789, at 2026-11-14T10:18:33Z, by Codename Kestrel.")
FIXTURES = ROOT / "test" / "fixtures" / "documents"
DECK = CORE_ROOT / "spec" / "examples" / "bless-deck" / "manifest.md"


def planted(text: str = PLANTED, *more: str) -> dict:
    """A page whose chapter "one" holds ``text``, and a chapter per further text."""
    return document("Planted", chapter("one", "One", heading(1, "One"), paragraph(text)),
                    *(chapter(f"more{n}", f"More {n}", heading(1, f"More {n}"), paragraph(extra))
                      for n, extra in enumerate(more, 1)))


def shown(found: list) -> list[tuple]:
    """What a finding shows of itself: its place, its label and the exemption that covers it."""
    return [(finding.where, finding.label, finding.exemption) for finding in found]


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
    assert shown(found) == [(provenance.GENERATION_TIMESTAMP, "timestamp", "generation-timestamp")]


def test_the_example_bless_deck_shows_only_the_documented_exemption(tmp_path: Path, capsys) -> None:
    """obs's example deck (spec/examples/bless-deck), its Document built by the core as
    test_bless_browser.py builds it, then the artifact by the CLI."""
    document = tmp_path / "deck.json"
    subprocess.run([sys.executable, "-m", "obs.document", "--source", str(DECK), "--document", str(document)],
                   check=True, capture_output=True)
    assert cli.main([str(document), str(tmp_path / "deck.html")]) == 0
    found = findings((tmp_path / "deck.html").read_text(encoding="utf-8"))
    assert "carries provenance" not in capsys.readouterr().err
    assert shown(found) == [(provenance.GENERATION_TIMESTAMP, "timestamp", "generation-timestamp")]


@pytest.mark.parametrize(("product_version", "expected_version"), [
    (None, "target-tag"),
    ("2.7.0", "2.7.0"),
], ids=["git-version", "declared-version"])
def test_a_build_resolves_generation_provenance_from_the_generator_and_target(
    tmp_path: Path, capsys, monkeypatch, product_version, expected_version
) -> None:
    source = tmp_path / "document.json"
    target_root = tmp_path / "target"
    target_root.mkdir()
    metadata = {"product": {"name": "Target"}}
    if product_version is not None:
        metadata["product"]["version"] = product_version
    source.write_text(json.dumps(document("Target", chapter("one", "One", paragraph("Content.")),
                                          metadata=metadata)), encoding="utf-8")
    def git_output(folder: Path, *arguments: str) -> str | None:
        folder = Path(folder).resolve()
        if arguments == ("rev-parse", "HEAD") and folder == target_root:
            return "target-commit"
        if arguments == ("describe", "--tags", "--always") and folder == target_root:
            return "target-tag"
        return None

    monkeypatch.setattr(renderer, "_generator_commit", lambda: "generator-commit", raising=False)
    monkeypatch.setattr(renderer, "_git_output", git_output, raising=False)
    destination = tmp_path / "artifact.html"

    assert cli.main(["--vault-root", str(target_root), str(source), str(destination)]) == 0

    generation = artifact_data.decode_artifact_data(destination.read_text(encoding="utf-8"))["document"]["generation"]
    assert generation["generator"]["commit"] == "generator-commit"
    assert generation["target"] == {
        "name": "Target", "version": expected_version, "commit": "target-commit",
    }
    assert "generation provenance" not in capsys.readouterr().err


def test_the_generation_record_names_each_component_that_built_the_page(tmp_path: Path, monkeypatch) -> None:
    """The page shows the Document's components as they are (artifact-ui, Generation provenance)."""
    built_by = [{"name": "html", "kind": "adapter", "version": "5.0.0", "commit": "ab" * 20},
                {"name": "paper", "kind": "style", "version": "1.2.3", "commit": "cd" * 20}]
    source = tmp_path / "document.json"
    source.write_text(json.dumps({**document("Target", chapter("one", "One", paragraph("Content."))),
                                  "components": built_by}), encoding="utf-8")
    monkeypatch.setattr(renderer, "_generator_commit", lambda: "generator-commit", raising=False)
    destination = tmp_path / "artifact.html"

    assert cli.main(["--vault-root", str(tmp_path), str(source), str(destination)]) == 0

    generation = artifact_data.decode_artifact_data(destination.read_text(encoding="utf-8"))["document"]["generation"]
    assert generation["components"] == built_by


def test_a_build_warns_when_no_generation_provenance_resolves(tmp_path: Path, capsys, monkeypatch) -> None:
    source = tmp_path / "document.json"
    target_root = tmp_path / "target"
    target_root.mkdir()
    source.write_text(json.dumps(document("Target", chapter("one", "One", paragraph("Content.")))),
                      encoding="utf-8")
    monkeypatch.setattr(renderer, "_generator_commit", lambda: None, raising=False)
    monkeypatch.setattr(renderer, "_git_output", lambda *_args: None, raising=False)

    assert cli.main(["--vault-root", str(target_root), str(source), str(tmp_path / "artifact.html")]) == 0

    error = capsys.readouterr().err
    artifact = (tmp_path / "artifact.html").read_text(encoding="utf-8")
    generation = artifact_data.decode_artifact_data(artifact)["document"]["generation"]
    assert generation["generator"]["commit"] == "unknown"
    assert generation["target"]["version"] == "unknown"
    assert generation["target"]["commit"] == "unknown"
    assert "generation provenance" in error and "Warning" in error


def test_git_output_observes_a_new_head_on_the_next_query(tmp_path: Path, monkeypatch) -> None:
    commits = iter(("first-commit", "second-commit"))
    calls = []

    def run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=next(commits))

    monkeypatch.setattr(renderer.subprocess, "run", run)

    assert renderer._git_output(tmp_path, "rev-parse", "HEAD") == "first-commit"
    assert renderer._git_output(tmp_path, "rev-parse", "HEAD") == "second-commit"
    assert len(calls) == 2


def test_generator_commit_uses_the_installed_vcs_commit(monkeypatch) -> None:
    commit = "ab" * 20
    installed = SimpleNamespace(read_text=lambda name: json.dumps({
        "url": "https://example.invalid/obs-html.git",
        "vcs_info": {"vcs": "git", "commit_id": commit},
    }))
    monkeypatch.setattr(renderer, "distribution", lambda _name: installed, raising=False)

    assert renderer._generator_commit() == commit


def test_generator_commit_is_unknown_without_installed_distribution(monkeypatch) -> None:
    def missing(_name: str):
        raise PackageNotFoundError("obs-html")

    monkeypatch.setattr(renderer, "distribution", missing, raising=False)

    assert renderer._generator_commit() is None


def test_generator_commit_uses_only_a_verified_obs_html_checkout(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "obs"
    source = root / "adapters" / "html"
    source.mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname = "obs"\n', encoding="utf-8")
    (source / "pyproject.toml").write_text('[project]\nname = "obs-html"\n', encoding="utf-8")
    installed = SimpleNamespace(read_text=lambda name: json.dumps({
        "url": source.as_uri(), "dir_info": {"editable": True},
    }))
    calls = []

    def git_output(folder: Path, *arguments: str) -> str | None:
        calls.append((Path(folder), arguments))
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(root)
        if arguments == ("rev-parse", "HEAD"):
            return "cd" * 20
        return None

    monkeypatch.setattr(renderer, "distribution", lambda _name: installed, raising=False)
    monkeypatch.setattr(renderer, "_git_output", git_output, raising=False)

    assert renderer._generator_commit() == "cd" * 20
    assert calls == [
        (source, ("rev-parse", "--show-toplevel")),
        (root, ("rev-parse", "HEAD")),
    ]


def test_generator_commit_never_uses_a_consumer_checkout(
    tmp_path: Path, monkeypatch
) -> None:
    consumer = tmp_path / "consumer"
    installed_package = consumer / ".venv" / "Lib" / "site-packages" / "obs_html"
    installed_package.mkdir(parents=True)
    installed = SimpleNamespace(read_text=lambda _name: None)
    monkeypatch.setattr(renderer, "__file__", str(installed_package / "render.py"))
    monkeypatch.setattr(renderer, "distribution", lambda _name: installed, raising=False)
    monkeypatch.setattr(
        renderer, "_git_output",
        lambda *_args: pytest.fail("the consumer Git root cannot identify the generator"), raising=False,
    )

    assert renderer._generator_commit() is None


def test_generator_commit_rejects_an_editable_package_inside_a_consumer(
    tmp_path: Path, monkeypatch
) -> None:
    consumer = tmp_path / "consumer"
    installed_package = consumer / ".venv" / "Lib" / "site-packages" / "obs_html"
    installed_package.mkdir(parents=True)
    installed = SimpleNamespace(read_text=lambda _name: json.dumps({
        "url": installed_package.as_uri(), "dir_info": {"editable": True},
    }))
    calls = []

    def git_output(folder: Path, *arguments: str) -> str | None:
        calls.append((Path(folder), arguments))
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(consumer)
        if arguments == ("rev-parse", "HEAD"):
            return "ef" * 20
        return None

    monkeypatch.setattr(renderer, "distribution", lambda _name: installed, raising=False)
    monkeypatch.setattr(renderer, "_git_output", git_output, raising=False)

    assert renderer._generator_commit() is None
    assert calls == [(installed_package, ("rev-parse", "--show-toplevel"))]


def test_generator_commit_does_not_read_noneditable_source_head(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "obs"
    source = root / "adapters" / "html"
    source.mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname = "obs"\n', encoding="utf-8")
    (source / "pyproject.toml").write_text('[project]\nname = "obs-html"\n', encoding="utf-8")
    installed = SimpleNamespace(read_text=lambda _name: json.dumps({
        "url": source.as_uri(), "dir_info": {},
    }))
    monkeypatch.setattr(renderer, "distribution", lambda _name: installed, raising=False)
    monkeypatch.setattr(
        renderer, "_git_output",
        lambda *_args: pytest.fail("a noneditable source path does not identify installed code"), raising=False,
    )

    assert renderer._generator_commit() is None


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


def test_the_adapters_own_specification_carries_no_provenance(tmp_path_factory) -> None:
    # The run's shared build of the adapter's specification, read only (test/spec_build.py).
    folder = spec_build.built(spec_build.base(tmp_path_factory), "adapter-spec")
    html = (folder / spec_build.adapter_spec_fence()[1]).read_text(encoding="utf-8")
    assert reported(findings(html)) == []


# Exceptions (architecture.md, Exceptions): a finding named by its label and digest, never its text.
EXCEPTIONS_OWNER = "architecture.md, Exceptions"
URL, SESSION_ID, TIME = "https://claude.ai/code/session_PLANTEDabc123", "session_OTHERxyz789", "2026-11-14T10:18"
PATH = PLANTED[PLANTED.index("/home"):PLANTED.index("/vault")]
"""The text each detector matches in PLANTED."""
LATER = "2026-11-15T09:40"
"""A second timestamp, which a place holds beside TIME."""
SECRETS = ("someone", "PLANTEDabc123", "OTHERxyz789", "2026-11-14", "2026-11-15", "10:18", "09:40", "estrel")
"""Every planted text: no warning, refusal or test name of exceptions holds any."""
ONE = "artifact-data notes[1].html"
"""The place of chapter "one" in the data island."""


def sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def entry(label: str, text: str, **more: str) -> dict:
    return {"check": "provenance", "label": label, "digest": sha(text), "reason": "Published on purpose.", **more}


def clean(text: str) -> bool:
    return not any(secret in text for secret in SECRETS)


def run(tmp_path: Path, capsys, page: dict | None = None, settings: dict | None = None,
        local: object = None, arguments: tuple[str, ...] = ()) -> tuple[int, str]:
    """Build ``page`` (PLANTED's) from a vault folder two levels below ``tmp_path`` with the CLI: the
    ``settings`` as --config's artifact settings, ``local`` written as the local file at
    ``tmp_path`` (text as it is, anything else as JSON). Its exit code (a refusal's too) and stderr."""
    folder = tmp_path / "vault" / "notes"
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "planted.json"
    source.write_text(json.dumps(page or planted()), encoding="utf-8")
    calls = [str(source), str(tmp_path / "planted.html"), *arguments]
    if settings is not None:
        (tmp_path / "cfg.json").write_text(json.dumps({"artifact": settings}), encoding="utf-8")
        calls = ["--config", str(tmp_path / "cfg.json"), *calls]
    if local is not None:
        (tmp_path / provenance.EXCEPTIONS_FILE).write_text(
            local if isinstance(local, str) else json.dumps(local), encoding="utf-8")
    try:
        code = cli.main(calls)
    except SystemExit as stopped:
        code = stopped.code
    return code, capsys.readouterr().err


def provenance_warnings(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("Warning: obs-html artifact: ")]


def test_each_finding_carries_the_digest_of_the_text_it_matched_and_shows_no_digest() -> None:
    found = reported(findings(artifact_html(planted())))
    assert {(finding.label, finding.digest) for finding in found} == {
        ("session-url", sha(URL)), ("session-id", sha(SESSION_ID)), ("absolute-path", sha(PATH)),
        ("timestamp", sha(TIME))}
    assert all(str(finding) == f"{finding.where}: {finding.label}" for finding in found)


def test_two_timestamps_in_one_place_are_two_digests_and_without_exceptions_one_warning(
        tmp_path: Path, capsys) -> None:
    page = planted(f"Met at {TIME}:00Z, again at {LATER}.")
    found = reported(findings(artifact_html(page)))
    assert [(finding.where, finding.label, finding.digest) for finding in found] == [
        (ONE, "timestamp", sha(TIME)), (ONE, "timestamp", sha(LATER))]
    code, err = run(tmp_path, capsys, page)
    assert code == 0 and len(provenance_warnings(err)) == 1 and f"obs-html artifact: {ONE}: " in err
    assert "sha256:" not in err


def test_an_exception_covers_its_label_and_digest_naming_its_layer_the_settings_first() -> None:
    found = findings(artifact_html(planted()))
    covered = excepted(found, (CheckException("session-id", sha(SESSION_ID), "local"),
                               CheckException("session-id", sha(SESSION_ID), "settings"),
                               CheckException("timestamp", sha(LATER), "local")))
    assert {finding.label: finding.exemption for finding in covered if finding.where == ONE} == {
        "session-url": None, "session-id": "exception:settings", "absolute-path": None, "timestamp": None}
    assert len(covered) == len(found)


def test_an_exception_with_a_place_covers_that_place_only() -> None:
    page = planted(f"Met at {TIME}.", f"Met at {TIME}.")
    covered = excepted(findings(artifact_html(page)), (CheckException("timestamp", sha(TIME), "local", ONE),))
    assert [(finding.where, finding.exemption) for finding in reported(covered)] == [
        ("artifact-data notes[2].html", None)]


def test_a_local_term_exception_covers_the_term_on_any_line(tmp_path: Path) -> None:
    listing = tmp_path / provenance.LOCAL_FILE
    listing.write_text("# private terms\nkestrel\n", encoding="utf-8")
    found = findings(artifact_html(planted()), local_terms(listing))
    rule = (CheckException("local-term", sha("Kestrel"), "local"),)
    assert "local-term:2" not in {finding.label for finding in reported(excepted(found, rule))}
    listing.write_text("# private terms\n\n\nkestrel\n", encoding="utf-8")  # The term moved two lines down.
    moved = findings(artifact_html(planted()), local_terms(listing))
    assert "local-term:4" in {finding.label for finding in reported(moved)}
    assert "local-term:4" not in {finding.label for finding in reported(excepted(moved, rule))}


def test_no_exception_renames_the_exemptions() -> None:
    html = with_island(artifact_html(planted()).replace(
        "<body>", '<body>\n<script id="plotly-script">var d = "2016-10-13 09:15:23";\n</script>', 1), REVIEWED)
    found = findings(html)
    every = tuple(CheckException("timestamp", finding.digest, layer)
                  for finding in found if finding.label == "timestamp" for layer in ("settings", "local"))
    exempt = {finding.where: finding.exemption for finding in found if finding.exemption}
    assert {finding.where: finding.exemption for finding in excepted(found, every)
            if finding.where in exempt} == exempt
    assert set(exempt.values()) == {"generation-timestamp", "vendored-library:plotly-script", "review-time"}


# The comment island's review times (architecture.md, Provenance check, review-time).
ISLAND_TAG = '<script id="obs-comments" type="application/json" data-comment-island>'
REVIEW_COMMENT = {"id": "c1", "author": "Alice", "created": "2026-11-09T10:00:00Z",
                  "modified": "2026-11-09T10:30:00Z", "state": "open", "target": {"chapter": "one"},
                  "body": {"mediaType": "text/plain", "text": f"Seen at {TIME} on the phone."}}
REVIEWED = {"version": 1, "files": [], "names": ["Alice"], "comments": [REVIEW_COMMENT],
            "decisions": [{"id": "d1", "reviewer": "Alice", "created": "2026-11-09T10:05:00Z",
                           "target": {"chapter": "one"}, "state": "accepted"}],
            "states": [{"id": "s1", "author": "Alice", "created": "2026-11-09T10:10:00Z", "target": "c1",
                        "state": "resolved"}]}
"""A reviewed copy's island: a comment with its two times and a timestamp in its body, a decision and
a state entry."""
REVIEW_TIMES = {"script#obs-comments.comments[0].created", "script#obs-comments.comments[0].modified",
                "script#obs-comments.decisions[0].created", "script#obs-comments.states[0].created"}


def with_island(html: str, value: object, tag: str = ISLAND_TAG) -> str:
    """``html`` with its comment island holding ``value``, written as the build writes it, and ``tag``
    as its start tag."""
    written = json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")
    built, count = re.subn(re.escape(ISLAND_TAG) + r".*?</script>", lambda _: f"{tag}{written}</script>", html)
    assert count == 1
    return built


def island_line(html: str) -> str:
    """The comment island's place as an HTML line, numbered as the check numbers lines."""
    lines = exposure.artifact_html(html).splitlines()
    return f"HTML line {next(number for number, line in enumerate(lines, 1) if 'id=\"obs-comments\"' in line)}"


def test_a_review_time_in_the_comment_island_is_exempt_and_every_other_timestamp_warns() -> None:
    html = with_island(artifact_html(planted("Plain text.")), REVIEWED)
    found = findings(html)
    assert {finding.where for finding in found if finding.exemption == "review-time"} == REVIEW_TIMES
    assert all(finding.label == "timestamp" for finding in found if finding.exemption == "review-time")
    assert shown(reported(found)) == [("script#obs-comments.comments[0].body.text", "timestamp", None)]
    refused = {**REVIEWED, "comments": [{**REVIEW_COMMENT, "created": "2026-11-09 10:00"}]}
    for other in (with_island(html, REVIEWED, ISLAND_TAG.replace(">", " data-edited>")),
                  with_island(html, refused)):
        found = findings(other)
        assert not any(finding.exemption == "review-time" for finding in found)
        assert {finding.where for finding in reported(found)} == {island_line(other)}


JSON = json.dumps(REVIEWED, separators=(",", ":"))
NESTED_TWICE = JSON.replace('"author":"Alice"', '"author":"Alice","author":"Alice"', 1)


@pytest.mark.parametrize("html", [
    f'<p>\n{ISLAND_TAG}{JSON}</script>\n<script id="obs-comments">{{}}</script>',
    f"<p>\n{ISLAND_TAG}{JSON}</script>\n<script type=x id=obs-comments></script>",
    f"<p>\n{ISLAND_TAG.replace(' data-comment-island', '')}{JSON}</script>",
    f"<p>\n{ISLAND_TAG}{json.dumps(REVIEWED, indent=1)}</script>",
    f"<p>\n{ISLAND_TAG}{JSON}\n</script>",
    f"<p>\n{ISLAND_TAG}{JSON[:-1]},\"version\":1}}</script>",
    f"<p>\n{ISLAND_TAG}{json.dumps({**REVIEWED, 'version': 2})}</script>",
    f"<p>\n{ISLAND_TAG}{JSON[:-1]}</script>",
    f"<p>\n{ISLAND_TAG}{NESTED_TWICE}</script>",
], ids=["a second element", "an unquoted second id", "another start tag", "JSON over lines",
        "the end tag on another line", "a key twice", "JSON the schema refuses", "not JSON",
        "a key twice in a comment"])
def test_an_island_of_any_other_shape_than_the_builds_is_its_html_line(html: str) -> None:
    assert provenance.comment_island(html) is None
    assert not any(finding.exemption == "review-time" for finding in findings(html))


def test_the_builds_island_is_its_line_without_the_json_and_its_value() -> None:
    assert provenance.comment_island(f"<p>\n  {ISLAND_TAG}{JSON}</script>\n") == (
        "HTML line 2", f"  {ISLAND_TAG}</script>", REVIEWED)
    assert provenance.review_time("script#obs-comments.states[3].created") == "review-time"
    assert {provenance.review_time(where) for where in ("script#obs-comments.comments[0].body.text",
                                                        "script#obs-comments.comments[0].created (the key)",
                                                        "script#obs-comments.decisions[0].modified",
                                                        "artifact-data comments[0].created")} == {None}


def test_a_vault_with_a_comment_builds_without_a_provenance_warning(tmp_path: Path, capsys) -> None:
    """The core builds a vault with an overlay comment into a Document, the CLI that into a page."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "manifest.md").write_text("- [[intro]]\n", encoding="utf-8")
    (vault / "intro.md").write_text("# Intro\n\nText.\n", encoding="utf-8")
    comment = {**REVIEW_COMMENT, "body": {"mediaType": "text/plain", "text": "Sent from the phone."},
               "target": {"chapter": "intro"}}
    (vault / "manifest.comments.alice.json").write_text(json.dumps(
        {"version": 1, "principal": "alice", "names": ["Alice"], "comments": [comment], "decisions": []}),
        encoding="utf-8")
    document = tmp_path / "document.json"
    subprocess.run([sys.executable, "-m", "obs.document", "--source", str(vault / "manifest.md"),
                    "--document", str(document)], check=True, capture_output=True)
    assert cli.main([str(document), str(tmp_path / "page.html")]) == 0
    assert "carries provenance" not in capsys.readouterr().err
    assert "Sent from the phone." in (tmp_path / "page.html").read_text(encoding="utf-8")


def test_a_committed_session_id_exception_and_a_local_timestamp_exception_remove_their_warnings(
        tmp_path: Path, capsys) -> None:
    """The local file is found up from a nested vault folder, as the local list is, and adds to the
    committed exceptions."""
    code, err = run(tmp_path, capsys, settings={"checkExceptions": [entry("session-id", SESSION_ID)]},
                    local={"checkExceptions": [entry("timestamp", TIME)]})
    assert code == 0 and clean(err)
    assert {re.search(r"\((\S+)\)", line)[1] for line in provenance_warnings(err)} == {"absolute-path", "session-url"}


def test_with_refuse_provenance_an_excepted_only_finding_builds_the_page(tmp_path: Path, capsys) -> None:
    code, err = run(tmp_path, capsys, planted(f"Met at {TIME}."), settings={"refuseProvenance": True},
                    local={"checkExceptions": [entry("timestamp", TIME, where=ONE)]})
    assert code == 0 and (tmp_path / "planted.html").is_file()
    assert "carries provenance" not in err and clean(err)


@pytest.mark.parametrize("label", ["timestamp", "absolute-path", "local-term"])
def test_a_committed_exception_of_a_local_only_label_fails_naming_its_entry(
        label: str, tmp_path: Path, capsys) -> None:
    code, err = run(tmp_path, capsys, settings={"checkExceptions": [entry(label, TIME)]})
    assert code == 2 and not (tmp_path / "planted.html").exists()
    assert f"{tmp_path / 'cfg.json'}: artifact.checkExceptions[0]: " in err
    assert provenance.EXCEPTIONS_FILE in err and EXCEPTIONS_OWNER in err and clean(err)


@pytest.mark.parametrize("field", ["reason", "where"])
def test_a_committed_exception_whose_text_carries_provenance_fails_naming_that_field(
        field: str, tmp_path: Path, capsys) -> None:
    (tmp_path / provenance.LOCAL_FILE).write_text("kestrel\n", encoding="utf-8")
    text = {"reason": f"Shown since {TIME}.", "where": "artifact-data notes[1].Kestrel"}[field]
    code, err = run(tmp_path, capsys, settings={"checkExceptions": [entry("session-id", SESSION_ID, **{field: text})]})
    assert code == 2 and f"{tmp_path / 'cfg.json'}: artifact.checkExceptions[0].{field}: " in err
    assert EXCEPTIONS_OWNER in err and clean(err)


def test_of_two_timestamps_in_one_place_one_excepted_the_other_still_warns_once(tmp_path: Path, capsys) -> None:
    page = planted(f"Met at {TIME}, again at {LATER}.")
    code, err = run(tmp_path, capsys, page, local={"checkExceptions": [entry("timestamp", TIME)]},
                    arguments=("--finding-digests",))
    assert code == 0 and provenance_warnings(err) == [line for line in err.splitlines() if ONE in line]
    assert len(provenance_warnings(err)) == 1 and sha(LATER) in err and sha(TIME) not in err


def test_an_exception_whose_place_is_an_html_line_fails_the_schema(tmp_path: Path, capsys) -> None:
    code, err = run(tmp_path, capsys, settings={"checkExceptions": [entry("session-id", SESSION_ID, where="HTML line 3")]})
    # The field path alone: config.py names the packaged file for a list item's failure (field report).
    assert code == 2 and ": artifact.checkExceptions[0].where: " in err
    code, err = run(tmp_path / "local", capsys, local={"checkExceptions": [entry("timestamp", TIME, where="HTML line 3")]})
    assert code == 2 and f"{tmp_path / 'local' / provenance.EXCEPTIONS_FILE}: checkExceptions[0].where: " in err


@pytest.mark.parametrize("content, field", [
    ("{not json", "top level"),
    ({"checkExceptions": [{"check": "provenance", "label": "timestamp", "digest": "sha256:short", "reason": "x"}]},
     "checkExceptions[0].digest"),
    ({"checkExceptions": [{"check": "exposure", "label": "timestamp", "digest": sha(TIME), "reason": "x"}]},
     "checkExceptions[0].check"),
    ({"checkExceptions": [{"check": "provenance", "label": "timestamp", "digest": sha(TIME)}]},
     "checkExceptions[0].reason"),
    ({"checkExceptions": [], "exceptions": []}, "exceptions"),
], ids=["not-json", "digest", "check", "reason", "key"])
def test_a_local_exceptions_file_that_breaks_its_form_names_the_file_and_the_field(
        content: object, field: str, tmp_path: Path, capsys) -> None:
    code, err = run(tmp_path, capsys, local=content)
    assert code == 2 and f"{tmp_path / provenance.EXCEPTIONS_FILE}: {field}: " in err
    assert EXCEPTIONS_OWNER in err


def test_with_finding_digests_each_warning_names_its_digests_and_without_it_none_does(
        tmp_path: Path, capsys) -> None:
    code, err = run(tmp_path, capsys, arguments=("--finding-digests",))
    named = {re.search(r"\((\S+), (sha256:[0-9a-f]{64})\)", line).groups() for line in provenance_warnings(err)}
    assert code == 0 and named == {("session-url", sha(URL)), ("session-id", sha(SESSION_ID)),
                                   ("absolute-path", sha(PATH)), ("timestamp", sha(TIME))}
    assert clean(err)
    assert "sha256:" not in run(tmp_path, capsys)[1]


def test_with_finding_digests_one_warning_names_both_digests_of_a_place(tmp_path: Path, capsys) -> None:
    code, err = run(tmp_path, capsys, planted(f"Met at {TIME}, again at {LATER}."), arguments=("--finding-digests",))
    assert code == 0 and len(provenance_warnings(err)) == 1
    assert f"(timestamp, {sha(TIME)}, {sha(LATER)})" in err and clean(err)


def test_with_finding_digests_a_refusal_names_the_digests_of_each_place(tmp_path: Path, capsys) -> None:
    code, err = run(tmp_path, capsys, settings={"refuseProvenance": True}, arguments=("--finding-digests",))
    assert code == 2 and err.count("sha256:") == 4 and sha(PATH) in err and clean(err)


def test_finding_digests_is_refused_on_a_call_that_renders_no_document(tmp_path: Path, capsys) -> None:
    with pytest.raises(SystemExit) as stopped:
        cli.main(["--print-chapter", str(tmp_path / "page.html"), "one", "--finding-digests"])
    assert stopped.value.code == 2 and "obs-html: --finding-digests: " in capsys.readouterr().err


def test_a_one_call_build_with_the_finding_digests_option_prints_each_digest(tmp_path: Path, core_root) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "manifest.md").write_text("---\ntitle: Digests\n---\n- [[chapter]]\n", encoding="utf-8")
    (vault / "chapter.md").write_text(f"# Chapter\n\nMet at {TIME}.\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-m", "obs.document", "--source", str(vault / "manifest.md"), "--adapter", "html",
         "--destination", str(tmp_path / "page.html"),
         "--adapter-option", "finding-digests=true"],
        capture_output=True, text=True, env={**os.environ, "UV_OFFLINE": "1"}, check=False)
    assert completed.returncode == 0, completed.stderr
    assert f"(timestamp, {sha(TIME)})" in completed.stderr


def test_no_test_name_of_exceptions_or_digests_holds_the_planted_text(request) -> None:
    names = [item.nodeid for item in request.session.items if item.path == Path(__file__)
             and ("exception" in item.name or "digest" in item.name)]
    assert names and all(clean(name) for name in names)
