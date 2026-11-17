"""Browser tests: they start the local Chrome/Edge/Chromium through Playwright."""
import base64
import copy
import json
import re
import shutil
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path

import pytest
import yaml
from pypdf import PdfReader

from conftest import FIXTURE, ROOT
from documents import chapter, document, node
from obs_html import cli, pdf


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


def _live_tracker(status: str) -> dict:
    """A Document whose Base declares the live-data capability note's live source over two issue
    notes; issue 1 is labelled ready, so the declaration derives Next for it (generic-tables.md,
    Current data, The check)."""
    note = (ROOT / "spec" / "capabilities" / "live-data.md").read_text(encoding="utf-8")
    declaration = yaml.safe_load(re.search(r"```yaml\n(.*?)```", note, re.S)[1])["obsHtml"]["liveSource"]
    issues = {1: {"state": "open", "labels": ["ready"], "status": status},
              2: {"state": "closed", "labels": [], "status": "Done"}}
    records = tuple({"id": f"widgets-{number}", "type": "note", "path": f"issues/widgets-{number}.md", "fields": {
        "kind": "issue", "repo": "widgets", "number": number, **item}}
        for number, item in issues.items())
    spec = {"filters": 'kind == "issue"', "views": [{"type": "table", "name": "Board", "order": ["file.name", "status"]}],
            "obsHtml": {"liveSource": copy.deepcopy(declaration)}}
    return document("Tracker", chapter("tracker", "Tracker", node("bases", source="", spec=spec)), records=records)


@pytest.mark.browser
def test_rendered_check_fails_on_a_live_source_that_does_not_reproduce_a_row_and_passes_once_corrected(
        pdf_browser, tmp_path, capsys) -> None:
    """generic-tables.md, Current data, The check: a row whose status the declaration's derive does
    not reproduce logs one console error naming its note and the field, so --check-rendered fails;
    the corrected note passes (spec/capabilities/live-data.md tells authors to run it)."""
    for status, name in (("Running", "wrong"), ("Next", "corrected")):
        (tmp_path / f"{name}.json").write_text(json.dumps(_live_tracker(status)), encoding="utf-8")
        assert cli.main([str(tmp_path / f"{name}.json"), str(tmp_path / f"{name}.html")]) == 0
    capsys.readouterr()
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--check-rendered", str(tmp_path / "wrong.html")])
    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    errors = [line for line in error.splitlines() if line.startswith("Console error: ")]
    assert len(errors) == 1, error
    assert "note issues/widgets-1.md" in errors[0] and "derive check of field status" in errors[0]
    cli.main(["--check-rendered", str(tmp_path / "corrected.html")])
    assert "status ready, 0 console errors," in capsys.readouterr().out


# Every text of a live table's line (live-data.js, READER_TEXT), each part around its {name} and {n}.
READER_TEXTS = [part for text in re.findall(r'^\s+\w+: "([^"]*)",$', re.search(
    r"const READER_TEXT = Object\.freeze\(\{\n(.*?)\n\s+\}\);", (ROOT / "src" / "obs_html" / "live-data.js").read_text(
        encoding="utf-8"), re.S)[1], re.M) for part in re.split(r"\{\w+\}", text) if len(part.strip()) > 3]


def _recording(monkeypatch) -> dict[str, list[str]]:
    """Every request, failed request and console error of the headless pages the CLI opens."""
    seen: dict[str, list[str]] = {"requests": [], "failed": [], "errors": []}
    opened = pdf._browser_page

    @contextmanager
    def recorded(operation, html):
        with opened(operation, html) as page:
            page.on("request", lambda request: seen["requests"].append(request.url))
            page.on("requestfailed", lambda request: seen["failed"].append(request.url))
            page.on("console", lambda message: seen["errors"].append(message.text) if message.type == "error" else None)
            yield page
    monkeypatch.setattr(pdf, "_browser_page", recorded)
    return seen


@pytest.mark.browser
def test_the_headless_page_turns_live_routes_off_and_aborts_only_a_declared_origin(
        pdf_browser, fixture_artifact, tmp_path) -> None:
    """generic-tables.md, The web route (Headless printing): the flag is set before the page loads,
    and a request to the origin its web route declares is aborted; a page without one aborts nothing."""
    (tmp_path / "tracker.json").write_text(json.dumps(_live_tracker("Next")), encoding="utf-8")
    assert cli.main([str(tmp_path / "tracker.json"), str(tmp_path / "tracker.html")]) == 0
    ask = "url => fetch(url).then(() => 'answered', () => 'refused')"
    for html, refused in ((tmp_path / "tracker.html", True), (fixture_artifact, False)):
        failed: list[str] = []
        with pdf._browser_page("--export-pdf", html) as page:
            page.on("requestfailed", lambda request: failed.append(request.url))
            page.goto(html.resolve().as_uri(), wait_until="load")
            page.wait_for_function("!!globalThis.obsPages")
            assert page.evaluate("globalThis.obsLiveOff") is True
            assert failed == []
            if refused:
                assert page.evaluate(ask, "https://api.example.test/repos") == "refused"
                assert failed == ["https://api.example.test/repos"]


@pytest.mark.browser
def test_printing_a_page_with_a_web_route_reads_nothing_and_prints_only_its_saved_rows(
        pdf_browser, fixture_artifact, tmp_path, capsys, monkeypatch) -> None:
    """The PDF build, --export-pdf and --check-rendered make no request to the declared origin, log
    no console error, and print the saved rows with no line under the table, so no date or time
    (cli.md, PDF output, Rendered check); the feature fixture, without a web route, aborts nothing."""
    seen = _recording(monkeypatch)
    source = tmp_path / "tracker.json"
    source.write_text(json.dumps(_live_tracker("Next")), encoding="utf-8")
    assert cli.main([str(source), str(tmp_path / "tracker.html")]) == 0
    assert cli.main([str(source), str(tmp_path / "built.pdf")]) == 0
    cli.main(["--export-pdf", str(tmp_path / "tracker.html"), "--output", str(tmp_path / "export.pdf")])
    capsys.readouterr()
    cli.main(["--check-rendered", str(tmp_path / "tracker.html")])
    assert "status ready, 0 console errors," in capsys.readouterr().out
    assert [url for url in seen["requests"] if "example.test" in url] == []
    assert seen["errors"] == [] and seen["failed"] == []
    for printed in ("built.pdf", "export.pdf"):
        text = "\n".join(page.extract_text() for page in PdfReader(tmp_path / printed).pages)
        assert "widgets-1" in text and "widgets-2" in text, printed
        assert [part for part in READER_TEXTS if part.strip() in text] == [], printed
    seen["failed"].clear()
    cli.main(["--export-pdf", str(fixture_artifact), "--output", str(tmp_path / "fixture.pdf")])
    assert seen["failed"] == []


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


def _links(pdf: Path) -> tuple[list[str], list[str]]:
    """``pdf``'s link annotations: the named destinations of its ``/Dest`` links, which must be entries
    of the catalog's ``/Dests``, and the URIs of the others."""
    reader = PdfReader(pdf)
    dests = set(reader.trailer["/Root"]["/Dests"])
    named, uris = [], []
    for page in reader.pages:
        for entry in page.get("/Annots") or []:
            link = entry.get_object()
            if link.get("/Subtype") == "/Link":
                if "/Dest" in link:
                    named.append(str(link["/Dest"]))
                else:
                    uris.append(str(link["/A"]["/URI"]))
    assert set(named) <= dests, (pdf, named)
    return named, uris


@pytest.mark.browser
def test_pdf_links_name_no_folder_and_two_prints_from_two_folders_are_equal(
        pdf_browser, fixture_artifact, tmp_path, monkeypatch) -> None:
    """Links to places the PDF holds jump inside it, the others name the companion HTML beside it
    (spec/artifact-ui.md, Pages and PDF), so prints from two folders are equal (architecture.md, Build time)."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    folders = (tmp_path / "one" / "notes", tmp_path / "two" / "elsewhere")
    for folder in folders:
        folder.mkdir(parents=True)
        shutil.copyfile(fixture_artifact, folder / "page.html")
        cli.main([str(FIXTURE), str(folder / "page.pdf")])
        cli.main(["--export-pdf", str(folder / "page.html"), "--output", str(folder / "export.pdf")])
    for name in ("page.pdf", "export.pdf"):
        assert (folders[0] / name).read_bytes() == (folders[1] / name).read_bytes(), name
        named, uris = _links(folders[0] / name)
        assert len(named) == 5, (name, named)
        assert sorted(uris) == sorted(["https://example.org/?a=1&b=2", *(
            f"./page.html#{place}" for place in ("tags", "datum", "other", "ranked"))]), (name, uris)
        assert not any(uri.startswith("file:") or tmp_path.as_posix() in uri for uri in uris), (name, uris)


@pytest.mark.browser
def test_a_pdf_link_to_a_file_beside_the_notes_names_its_path_from_the_page(pdf_browser, tmp_path) -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    [site] = [link for link in document["links"] if link["id"] == "the-site"]
    site["href"] = "files/report.pdf"
    source = tmp_path / "document.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    cli.main([str(source), str(tmp_path / "print" / "report.pdf")])
    _, uris = _links(tmp_path / "print" / "report.pdf")
    assert "./files/report.pdf" in uris and not any(uri.startswith(("file:", "https:")) for uri in uris), uris
    assert sorted(uri for uri in uris if uri.startswith("./report.html")) == sorted(
        f"./report.html#{place}" for place in ("tags", "datum", "other", "ranked")), uris
