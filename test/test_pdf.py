"""Browser tests: they start the local Chrome/Edge/Chromium through Playwright."""
import base64
from io import BytesIO

import pytest
from pypdf import PdfReader

from conftest import FIXTURE
from obs_html import cli


PIXEL = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


@pytest.mark.browser
def test_pdf_destination_prints_the_rendered_document(pdf_browser, tmp_path, capsys) -> None:
    destination = tmp_path / "artifact.pdf"
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "logo.png").write_bytes(base64.b64decode(PIXEL))
    cli.main([str(FIXTURE), str(destination)])
    reader = PdfReader(BytesIO(destination.read_bytes()))
    box = reader.pages[0].mediabox
    assert (round(float(box.width) / 72 * 25.4, 1), round(float(box.height) / 72 * 25.4, 1)) == (215.9, 279.4)
    assert "Fixture document" in reader.pages[0].extract_text()
    assert len(reader.pages) >= 4  # Cover, contents, abstract and chapters start new pages.
    assert sorted(path.name for path in tmp_path.iterdir()) == ["artifact.pdf", "images"]


@pytest.mark.browser
def test_export_pdf_and_rendered_check_read_existing_html(pdf_browser, fixture_artifact, tmp_path, capsys) -> None:
    html = fixture_artifact
    cli.main(["--export-pdf", str(html), "--output", str(tmp_path / "artifact.pdf")])
    assert PdfReader(tmp_path / "artifact.pdf").pages
    cli.main(["--check-rendered", str(html)])
    assert "status ready, 0 console errors," in capsys.readouterr().out


@pytest.mark.browser
def test_rendered_check_fails_on_console_errors(pdf_browser, tmp_path, capsys) -> None:
    html = tmp_path / "broken.html"
    html.write_text('<!doctype html><html data-artifact-status="ready"><script>console.error("bad")</script>',
                    encoding="utf-8")
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--check-rendered", str(html)])
    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert "Console error: bad" in error  # The console's own error, as the check reports it.
    assert f"\n{html}: --check-rendered: " in f"\n{error}", error


@pytest.mark.browser
def test_two_pdf_prints_under_one_build_time_are_equal_and_carry_its_date(
        pdf_browser, fixture_artifact, tmp_path, monkeypatch) -> None:
    """SOURCE_DATE_EPOCH sets both document information dates (architecture.md, Build time)."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    dated = ("D:20231114221320+00'00'",) * 2
    for name in ("a.pdf", "b.pdf"):
        cli.main(["--export-pdf", str(fixture_artifact), "--output", str(tmp_path / name)])
    assert (tmp_path / "a.pdf").read_bytes() == (tmp_path / "b.pdf").read_bytes()
    destination = tmp_path / "built.pdf"
    cli.main([str(FIXTURE), str(destination)])
    for pdf in (tmp_path / "a.pdf", destination):
        metadata = PdfReader(pdf).metadata
        assert (metadata["/CreationDate"], metadata["/ModDate"]) == dated, pdf
