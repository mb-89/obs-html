"""Images and attachments render from the Document's assets, never from the vault or the network.

The core embeds each referenced vault file's bytes and each fetched remote image's bytes in its
asset (obs architecture, Asset bytes); an image whose asset has no bytes shows its alt text.
"""
import base64
import shutil
import subprocess
import sys

import pytest

from browser.viewer import open_viewer
from conftest import PIXEL, built_once
from documents import chapter, document as build, node, paragraph
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.render import RenderError, render


CONFIG = load_config()
PIXEL_IMAGE = f'src="data:image/png;base64,{PIXEL}"'
BADGE = (b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
         b'<rect width="40" height="20" fill="#7c3aed"/></svg>')


def _notes(document: dict) -> dict[str, dict]:
    return {note["slug"]: note for note in decode_artifact_data(render(document, CONFIG))["notes"]}


def _vault_document(folder, core_root) -> None:
    """A Document the core builds from a vault with images, an embedded file and an attachment."""
    vault = folder / "vault"
    (vault / "media").mkdir(parents=True)
    (vault / "input").mkdir()
    (vault / "media" / "pixel.png").write_bytes(base64.b64decode(PIXEL))
    (vault / "input" / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (vault / "manifest.md").write_text(
        '---\ntitle: Assets\nsubtitle: "![Mark](media/pixel.png)"\n---\n- [[chapter]]\n', encoding="utf-8")
    (vault / "chapter.md").write_text(
        "---\nlogo: \"![Logo](media/pixel.png)\"\n---\n"
        "# Chapter\n\nAn image ![Pixel](media/pixel.png), an embed ![[pixel.png]] and "
        "![the data](input/data.csv).\n", encoding="utf-8")
    run = [sys.executable, "-m"]
    subprocess.run([*run, "obs.capabilities", "--notes", str(core_root / "spec" / "capabilities"),
                    "--output", str(folder / "capabilities.json")], check=True)
    subprocess.run([*run, "obs.document", "--source", str(vault / "manifest.md"),
                    "--document", str(folder / "document.json"),
                    "--capability-reference", str(folder / "capabilities.json")], check=True)
    shutil.rmtree(vault)


def test_a_document_whose_vault_was_deleted_renders_every_image_and_attachment(tmp_path_factory, core_root):
    import json

    folder = built_once(tmp_path_factory, "images-from-assets", lambda path: _vault_document(path, core_root))
    assert not (folder / "vault").exists()
    notes = _notes(json.loads((folder / "document.json").read_text(encoding="utf-8")))

    body = notes["chapter"]["html"]
    assert f'<img {PIXEL_IMAGE} alt="Pixel">' in body
    assert f'<img {PIXEL_IMAGE} alt="">' in body
    assert '<span class="source-reference" data-source-path="input/data.csv">the data</span>' in body
    assert f'<img {PIXEL_IMAGE} alt="Logo">' in notes["chapter"]["frontmatterHtml"]["logo"]
    assert f'<img {PIXEL_IMAGE} alt="Mark">' in notes["home"]["html"]
    assert 'src="media/' not in json.dumps(notes)


@pytest.mark.parametrize("image, what", [
    (node("embeds", target="x.png", chapter=None, asset="gone"), "embed 'x.png' names asset 'gone'"),
    ({"type": "text", "attrs": {"asset": "gone"}, "children": [], "text": "X"}, "image names asset 'gone'"),
])
def test_an_image_naming_an_unknown_asset_names_the_chapter_and_the_remedy(image, what) -> None:
    with pytest.raises(RenderError, match=rf"^Chapter one: .*{what}.*regenerate the Document with the obs core"):
        render(build("Doc", chapter("one", "One", paragraph(image))), CONFIG)


def _remote_document() -> dict:
    """A remote image the build fetched and one it could not fetch, in the subtitle and in text."""
    fetched = {"id": "badge", "href": "https://badges.test/fetched.svg", "mediaType": "image/svg+xml",
               "data": base64.b64encode(BADGE).decode("ascii")}
    failed = {"id": "gone", "href": "https://badges.test/gone.svg", "mediaType": "image/svg+xml"}
    document = build(
        "Remote", chapter("one", "One", paragraph(node("attachments", asset="badge", label="Fetched"), " ",
                                                  node("attachments", asset="gone", label="Gone"))),
        metadata={"subtitle": f"![Fetched]({fetched['href']}) ![Gone]({failed['href']})"})
    document["assets"] = [fetched, failed]
    return document


def test_an_image_without_data_shows_its_alt_text_and_never_its_url() -> None:
    notes = _notes(_remote_document())
    for html in (notes["one"]["html"], notes["home"]["html"]):
        assert '<span class="image-unavailable" role="img" aria-label="Gone">Gone</span>' in html
        assert "gone.svg" not in html
        assert "fetched.svg" not in html
        assert 'alt="Fetched"' in html


@pytest.mark.browser
def test_with_the_network_blocked_a_fetched_remote_image_renders_and_a_failed_one_shows_its_label(
        tmp_path, reader_browser) -> None:
    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, render(_remote_document(), CONFIG), "light")
    subtitle = frame.locator(".document-subtitle").first
    image = subtitle.locator('img[alt="Fetched"]')
    image.wait_for()
    assert image.evaluate("node => node.complete && node.naturalWidth") == 40
    label = subtitle.locator(".image-unavailable")
    assert label.inner_text() == "Gone"
    assert label.is_visible()
    assert errors == []
