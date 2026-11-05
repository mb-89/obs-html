"""Browser tests: they start the local Chrome/Edge/Chromium through Playwright."""
import base64
from io import BytesIO

import pytest
from pypdf import PdfReader

from conftest import FIXTURE
from obs_html import cli


PIXEL = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


def test_pdf_destination_prints_the_rendered_document(tmp_path, capsys) -> None:
    destination = tmp_path / "artifact.pdf"
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "logo.png").write_bytes(base64.b64decode(PIXEL))
    cli.main([str(FIXTURE), str(destination), "--execute-commands", "--command-root", str(tmp_path)])
    reader = PdfReader(BytesIO(destination.read_bytes()))
    box = reader.pages[0].mediabox
    assert (round(float(box.width) / 72 * 25.4, 1), round(float(box.height) / 72 * 25.4, 1)) == (215.9, 279.4)
    assert "Fixture document" in reader.pages[0].extract_text()
    assert len(reader.pages) >= 4  # Cover, contents, abstract and chapters start new pages.
    assert sorted(path.name for path in tmp_path.iterdir()) == ["artifact.pdf", "images"]


def test_export_pdf_and_rendered_check_read_existing_html(fixture_artifact, tmp_path, capsys) -> None:
    html = fixture_artifact
    cli.main(["--export-pdf", str(html), "--output", str(tmp_path / "artifact.pdf")])
    assert PdfReader(tmp_path / "artifact.pdf").pages
    cli.main(["--check-rendered", str(html)])
    assert "status ready, 0 console errors," in capsys.readouterr().out


def test_rendered_check_fails_on_console_errors(tmp_path, capsys) -> None:
    html = tmp_path / "broken.html"
    html.write_text('<!doctype html><html data-artifact-status="ready"><script>console.error("bad")</script>',
                    encoding="utf-8")
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--check-rendered", str(html)])
    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert "Console error: bad" in error and "1 console errors" in error
