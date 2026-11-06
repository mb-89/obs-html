"""The manifest's `document number` in the page frame's running footer and the copied comments.

The design owner is obs input-model.md (Cover metadata and history): the field names no
application or vendor. The test builds the Document with the core, renders it, and opens the
artifact file directly, where the clipboard is not limited (Claude's viewer blocks it).
"""
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import CORE_ROOT

from obs_html.cli import main as obs_html

# A clipboard that keeps what the artifact writes, so the copied comments can be read back.
CLIPBOARD = """Object.defineProperty(navigator, "clipboard", {configurable: true, value: {
    writeText: async (text) => { globalThis.copiedText = text; },
}});"""


def _artifact(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "manifest.md").write_text(
        "---\ntitle: Numbered\ndocument number: X-1\ntemplate: T-7\n---\n- [[one]]\n", encoding="utf-8")
    (vault / "one.md").write_text("# One\n\nText.\n", encoding="utf-8")
    built, capabilities = tmp_path / "document.json", tmp_path / "capabilities.json"
    subprocess.run([sys.executable, "-m", "obs.capabilities", "--notes",
                    str(CORE_ROOT / "spec" / "capabilities"), "--output", str(capabilities)], check=True)
    subprocess.run([sys.executable, "-m", "obs.document", "--source", str(vault / "manifest.md"),
                    "--document", str(built), "--capability-reference", str(capabilities)], check=True)
    destination = tmp_path / "artifact.html"
    assert obs_html([str(built), str(destination)]) == 0
    return destination


@pytest.mark.browser
def test_the_document_number_shows_in_the_running_footer_and_the_copied_comments(
        tmp_path: Path, reader_browser) -> None:
    from playwright.sync_api import expect

    errors: list[str] = []
    page = reader_browser.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.add_init_script(CLIPBOARD)
    page.goto(_artifact(tmp_path).as_uri())
    expect(page.locator("html")).to_have_attribute("data-artifact-status", "ready")
    page.evaluate("globalThis.obsPages.setPaged(true)")
    page.evaluate("location.hash = '#one'")
    expect(page.locator("[data-active-chapter]")).to_have_attribute("data-chapter", "one")
    page.evaluate("globalThis.obsArtifact.whenChapterReady()")
    footer = page.locator(".paper-sheet[data-page-chapter='one'] .paper-footer").first.inner_text()
    assert "X-1 · T-7" in footer, footer
    # The copy's outcome is the announcer's last message; the copied text is what the clipboard got.
    copied = page.evaluate("""() => new Promise((resolve) => {
        const announcer = document.querySelector("[data-comment-announcer]");
        new MutationObserver(() => {
            if (announcer.textContent !== "Copying comments…") resolve([announcer.textContent, globalThis.copiedText]);
        }).observe(announcer, {childList: true, characterData: true, subtree: true});
        globalThis.obsComments.data.annotations.push({id: "c1", author: "Ada", text: "Check.", status: "open",
            target: {chapter: "one", quote: "Text", start: 0, end: 4}, replies: []});
        document.querySelector("[data-comment-copy]").click();
    })""")
    assert copied[0] == "Comments copied to clipboard.", copied[0]
    assert copied[1].splitlines()[0] == "# Comments — Numbered · X-1", copied[1]
    assert errors == []

