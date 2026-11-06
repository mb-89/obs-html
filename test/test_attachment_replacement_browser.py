"""Native-browser tier: the obsHtml.attachments trusted extension over the real artifact runtime."""
from pathlib import Path

import pytest

from artifacts import artifact_html
from documents import chapter, document, heading, paragraph


BUNDLE = """globalThis.obsArtifact.registerApplication({id: "fixture-v1", actions: [
    {id: "attach", accept: ".pdf", help: "Attach evidence.", handle: async () => true}]});"""

# Attach evidence to two records through the canonical transaction, as a trusted bundle does,
# and return the attachment's key and the artifact revision after that commit.
SEED = """async () => {
    const artifact = globalThis.obsArtifact;
    const bytes = new TextEncoder().encode("%PDF old");
    const descriptor = await globalThis.obsPayload.describeAsset(
        "assets/evidence/test.pdf", bytes, "application/pdf");
    const reference = `obs-asset:${descriptor.key}`;
    const notes = artifact.canonicalNotes().map(note => ["test", "summary"].includes(note.slug)
        ? {...note, frontmatter: {...note.frontmatter, evidence: reference},
           html: `<a href="${reference}">Evidence</a>`}
        : note);
    const staged = await artifact.stageCanonicalTransaction({expectedRevision: artifact.revision, notes,
        assetChanges: [{...descriptor, bytes}]});
    staged.commit();
    return {key: descriptor.key, revision: artifact.revision};
}"""

STATE = """async () => {
    const artifact = globalThis.obsArtifact;
    const notes = Object.fromEntries(artifact.canonicalNotes().map(note => [note.slug, note]));
    const assets = artifact.embeddedAssets();
    const members = {};
    for (const asset of Object.values(assets)) {
        if (typeof asset === "object") {
            members[asset.archivePath] = new TextDecoder().decode(
                await globalThis.obsPayload.readMember(asset.archivePath));
        }
    }
    const keys = Object.keys(assets).filter(key => typeof assets[key] === "object").sort();
    return {revision: artifact.revision, keys, members,
        evidence: ["test", "summary", "other"].map(slug => notes[slug].frontmatter.evidence ?? null),
        html: ["test", "summary"].map(slug => notes[slug].html)};
}"""

REPLACE = """async ({expectedRevision, key, text, mime, failRewrite}) => {
    const zip = globalThis.ObsHtmlZipRewrite;
    if (failRewrite) {
        globalThis.ObsHtmlZipRewrite = {...zip, rewrite: () => { throw new Error("compression failed"); }};
    }
    try {
        return await globalThis.obsArtifact.trustedExtension("obsHtml.attachments").replace({
            expectedRevision, key, bytes: new TextEncoder().encode(text), mime});
    } catch (error) {
        return {error: error.message};
    } finally {
        globalThis.ObsHtmlZipRewrite = zip;
    }
}"""


def _artifact(tmp_path: Path, trusted: bool) -> Path:
    source = document(
        "Evidence",
        chapter("one", "One", heading(1, "One"), paragraph("Chapter.")),
        records=tuple({"id": slug, "type": "note", "path": f"{slug}.md", "fields": {"title": slug}} for slug in ("test", "summary", "other")),
    )
    path = tmp_path / ("trusted.html" if trusted else "plain.html")
    path.write_text(artifact_html(source, trusted_runtime=("fixture-v1", BUNDLE) if trusted else None),
                    encoding="utf-8")
    return path


def _open(reader_browser, artifact: Path):
    from playwright.sync_api import expect

    page = reader_browser.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(artifact.as_uri())
    expect(page.locator("html")).to_have_attribute("data-artifact-status", "ready")
    assert errors == []
    return page


@pytest.mark.browser
def test_trusted_extension_replaces_an_attachment_and_its_records_in_one_transaction(
        tmp_path: Path, reader_browser) -> None:
    page = _open(reader_browser, _artifact(tmp_path, trusted=True))
    seeded = page.evaluate(SEED)
    key, revision = seeded["key"], seeded["revision"]
    before = page.evaluate(STATE)
    assert before["keys"] == [key]
    assert before["members"] == {"vault/assets/evidence/test.pdf": "%PDF old"}

    stale = page.evaluate(REPLACE, {"expectedRevision": revision - 1, "key": key, "text": "%PDF new"})
    assert "obsHtml.attachments: revision" in stale["error"] and "is stale" in stale["error"]
    assert page.evaluate(STATE) == before

    # Part-way failure: the records are rewritten and staged, then the archive rewrite fails.
    broken = page.evaluate(REPLACE, {"expectedRevision": revision, "key": key, "text": "%PDF new",
                                     "failRewrite": True})
    assert "obsHtml.attachments: staging failed, nothing was applied: compression failed" in broken["error"]
    assert page.evaluate(STATE) == before

    invalid = page.evaluate(REPLACE, {"expectedRevision": revision, "key": key, "text": "<p>",
                                      "mime": "text/html"})
    assert "obsHtml.attachments: the replacement is invalid" in invalid["error"]
    assert page.evaluate(STATE) == before

    result = page.evaluate(REPLACE, {"expectedRevision": revision, "key": key, "text": "%PDF new"})
    assert "error" not in result, result
    assert result["previousKey"] == key and result["dependents"] == ["test", "summary"]
    after = page.evaluate(STATE)
    assert after["revision"] == revision + 1
    assert after["keys"] == [result["key"]]
    assert after["members"] == {"vault/assets/evidence/test.pdf": "%PDF new"}
    reference = f"obs-asset:{result['key']}"
    assert after["evidence"] == [reference, reference, None]
    assert all(reference in markup and key not in markup for markup in after["html"])

    again = page.evaluate(REPLACE, {"expectedRevision": revision, "key": result["key"], "text": "%PDF newer"})
    assert "is stale" in again["error"], "a replacement prepared against the old revision is refused"
    assert page.evaluate(STATE) == after


@pytest.mark.browser
def test_trusted_extension_refuses_html_without_a_trusted_runtime_bundle(tmp_path: Path, reader_browser) -> None:
    page = _open(reader_browser, _artifact(tmp_path, trusted=False))
    refused = page.evaluate(REPLACE, {"expectedRevision": 0, "key": "0" * 64, "text": "%PDF new"})
    assert "no registered trusted runtime bundle" in refused["error"]
    assert "--trusted-runtime-bundle ID=PATH" in refused["error"]
