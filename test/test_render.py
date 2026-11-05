import re

import pytest

from obs_html.config import load_config
from obs_html.render import RenderError, render
from obs_html.artifact_data import decode_artifact_data

from conftest import PIXEL
from documents import chapter, document as build, heading, node, paragraph, text


CONFIG = load_config()


def _render(document, runner=lambda command: f"ran {command}") -> str:
    return render(document, CONFIG, runner)


def _model(document, runner=lambda command: f"ran {command}") -> dict:
    return decode_artifact_data(_render(document, runner))


def _notes(document, runner=lambda command: f"ran {command}") -> dict:
    return {note["slug"]: note for note in _model(document, runner)["notes"]}


def test_the_artifact_shell_carries_the_runtime_and_the_island(document) -> None:
    html = _render(document)
    assert "<title>Fixture document</title>" in html
    for script in ("artifact-bootstrap-script", "artifact-data", "obs-comments", "query-script",
                   "base-script", "data-table-script", "artifact-script", "pages-script",
                   "storage-script", "bar-scripts"):
        assert f'id="{script}"' in html
    assert html.count('class="dock-bar ') == 5  # comments, filter, search, settings, toc
    assert 'data-artifact-data' in html


def test_front_pages_follow_the_profile_order(document) -> None:
    model = _model(document)
    assert model["document"]["pages"] == [
        {"page": "cover"}, {"page": "contents", "title": "Contents"}, {"page": "abstract", "title": "Abstract"}]
    assert model["reading"]["paged"] is True
    home = model["notes"][0]
    assert (home["slug"], home["generated"], home["depth"]) == ("home", "home", 0)
    assert '<div class="cover-product"><div>Widget</div><div>2</div></div>' in home["html"]
    assert '<span class="cover-organization">Example org</span>' in home["html"]
    assert '<p class="cover-type">Specification</p>' in home["html"]
    assert "<dt>Authors</dt><dd>Ada, Lin</dd>" in home["html"]
    assert "<p>A short &lt;abstract&gt;.</p>" in home["html"]
    assert "obsHtml" not in model["document"]["metadata"]


def test_defaults_apply_without_a_profile(document) -> None:
    del document["manifest"]["metadata"]["obsHtml"]
    model = _model(document)
    assert [page["page"] for page in model["document"]["pages"]] == ["cover", "abstract", "contents"]
    assert model["paper"] == {"widthMillimeters": 210, "heightMillimeters": 297, "marginMillimeters": 20.0}


@pytest.mark.parametrize(("profile", "field"), [
    ({"layout": "sideways"}, "obsHtml.layout"),
    ({"heading": "huge"}, "obsHtml.heading"),
    ({"query": {"scope": "everything"}}, "obsHtml.query.scope"),
])
def test_an_invalid_presentation_profile_names_the_manifest_field_and_the_remedy(document, profile, field) -> None:
    """The adapter checks its own namespace; the obs core does not read it."""
    document["manifest"]["metadata"]["obsHtml"] = profile
    with pytest.raises(RenderError) as failure:
        _model(document)
    assert str(failure.value).startswith(f"Manifest frontmatter {field}: ")
    assert "Remedy:" in str(failure.value) and "profile.schema.json" in str(failure.value)


def test_profile_print_choice_sets_the_paper(document) -> None:
    assert _model(document)["paper"] == {
        "widthMillimeters": 215.9, "heightMillimeters": 279.4, "marginMillimeters": 15.0}


def test_chapters_become_notes_in_reading_order_with_depth(document) -> None:
    model = _model(document)
    assert model["toc"] == ["home", "intro", "guide-usage", "appendix"]
    depths = {note["slug"]: note["depth"] for note in model["notes"] if note["slug"] in model["toc"]}
    assert depths == {"home": 0, "intro": 0, "guide-usage": 1, "appendix": 0}


def test_headings_carry_anchors_and_untitled_chapters_stay_as_authored(document) -> None:
    notes = _notes(document)
    assert '<h3 id="guide-usage--details">Details</h3>' in notes["guide-usage"]["html"]
    assert notes["appendix"]["html"].startswith("<p>")  # As the interim: the reader names it.


def test_structural_nodes_render_escaped(document) -> None:
    html = "".join(note["html"] for note in _model(document)["notes"])
    assert "<code>x &lt; y</code>" in html
    assert "<ol>\n<li>one</li>\n<li>two</li>\n</ol>" in html
    assert '<a href="https://example.org/?a=1&amp;b=2">the site</a>' in html
    assert f'<img src="data:image/png;base64,{PIXEL}" alt="a logo">' in html


def test_wikilinks_resolve_to_chapter_routes(document) -> None:
    html = "".join(note["html"] for note in _model(document)["notes"])
    assert '<a class="internal-link" href="#guide-usage/details">the details</a>' in html
    assert '<span class="unresolved" title="missing">gone</span>' in html


def test_chapter_frontmatter_feeds_the_note_not_its_body(document) -> None:
    intro = _notes(document)["intro"]
    assert intro["frontmatter"] == {"owner": "Ada", "tags": ["a", "b"]}
    assert intro["frontmatterHtml"] == {"owner": "Ada", "tags": "a, b"}
    assert "owner" not in intro["html"]


def test_marks_render_a_semantic_paragraph_with_a_named_icon_rail(document) -> None:
    html = _render(document)
    intro = decode_artifact_data(html)["notes"][1]
    assert intro["marks"][0]["kind"] == "risk" and intro["marks"][0]["label"] == "limit"
    assert intro["marks"][0]["anchor"] == "mark-intro-risk-limit"
    assert 'class="semantic-mark semantic-mark--risk" data-mark-kind="risk"' in intro["html"]
    assert '<span class="resource-icon" data-icon="mark.risk" aria-hidden="true">!</span>' in intro["html"]
    assert "#mark/" not in intro["html"]


def test_unknown_mark_kinds_fail(document) -> None:
    for node in document["chapters"][0]["content"]:
        for child in node["children"]:
            if child["type"] == "marks":
                child["attrs"]["category"] = "nonsense"
    with pytest.raises(RenderError, match="mark kind 'nonsense'"):
        _render(document)


def test_base_views_become_runtime_tables(document) -> None:
    intro = _notes(document)["intro"]
    assert '<div class="data-table-placeholder" data-base-table="intro-base-1"></div>' in intro["html"]
    table = intro["tables"][0]
    assert table["key"] == "intro-base-1"
    assert table["definition"]["views"][0]["name"] == "Items"


def test_records_join_the_queryable_population_outside_the_reading_order(document) -> None:
    model = _model(document)
    records = {note["slug"]: note for note in model["notes"] if note["slug"] not in model["toc"]}
    assert set(records) == {"alpha", "beta", "gamma", "other", "ranked", "datum"}  # ranked, datum: included notes.
    assert records["alpha"]["frontmatter"] == {
        "kind": "item", "rank": 1, "item": {"name": "Alpha"}, "obs": {"document": False}}
    assert records["alpha"]["html"] == ""


def test_a_record_path_is_its_note_source_path() -> None:
    source = build("Paths", chapter("items-alpha", "Alpha"), records=(
        {"id": "items-alpha", "type": "note", "path": "items/alpha.md", "fields": {}},
        {"id": "items-beta", "type": "note", "path": "items/beta.md", "fields": {}}))
    notes = _notes(source)
    assert notes["items-alpha"]["sourcePath"] == "items/alpha.md"
    assert notes["items-beta"]["sourcePath"] == "items/beta.md"


def test_frontmatter_wikilinks_link_the_chapter_their_record_path_names() -> None:
    fields = {"dependsOn": ["[[capabilities/markdown]]", "[[wikilinks|Links]]", "[[gone]]", "[[detail]]"]}
    source = build("Links", chapter("capabilities-markdown", "Markdown"),
                   chapter("capabilities-wikilinks", "Wikilinks"), chapter("capabilities-bases", "Bases"),
                   records=(
                       {"id": "capabilities-markdown", "type": "note", "path": "capabilities/markdown.md",
                        "fields": {}},
                       {"id": "capabilities-wikilinks", "type": "note", "path": "capabilities/wikilinks.md",
                        "fields": {}},
                       {"id": "capabilities-bases", "type": "note", "path": "capabilities/bases.md",
                        "fields": fields},
                       {"id": "detail", "type": "note", "path": "detail.md", "fields": {}}))
    html = _notes(source)["capabilities-bases"]["frontmatterHtml"]["dependsOn"]
    assert html == ('<a class="internal-link" href="#capabilities-markdown">Markdown</a>, '
                    '<a class="internal-link" href="#capabilities-wikilinks">Links</a>, '
                    '<span class="unresolved" title="gone">gone</span>, '
                    '<span class="unresolved" title="detail">detail</span>')


def _filtered(filters: object, view_filters: object = None) -> dict:
    view = {"type": "table", "name": "Items", "order": ["file.name"],
            **({"filters": view_filters} if view_filters is not None else {})}
    base = node("bases", source="filters: ...\n", spec={"filters": filters, "views": [view]})
    return build("Filters", chapter("items", "Items", base))


@pytest.mark.parametrize(("filters", "view_filters", "expression"), [
    ("rank > 1", None, "rank > 1"),
    ({"and": ['kind == "item"', 'file.size == 1']}, None, "file.size == 1"),
    ('kind == "item"', {"or": ['formula.total == 1']}, "formula.total == 1"),
    ({"xor": ['kind == "item"']}, None, '{"xor": ["kind == \\"item\\""]}'),
])
def test_a_filter_the_adapter_cannot_evaluate_names_the_base_the_expression_and_what_is_supported(
        filters, view_filters, expression) -> None:
    with pytest.raises(RenderError) as failure:
        _render(_filtered(filters, view_filters))
    message = str(failure.value)
    assert 'Base "Items" (items-base-1) in chapter items' in message
    assert f"cannot evaluate the filter: {expression}. " in message
    assert "Supported:" in message and "file.name, file.path, file.folder, file.ext" in message


def test_the_filter_check_accepts_and_refuses_what_the_shared_conformance_fixture_says(core_root) -> None:
    import json
    fixture = json.loads((core_root / "test" / "fixtures" / "bases-filter-conformance.json").read_text(
        encoding="utf-8"))
    for case in fixture["cases"]:
        _render(_filtered(case["filter"]))
    for filters in fixture["unsupported"]:
        with pytest.raises(RenderError, match="cannot evaluate the filter"):
            _render(_filtered(filters))


def test_an_ignored_record_marks_its_note_and_an_ignored_chapter_stays_in_the_reading_order() -> None:
    link = node("wikilinks", target="kept", chapter="kept", heading="", label="kept")
    source = build("Ignored", chapter("kept", "Kept"), chapter("index", "Index", paragraph(link)), records=(
        {"id": "kept", "type": "note", "path": "kept.md", "fields": {"ignored": True}, "ignored": True},
        {"id": "aside", "type": "note", "path": "aside.md", "fields": {"ignored": True}, "ignored": True},
        {"id": "index", "type": "note", "path": "index.md", "fields": {}}))
    model = _model(source)
    notes = {note["slug"]: note for note in model["notes"]}
    assert notes["kept"]["ignored"] is True and notes["aside"]["ignored"] is True
    assert "ignored" not in notes["index"]
    assert "kept" in model["toc"]
    assert '<a class="internal-link" href="#kept">Kept</a>' in notes["index"]["html"]


def test_command_fences_render_escaped_output_and_skip_silent_producers(document) -> None:
    commands = []
    notes = _notes(document, lambda command: commands.append(command) or "<b>derived</b>\n")
    assert commands == ["echo derived"]
    assert '<pre class="command-output">&lt;b&gt;derived&lt;/b&gt;\n</pre>' in notes["intro"]["html"]


def test_command_fences_require_authorization(document) -> None:
    with pytest.raises(RenderError, match="authorization"):
        render(document, CONFIG)


def test_unsupported_capabilities_are_refused(document) -> None:
    document["capabilities"].append("figures")
    with pytest.raises(RenderError, match="does not render: figures"):
        _render(document)


def test_an_unknown_node_type_renders_its_text_and_warns_once_naming_the_source_and_the_remedy(
        capsys) -> None:
    def unknown(value: str) -> dict:
        return {"type": "shout", "attrs": {}, "children": [text(value)]}

    # A type the Document does not declare as a capability, as a newer core's structural types are.
    unknowing = build("Unknown", chapter("one", "One", paragraph("Say ", unknown("<loud>"), "."),
                                         paragraph(unknown("again"))))
    unknowing["capabilities"].remove("shout")
    notes = _notes(unknowing)
    html = notes["one"]["html"]
    assert 'Say <span class="unknown-node" data-node-type="shout">&lt;loud&gt;</span>.' in html
    assert '<span class="unknown-node" data-node-type="shout">again</span>' in html
    warnings = [line for line in capsys.readouterr().err.splitlines() if "'shout'" in line]
    assert len(warnings) == 1
    assert warnings[0].startswith("Warning: obs-html (src/obs_html/render.py): ")
    assert "chapter 'one'" in warnings[0] and "Remedy:" in warnings[0]


def test_the_home_slug_is_reserved(document) -> None:
    document["chapters"][1]["id"] = "home"
    with pytest.raises(RenderError, match="reserved"):
        _render(document)


def test_a_minimal_document_renders(document) -> None:
    minimal = {"schemaVersion": 1, "manifest": {"title": "Only", "metadata": {}}, "chapters": [],
               "links": [], "assets": [], "records": [], "semanticResources": [], "diagnostics": [],
               "capabilities": []}
    model = decode_artifact_data(render(minimal, CONFIG))
    assert '<h1 class="document-title">Only</h1>' in model["notes"][0]["html"]
    assert model["toc"] == ["home"]


def test_island_compression_follows_the_settings(document, tmp_path) -> None:
    import json
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"artifact": {"dataCompression": "none"}}), encoding="utf-8")
    html = render(document, load_config(settings), lambda command: "")
    assert re.search(r'<script id="artifact-data" type="application/json"[^>]*data-compression="none"', html)


def test_metadata_markdown_renders_inline_on_the_cover_and_in_the_frontmatter_panel(document) -> None:
    metadata = document["manifest"]["metadata"]
    metadata["subtitle"] = ("Bridge **subtitle** ![Obsidian](https://example.invalid/obsidian.svg) → "
                            "![HTML](https://example.invalid/html.svg) <b>raw</b>")
    document["assets"] += [  # The core fetched the first badge and could not fetch the second.
        {"id": "obsidian", "href": "https://example.invalid/obsidian.svg", "mediaType": "image/png", "data": PIXEL},
        {"id": "html", "href": "https://example.invalid/html.svg", "mediaType": "image/svg+xml"}]
    document["chapters"][0]["metadata"]["source"] = "https://example.org/a?b=1&c=2"
    document["chapters"][0]["content"][0]["attrs"]["metadata"]["source"] = "https://example.org/a?b=1&c=2"
    notes = _notes(document)
    home = notes["home"]["html"]
    assert ('<div class="document-subtitle">Bridge <strong>subtitle</strong> '
            f'<img src="data:image/png;base64,{PIXEL}" alt="Obsidian"> → '
            '<span class="image-unavailable" role="img" aria-label="HTML">HTML</span> &lt;b&gt;raw&lt;/b&gt;</div>') in home
    panel = notes["intro"]["frontmatterHtml"]
    assert panel["source"] == '<a href="https://example.org/a?b=1&amp;c=2">https://example.org/a?b=1&amp;c=2</a>'
    assert panel["tags"] == "a, b"


def test_fenced_code_renders_as_a_block_and_inline_code_breaks_between_words(document) -> None:
    appendix = next(chapter for chapter in document["chapters"] if chapter["id"] == "appendix")
    appendix["content"].append({"type": "code", "attrs": {"language": "text"}, "children": [],
                                "text": "CODE <here>\n"})
    appendix["content"].append({"type": "code", "attrs": {"language": ""}, "children": [], "text": "plain\n"})
    appendix["content"].append({"type": "paragraph", "attrs": {}, "children": [
        {"type": "code", "attrs": {}, "children": [], "text": "src/obs_html/cfg.json --timings"}]})
    html = _notes(document)["appendix"]["html"]
    assert '<pre><code class="language-text">CODE &lt;here&gt;\n</code></pre>\n' in html
    assert "<pre><code>plain\n</code></pre>\n" in html
    assert "<code>src/<wbr>obs_<wbr>html/<wbr>cfg.<wbr>json --timings</code>" in html


def test_lists_of_single_paragraph_items_render_tight(document) -> None:
    html = _notes(document)["intro"]["html"]
    assert "<ol>\n<li>one</li>\n<li>two</li>\n</ol>" in html


def test_a_loose_list_renders_its_paragraphs_even_with_one_paragraph_per_item(document) -> None:
    intro = next(chapter for chapter in document["chapters"] if chapter["id"] == "intro")
    listing = next(node for node in intro["content"] if node["type"] == "list")
    listing["attrs"]["tight"] = False
    html = _notes(document)["intro"]["html"]
    assert "<ol>\n<li><p>one</p>\n</li>\n<li><p>two</p>\n</li>\n</ol>" in html


def test_unaliased_wikilinks_show_the_chapter_title(document) -> None:
    document["chapters"][1]["content"].append({"type": "paragraph", "attrs": {}, "children": [
        {"type": "wikilinks", "attrs": {"target": "intro", "chapter": "intro", "heading": "", "label": "intro"}, "children": []}]})
    html = _notes(document)["appendix"]["html"]
    assert '<a class="internal-link" href="#intro">Intro</a>' in html


def _linking(*links: dict) -> dict:
    """Two chapters whose ids both end in the link target, so only attrs.chapter can choose."""
    return build("Links", chapter("design-input-architecture", "Architecture"),
                 chapter("design-output-architecture", "Built architecture"),
                 chapter("index", "Index", paragraph(*links)))


def test_a_wikilink_links_to_the_chapter_the_core_names() -> None:
    link = node("wikilinks", target="architecture", chapter="design-input-architecture",
                heading="", label="architecture")
    html = _notes(_linking(link))["index"]["html"]
    assert '<a class="internal-link" href="#design-input-architecture">Architecture</a>' in html


def test_a_link_to_the_manifest_links_to_the_home_page() -> None:
    link = node("wikilinks", target="manifest", chapter="home", heading="", label="manifest")
    html = _notes(_linking(link))["index"]["html"]
    assert '<a class="internal-link" href="#home">Links</a>' in html


def test_a_wikilink_without_a_chapter_is_unresolved_even_when_an_id_matches() -> None:
    link = node("wikilinks", target="index", chapter=None, heading="", label="index")
    html = _notes(_linking(link))["index"]["html"]
    assert '<span class="unresolved" title="index">index</span>' in html


def test_an_embed_links_to_its_chapter_or_renders_unresolved() -> None:
    html = _notes(_linking(node("embeds", target="architecture", chapter="design-input-architecture"),
                           node("embeds", target="index", chapter=None)))["index"]["html"]
    assert '<a class="internal-link embed" href="#design-input-architecture">Architecture</a>' in html
    assert '<span class="unresolved embed" title="index">index</span>' in html


def test_a_link_to_a_chapter_the_document_lacks_names_its_chapter_and_the_remedy() -> None:
    link = node("wikilinks", target="gone", chapter="gone", heading="", label="gone")
    with pytest.raises(RenderError, match="Chapter index: a link names chapter 'gone'.*regenerate"):
        _render(_linking(link))


def _unlisted(*links: dict) -> dict:
    """A listed chapter linking to a note the core included with toc: false."""
    unlisted = chapter("reached", "Reached by a link", paragraph("Unlisted prose."))
    unlisted["toc"] = False
    return build("Unlisted", chapter("index", "Index", paragraph(*links)), unlisted)


def test_a_toc_false_chapter_is_a_note_outside_the_contents_and_reading_order() -> None:
    link = node("wikilinks", target="reached", chapter="reached", heading="", label="reached")
    model = _model(_unlisted(link))
    notes = {note["slug"]: note for note in model["notes"]}
    assert model["toc"] == ["home", "index"]
    assert notes["reached"]["html"] == "<p>Unlisted prose.</p>\n"
    assert "record" not in notes["reached"] and "obs" not in notes["reached"]["frontmatter"]
    assert '<a class="internal-link" href="#reached">Reached by a link</a>' in notes["index"]["html"]


def test_a_toc_false_chapter_links_home() -> None:
    document = _unlisted()
    document["chapters"][1]["content"].append(paragraph(
        node("wikilinks", target="manifest", chapter="home", heading="", label="manifest")))
    html = _notes(document)["reached"]["html"]
    assert '<a class="internal-link" href="#home">Unlisted</a>' in html


def test_home_headings_carry_anchors_that_name_the_front_page_groups() -> None:
    source = build("Doc", chapter("one", "One"), abstract=(heading(2, "Metadata"),))
    home = _notes(source)["home"]["html"]
    assert '<h2 id="home--metadata">Metadata</h2>' in home
