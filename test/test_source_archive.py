"""The source archive a Document carries, packaged by obs-html.

Reader: whoever changes how obs-html packages a Document's sourceArchive (source_archive.py);
input-model.md, "Optional reproduction archive", owns the behaviour.

Each check reads the HTML or the PDF in Python: the archive's bytes from its island, unzipped;
the PDF's attachment through pypdf.
"""
import base64
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from conftest import PIXEL
from documents import chapter, document, heading, node, paragraph
from obs_html import cli
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render
from obs_html.source_archive import ARCHIVE_NAME, attach, embedded

CONFIG = load_config()
SCRIPT = b"print('rebuilt')\n"


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
    ]}
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

