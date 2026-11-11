"""Browser tier: every file offer saves through the host's save path (spec/capabilities/file-offers.md).

Reader: whoever changes a control that hands the reader a file, or the downloads feature's
file offers (file-offers.js).

A fake of Claude's artifact runtime, ``claude.use`` as the viewer's type definitions describe it,
stands in before the artifact's scripts (test/browser/viewer.py, ``with_stand_in``): without the
``downloads`` capability the file offers are hidden and the downloads warning says what to
declare; with it each offer calls ``save({filename, data})``, and a refusal shows beside the
control. Without the runtime each offer is a browser download, as it always was.
"""
import base64
import json
from pathlib import Path

import pytest

from artifacts import artifact_html
from browser.viewer import open_viewer, with_stand_in
from documents import chapter, document, heading, node, paragraph

REPORT = b"%PDF-1.4\n% obs file offers fixture\n%%EOF\n"
BUILD = {"repository": "https://example.invalid/obs", "commit": "0123456789abcdef0123456789abcdef01234567",
         "lockfiles": {"uv.lock": {"obs": "0.2.3"}},
         "arguments": ["--adapter", "html", "--destination", "report.html", "--adapter-option",
                       "embed-attachments=true", "--embed-source"]}
WIDTHS = {"wide": 1100, "phone": 390}
# The file offers of the fixture and the file each one hands over.
OFFERS = {"reviewed": "[data-comment-save]", "source": "[data-source-exports] [data-source-download]",
          "attachment": "[data-active-chapter] a.attachment-download"}
NO_SAVE_PICKER = "delete window.showSaveFilePicker"


def fake_claude(downloads: str) -> str:
    """Claude's artifact runtime: ``use`` resolves later, never within the first run, to the
    ``downloads`` namespace (``downloads`` "saves" or "declines") or to null ("absent")."""
    return NO_SAVE_PICKER + ";" + """
(() => {
    const saves = [];
    globalThis.fakeClaude = {saves};
    const mode = %s;
    const downloads = Object.freeze({
        async save({filename, data}) {
            const blob = data instanceof Blob ? data : new Blob([data]);
            const head = new TextDecoder("latin1").decode(new Uint8Array(await blob.slice(0, 16).arrayBuffer()));
            saves.push({filename, head, size: blob.size});
            if (mode === "declines") throw {code: "declined", message: "The viewer declined the save."};
            return {status: "saved"};
        },
    });
    globalThis.claude = Object.freeze({
        use: (name) => new Promise((resolve) => setTimeout(
            () => resolve(name === "downloads" && mode !== "absent" ? downloads : null), 0)),
    });
})();""" % json.dumps(downloads)


def offers_document() -> dict:
    """A Document with an attachment and a source archive, so it carries every kind of offer the
    fixture reaches: the reviewed HTML, the source ZIP and an attachment."""
    source = document("Offers", chapter("one", "One", heading(1, "One"), paragraph(
        node("embeds", target="report.pdf", chapter=None, asset="report-pdf"))))
    source["assets"] = [{"id": "report-pdf", "href": "report.pdf", "mediaType": "application/pdf",
                         "path": "input/report.pdf", "data": base64.b64encode(REPORT).decode("ascii")}]
    source["capabilities"] = sorted({*source["capabilities"], "embeds"})
    source["sourceArchive"] = {"files": [
        {"path": "manifest.md", "data": base64.b64encode(b"- [[one]]\n").decode("ascii")},
        {"path": "input/report.pdf", "asset": "report-pdf"},
    ], "build": json.loads(json.dumps(BUILD))}
    return source


def artifact() -> str:
    return artifact_html(offers_document(), embed_attachments=True)


def show(frame, offer: str) -> None:
    """Bring the offer's place on screen: its bar, or the chapter that holds the attachment, with
    the pointer off the last control, whose help card would cover the next."""
    frame.page.mouse.move(0, 0)
    frame.page.keyboard.press("Escape")
    frame.locator("html").evaluate("() => ['comments', 'settings'].forEach(obsArtifact.closeBar)")
    if offer == "reviewed":
        frame.locator("html").evaluate("() => obsArtifact.openBar('comments')")
    elif offer == "source":
        frame.locator("html").evaluate("() => obsArtifact.openBar('settings')")
    else:
        frame.locator("html").evaluate("() => { obsPages.setPaged(false); obsArtifact.activateChapter('one'); }")


def runtime_answered(frame) -> None:
    """Wait until the page has asked the runtime for downloads and had its answer."""
    frame.locator("html").evaluate("() => globalThis.obsFileOffers?.ready")


@pytest.mark.browser
@pytest.mark.parametrize("width", WIDTHS.values(), ids=WIDTHS.keys())
def test_in_claude_without_downloads_every_offer_is_hidden_and_the_warning_says_what_to_declare(
        tmp_path: Path, reader_browser, width: int) -> None:
    from playwright.sync_api import expect

    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, artifact(), "light", width=width,
                               init_script=fake_claude("absent"))
    runtime_answered(frame)
    for offer, selector in {**OFFERS, "attach": "[data-source-exports] [data-source-attach]"}.items():
        show(frame, "source" if offer == "attach" else offer)
        expect(frame.locator(selector)).to_have_count(1)
        expect(frame.locator(selector)).to_be_hidden()
    warning = frame.locator('dl[data-capability="downloads"]')
    expect(warning).to_have_count(1)
    expect(warning).to_contain_text("downloads capability")
    assert errors == []


@pytest.mark.browser
@pytest.mark.parametrize("width", WIDTHS.values(), ids=WIDTHS.keys())
def test_in_claude_with_downloads_every_offer_saves_through_it(tmp_path: Path, reader_browser, width: int) -> None:
    from playwright.sync_api import expect

    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, artifact(), "light", width=width,
                               init_script=fake_claude("saves"))
    runtime_answered(frame)
    expected = {"reviewed": ("Offers-reviewed.html", "<!doctype html>"),
                "source": ("obs-html-source.zip", "PK"), "attachment": ("report.pdf", "%PDF-1.4")}
    for count, (offer, (filename, head)) in enumerate(expected.items(), start=1):
        show(frame, offer)
        frame.locator(OFFERS[offer]).click()
        frame.wait_for_function(f"() => fakeClaude.saves.length >= {count}", timeout=5000)
        saved = frame.locator("html").evaluate("() => fakeClaude.saves")[-1]
        assert saved["filename"] == filename and saved["size"] > 0, saved
        assert saved["head"].lower().startswith(head.lower()), saved
    assert len(frame.locator("html").evaluate("() => fakeClaude.saves")) == 3
    assert errors == []


@pytest.mark.browser
def test_in_claude_a_declined_save_says_so_beside_the_offer(tmp_path: Path, reader_browser) -> None:
    from playwright.sync_api import expect

    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, artifact(), "light", width=WIDTHS["phone"],
                               init_script=fake_claude("declines"))
    runtime_answered(frame)
    show(frame, "attachment")
    link = frame.locator(OFFERS["attachment"])
    link.click()
    note = frame.locator("[data-active-chapter] a.attachment-download + [data-capability-message]")
    expect(note).to_contain_text("declined")
    assert len(frame.locator("html").evaluate("() => fakeClaude.saves")) == 1
    assert errors == []


@pytest.mark.browser
def test_without_the_runtime_every_offer_is_a_browser_download(tmp_path: Path, reader_browser) -> None:
    path = tmp_path / "offers.html"
    path.write_text(with_stand_in(artifact(), NO_SAVE_PICKER), encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": WIDTHS["phone"], "height": 800})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(path.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    expected = {"reviewed": b"<!doctype html>", "source": b"PK", "attachment": REPORT}
    for offer, head in expected.items():
        show(page.main_frame, offer)
        with page.expect_download(timeout=5000) as download:
            page.locator(OFFERS[offer]).click()
        saved = tmp_path / download.value.suggested_filename
        download.value.save_as(saved)
        assert saved.read_bytes().lower().startswith(head.lower()), offer
    assert errors == []
