"""Native-browser tier: property editors commit canonical edits that survive a reviewed copy.

Moved from the interim's test_property_editors_browser.py
(test_native_property_edits_survive_actual_reviewed_download_and_reopen), rebuilt on a Document
as the core emits it: the property-editor fence is a ``property-editors`` node.
"""
from pathlib import Path

import pytest

from obs_html.config import load_config
from obs_html.render import render

from documents import chapter, document as build, heading, node, paragraph


pytestmark = pytest.mark.browser
CONFIG = load_config()
EDITOR = node("property-editors", source="version: 1\nfield: explanation\nlabel: Explanation\n",
              spec={"version": 1, "field": "explanation", "label": "Explanation"}, writes=["explanation"])
TABLE = {"obs": {"records": "note"}, "views": [{"type": "table", "order": ["identifier", "explanation"]}]}


def _artifact(path: Path) -> Path:
    chapters, records = [], []
    for name in ("one", "two"):
        fields = {"explanation": f"Original {name}", "identifier": name}
        chapters.append(chapter(name, name.title(), heading(1, name.title()), paragraph("Source text."), EDITOR,
                                node("bases", source="", spec=TABLE), metadata=fields))
        records.append({"id": name, "type": "note", "path": f"{name}.md", "fields": fields})
    path.write_text(render(build("Edits", *chapters, records=tuple(records)), CONFIG), encoding="utf-8")
    return path


def test_native_property_edits_survive_actual_reviewed_download_and_reopen(tmp_path, reader_browser) -> None:
    from playwright.sync_api import expect

    artifact = _artifact(tmp_path / "artifact.html")
    malicious = 'Accepted α 中 </script><script>window.editExecuted=true</script> **literal**'
    context = reader_browser.new_context(accept_downloads=True)
    context.add_init_script("delete window.showSaveFilePicker")
    page = context.new_page()
    page.set_default_timeout(5000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def open_chapter(path: Path, slug: str) -> None:
        page.goto(path.as_uri() + f"#{slug}")
        page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
        page.evaluate(f"obsPages.setPaged(false); obsArtifact.activateChapter('{slug}')")

    def save(name: str) -> Path:
        page.evaluate("obsArtifact.openBar('comments')")
        with page.expect_download() as download:
            page.locator("[data-comment-save]").click()
        saved = tmp_path / name
        download.value.save_as(saved)
        return saved

    try:
        open_chapter(artifact, "one")
        editor = page.locator("[data-active-chapter] [data-property-editor]")
        expect(editor).to_have_value("Original one")
        editor.fill(malicious)
        editor.press("Tab")
        explanation = "name => obsArtifact.records.find(note => note.slug === name).frontmatter.explanation"
        assert page.evaluate(f"({explanation})('one')") == malicious
        assert malicious in page.locator("[data-active-chapter] .data-table-shell table").inner_text()
        assert page.evaluate(f"({explanation})('two')") == "Original two"
        assert page.evaluate("""() => {
            try { obsArtifact.commitProperty('one', 'identifier', 'changed'); return false; }
            catch (_) { return true; }
        }""")
        assert page.evaluate("""obsQuery.compile('explanation:"Accepted"').match(
            obsArtifact.records.find(note => note.slug === 'one'))""")
        assert not page.evaluate("Boolean(window.editExecuted)")
        page.evaluate("""() => {
            obsComments.data.reviewers.push('Reader');
            obsComments.data.annotations.push({id:'kept-comment', author:'Reader', text:'Keep this comment',
              status:'open', replies:[], target:{chapter:'one',quote:'Source text.',start:0,end:12}});
            obsComments.data.reviews.push({chapter:'one',item:'item-1',reviewer:'Reader',state:'accepted'});
        }""")
        open_chapter(save("reviewed.html"), "one")
        expect(page.locator("[data-active-chapter] [data-property-editor]")).to_have_value(malicious)
        assert page.evaluate("obsComments.data.annotations[0].text") == "Keep this comment"
        assert page.evaluate("obsComments.data.reviews[0].state") == "accepted"
        assert not page.evaluate("Boolean(window.editExecuted)")
        page.evaluate("obsArtifact.activateChapter('two')")
        editor = page.locator("[data-active-chapter] [data-property-editor]")
        expect(editor).to_have_value("Original two")
        editor.fill("")
        editor.press("Tab")
        open_chapter(save("reviewed-twice.html"), "two")
        expect(page.locator("[data-active-chapter] [data-property-editor]")).to_have_value("")
        assert page.evaluate(f"({explanation})('one')") == malicious
        assert page.evaluate("obsArtifact.records.find(note => note.slug === 'one').frontmatter.identifier") == "one"
        assert page.evaluate("obsComments.data.annotations.length") == 1
        open_chapter(save("reviewed-no-new-edits.html"), "two")
        expect(page.locator("[data-active-chapter] [data-property-editor]")).to_have_value("")
        assert page.evaluate(f"({explanation})('one')") == malicious
        assert page.evaluate("obsComments.data.reviews[0].state") == "accepted"
        assert errors == []
    finally:
        context.close()


def test_the_runtime_commits_only_the_fields_the_notes_editors_declare(tmp_path, reader_browser) -> None:
    """artifact.js's commit guard (``obsArtifact.commitCanonicalProjection``) accepts a field only
    when a property editor of the note declares it in the core's ``attrs.writes``; it refuses
    every other field, protected or not, and every field of a note without an editor."""
    spec = {"version": 1, "field": "explanation", "label": "Explanation",
            "projection": {"blank": {"status": "finding"}, "nonblank": {"status": "explained"}}}
    editor = node("property-editors", source="", spec=spec, writes=["explanation", "status"])
    fields = {"explanation": "Original", "status": "explained", "identifier": "one", "title": "One"}
    source = build("Edits", chapter("one", "One", heading(1, "One"), editor, metadata=fields),
                   chapter("two", "Two", heading(1, "Two"), metadata=dict(fields)),
                   records=({"id": "one", "type": "note", "path": "one.md", "fields": fields},
                            {"id": "two", "type": "note", "path": "two.md", "fields": dict(fields)}))
    artifact = tmp_path / "artifact.html"
    artifact.write_text(render(source, CONFIG), encoding="utf-8")
    page = reader_browser.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    refused = """([slug, fields]) => {
        try { obsArtifact.commitCanonicalProjection([{slug, fields}]); return null; }
        catch (error) { return error.message; }
    }"""
    for slug, update in (("one", {"identifier": "changed"}), ("one", {"title": "Changed"}),
                         ("one", {"status": "finding", "identifier": "changed"}), ("two", {"status": "finding"}),
                         ("two", {"explanation": "Changed"})):
        message = page.evaluate(refused, [slug, update])
        assert message and "attrs.writes" in message, (slug, update, message)
    frontmatter = "slug => obsArtifact.records.find(note => note.slug === slug).frontmatter"
    assert page.evaluate(f"({frontmatter})('one')") == fields
    assert page.evaluate(f"({frontmatter})('two')") == fields
    assert page.evaluate("obsArtifact.commitCanonicalProjection([{slug:'one', fields:{status:'finding'}}])")
    assert page.evaluate("obsArtifact.commitProperty('one', 'explanation', '')") is True
    assert page.evaluate(f"({frontmatter})('one')") == {**fields, "status": "finding", "explanation": ""}
    assert errors == []
