"""obs_html.pdf_links without a browser: small PDFs with pypdf link annotations (spec/artifact-ui.md,
Pages and PDF)."""
import sys
from io import BytesIO
from pathlib import Path, PureWindowsPath

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link

from obs_html.pdf_links import portable


def _pdf(*uris: str, dest: bool = False) -> bytes:
    """A one-page PDF with one link annotation per URI, and one ``/Dest`` link where ``dest`` is set."""
    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    for index, uri in enumerate(uris):
        writer.add_annotation(0, Link(rect=(10, 10 + 20 * index, 90, 25 + 20 * index), url=uri))
    if dest:
        writer.add_annotation(0, Link(rect=(100, 10, 190, 25), target_page_index=0))
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _links(pdf: bytes) -> list[str]:
    """Each link annotation of ``pdf``: its URI, or ``dest`` for one with a ``/Dest``."""
    found = []
    for page in PdfReader(BytesIO(pdf)).pages:
        for entry in page.get("/Annots") or []:
            link = entry.get_object()
            found.append("dest" if "/Dest" in link else str(link["/A"]["/URI"]))
    return found


@pytest.fixture
def printed(tmp_path) -> Path:
    folder = tmp_path / "notes"
    folder.mkdir()
    return folder / ".page.k3x9.html"


def test_links_to_the_printed_page_name_the_companion_and_their_fragment(printed) -> None:
    pdf = _pdf(f"{printed.as_uri()}?#datum", f"{printed.as_uri()}#x", printed.as_uri())
    result = portable(pdf, printed, "page.html")
    assert _links(result) == ["./page.html#datum", "./page.html#x", "./page.html"]


@pytest.mark.parametrize(("companion", "named"), [
    ("my page.html", "./my%20page.html#datum"), ("grün.html", "./gr%C3%BCn.html#datum")])
def test_a_companion_name_is_percent_encoded_to_ascii(printed, companion, named) -> None:
    [uri] = _links(portable(_pdf(f"{printed.as_uri()}?#datum"), printed, companion))
    assert uri == named and uri.isascii()


def test_links_to_other_local_files_name_their_path_from_the_page_folder(printed, tmp_path) -> None:
    report = printed.parent / "files" / "report.pdf"
    shared = tmp_path / "shared" / "x y.pdf"
    pdf = _pdf(report.as_uri(), f"{shared.as_uri()}?page=2#top")
    assert _links(portable(pdf, printed, "page.html")) == ["./files/report.pdf", "../shared/x%20y.pdf?page=2#top"]


@pytest.mark.skipif(sys.platform != "win32", reason="only Windows has drives")
def test_a_file_on_another_drive_loses_its_link(printed) -> None:
    drive = "D:" if PureWindowsPath(printed).drive.upper() != "D:" else "E:"
    other = Path(f"{drive}\\elsewhere\\report.pdf")
    result = portable(_pdf(other.as_uri(), "https://example.org/"), printed, "page.html")
    assert _links(result) == ["https://example.org/"]


def test_other_links_and_every_other_object_stay(printed) -> None:
    pdf = _pdf("https://example.org/?a=1&b=2", "mailto:someone@example.org", printed.as_uri(), dest=True)
    result = portable(pdf, printed, "page.html")
    assert _links(result) == ["https://example.org/?a=1&b=2", "mailto:someone@example.org", "./page.html", "dest"]
    before, after = PdfReader(BytesIO(pdf)), PdfReader(BytesIO(result))
    for reader in (before, after):  # The /Dest link still names the first page, fitted.
        target, fit = reader.pages[0]["/Annots"][3].get_object()["/Dest"]
        assert (target.idnum, fit) == (reader.pages[0].indirect_reference.idnum, "/Fit")
    assert after.pages[0].get_contents() == before.pages[0].get_contents()


def test_a_pdf_without_file_links_is_returned_as_given(printed) -> None:
    pdf = _pdf("https://example.org/", "mailto:someone@example.org", dest=True)
    assert portable(pdf, printed, "page.html") is pdf


def test_no_result_holds_a_file_uri(printed, tmp_path) -> None:
    pdf = _pdf(f"{printed.as_uri()}?#datum", (tmp_path / "a.pdf").as_uri(), (printed.parent / "b.pdf").as_uri())
    links = _links(portable(pdf, printed, "page.html"))
    assert links and not any(link.startswith("file:") or str(tmp_path.as_posix()) in link for link in links)
