"""Callouts, embeds and attachments render as the interim adapter in obs rendered them.

Each test builds a contract-valid Document as the core emits it (see the core's vault.py:
a callout's ``kind`` is the canonical type, its ``title`` the authored rest of the marker line;
an attachment names a Document asset; an embed keeps its target and the chapter it resolves to).
"""
import re
import json

import pytest

from artifacts import artifact_html
from conftest import ROOT
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import render
from obs_html.artifact_data import decode_artifact_data

from conftest import PIXEL
from documents import chapter, document as build, heading, node, paragraph, text, without_node_ids


CONFIG = load_config()
# Canonical callout type: (tone, accessible name), as the interim's callouts.py and its tests had them.
CALLOUTS = {
    "note": "accent", "abstract": "accent", "info": "accent", "todo": "accent", "tip": "accent",
    "success": "success", "question": "warning", "warning": "warning", "failure": "failure",
    "danger": "failure", "bug": "failure", "example": "accent", "quote": "neutral",
}


def _html(*content: dict, assets: list[dict] | None = None, records: tuple[dict, ...] = ()) -> str:
    document = build("Doc", chapter("one", "One", *content), chapter("two", "Two"), records=records)
    document["assets"] = assets or []
    notes = decode_artifact_data(render(document, CONFIG))["notes"]
    return next(note for note in notes if note["slug"] == "one")["html"]


def _callout(kind: str, title: str | list[dict] = "", *body: str | dict) -> dict:
    """A callout node; a string ``title`` is the one text node the core parses plain text into."""
    nodes = title if isinstance(title, list) else [text(title)] if title else []
    result = {"type": "callouts", "attrs": {"kind": kind, "title": nodes}, "children": []}
    if body:
        result["children"] = [paragraph(*body)]
    return result


@pytest.mark.parametrize("kind", sorted(CALLOUTS))
def test_callout_types_render_as_titled_tone_cards(kind) -> None:
    link = node("wikilinks", target="two", chapter="two", heading="", label="two")
    name = kind.capitalize()  # The core's title for an untitled callout of this kind.
    html = _html(_callout(kind, name, "Body with ", link, "."))
    tone = CALLOUTS[kind]
    assert html == (
        f'<aside class="content-card content-callout content-callout--{tone}" '
        f'data-callout="{kind}" aria-label="{name}">\n'
        f'<header class="content-card-title">{name}</header>\n'
        '<p>Body with <a class="internal-link" href="#two">Two</a>.</p>\n'
        '</aside>\n'
    )


def test_a_callout_title_renders_its_inline_nodes() -> None:
    link = node("wikilinks", target="two", chapter="two", heading="", label="limits")
    strong = {"type": "strong", "attrs": {}, "children": [link]}
    html = _html(_callout("warning", [text("Check "), strong, text(" <b>raw</b>")], "First."))
    assert ('<header class="content-card-title">Check <strong><a class="internal-link" href="#two">'
            'limits</a></strong> &lt;b&gt;raw&lt;/b&gt;</header>') in html
    assert "[!" not in html


def test_a_callout_title_heading_link_shows_the_core_s_link_label() -> None:
    """``> [!note] See [[two#Authorization]]``: the title shows the label the core gave the link
    (obs capabilities/wikilinks#Link text), never the chapter title alone."""
    link = node("wikilinks", target="two", chapter="two", heading="Authorization",
                label="Command Fences > Authorization")
    html = _html(_callout("note", [text("See "), link], "Body."))
    assert ('<header class="content-card-title">See <a class="internal-link" href="#two">'
            'Command Fences &gt; Authorization</a></header>') in html


def test_a_callout_with_only_a_title_renders_a_titled_card() -> None:
    assert _html(_callout("success", "All checks passed")) == (
        '<aside class="content-card content-callout content-callout--success" '
        'data-callout="success" aria-label="Success">\n'
        '<header class="content-card-title">All checks passed</header>\n'
        '</aside>\n'
    )


def test_important_is_an_untitled_emphasis_card_that_accepts_a_title() -> None:
    assert _html(_callout("important", "", "The conclusion.")) == (
        '<aside class="content-card content-emphasis" aria-label="Important">\n'
        '<p>The conclusion.</p>\n</aside>\n'
    )
    assert _html(_callout("important", "Key result", "The conclusion.")) == (
        '<aside class="content-card content-emphasis" aria-label="Important">\n'
        '<header class="content-card-title">Key result</header>\n'
        '<p>The conclusion.</p>\n</aside>\n'
    )


def test_an_unknown_callout_kind_names_the_chapter_the_kind_and_the_remedy() -> None:
    with pytest.raises(InputError) as failure:
        _html(_callout("shout", "", "Body."))
    assert failure.value.source == "Document of manifest.md"
    assert re.fullmatch(r"chapters\[0\]\.content\[\d+\]\.attrs\.kind", failure.value.field), failure.value.field
    assert "obs-document" in failure.value.remedy


IMAGE = {"id": "logo", "href": "images/logo.png", "mediaType": "image/png", "path": "images/logo.png",
         "data": PIXEL}
DATA = {"id": "data", "href": "input/data.bin", "mediaType": "application/octet-stream", "path": "input/data.bin",
        "data": "AA=="}


def test_an_image_attachment_is_document_content() -> None:
    html = _html(paragraph(node("attachments", asset="logo", label="The logo")), assets=[IMAGE])
    assert html == f'<p><img src="data:image/png;base64,{PIXEL}" alt="The logo"></p>\n'


def test_a_file_attachment_renders_as_provenance_text() -> None:
    html = _html(paragraph("See ", node("attachments", asset="data", label="the data"), "."), assets=[DATA])
    assert html == ('<p>See <span class="source-reference" data-source-path="input/data.bin">the data</span>'
                    ' (<code>input/<wbr>data.<wbr>bin</code>).</p>\n')


def test_an_unlabelled_file_attachment_is_labelled_by_its_file_name() -> None:
    html = _html(paragraph(node("attachments", asset="data", label="")), assets=[DATA])
    assert '<span class="source-reference" data-source-path="input/data.bin">data.bin</span>' in html


def test_an_attachment_naming_an_unknown_asset_names_the_chapter_and_the_remedy() -> None:
    with pytest.raises(InputError) as failure:
        _html(paragraph(node("attachments", asset="gone", label="x")))
    assert failure.value.source == "Document of manifest.md"
    assert re.fullmatch(r"chapters\[0\]\.content\[\d+\]\.children\[0\]\.attrs\.asset", failure.value.field), failure.value.field
    assert "obs-document" in failure.value.remedy


def test_attachments_never_carry_an_absolute_local_path() -> None:
    """The core checks that the file exists inside the vault; the adapter shows its vault path, never
    the reference as authored."""
    absolute = {"id": "abs", "href": "/srv/vault/data.bin", "mediaType": "application/octet-stream",
                "path": "data.bin", "data": "AA=="}
    html = _html(paragraph(node("attachments", asset="abs", label="x")), assets=[absolute])
    assert html == ('<p><span class="source-reference" data-source-path="data.bin">x</span>'
                    ' (<code>data.<wbr>bin</code>)</p>\n')


def test_a_file_embed_renders_like_an_attachment() -> None:
    icon = {"id": "icon", "href": "icon.svg", "mediaType": "image/svg+xml", "path": "icon.svg", "data": "PHN2Zy8+"}
    html = _html(paragraph(node("embeds", target="icon.svg", chapter=None, asset="icon"), " ",
                           node("embeds", target="input/data.bin", chapter=None, asset="data")),
                 assets=[icon, DATA])
    assert html == ('<p><img src="data:image/svg+xml;base64,PHN2Zy8+" alt=""> '
                    '<span class="source-reference" data-source-path="input/data.bin">data.bin</span>'
                    ' (<code>input/<wbr>data.<wbr>bin</code>)</p>\n')


def test_callout_bodies_render_their_inline_nodes() -> None:
    html = _html(_callout("tip", "", text("Use "), node("attachments", asset="data", label="it")), assets=[DATA])
    assert '<p>Use <span class="source-reference" data-source-path="input/data.bin">it</span>' in html


def test_a_core_built_callout_body_renders_its_list_wikilink_nested_callout_and_link() -> None:
    """The ``callouts`` vault of fixtures/build_documents.py, built by the core: the body arrives as
    nodes, and the Document names callouts, not extensions."""
    document = json.loads((ROOT / "test" / "fixtures" / "documents" / "callouts.json").read_text(encoding="utf-8"))
    assert "callouts" in document["capabilities"] and "extensions" not in document["capabilities"]
    html = without_node_ids(next(note for note in decode_artifact_data(render(document, CONFIG))["notes"]
                                 if note["slug"] == "guide")["html"])
    assert html.endswith(
        '<aside class="content-card content-callout content-callout--warning" data-callout="warning" '
        'aria-label="Warning">\n<header class="content-card-title">Check the limits</header>\n'
        '<ul>\n<li>first item</li>\n<li>see <a class="internal-link" href="#target">Target</a></li>\n</ul>\n'
        '<aside class="content-card content-callout content-callout--accent" data-callout="tip" '
        'aria-label="Tip">\n<header class="content-card-title">Tip</header>\n'
        '<p>Nested <strong>tip</strong> with <a href="https://example.org">a link</a>.</p>\n'
        '</aside>\n</aside>\n'
    )


@pytest.mark.browser
def test_callout_tones_are_distinct_titled_cards_in_the_reader(tmp_path, reader_browser) -> None:
    """Moved from the interim's browser tests: each tone has its own border and fill, and the
    title takes the border colour, in the paged reader and the print book alike."""
    kinds = ["note", "success", "warning", "danger", "quote"]
    document = build("Doc", chapter("one", "One", *(_callout(kind, kind.capitalize(), f"{kind} body.")
                                                   for kind in kinds)))  # The core's titles.
    artifact = tmp_path / "artifact.html"
    artifact.write_text(artifact_html(document), encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": 1200, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate("obsArtifact.activateChapter('one')")
    page.evaluate("window.print = () => {}; globalThis.obsPages.exportPDF()")
    for root in ("[data-chapter-body]", ".print-book"):
        cards = page.locator(f"{root} aside.content-callout").evaluate_all("""nodes => nodes.map(node => {
            const style = getComputedStyle(node);
            const title = node.querySelector(':scope > .content-card-title');
            return {kind: node.dataset.callout, border: style.borderTopColor,
                    fill: style.backgroundColor, title: title.textContent,
                    titleColor: getComputedStyle(title).color};
        })""")
        assert [card["kind"] for card in cards] == kinds, root
        assert [card["title"] for card in cards] == [kind.capitalize() for kind in kinds]
        assert len({card["border"] for card in cards}) == len(kinds)
        assert len({card["fill"] for card in cards}) == len(kinds)
        assert all(card["titleColor"] == card["border"] for card in cards)
    assert errors == []


def _identified(block: dict, identifier: str) -> dict:
    """``block`` with the core id the core's node_ids gives it."""
    return {**block, "id": identifier}


VISION = (
    _identified(heading(1, "Vision"), "section-title"),
    _identified(paragraph("The statement, see ", node("wikilinks", target="", chapter="vision", heading="Pitch",
                                                       label="Pitch"), "."), "statement"),
    _identified(heading(2, "Pitch"), "section-pitch"),
    _identified(paragraph("For owners."), "paragraph-owners"),
    _identified(heading(3, "Detail"), "section-detail"),
    _identified(paragraph("Detail of the pitch."), "paragraph-detail"),
    _identified(heading(2, "Later"), "section-later"),
    _identified(paragraph("Not part of the pitch."), "paragraph-later"),
)


def _embed(fragment: str, block: str) -> dict:
    return node("embeds", target="vision", chapter="vision", heading=fragment, block=block)


def _embedding(*content: dict, vision: tuple[dict, ...] = VISION) -> dict:
    """Each note's html, of a Document whose chapter one holds ``content`` and whose chapter vision ``vision``."""
    document = build("Doc", chapter("one", "One", _identified(heading(1, "One"), "section-one"), *content),
                     chapter("vision", "Vision", *vision))
    return {note["slug"]: note for note in decode_artifact_data(render(document, CONFIG))["notes"]}


def _copies(html: str) -> list[str]:
    return re.findall(r'<div class="embed" .*?\n</div>\n', html, re.S)


def test_a_block_embed_shows_the_block_and_links_to_where_it_lives() -> None:
    notes = _embedding(_embed("^statement", "statement"))

    assert _copies(notes["one"]["html"]) == [
        '<div class="embed" data-embed-chapter="vision" data-embed-block="statement">\n'
        '<p>The statement, see <a class="internal-link" href="#vision/pitch">Pitch</a>.</p>\n'
        '<p class="embed-source"><a class="internal-link embed" href="#vision/block-statement">Vision</a></p>\n'
        '</div>\n']
    # Where it lives, the block carries its anchor, as the target of a block link does.
    assert '<p data-node-id="statement" id="vision--block-statement">' in notes["vision"]["html"]


def test_a_section_embed_shows_its_heading_up_to_the_next_of_its_level() -> None:
    [copy] = _copies(_embedding(_embed("Pitch", "section-pitch"))["one"]["html"])

    assert copy == (
        '<div class="embed" data-embed-chapter="vision" data-embed-block="section-pitch">\n'
        '<h2>Pitch</h2>\n<p>For owners.</p>\n<h3>Detail</h3>\n<p>Detail of the pitch.</p>\n'
        '<p class="embed-source"><a class="internal-link embed" href="#vision/pitch">Vision</a></p>\n</div>\n')


def test_links_in_a_shown_block_go_where_they_go_in_its_chapter() -> None:
    [copy] = _copies(_embedding(_embed("^statement", "statement"))["one"]["html"])

    assert re.findall(r'href="([^"]+)"', copy) == ["#vision/pitch", "#vision/block-statement"]


def test_a_shown_copy_carries_no_id_and_no_anchor() -> None:
    marked = _identified(paragraph("Marked. ", node("marks", category="risk", id="watch")), "marked")
    linked = paragraph(node("wikilinks", target="vision", chapter="vision", heading="^statement",
                            label="Vision > ^statement", block="statement"))
    vision = (*VISION[:3], marked, *VISION[3:])
    notes = _embedding(_embed("Pitch", "section-pitch"), linked, vision=vision)
    [copy] = _copies(notes["one"]["html"])

    assert "Marked." in copy and "<h2>Pitch</h2>" in copy
    assert not re.search(r'\s(?:id|data-node-id)="', copy)
    assert notes["one"]["marks"] == []  # The mark has its one entry where it lives.
    assert [mark["anchor"] for mark in notes["vision"]["marks"]] == ["mark-vision-risk-watch"]


def test_a_block_embed_in_a_table_cell_is_its_link_alone() -> None:
    cell = {"type": "table-cell", "attrs": {}, "children": [_embed("^statement", "statement")]}
    table = {"type": "table", "attrs": {}, "children": [{"type": "table-row", "attrs": {}, "children": [cell]}]}
    html = _embedding(table)["one"]["html"]

    assert _copies(html) == []
    assert '<td><a class="internal-link embed" href="#vision/block-statement">Vision</a></td>' in html


@pytest.mark.parametrize("vision", [
    VISION[:1],  # The block is not in its chapter.
    (*VISION[:2], _identified(heading(2, "Pitch"), "section-pitch"),  # The embeds show each other.
     node("embeds", target="one", chapter="one", heading="One", block="section-one")),
], ids=["missing", "cycle"])
def test_an_embed_whose_block_is_not_in_its_chapter_is_refused(vision: tuple[dict, ...]) -> None:
    with pytest.raises(InputError) as failure:
        _embedding(_embed("Pitch", "section-pitch"), vision=vision)

    assert failure.value.source == "Document of manifest.md"
    assert re.fullmatch(r"chapters\[\d+\]\.content\[\d+\]\.attrs\.block", failure.value.field)
    assert "obs-document" in failure.value.remedy


def test_a_shown_figure_keeps_the_number_it_has_where_it_lives() -> None:
    document = json.loads((ROOT / "test" / "fixtures" / "documents" / "figure-references.json").read_text(encoding="utf-8"))
    chapters = {chapter_["id"]: chapter_ for chapter_ in document["chapters"]}
    chapters["one"]["content"].append(node("embeds", target="two", chapter="two", heading="^d", block="d"))
    notes = {note["slug"]: note["html"] for note in decode_artifact_data(render(document, CONFIG))["notes"]}
    [copy] = _copies(notes["one"])

    assert '<span class="figure-number">Figure 2.4:</span> Figure d.' in copy
    assert '<span class="figure-number">Figure 2.4:</span> Figure d.' in notes["two"]
    assert not re.search(r'\s(?:id|data-node-id)="', copy)
