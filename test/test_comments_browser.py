"""The Comments bar renders the core's resolved comments, and its review items are Document blocks
(spec/input-model.md, Comments and the core model).

Reader: whoever changes how the Comments bar finds its review items or maps the core's comments.

The first test is the mapping the block-id work measured once (every review item of every fixture
Document is a core node id of its chapter, one to one), kept so it is checked on every run.
"""
import copy
import json

import pytest

from artifacts import artifact_html
from conftest import FIXTURE, ROOT
from core_calls import chapter_targets

pytestmark = pytest.mark.browser
DOCUMENTS = sorted((ROOT / "test" / "fixtures" / "documents").glob("*.json"))
# Each fixture Document's review items: per open chapter, the items the adapter had before they were
# block ids, less the data tables' hidden status paragraphs, which are no content.
REVIEW_ITEMS = {"artifact-change": 10, "callouts": 4, "cards": 10, "complete": 25, "document": 20, "equations": 5,
                "features": 53, "figure-references": 15, "figures": 8, "projections": 8,
                "property-editor-projection": 0, "pugh": 2, "registers": 10, "self-link": 33, "source-archive": 2,
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
    # The home page shows the manifest abstract, whose blocks have ids but no chapter of the core's.
    targets = chapter_targets({"records": document["records"], "chapters": [
        *document["chapters"], {"id": HOME, "content": document["manifest"].get("abstract", []), "children": []}]})
    assert [item for item in items if item["id"] not in targets.get(item["chapter"], set())] == []
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
    ]}
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
    assert shown["island"] == document["comments"]
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
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    await new Promise((resolve) => setTimeout(resolve, 0));
    document.querySelector("[data-comment-add]").click();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const target = obsComments.data.annotations.at(-1).target;
    const marked = [...CSS.highlights.get("obs-comments")].map((painted) => painted.toString());
    return {target, heading: heading.dataset.nodeId, selected: range.toString(), marked};
}"""


def test_a_selection_across_blocks_targets_the_block_it_starts_in(tmp_path, reader_browser) -> None:
    """Nothing targets a chapter and a quote: the heading the selection starts in is its target, and
    the positions, counted from the heading's start, find the selected text again."""
    page, errors = _open(reader_browser, _artifact(tmp_path, json.loads(FIXTURE.read_text(encoding="utf-8"))))
    shown = page.evaluate(SELECT_ACROSS)
    assert shown["target"]["node"] == shown["heading"] == "section-36539243"
    assert (shown["target"]["start"], shown["target"]["quote"]) == (0, shown["selected"])
    assert shown["selected"] in shown["marked"]
    assert errors == []
