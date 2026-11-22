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


BOTTOM_LINES = ROOT / "test" / "fixtures" / "documents" / "bottom-lines.json"
"""The bottom-line vault of fixtures/build_documents.py, built by the core (artifact-ui.md, Bottom lines)."""


def _bottom_lines(change=None) -> dict[str, str]:
    """Each note's html, of the bottom-line vault's Document as ``change`` leaves it."""
    document = json.loads(BOTTOM_LINES.read_text(encoding="utf-8"))
    if change is not None:
        change(document, _chapters_of(document))
    return {note["slug"]: note["html"] for note in decode_artifact_data(render(document, CONFIG))["notes"]}


def _chapters_of(document: dict) -> dict[str, dict]:
    found = {}
    stack = list(document["chapters"])
    while stack:
        current = stack.pop()
        found[current["id"]] = current
        stack.extend(current["children"])
    return found


BOX = '<aside class="content-card content-emphasis" data-callout="bluf" aria-label="Bottom line"'


def _box(html: str) -> str:
    """The page's one bottom-line box."""
    [box] = re.findall(rf'{BOX}.*?\n</aside>\n', html, re.S) if html.count(BOX) == 1 else [None]
    assert box is not None, html
    return box


def _items(box: str) -> list[str]:
    return re.findall(r"<li .*?</li>", box, re.S)


def test_a_bottom_line_renders_under_the_chapter_title_wherever_authored() -> None:
    notes = _bottom_lines()

    product, plan = notes["product"], notes["plan"]
    assert re.match(r'<h1 id="product--product"[^>]*>Product</h1>\n' + re.escape(BOX) + ' data-node-id="callouts-',
                    product)
    assert product.index("Intro prose.") > product.index(_box(product))
    assert product.count('data-callout="bluf"') == 1  # Nothing at the authored place.
    assert re.match(r"<h1[^>]*>Plan</h1>\n" + re.escape(BOX), plan)
    assert plan.index(_box(plan)) < plan.index(">Steps</h2>")
    assert '<header class="content-card-title">Why it matters</header>' in _box(notes["vision"])


def test_a_bottom_line_is_first_without_a_leading_heading_and_a_bless_record_follows_it() -> None:
    def change(document, chapters):
        chapters["step"]["content"] = [node for node in chapters["step"]["content"] if node["type"] != "section"]
        chapters["plan"]["bless"] = {"version": "1" * 64, "answer": {
            "chapter": "plan", "version": "1" * 64, "verdict": "decline", "comment": "Not yet."}}

    notes = _bottom_lines(change)

    assert notes["step"].startswith(BOX)
    plan = notes["plan"]
    assert plan.index(_box(plan)) < plan.index("data-bless-record") < plan.index(">Steps</h2>")


def test_a_bottom_line_lists_its_children_s_leads_with_links() -> None:
    box = _box(_bottom_lines()["product"])

    vision, plan = _items(box)
    assert re.fullmatch(r'<li data-embed-chapter="vision" data-embed-block="paragraph-[0-9a-f]+"><p><a class="internal-link" '
                        r'href="#vision">Vision</a><br>\nVision lead, for every <a class="internal-link" '
                        r'href="#other/owner">owner</a>\.</p>\n</li>', vision)
    assert re.fullmatch(r'<li data-embed-chapter="plan" data-embed-block="paragraph-[0-9a-f]+"><p><a class="internal-link" '
                        r'href="#plan">Plan</a><br>\nPlan lead\.</p>\n</li>', plan)
    assert box.index('<ul class="bottom-line-list">') > box.index("The product in one sentence")


def test_a_child_s_title_stands_alone_on_its_line_so_its_punctuation_is_never_doubled() -> None:
    def change(document, chapters):
        chapters["vision"]["title"] = "Part 1: scope"
        chapters["plan"]["title"] = "Why now?"

    box = _box(_bottom_lines(change)["product"])

    assert '>Part 1: scope</a><br>\nVision lead, for every ' in box
    assert '>Why now?</a><br>\nPlan lead.</p>' in box
    assert "</a>:" not in box


def test_only_the_lead_goes_up_and_only_one_level() -> None:
    notes = _bottom_lines()

    product = notes["product"]
    assert "Vision second paragraph." not in product and "Step lead." not in product
    assert not re.search(r'\s(?:id|data-node-id)="', "".join(_items(_box(product))))
    assert [re.search(r'data-embed-chapter="([^"]+)"', item)[1] for item in _items(_box(notes["plan"]))] == ["step"]
    assert '<ul class="bottom-line-list">' not in notes["step"] and '<ul class="bottom-line-list">' not in notes["vision"]
    assert 'data-callout="bluf"' not in notes["other"]


def test_home_lists_the_top_level_leads_after_its_own_bottom_line() -> None:
    home = _bottom_lines()["home"]
    box = _box(home)

    assert home.index(box) < home.index("Abstract prose.")
    assert box.index("The probe in one sentence.") < box.index('<ul class="bottom-line-list">')
    assert [re.search(r'data-embed-chapter="([^"]+)"', item)[1] for item in _items(box)] == ["product"]
    assert "Aside lead." not in home  # A note the manifest does not list is no top-level chapter.
    assert ('<a class="internal-link" href="#product">Product</a><br>\nThe product in one sentence; see '
            '<a class="internal-link" href="#vision/block-statement">the vision statement</a>.') in box


def test_a_page_without_its_own_bottom_line_shows_its_children_s_leads() -> None:
    def change(document, chapters):
        product = chapters["product"]
        del product["bottomLine"]
        product["content"] = [node for node in product["content"] if node["type"] != "callouts"]
        del document["manifest"]["bottomLine"]
        document["manifest"]["abstract"] = [node for node in document["manifest"]["abstract"]
                                            if node["type"] != "callouts"]

    notes = _bottom_lines(change)

    for page, children in (("product", ["vision", "plan"]), ("home", [])):
        if not children:
            assert BOX not in notes[page]  # Its children have no lead: no box, no list.
            continue
        box = _box(notes[page])
        assert box.startswith(BOX + '>\n<header class="content-card-title">Bottom line</header>\n<ul class="bottom-line-list">')
        assert "data-node-id" not in box
        assert [re.search(r'data-embed-chapter="([^"]+)"', item)[1] for item in _items(box)] == children


def test_a_link_in_a_lead_that_went_up_goes_where_it_goes_in_its_chapter() -> None:
    notes = _bottom_lines()

    [vision] = [item for item in _items(_box(notes["product"])) if 'data-embed-chapter="vision"' in item]
    assert re.findall(r'href="([^"]+)"', vision) == ["#vision", "#other/owner"]
    assert re.findall(r'href="([^"]+)"', _items(_box(notes["home"]))[0]) == ["#product", "#vision/block-statement"]


@pytest.mark.parametrize(("change", "field"), [
    (lambda chapters: chapters["product"]["bottomLine"].update(callout="paragraph-missing"), "callout"),
    (lambda chapters: chapters["product"]["bottomLine"].update(
        callout=next(node["id"] for node in chapters["product"]["content"] if node["type"] == "paragraph")), "callout"),
    (lambda chapters: chapters["vision"]["bottomLine"].update(lead="paragraph-missing"), "lead"),
], ids=["missing", "no-callout", "lead"])
def test_a_stale_bottom_line_is_refused(change, field: str) -> None:
    with pytest.raises(InputError) as failure:
        _bottom_lines(lambda document, chapters: change(chapters))

    assert failure.value.source == "Document of manifest.md"
    assert re.fullmatch(rf"chapters\[\d+\](?:\.children\[\d+\])*\.bottomLine\.{field}", failure.value.field)
    assert "obs-document" in failure.value.remedy


BOTTOM_LINE_PLACES = """async ({slug, paged}) => {
    obsPages.setPaged(paged);
    await obsArtifact.activateChapter(slug);
    await obsArtifact.whenChapterReady();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    // The emphasis box bleeds into the margin as every card does (artifact-ui.md, Takeaways and orientation):
    // its text stays in the text column, and the box on the screen.
    const place = (root) => [...root.querySelectorAll('aside[data-callout="bluf"]')].map((box) => {
        const column = box.parentElement.getBoundingClientRect(), outer = box.getBoundingClientRect();
        const style = getComputedStyle(box);
        const inner = outer.width - ["Left", "Right"].reduce((sum, side) => sum + parseFloat(style[`padding${side}`])
            + parseFloat(style[`border${side}Width`]), 0);
        return {before: box.previousElementSibling?.textContent.trim() ?? null,
                inColumn: inner <= column.width + 0.5 && outer.left >= 0 && outer.right <= innerWidth,
                shown: box.checkVisibility()};
    });
    return {body: place(document.querySelector("[data-chapter-body]")),
            sideways: [document.documentElement, document.querySelector(".chapter-scroll")]
                .map((element) => element.scrollWidth - element.clientWidth)};
}"""


def _bottom_line_page(tmp_path, browser, width: int):
    artifact = tmp_path / "bottom-lines.html"
    artifact.write_text(artifact_html(json.loads(BOTTOM_LINES.read_text(encoding="utf-8"))), encoding="utf-8")
    page = browser.new_page(viewport={"width": width, "height": 844 if width < 600 else 900})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    return page, errors


@pytest.mark.browser
def test_a_bottom_line_leads_its_page_in_every_layout(tmp_path, reader_browser) -> None:
    """Scrolling at 1200 and 390 px and paged, the box stands right under the chapter's title, and on
    the paged Home under the Abstract page's; the print book shows each box under its chapter's title
    (artifact-ui.md, Bottom lines)."""
    page, errors = _bottom_line_page(tmp_path, reader_browser, 1200)
    scrolling = {slug: page.evaluate(BOTTOM_LINE_PLACES, {"slug": slug, "paged": False}) for slug in ("product", "plan")}
    paged = {slug: page.evaluate(BOTTOM_LINE_PLACES, {"slug": slug, "paged": True}) for slug in ("home", "product")}
    page.evaluate("window.print = () => {}")
    page.evaluate("globalThis.obsPages.exportPDF()")
    page.wait_for_function("document.querySelectorAll('.print-book aside[data-callout=\"bluf\"]').length === 5")
    printed = page.evaluate("""() => [...document.querySelectorAll('.print-book aside[data-callout="bluf"]')]
        .map((box) => box.previousElementSibling.textContent.trim())""")
    phone, phone_errors = _bottom_line_page(tmp_path, reader_browser, 390)
    narrow = phone.evaluate(BOTTOM_LINE_PLACES, {"slug": "product", "paged": False})

    for view, title in ((scrolling["product"], "Product"), (scrolling["plan"], "Plan"), (paged["product"], "Product"),
                        (paged["home"], "Abstract"), (narrow, "Product")):
        assert [(box["before"], box["shown"], box["inColumn"]) for box in view["body"]] == [(title, True, True)], view
    assert narrow["sideways"] == [0, 0]
    assert printed == ["Abstract", "Product", "Vision", "Plan", "Step"]
    assert errors == [] and phone_errors == []


@pytest.mark.browser
def test_a_parent_s_preview_begins_with_its_bottom_line_and_holds_no_child_s_lead(tmp_path, reader_browser) -> None:
    from playwright.sync_api import expect

    page, errors = _bottom_line_page(tmp_path, reader_browser, 1200)
    page.evaluate("obsPages.setPaged(false); obsArtifact.activateChapter('other')")
    page.locator("[data-chapter-body] p a[href='#product']").hover()
    card = page.locator("#hover-card")
    expect(card.locator(".hover-card-title")).to_have_text("Product")
    preview = card.locator("p").first.text_content()

    assert preview.startswith("The product in one sentence; see the vision statement."), preview
    assert "Vision lead" not in preview and "Plan lead" not in preview
    assert "Intro prose." in preview
    assert errors == []
