"""Attachment editions: one Document gives a light edition and a self-contained evidence edition.

obs-html --embed-attachments (the interim's option name and default, obs cli.md "Attachments per
build") renders each marked attachment as a download built from its asset's embedded bytes, with
its name, type and size; without it, the attachment shows its label and vault path and its bytes
stay out of the HTML. The download control belongs to the downloads feature (features.py).
"""
import base64
import json
import re
import shutil
import subprocess
import sys

import pytest

from conftest import built_once
from obs_html import cli
from obs_html.artifact_data import decode_artifact_data


REPORT = b"%PDF-1.4\n% obs attachment edition fixture\n" + bytes(range(256)) * 5 + b"\n%%EOF\n"
DOWNLOAD = re.compile(r'<a class="attachment-download" href="data:application/pdf;base64,([^"]+)" '
                      r'download="report\.pdf" data-attachment-download>(.*?)</a>')


def _vault_document(folder, core_root) -> None:
    """A Document the core builds from a vault whose note marks a PDF attachment, then the vault goes."""
    vault = folder / "vault"
    (vault / "input").mkdir(parents=True)
    (vault / "input" / "report.pdf").write_bytes(REPORT)
    (vault / "manifest.md").write_text("---\ntitle: Editions\n---\n- [[chapter]]\n", encoding="utf-8")
    (vault / "chapter.md").write_text("# Chapter\n\nSee ![the report](input/report.pdf).\n", encoding="utf-8")
    run = [sys.executable, "-m"]
    subprocess.run([*run, "obs.capabilities", "--notes", str(core_root / "spec" / "capabilities"),
                    "--output", str(folder / "capabilities.json")], check=True)
    subprocess.run([*run, "obs.document", "--source", str(vault / "manifest.md"),
                    "--document", str(folder / "document.json"),
                    "--capability-reference", str(folder / "capabilities.json")], check=True)
    shutil.rmtree(vault)


@pytest.fixture(scope="module")
def editions(tmp_path_factory, core_root):
    """The light and the evidence artifact of one core-built Document, through the CLI."""
    folder = built_once(tmp_path_factory, "attachment-editions", lambda path: _vault_document(path, core_root))
    out = tmp_path_factory.mktemp("editions")
    cli.main([str(folder / "document.json"), str(out / "light.html")])
    cli.main([str(folder / "document.json"), str(out / "evidence.html"), "--embed-attachments"])
    return {name: (out / f"{name}.html") for name in ("light", "evidence")}


def _chapter(path) -> str:
    notes = decode_artifact_data(path.read_text(encoding="utf-8"))["notes"]
    return next(note["html"] for note in notes if note["slug"] == "chapter")


def test_the_evidence_edition_offers_a_download_of_the_asset_bytes_with_name_type_and_size(editions) -> None:
    match = DOWNLOAD.search(_chapter(editions["evidence"]))
    assert match, _chapter(editions["evidence"])
    assert base64.b64decode(match.group(1)) == REPORT
    shown = re.sub(r"<[^>]+>", "", match.group(2))
    assert shown == "the report (report.pdf, PDF, 1.3 KB)"


def test_the_light_edition_shows_label_and_vault_path_and_does_not_embed_the_bytes(editions) -> None:
    body = _chapter(editions["light"])
    assert '<span class="source-reference" data-source-path="input/report.pdf">the report</span>' in body
    assert "data-attachment-download" not in body
    html = editions["light"].read_text(encoding="utf-8")
    assert base64.b64encode(REPORT).decode("ascii")[:200] not in html
    assert base64.b64encode(REPORT).decode("ascii")[:200] not in json.dumps(
        decode_artifact_data(html))


@pytest.mark.browser
def test_clicking_the_evidence_download_saves_the_asset_bytes(editions, reader_browser, tmp_path) -> None:
    context = reader_browser.new_context(accept_downloads=True)
    page = context.new_page()
    page.set_default_timeout(5000)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(editions["evidence"].as_uri() + "#chapter")
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('chapter')")
    with page.expect_download() as download:
        page.locator("[data-active-chapter] [data-attachment-download]").click()
    assert download.value.suggested_filename == "report.pdf"
    saved = tmp_path / "saved.pdf"
    download.value.save_as(saved)
    assert saved.read_bytes() == REPORT
    assert errors == []
