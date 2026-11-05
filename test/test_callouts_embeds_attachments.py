"""Callouts, embeds and attachments render as the interim adapter in obs rendered them.

Each test builds a contract-valid Document as the core emits it (see the core's vault.py:
a callout's ``kind`` is the canonical type, its ``title`` the authored rest of the marker line;
an attachment names a Document asset; an embed keeps its target and the chapter it resolves to).
"""
import pytest

from obs_html.config import load_config
from obs_html.render import RenderError, render
from obs_html.artifact_data import decode_artifact_data

from documents import chapter, document as build, node, paragraph, text


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


def _callout(kind: str, title: str = "", *body: str | dict) -> dict:
    result = {"type": "callouts", "attrs": {"kind": kind, "title": title}, "children": []}
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


def test_a_callout_title_renders_its_inline_markdown_and_wikilinks() -> None:
    record = {"id": "two", "type": "note", "path": "two.md", "fields": {}}
    html = _html(_callout("warning", "Check **[[two|limits]]** <b>raw</b>", "First."), records=(record,))
    assert ('<header class="content-card-title">Check <strong><a class="internal-link" href="#two">'
            'limits</a></strong> &lt;b&gt;raw&lt;/b&gt;</header>') in html
    assert "[!" not in html


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
    with pytest.raises(RenderError, match=r"Chapter one: callout kind 'shout' .*regenerate"):
        _html(_callout("shout", "", "Body."))


IMAGE = {"id": "logo", "href": "images/logo.png", "mediaType": "image/png"}
DATA = {"id": "data", "href": "input/data.bin", "mediaType": "application/octet-stream"}


def test_an_image_attachment_is_document_content() -> None:
    html = _html(paragraph(node("attachments", asset="logo", label="The logo")), assets=[IMAGE])
    assert html == '<p><img src="images/logo.png" alt="The logo"></p>\n'


def test_a_file_attachment_renders_as_provenance_text() -> None:
    html = _html(paragraph("See ", node("attachments", asset="data", label="the data"), "."), assets=[DATA])
    assert html == ('<p>See <span class="source-reference" data-source-path="input/data.bin">the data</span>'
                    ' (<code>input/<wbr>data.<wbr>bin</code>).</p>\n')


def test_an_unlabelled_file_attachment_is_labelled_by_its_file_name() -> None:
    html = _html(paragraph(node("attachments", asset="data", label="")), assets=[DATA])
    assert '<span class="source-reference" data-source-path="input/data.bin">data.bin</span>' in html


def test_an_attachment_naming_an_unknown_asset_names_the_chapter_and_the_remedy() -> None:
    with pytest.raises(RenderError, match=r"Chapter one: attachment names asset 'gone'.*regenerate"):
        _html(paragraph(node("attachments", asset="gone", label="x")))


def test_attachments_never_carry_an_absolute_local_path() -> None:
    absolute = {"id": "abs", "href": "/srv/vault/data.bin", "mediaType": "application/octet-stream"}
    with pytest.raises(RenderError, match=r"Chapter one: attachment 'abs' .*absolute.*vault-relative"):
        _html(paragraph(node("attachments", asset="abs", label="x")), assets=[absolute])


def test_a_note_embed_links_to_its_chapter_or_renders_unresolved() -> None:
    html = _html(paragraph(node("embeds", target="two", chapter="two"), " ",
                           node("embeds", target="missing", chapter=None)))
    assert html == ('<p><a class="internal-link embed" href="#two">Two</a> '
                    '<span class="unresolved embed" title="missing">missing</span></p>\n')


def test_a_file_embed_renders_like_an_attachment() -> None:
    html = _html(paragraph(node("embeds", target="icon.svg", chapter=None), " ",
                           node("embeds", target="input/data.bin", chapter=None)))
    assert html == ('<p><img src="icon.svg" alt=""> '
                    '<span class="source-reference" data-source-path="input/data.bin">data.bin</span>'
                    ' (<code>input/<wbr>data.<wbr>bin</code>)</p>\n')


def test_callout_bodies_render_their_inline_nodes() -> None:
    html = _html(_callout("tip", "", text("Use "), node("attachments", asset="data", label="it")), assets=[DATA])
    assert '<p>Use <span class="source-reference" data-source-path="input/data.bin">it</span>' in html


@pytest.mark.browser
def test_callout_tones_are_distinct_titled_cards_in_the_reader(tmp_path, reader_browser) -> None:
    """Moved from the interim's browser tests: each tone has its own border and fill, and the
    title takes the border colour, in the paged reader and the print book alike."""
    kinds = ["note", "success", "warning", "danger", "quote"]
    document = build("Doc", chapter("one", "One", *(_callout(kind, kind.capitalize(), f"{kind} body.")
                                                   for kind in kinds)))  # The core's titles.
    artifact = tmp_path / "artifact.html"
    artifact.write_text(render(document, CONFIG), encoding="utf-8")
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
    page.close()
    assert errors == []
