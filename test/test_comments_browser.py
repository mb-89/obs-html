"""The Comments bar renders the core's resolved comments, and its review items are Document blocks
(spec/input-model.md, Comments and the core model).

Reader: whoever changes how the Comments bar finds its review items or maps the core's comments.

The first test is the mapping the block-id work measured once (every review item of every fixture
Document is a core node id of its chapter, one to one), kept so it is checked on every run.
"""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from artifacts import artifact_html
from conftest import FIXTURE, ROOT, built_once
from core_calls import unresolved_targets, with_ids
from documents import chapter, document as build_document, heading, node, paragraph

pytestmark = pytest.mark.browser
DOCUMENTS = sorted((ROOT / "test" / "fixtures" / "documents").glob("*.json"))
# Each fixture Document's review items: per open chapter, the items the adapter had before they were
# block ids, less the data tables' hidden status paragraphs, which are no content.
REVIEW_ITEMS = {"artifact-change": 10, "bottom-lines": 12, "callouts": 4, "cards": 10, "columns": 20, "complete": 25, "decision-verdict": 3, "document": 23,
                "equations": 5, "features": 61, "figure-references": 15, "figures": 9, "projections": 8,
                "property-editor-projection": 0, "pugh": 2, "registers": 12, "self-link": 33, "source-archive": 2,
                "structural": 5, "table-help": 2}
HOME = "home"
PARAGRAPH = {"chapter": "intro", "node": "paragraph-957766ff"}
ROW = {"chapter": "intro", "node": "bases-cc30b281:alpha"}


def _open(reader_browser, path):
    page = reader_browser.new_page(viewport={"width": 1200, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: message.type == "error" and errors.append(message.text))
    page.goto(path.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    page.evaluate("obsArtifact.whenChapterReady()")
    return page, errors


def _artifact(tmp_path, document: dict):
    artifact = tmp_path / "artifact.html"
    artifact.write_text(artifact_html(document), encoding="utf-8")
    return artifact


def test_the_review_item_counts_name_every_fixture() -> None:
    assert sorted(REVIEW_ITEMS) == [path.stem for path in DOCUMENTS]


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda path: path.stem)
def test_every_review_item_of_a_fixture_is_a_block_of_its_chapter(path, tmp_path, reader_browser) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    artifact = tmp_path / path.name.replace(".json", ".html")
    artifact.write_text(artifact_html(document), encoding="utf-8")
    page, errors = _open(reader_browser, artifact)
    items = page.evaluate("obsComments.reviewItems()")
    # Each item's decision target, through the one mapping: the home page's items are the abstract's.
    targets = page.evaluate("""(items) => obsCommentModel.toCore({files: [], names: [], annotations: [], states: [],
        decisions: items.map((item, index) => ({id: `d${index}`, reviewer: "R", created: "2026-11-09T10:00:00Z",
            target: {chapter: item.chapter, node: item.id}, state: "accepted"}))}).decisions.map((d) => d.target)""",
                            items)
    assert unresolved_targets(targets, document) == []
    assert sum(item["chapter"] == HOME for item in items) == sum("abstract" in target for target in targets)
    assert len({(item["chapter"], item["id"]) for item in items}) == len(items) == REVIEW_ITEMS[path.stem]
    assert errors == []


def _reviewed(document: dict) -> dict:
    document = copy.deepcopy(document)
    document["comments"] = {"version": 1, "files": ["manifest.comments.alice.json"], "comments": [
        {"id": "c1", "author": "Alice", "created": "2026-11-09T10:00:00Z", "state": "open",
         "body": {"mediaType": "text/plain", "text": "Clarify this."}, "target": PARAGRAPH},
        {"id": "c2", "author": "Bob", "created": "2026-11-09T11:00:00Z", "state": "resolved",
         "body": {"mediaType": "text/plain", "text": "Agreed."}, "inReplyTo": "c1"},
    ], "decisions": [
        {"id": "d1", "reviewer": "Alice", "created": "2026-11-09T10:01:00Z", "target": PARAGRAPH, "state": "accepted"},
        {"id": "d2", "reviewer": "Bob", "created": "2026-11-09T10:02:00Z", "target": PARAGRAPH, "state": "rejected"},
        {"id": "d3", "reviewer": "Bob", "created": "2026-11-09T10:03:00Z", "target": ROW, "state": "accepted"},
    ], "states": []}
    return document


STATES = """async () => {
    await obsArtifact.activateChapter("intro");
    await obsArtifact.whenChapterReady();
    obsArtifact.openBar("comments", "right");
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const state = (selector) => document.querySelector(selector)?.dataset.reviewState;
    return {
        paragraph: state('[data-review-item="paragraph-957766ff"]'),
        row: state('[data-review-item="bases-cc30b281:alpha"]'),
        threads: [...document.querySelectorAll("[data-comment-list] [data-comment-id]")].map((node) => node.dataset.commentId),
        island: JSON.parse(document.querySelector("[data-comment-island]").textContent),
    };
}"""


def test_the_bar_shows_the_resolved_model_and_a_reviewed_copy_shows_the_same_states(tmp_path, reader_browser) -> None:
    document = _reviewed(json.loads(FIXTURE.read_text(encoding="utf-8")))
    artifact = tmp_path / "artifact.html"
    artifact.write_text(artifact_html(document), encoding="utf-8")
    page, errors = _open(reader_browser, artifact)
    shown = page.evaluate(STATES)
    assert (shown["paragraph"], shown["row"], shown["threads"]) == ("rejected", "accepted", ["c1", "c2"])
    assert shown["island"] == {**document["comments"], "names": ["Reviewer"]}
    copy_path = tmp_path / "reviewed.html"
    copy_path.write_text(page.evaluate("obsComments.reviewedHtml()"), encoding="utf-8")
    reopened, reopened_errors = _open(reader_browser, copy_path)
    assert reopened.evaluate(STATES) == shown
    assert errors == reopened_errors == []


SELECT_ACROSS = """async () => {
    await obsArtifact.activateChapter("intro");
    await obsArtifact.whenChapterReady();
    obsArtifact.openBar("comments", "right");
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const heading = document.querySelector("[data-chapter-body] h1[data-node-id]");
    const paragraph = document.querySelector('[data-chapter-body] [data-node-id="paragraph-957766ff"]');
    const range = document.createRange();
    range.setStart(heading.firstChild, 0);
    range.setEnd(paragraph.querySelector(".semantic-mark-content").firstChild, 4);
    const selected = new Promise((resolve) => document.addEventListener("selectionchange", resolve, {once: true}));
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    await selected;
    document.querySelector("[data-comment-add]").click();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const target = obsComments.data.annotations.at(-1).target;
    const marked = [...CSS.highlights.get("obs-comments")].map((painted) => painted.toString());
    const own = range.cloneContents();
    own.querySelectorAll("[data-review-gutter]").forEach((gutter) => gutter.remove());
    return {target, heading: heading.dataset.nodeId, selected: range.toString(), own: own.textContent, marked};
}"""


def test_a_selection_across_blocks_targets_the_block_it_starts_in(tmp_path, reader_browser) -> None:
    """Nothing targets a chapter and a quote: the heading the selection starts in is its target, and
    the positions, counted from the heading's start, find the selected text again; the quote is the
    selection's own text, without the review gutter it crosses."""
    page, errors = _open(reader_browser, _artifact(tmp_path, json.loads(FIXTURE.read_text(encoding="utf-8"))))
    shown = page.evaluate(SELECT_ACROSS)
    assert shown["target"]["node"] == shown["heading"] == "section-36539243"
    assert (shown["target"]["start"], shown["target"]["quote"]) == (0, shown["own"])
    assert shown["selected"] in shown["marked"]
    assert errors == []


RESOLVE_AS_BOB = """async () => {
    await obsArtifact.activateChapter("intro");
    await obsArtifact.whenChapterReady();
    obsArtifact.openBar("comments", "right");
    const author = document.querySelector("[data-comment-author]");
    author.value = "Bob";
    author.dispatchEvent(new Event("change"));
    const card = (id) => document.querySelector(`[data-comment-list] [data-comment-id="${id}"] > .comment-card`);
    const readOnly = (id) => card(id).querySelector(".comment-text-editor").readOnly;
    const editable = {c1: readOnly("c1"), c2: readOnly("c2")};
    const deletes = (id) => [...card(id).querySelectorAll("button")].some((item) => item.textContent === "Delete");
    const deletable = {c1: deletes("c1"), c2: deletes("c2")};
    const button = () => [...card("c1").querySelectorAll("button")].find((item) => /Resolve|Reopen/.test(item.textContent));
    const before = button().textContent;
    button().click();
    const after = button().textContent;
    return {editable, deletable, before, after, island: JSON.parse(document.querySelector("[data-comment-island]").textContent)};
}"""


def test_a_readers_resolve_of_anothers_comment_is_their_own_state_entry_and_only_own_bodies_edit(
        tmp_path, reader_browser) -> None:
    """Only the reader's own comment edits and deletes; the island the reader saves carries the reader's
    name as its names."""
    document = _reviewed(json.loads(FIXTURE.read_text(encoding="utf-8")))
    page, errors = _open(reader_browser, _artifact(tmp_path, document))
    shown = page.evaluate(RESOLVE_AS_BOB)
    assert shown["editable"] == {"c1": True, "c2": False}
    assert shown["deletable"] == {"c1": False, "c2": True}
    assert shown["island"]["names"] == ["Bob"]
    assert (shown["before"], shown["after"]) == ("Resolve", "Reopen")
    island = shown["island"]
    assert island["comments"] == document["comments"]["comments"]
    assert [(state["author"], state["target"], state["state"]) for state in island["states"]] == \
        [("Bob", "c1", "resolved")]
    assert errors == []


COMMENT_ON = """async ({chapter, node, quote}) => {
    await obsArtifact.activateChapter(chapter);
    await obsArtifact.whenChapterReady();
    obsArtifact.openBar("comments", "right");
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const block = document.querySelector(`[data-chapter-body] [data-node-id="${node}"]`);
    const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
    let text = null;
    while (walker.nextNode()) {
        if (!walker.currentNode.parentElement.closest("[data-review-gutter]") &&
                walker.currentNode.data.includes(quote)) { text = walker.currentNode; break; }
    }
    const range = document.createRange();
    range.setStart(text, text.data.indexOf(quote));
    range.setEnd(text, text.data.indexOf(quote) + quote.length);
    const selected = new Promise((resolve) => document.addEventListener("selectionchange", resolve, {once: true}));
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    await selected;
    document.querySelector("[data-comment-add]").click();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    return obsComments.data.annotations.at(-1).target;
}"""

PAINTED = """async ({chapter, bar}) => {
    await obsArtifact.activateChapter(chapter);
    await obsArtifact.whenChapterReady();
    if (bar) obsArtifact.openBar("comments", "right");
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    return [...(CSS.highlights.get("obs-comments") || [])].map((painted) => painted.toString());
}"""


@pytest.mark.parametrize(("chapter", "node", "quote"), [
    ("intro", "paragraph-957766ff", "the de"),
    ("appendix", None, "heading he"),
], ids=["marked paragraph", "unmarked paragraph"])
def test_a_reopened_reviewed_copy_paints_a_comment_on_its_quote(chapter, node, quote, tmp_path, reader_browser) -> None:
    """A comment's positions count the block's own text, not the review gutter's controls, so the copy
    reopens with its highlight on the quoted characters, with the Comments bar closed and open."""
    page, errors = _open(reader_browser, _artifact(tmp_path, json.loads(FIXTURE.read_text(encoding="utf-8"))))
    if node is None:
        node = page.evaluate("""async (chapter) => { await obsArtifact.activateChapter(chapter);
            await obsArtifact.whenChapterReady();
            return document.querySelector("[data-chapter-body] p[data-node-id]").dataset.nodeId; }""", chapter)
    target = page.evaluate(COMMENT_ON, {"chapter": chapter, "node": node, "quote": quote})
    assert (target["node"], target["quote"]) == (node, quote)
    assert page.evaluate(PAINTED, {"chapter": chapter, "bar": True}) == [quote]
    copy_path = tmp_path / "reviewed.html"
    copy_path.write_text(page.evaluate("obsComments.reviewedHtml()"), encoding="utf-8")
    reopened, reopened_errors = _open(reader_browser, copy_path)
    assert reopened.evaluate(PAINTED, {"chapter": chapter, "bar": False}) == [quote]
    assert reopened.evaluate(PAINTED, {"chapter": chapter, "bar": True}) == [quote]
    assert errors == reopened_errors == []


SAVED_BY_3_9_0 = ROOT / "test" / "fixtures" / "comments-saved-by-3.9.0.html"


def _old_island() -> dict:
    text = SAVED_BY_3_9_0.read_text(encoding="utf-8")
    return json.loads(text.split("data-comment-island>", 1)[1].rsplit("</script>", 1)[0])


def test_a_copy_saved_by_3_9_0_reopens_with_each_highlight_on_its_quote(tmp_path, reader_browser) -> None:
    """Release 3.9.0's positions counted the open bar's review gutter: its copy, rebuilt with its
    comments or loaded into a built artifact, paints each comment on its quote in its block."""
    old = _old_island()
    quotes = {comment["target"]["chapter"]: comment["target"]["quote"] for comment in old["comments"]}
    assert quotes == {"intro": "the de", "appendix": "heading he"}
    assert all(comment["target"]["prefix"].startswith("✓×💬") for comment in old["comments"])
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rebuilt, errors = _open(reader_browser, _artifact(tmp_path, {**document, "comments": old}))
    loaded, loaded_errors = _open(reader_browser, _artifact(tmp_path, document))
    loaded.set_input_files("[data-comment-files]", str(SAVED_BY_3_9_0))
    loaded.wait_for_function("obsComments.data.annotations.length === 2")
    for page in (rebuilt, loaded):
        for chapter, quote in quotes.items():
            assert page.evaluate(PAINTED, {"chapter": chapter, "bar": False}) == [quote], chapter
            assert page.evaluate(PAINTED, {"chapter": chapter, "bar": True}) == [quote], chapter
    assert errors == loaded_errors == []


QUOTE = "detail prose sits in"
GLOSSARY_ROW = "[data-active-chapter] tr[data-row-key='note:alpha']"
ALPHA_DETAIL = "[data-active-chapter] tr[data-detail-owner='note:alpha']"


def _term(identifier: str, summary: str, *body: dict) -> dict:
    metadata = {"kind": "term", "summary": summary}
    return {**chapter(identifier, identifier.title(), *body, metadata=metadata), "toc": False}


def _glossary() -> dict:
    """A chapter glossary whose Base selects two unlisted kind: term notes, as in the issue's vault."""
    base = node("bases", source="", spec={"filters": 'kind == "term"', "views": [
        {"type": "table", "name": "Terms", "order": ["file.name", "summary"]}]})
    terms = {"alpha": ("The first term.", paragraph("Alpha detail prose sits in the note body."),
                       paragraph("A second paragraph of alpha.")),
             "beta": ("The second term.", paragraph("Beta prose."))}
    return with_ids(build_document(
        "Glossary", chapter("glossary", "Glossary", heading(1, "Glossary"), base),
        *(_term(name, summary, *body) for name, (summary, *body) in terms.items()),
        records=tuple({"id": name, "type": "note", "path": f"{name}.md", "fields": {"kind": "term", "summary": summary}}
                      for name, (summary, *_body) in terms.items())))


QUOTE_RECTS = """([selector, quote]) => {
    const section = document.querySelector(selector);
    const walker = document.createTreeWalker(section, NodeFilter.SHOW_TEXT);
    while (walker.nextNode() && !walker.currentNode.data.includes(quote));
    const text = walker.currentNode, at = text.data.indexOf(quote);
    const rect = (offset) => { const range = document.createRange();
        range.setStart(text, offset); range.setEnd(text, offset + 1); return range.getBoundingClientRect(); };
    const first = rect(at), last = rect(at + quote.length - 1);
    return {x0: first.left + 1, y0: first.top + first.height / 2, x1: last.right - 1, y1: last.top + last.height / 2};
}"""
SELECT_IN = """async ([node, quote]) => {
    const block = document.querySelector(`[data-chapter-body] [data-node-id="${node}"]`);
    const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
    while (walker.nextNode() && !walker.currentNode.data.includes(quote));
    const text = walker.currentNode, range = document.createRange();
    range.setStart(text, text.data.indexOf(quote));
    range.setEnd(text, text.data.indexOf(quote) + quote.length);
    const selected = new Promise((resolve) => document.addEventListener("selectionchange", resolve, {once: true}));
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    await selected;
    document.querySelector("[data-comment-add]").click();
    return obsComments.data.annotations.at(-1).target;
}"""
SETTLED = "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
HIGHLIGHTS = "[...(CSS.highlights.get('obs-comments') || [])].map((painted) => painted.toString())"
EXPAND = f"""async () => {{
    await obsArtifact.activateChapter("glossary");
    await obsArtifact.whenChapterReady();
    document.querySelector("{GLOSSARY_ROW} .data-table-tree-toggle").click();
    await {SETTLED};
}}"""


def _badge(page) -> str:
    return page.locator(f"{GLOSSARY_ROW} .review-action--comment").get_attribute("data-count")


def test_a_selection_in_a_note_detail_comments_on_the_notes_block(tmp_path, reader_browser) -> None:
    """A selection in a row's note detail targets the block of the note it starts in, under the
    note's chapter, as on the note's own page; the row's badge counts it, open or collapsed, and its
    Target opens the row's details on the quote, also in a reviewed copy (input-model.md, Comments
    and the core model)."""
    document = _glossary()
    [alpha] = [item for item in document["chapters"] if item["id"] == "alpha"]
    paragraph_id = next(item["id"] for item in alpha["content"] if item["type"] == "paragraph")
    page, errors = _open(reader_browser, _artifact(tmp_path, document))
    page.evaluate("""async () => { await obsArtifact.activateChapter("glossary");
        await obsArtifact.whenChapterReady(); obsArtifact.openBar("comments", "right"); }""")
    page.evaluate(EXPAND)
    page.locator(ALPHA_DETAIL).wait_for()
    drag = page.evaluate(QUOTE_RECTS, [f"{ALPHA_DETAIL} section[data-reference-note='alpha']", QUOTE])
    page.mouse.move(drag["x0"], drag["y0"])
    page.mouse.down()
    page.mouse.move(drag["x1"], drag["y1"], steps=5)
    page.mouse.up()
    assert page.evaluate("getSelection().toString()") == QUOTE
    page.evaluate(SETTLED)
    add = page.locator("[data-comment-add]")
    assert add.is_enabled(), add.get_attribute("title")
    add.click()
    target = page.evaluate("obsComments.data.annotations.at(-1).target")
    assert target == {"chapter": "alpha", "node": paragraph_id, "quote": QUOTE, "prefix": "Alpha ",
                      "suffix": " the note body.\nA second paragraph of al", "start": 6, "end": 26}
    assert unresolved_targets([target], document) == []
    assert _badge(page) == "1"
    page.locator(f"{GLOSSARY_ROW} .data-table-tree-toggle").click()
    page.locator(ALPHA_DETAIL).wait_for(state="detached")
    assert _badge(page) == "1"
    page.locator("[data-comment-list] .comment-target").first.click()
    page.locator(ALPHA_DETAIL).wait_for()
    page.evaluate(SETTLED)
    assert page.evaluate("document.querySelector('[data-active-chapter]').dataset.chapter") == "glossary"
    assert page.evaluate(HIGHLIGHTS) == [QUOTE]
    copy_path = tmp_path / "reviewed.html"
    copy_path.write_text(page.evaluate("obsComments.reviewedHtml()"), encoding="utf-8")
    assert page.evaluate(PAINTED, {"chapter": "alpha", "bar": True}) == [QUOTE]
    own = page.evaluate(SELECT_IN, [paragraph_id, QUOTE])
    assert {key: own[key] for key in ("chapter", "node", "quote", "start", "end")} == {
        key: target[key] for key in ("chapter", "node", "quote", "start", "end")}
    reopened, reopened_errors = _open(reader_browser, copy_path)
    reopened.evaluate(EXPAND)
    reopened.locator(ALPHA_DETAIL).wait_for()
    assert reopened.evaluate(HIGHLIGHTS) == [QUOTE]
    reopened.evaluate("""async () => { obsArtifact.openBar("comments", "right");
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))); }""")
    assert reopened.evaluate(HIGHLIGHTS) == [QUOTE]
    assert errors == reopened_errors == []


# Artifact-ui.md "Comments bar": metadata cards. A chapter whose blocks and section set fields, built by
# the core, with prose enough before its section that the section starts off screen, and a note of
# front matter only.
FILLER = "".join(f"Filler paragraph {index} keeps the section below the first screen.\n\n" for index in range(40))
FIELDS_NOTE = ("---\nowner: ana\nstatus: draft\n---\n# Chapter\n\nIntro text.\n\n" + FILLER +
               "## Part\n\nstatus:: review\n\nPart prose.\nowner:: lin\n\n- item one\n- item two\n\n"
               "reviewer::\nowner::\n")
CARDS = "[data-comment-list] > [data-metadata-card]"
CARD_STATE = f"""() => [...document.querySelectorAll("{CARDS}")].map((card) => ({{
    id: card.dataset.metadataCard,
    path: card.querySelector(".metadata-target").textContent,
    fields: [...card.querySelectorAll("[data-metadata-field], [data-metadata-source-file]")].map((row) => [
        row.querySelector(".comment-key").textContent, row.querySelector(".comment-value").textContent,
        row.hasAttribute("data-override")]),
    onScreen: card.hasAttribute("data-on-screen"),
}}))"""
SHOWN = """() => ({
    comments: document.querySelectorAll("[data-comment-list] > .comment-node").length,
    metadata: document.querySelectorAll("[data-comment-list] > [data-metadata-card]").length,
    state: document.querySelector("[data-comment-filter-state]").textContent,
})"""
METADATA_HIGHLIGHT = ("[...(CSS.highlights.get('obs-metadata') || [])].map(String).join(' ')"
                      ".replace(/\\s+/g, ' ').trim()")


def _fields_vault(folder: Path, core_root: Path) -> None:
    vault = folder / "vault"
    vault.mkdir()
    (vault / "manifest.md").write_text("---\ntitle: Fields\n---\n- [[chapter]]\n- [[only]]\n", encoding="utf-8")
    (vault / "chapter.md").write_text(FIELDS_NOTE, encoding="utf-8")
    (vault / "only.md").write_text("---\nowner: ana\n---\n", encoding="utf-8")
    run = [sys.executable, "-m"]
    subprocess.run([*run, "obs.capabilities", "--notes", str(core_root / "spec" / "capabilities"),
                    "--output", str(folder / "capabilities.json")], check=True)
    subprocess.run([*run, "obs.document", "--source", str(vault / "manifest.md"),
                    "--document", str(folder / "document.json"),
                    "--capability-reference", str(folder / "capabilities.json")], check=True)
    (folder / "artifact.html").write_text(
        artifact_html(json.loads((folder / "document.json").read_text(encoding="utf-8"))), encoding="utf-8")


@pytest.fixture(scope="module")
def fields_artifact(tmp_path_factory, core_root) -> Path:
    """The block-fields Document the core builds, rendered once per run."""
    return built_once(tmp_path_factory, "metadata-cards", lambda folder: _fields_vault(folder, core_root)) \
        / "artifact.html"


def _bar(page) -> None:
    page.evaluate(f"""async () => {{ obsArtifact.openBar("comments", "right"); await {SETTLED}; }}""")


def test_each_block_with_fields_has_a_card_in_order_with_its_path_and_its_click_jumps_and_highlights(
        fields_artifact, reader_browser) -> None:
    page, errors = _open(reader_browser, fields_artifact)
    _bar(page)
    cards = page.evaluate(CARD_STATE)
    # Each note's front matter is its first card, with Source file; then a card per block that sets a field.
    assert [card["path"] for card in cards] == [
        "Fields › front matter", "Chapter › front matter", "Chapter › Part", "Chapter › Part › paragraph",
        "Chapter › Part › list", "Only › front matter"]
    assert cards[1]["fields"] == [["owner", "ana", False], ["status", "draft", False],
                                  ["Source file", "chapter.md", False]]
    # A card shows the fields set on its block, marks an override of an inherited value, and an empty key:: as unset.
    assert cards[2]["fields"] == [["status", "review overrides draft", True]]
    assert cards[3]["fields"] == [["owner", "lin overrides ana", True]]
    assert cards[4]["fields"] == [["reviewer", "unset", False], ["owner", "unset overrides ana", True]]
    assert cards[5]["fields"] == [["owner", "ana", False], ["Source file", "only.md", False]]
    # Home is open: only its card marks what is on screen.
    assert [card["onScreen"] for card in cards] == [True, False, False, False, False, False]

    page.locator(f"{CARDS}[data-metadata-kind='block'] .metadata-target").nth(1).click()
    page.wait_for_function("document.querySelector('[data-active-chapter]').dataset.chapter === 'chapter'")
    page.evaluate(SETTLED)
    assert page.evaluate(METADATA_HIGHLIGHT) == "Part prose."
    assert page.evaluate("""() => { const block = document.querySelector('[data-chapter-body] p:has(+ ul)');
        const view = document.querySelector('[data-chapter-scroll]').getBoundingClientRect();
        const box = block.getBoundingClientRect(); return box.top >= view.top && box.bottom <= view.bottom; }""")
    # Scrolling marks the cards of what is on screen: the section start and the list are near the paragraph.
    assert [card["onScreen"] for card in page.evaluate(CARD_STATE)] == [False, True, True, True, True, False]
    page.evaluate(f"""async () => {{ document.querySelector('[data-chapter-scroll]').scrollTop = 0; await {SETTLED}; }}""")
    assert [card["onScreen"] for card in page.evaluate(CARD_STATE)] == [False, True, False, False, False, False]
    # A section's card highlights its section, heading and blocks.
    page.locator(f"{CARDS}[data-metadata-kind='block'] .metadata-target").first.click()
    page.evaluate(SETTLED)
    assert page.evaluate(METADATA_HIGHLIGHT) == "Part Part prose. item one item two"
    assert errors == []


def test_the_kind_filter_and_field_queries_choose_the_metadata_cards(fields_artifact, reader_browser) -> None:
    page, errors = _open(reader_browser, fields_artifact)
    _bar(page)
    page.evaluate("""() => obsComments.data.annotations.push({id: "c1", author: "Ada", created: "2026-11-22T10:00:00Z",
        mediaType: "text/plain", text: "On the intro.", state: "open", replies: [],
        target: {chapter: "chapter", quote: "Intro text.", prefix: "", suffix: "", start: 8, end: 19}})""")
    kind = page.locator("[data-comment-kind]")
    filter_input = page.locator("[data-comment-filter-input]")
    filter_input.dispatch_event("input")
    assert page.evaluate(SHOWN) == {"comments": 1, "metadata": 6, "state": "1 of 1 comments, 6 of 6 metadata cards"}
    # The comment on the intro stands after its chapter's front matter and before the Part section's cards.
    assert page.evaluate("""() => [...document.querySelector("[data-comment-list]").children].map((card) =>
        card.dataset.metadataCard?.startsWith("block:") ? "block" : card.dataset.metadataCard || card.dataset.commentId)""") == [
        "frontmatter:home", "frontmatter:chapter", "c1", "block", "block", "block", "frontmatter:only"]
    kind.select_option("comments")
    assert page.evaluate(SHOWN) == {"comments": 1, "metadata": 0, "state": "1 of 1 comments"}
    kind.select_option("metadata")
    assert page.evaluate(SHOWN) == {"comments": 0, "metadata": 6, "state": "6 of 6 metadata cards"}
    # A field query matches a card by its block's effective values, as the core's block records do.
    filter_input.fill("owner: lin")
    assert [card["path"] for card in page.evaluate(CARD_STATE)] == ["Chapter › Part › paragraph"]
    filter_input.fill("status: review")
    assert [card["path"] for card in page.evaluate(CARD_STATE)] == [
        "Chapter › Part", "Chapter › Part › paragraph", "Chapter › Part › list"]
    filter_input.fill("owner: ana")
    assert [card["path"] for card in page.evaluate(CARD_STATE)] == [
        "Chapter › front matter", "Chapter › Part", "Only › front matter"]
    kind.select_option("all")
    assert page.evaluate(SHOWN)["state"] == "0 of 1 comments, 3 of 6 metadata cards"
    assert errors == []


def test_a_metadata_only_note_shows_empty_with_the_bar_closed_and_the_page_has_no_chevron(
        fields_artifact, reader_browser) -> None:
    page, errors = _open(reader_browser, fields_artifact)
    page.evaluate("""async () => { await obsArtifact.activateChapter("only"); await obsArtifact.whenChapterReady(); }""")
    # The page shows its frame, the note's title and page number, and none of its fields.
    assert page.evaluate("""() => ({
        body: document.querySelector("[data-chapter-body]").textContent.includes("ana"),
        bar: obsArtifact.isBarOpen("comments"),
        chevron: document.querySelectorAll("[data-frontmatter-toggle], .frontmatter-toggle").length,
        table: document.querySelectorAll("[data-frontmatter-panel], .frontmatter-panel").length,
    })""") == {"body": False, "bar": False, "chevron": 0, "table": 0}
    assert errors == []
