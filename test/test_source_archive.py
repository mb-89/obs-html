"""The source archive and the CSS snippets a Document carries, packaged and applied by obs-html.

Reader: whoever changes how obs-html packages a Document's sourceArchive (source_archive.py) or
embeds the CSS snippets its manifest lists (render.py); input-model.md, "Optional reproduction
archive" and "Artifact presentation profile", owns the behaviour.

Each check reads the HTML or the PDF in Python: the archive's bytes from its island, unzipped;
the snippets' style elements in document order; the PDF's attachment through pypdf. The parity
check builds the source-archive fixture vault with the interim adapter as well and compares what
both offer.
"""
import base64
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from conftest import PIXEL, ROOT, built_once
from documents import chapter, document, heading, node, paragraph
from fixtures import build_documents
from obs_html import cli
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render
from obs_html import reproduce
from obs_html.source_archive import ARCHIVE_NAME, attach, embedded

CONFIG = load_config()
SCRIPT = b"print('rebuilt')\n"
FIXTURE = ROOT / "test" / "fixtures" / "documents" / "source-archive.json"
STYLE = re.compile(r"<style\b[^>]*>")
BUILD = {"repository": "https://example.invalid/obs", "commit": "0123456789abcdef0123456789abcdef01234567",
         "lockfiles": {"uv.lock": {"obs": "0.2.3", "pypdf": "6.21.2"}},
         "arguments": ["--adapter", "html", "--destination", "report.html", "--adapter-option",
                       "embed-attachments=true", "--embed-source"]}


def archived(snippets: list[str] | None = None) -> dict:
    """A Document whose vault holds an image (an asset), a script and a snippet, all archived."""
    metadata = {"obsHtml": {"cssSnippets": snippets}} if snippets is not None else None
    source = document("Archived", chapter("one", "One", heading(1, "One"), paragraph(
        node("embeds", target="pixel.png", chapter=None, asset="pixel-png"))), metadata=metadata)
    source["assets"] = [{"id": "pixel-png", "href": "pixel.png", "mediaType": "image/png",
                         "path": "media/pixel.png", "data": PIXEL}]
    source["capabilities"] = sorted({*source["capabilities"], "embeds"})
    source["cssSnippets"] = [
        {"name": "house", "path": ".obsidian/snippets/house.css", "text": "p { color: rgb(1, 2, 3); }\n"},
        {"name": "print", "path": ".obsidian/snippets/print.css", "text": "h1 { color: rgb(4, 5, 6); }\n"},
    ]
    source["sourceArchive"] = {"files": [
        {"path": "manifest.md", "data": base64.b64encode(b"- [[one]]\n").decode("ascii")},
        {"path": "media/pixel.png", "asset": "pixel-png"},
        {"path": "scripts/build.py", "data": base64.b64encode(SCRIPT).decode("ascii")},
    ], "build": json.loads(json.dumps(BUILD))}
    return source


def members(html: str) -> dict[str, bytes]:
    archive = embedded(html, "artifact.html")
    assert archive is not None, "test_source_archive.py: the HTML carries no source archive"
    with zipfile.ZipFile(io.BytesIO(archive)) as opened:
        assert opened.testzip() is None
        return {name: opened.read(name) for name in opened.namelist()}


def test_the_archive_download_unzips_to_the_documents_source_files() -> None:
    html = render(archived(), CONFIG)
    files = members(html)

    assert {name: data for name, data in files.items() if name.startswith("vault/")} == {
        "vault/manifest.md": b"- [[one]]\n",
        "vault/media/pixel.png": base64.b64decode(PIXEL),
        "vault/scripts/build.py": SCRIPT,
    }
    model = decode_artifact_data(html)
    assert model["sourceArchiveComplete"] is True
    # The download is the island's ZIP (artifact.js, downloadSourceArchive), offered on the cover and in
    # Settings, which the downloads feature owns; attaching it to a saved PDF ships only with it.
    assert 'id="canary-downloads"' in html and 'data-source-download' in html
    assert 'id="pdf-library-script"' in html and "globalThis.obsArchive" in html


def test_build_config_records_what_rebuilds_the_artifact() -> None:
    """The archive refers to the generator instead of copying it (input-model.md, Optional
    reproduction archive): build-config.json names obs's repository and commit, the lockfile
    versions, the schema version, the adapter's options and the exact command; no generator/."""
    files = members(render(archived(), CONFIG, embed_attachments=True))

    assert json.loads(files["build-config.json"]) == {
        "schemaVersion": 1,
        "obs": {"repository": BUILD["repository"], "commit": BUILD["commit"]},
        "lockfiles": BUILD["lockfiles"],
        "adapterOptions": {"embed-attachments": True},
        "command": ["obs-document", "--source", "vault/manifest.md", *BUILD["arguments"]],
    }
    assert files["reproduce.py"] == (Path(reproduce.__file__).read_bytes())
    assert not any(name.startswith("generator/") for name in files)
    assert json.loads(files["source-inventory.json"])["generator"] == []
    assert b"python reproduce.py" in files["REPRODUCE.txt"]


DECLARED = {"url": "https://example.invalid/house-style.git", "ref": "89abcdef0123456789abcdef0123456789abcdef",
            "path": "styles/house"}


def test_build_config_records_the_declared_style_the_rebuild_resolves() -> None:
    """The archived build configuration names the style the manifest declares (obs's architecture,
    Declared style), so a rebuild from the archive resolves the same pinned style."""
    source = archived()
    source["style"] = DECLARED
    source["sourceArchive"]["build"]["style"] = DECLARED

    config = json.loads(members(render(source, CONFIG))["build-config.json"])

    assert config["style"] == DECLARED
    assert "style" not in json.loads(members(render(archived(), CONFIG))["build-config.json"])


def test_a_one_off_style_override_is_not_archived_so_the_rebuild_keeps_the_declared_style(tmp_path: Path) -> None:
    """obs-html --style FOLDER styles this one build only: the archive records the declared style and
    the recorded command, neither of which names the override (obs's architecture, Declared style)."""
    source = archived()
    source["style"] = DECLARED
    source["sourceArchive"]["build"]["style"] = DECLARED
    (tmp_path / "document.json").write_text(json.dumps(source), encoding="utf-8")
    override = tmp_path / "one-off-style"
    override.mkdir()
    (override / "style.css").write_text("body { color: rgb(7, 8, 9); }\n", encoding="utf-8")

    assert cli.main([str(tmp_path / "document.json"), str(tmp_path / "artifact.html"), "--style", str(override)]) == 0

    html = (tmp_path / "artifact.html").read_text(encoding="utf-8")
    assert "rgb(7, 8, 9)" in html, "the override styles this build"
    files = members(html)
    config = json.loads(files["build-config.json"])
    assert config["style"] == DECLARED
    assert "--style" not in config["command"]
    assert not any(b"one-off-style" in data for data in files.values())


def test_an_archive_without_a_recorded_adapter_fails_naming_its_field() -> None:
    source = archived()
    source["sourceArchive"]["build"]["arguments"] = ["--embed-source"]

    with pytest.raises(InputError) as failure:
        render(source, CONFIG)

    assert (failure.value.source, failure.value.field) == ("Document of manifest.md", "sourceArchive.build.arguments")
    assert "--adapter" in failure.value.remedy


def extracted(folder: Path, arguments: list[str] | None = None) -> Path:
    """The archive of ``archived()`` extracted into ``folder``."""
    source = archived()
    if arguments is not None:
        source["sourceArchive"]["build"]["arguments"] = arguments
    with zipfile.ZipFile(io.BytesIO(embedded(render(source, CONFIG), "artifact.html"))) as opened:
        opened.extractall(folder)
    return folder


def test_reproduce_installs_the_recorded_commit_and_reruns_the_recorded_command(tmp_path: Path) -> None:
    here = extracted(tmp_path)
    config = json.loads((here / "build-config.json").read_text(encoding="utf-8"))
    checkout = here / "obs"

    steps = reproduce.steps(config, here, BUILD["repository"], execute_commands=False)

    assert [(step.name, step.command) for step in steps] == [
        ("clone", ["git", "clone", "--quiet", "--no-checkout", BUILD["repository"], str(checkout)]),
        ("checkout", ["git", "-C", str(checkout), "checkout", "--quiet", "--detach", BUILD["commit"]]),
        ("install", ["uv", "sync", "--frozen", "--project", str(checkout)]),
        ("rebuild", ["uv", "run", "--frozen", "--project", str(checkout), *config["command"],
                     "--adapter-config", str(checkout / "adapters.json")]),
    ]
    assert steps[-1].environment == {"UV_PROJECT": str(checkout)}
    checkout.mkdir()
    assert [step.name for step in reproduce.steps(config, here, BUILD["repository"], False)][0] == "checkout"


def test_reproduce_runs_recorded_command_fences_only_when_asked(tmp_path: Path) -> None:
    here = extracted(tmp_path, ["--adapter", "html", "--destination", "a.html", "--execute-commands",
                                "--embed-source"])
    config = json.loads((here / "build-config.json").read_text(encoding="utf-8"))

    with pytest.raises(SystemExit) as refused:
        reproduce.steps(config, here, BUILD["repository"], execute_commands=False)

    assert "reproduce.py" in str(refused.value.code) and "--execute-commands" in str(refused.value.code)
    assert reproduce.steps(config, here, BUILD["repository"], execute_commands=True)[-1].command[-3] == \
        "--embed-source"


def test_a_failed_clone_names_the_commit_and_the_remedy(tmp_path: Path) -> None:
    """The extracted reproduce.py on a repository that does not exist: git fails at once, offline."""
    here = extracted(tmp_path / "archive")
    missing = tmp_path / "no-such-repository"

    result = subprocess.run([sys.executable, "-I", str(here / "reproduce.py"), "--repository", str(missing)],
                            capture_output=True, text=True, cwd=tmp_path)

    assert result.returncode != 0
    assert result.stderr.startswith("reproduce.py: clone:")
    assert BUILD["commit"] in result.stderr and str(missing) in result.stderr
    assert "--repository" in result.stderr.split("Remedy:", 1)[1]


def test_an_archived_image_has_one_byte_owner_the_zip_member() -> None:
    html = render(archived(), CONFIG)
    model = decode_artifact_data(html)
    one = next(note for note in model["notes"] if note["slug"] == "one")

    assert PIXEL not in json.dumps(model)
    key = re.search(r'obs-asset:([a-f0-9]{64})', one["html"])[1]
    assert model["embeddedAssets"][key] == {"archivePath": "vault/media/pixel.png", "mime": "image/png",
                                            "sha256": hashlib.sha256(base64.b64decode(PIXEL)).hexdigest()}


def test_a_document_without_an_archive_ships_neither_the_archive_nor_its_attach_code() -> None:
    source = archived()
    del source["sourceArchive"]
    html = render(source, CONFIG)

    assert 'id="obs-source-archive"' not in html and embedded(html, "artifact.html") is None
    assert 'id="pdf-library-script"' not in html and "globalThis.obsArchive" not in html
    one = next(note for note in decode_artifact_data(html)["notes"] if note["slug"] == "one")
    assert f'data:image/png;base64,{PIXEL}' in one["html"]


def test_an_archived_file_naming_an_unknown_asset_fails_naming_its_field() -> None:
    source = archived()
    source["sourceArchive"]["files"][1]["asset"] = "missing"

    with pytest.raises(InputError) as failure:
        render(source, CONFIG)

    assert failure.value.source == "Document of manifest.md"
    assert failure.value.field == "sourceArchive.files[1].asset"


def blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_the_archive_attaches_to_a_saved_pdf_as_the_interim_does(tmp_path: Path) -> None:
    html = tmp_path / "artifact.html"
    html.write_text(render(archived(), CONFIG), encoding="utf-8")
    pdf = tmp_path / "saved.pdf"
    pdf.write_bytes(blank_pdf())
    output = tmp_path / "with-source.pdf"

    assert cli.main(["--attach-source-to-pdf", str(pdf), "--source-artifact", str(html),
                     "--output", str(output)]) == 0

    attachments = PdfReader(output).attachments
    assert list(attachments) == [ARCHIVE_NAME]
    assert attachments[ARCHIVE_NAME] == [embedded(html.read_text(encoding="utf-8"), html)]
    with pytest.raises(InputError) as again:
        attach(output.read_bytes(), b"zip", output)
    assert (again.value.source, again.value.field) == (str(output), "--attach-source-to-pdf")


def test_attaching_needs_an_artifact_with_an_archive(tmp_path: Path) -> None:
    source = archived()
    del source["sourceArchive"]
    html = tmp_path / "artifact.html"
    html.write_text(render(source, CONFIG), encoding="utf-8")
    pdf = tmp_path / "saved.pdf"
    pdf.write_bytes(blank_pdf())

    with pytest.raises(SystemExit):
        cli.main(["--attach-source-to-pdf", str(pdf), "--source-artifact", str(html),
                  "--output", str(tmp_path / "out.pdf")])
    assert not (tmp_path / "out.pdf").exists()


def test_a_pdf_destination_of_an_archived_document_carries_the_archive(tmp_path: Path, monkeypatch) -> None:
    """A Document built with --embed-source and rendered to PDF attaches its ZIP, from the
    Document alone (obs architecture, Source archive); printing itself is the browser's."""
    from obs_html import pdf as printing

    monkeypatch.setattr(printing, "export_pdf", lambda _html: blank_pdf())
    source = tmp_path / "document.json"
    source.write_text(json.dumps(archived()), encoding="utf-8")

    assert cli.main([str(source), str(tmp_path / "artifact.pdf")]) == 0

    attachment = PdfReader(tmp_path / "artifact.pdf").attachments[ARCHIVE_NAME][0]
    with zipfile.ZipFile(io.BytesIO(attachment)) as opened:
        assert opened.read("vault/scripts/build.py") == SCRIPT


def test_listed_snippets_follow_every_packaged_style_in_listed_order() -> None:
    html = render(archived(["print", "house"]), CONFIG)
    styles = STYLE.findall(html)

    assert styles[-2:] == ['<style data-css-snippet="print">', '<style data-css-snippet="house">']
    assert all("data-css-snippet" not in style for style in styles[:-2])
    assert '<style data-css-snippet="house">p { color: rgb(1, 2, 3); }\n</style>' in html


def test_unlisted_snippets_are_not_embedded() -> None:
    html = render(archived(["house"]), CONFIG)

    assert 'data-css-snippet="house"' in html and "rgb(4, 5, 6)" not in html
    assert "data-css-snippet" not in render(archived(), CONFIG)


def test_an_unknown_snippet_fails_naming_the_manifest_and_the_available_snippets() -> None:
    with pytest.raises(InputError) as failure:
        render(archived(["house", "missing"]), CONFIG)

    assert failure.value.source == "manifest.md"
    assert failure.value.field == "obsHtml.cssSnippets[1]"
    assert "house" in failure.value.remedy and "print" in failure.value.remedy


def test_a_snippet_that_closes_its_style_element_fails_naming_its_file() -> None:
    source = archived(["house"])
    source["cssSnippets"][0]["text"] = "p {} </style><script>"

    with pytest.raises(InputError) as failure:
        render(source, CONFIG)

    assert failure.value.source == ".obsidian/snippets/house.css"


def test_an_unknown_snippet_is_named_below_the_vault_root(tmp_path: Path, capsys) -> None:
    source = tmp_path / "document.json"
    source.write_text(json.dumps(archived(["missing"])), encoding="utf-8")

    with pytest.raises(SystemExit):
        cli.main([str(source), "--check", "--vault-root", "vault"])

    assert f"{Path('vault', 'manifest.md')}: obsHtml.cssSnippets[0]:" in capsys.readouterr().err


@pytest.fixture(scope="module")
def interim(tmp_path_factory) -> str:
    """The source-archive fixture vault built by the interim adapter with --embed-source."""
    from obs_html_interim.cli import main as interim_main

    def build(folder: Path) -> None:
        vault = folder / "vault"
        vault.mkdir()
        build_documents.VAULTS["source-archive"](vault)
        assert interim_main(["--source", str(vault / "manifest.md"), "--output", str(folder / "interim.html"),
                             "--embed-source"]) == 0

    return (built_once(tmp_path_factory, "source-archive-interim", build) / "interim.html").read_text(encoding="utf-8")


SNIPPET = re.compile(r'<style data-css-snippet="([^"]*)">(.*?)</style>', re.DOTALL)


def test_the_fixture_vault_offers_what_the_interim_offers(interim: str) -> None:
    """Parity on one vault both adapters accept: the same vault files in the ZIP, the same
    top-level members (build configuration, rebuild script and instructions, source inventory),
    the same snippets in the same order, the same download and PDF attachment names. The interim's
    ZIP adds its generator/ copy, which this adapter's archive refers to instead (architecture.md,
    Known differences from the interim)."""
    ours = render(json.loads(FIXTURE.read_text(encoding="utf-8")), CONFIG)
    our_members, interim_members = members(ours), members(interim)

    assert {name: data for name, data in our_members.items() if name.startswith("vault/")} == \
        {name: data for name, data in interim_members.items() if name.startswith("vault/")}
    assert {name for name in our_members if "/" not in name} == {name for name in interim_members if "/" not in name}
    assert any(name.startswith("generator/") for name in interim_members)
    assert not any(name.startswith("generator/") for name in our_members)
    assert json.loads(our_members["build-config.json"])["command"][:3] == ["obs-document", "--source", "vault/manifest.md"]
    assert SNIPPET.findall(ours) == SNIPPET.findall(interim) != []
    for marker in ("data-source-download", "data-source-attach", 'id="pdf-library-script"'):
        assert marker in ours and marker in interim, marker
    names = {"obs-html-source.zip"}
    assert names <= set(re.findall(r'"(obs-html-[a-z-]+\.zip)"', interim))
    assert names <= set(re.findall(r'"(obs-html-[a-z-]+\.zip)"', ours)) and ARCHIVE_NAME in names
