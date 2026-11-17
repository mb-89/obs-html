"""Browser tier: a live table's rows after a read in Claude's artifact viewer (generic-tables.md,
Current data: Projection, Never saved, Status line).

Reader: whoever changes how the tables feature's live-source part shows what a read returns.

A fake viewer stands in (live_viewer.py, ``stand_in``): its ``list_issues`` answers with issue 3,
closed since the build, a new issue 5 and a new issue 6 with hostile text. The closed issue's row
moves to Done with its new cells, the group captions recount, the new rows appear in their group
and open to their text, and the line reads "Showing current data". The register's Base takes only
notes of kind issue, so no new item becomes its row. Print shows the current rows and the line,
without the button or the refresh key. A read is never saved: the reviewed copy's bytes, the
generation timestamp and readerState are those of the page before it; the Comments bar shows the
saved rows, and a comment made there survives Save reviewed HTML and reopening. A column only a
declared target has is known again when the copy reopens without the viewer. The routes'
failures are test_live_connector_browser.py's; the pure layer is live-data.test.js's.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from playwright.sync_api import expect

from artifacts import artifact_html
from browser.viewer import open_viewer, with_stand_in
from live_viewer import LINE, SHELL, SHOW, stand_in, tracker

pytestmark = pytest.mark.browser
ROWS = f"{SHELL} tbody tr[data-row-key]"
READ_ROWS = """() => [...document.querySelectorAll('[data-active-chapter] .data-table-shell tbody tr[data-row-key]')]
    .map(row => [row.dataset.rowKey, row.innerText.replace(/[\\u25b8\\u25be]/g, '').replace(/\\s+/g, ' ').trim()])"""
SAVED = """async () => ({
    html: await obsComments.reviewedHtml(),
    timestamp: JSON.parse(obsArtifact.serializeModel()).document.generation.timestamp,
    state: obsArtifact.readerState(),
    changed: obsNotices.has("changed-html"),
})"""


@pytest.fixture(scope="module")
def artifact() -> str:
    return artifact_html(tracker())


@pytest.fixture(scope="module")
def read(artifact, shared_reader_browser, tmp_path_factory):
    """One page in the viewer, consent granted, after its read: the frame and its errors."""
    errors: list[str] = []
    _, frame = open_viewer(tmp_path_factory.mktemp("live-rows"), shared_reader_browser, errors, artifact, "light",
                           init_script=stand_in())
    frame.evaluate(SHOW, "live")
    expect(frame.locator(LINE)).to_have_text("Showing current data")
    return frame, errors


def _without_stand_in(copy: str) -> str:
    """A reviewed copy as a reader reopens it: the stand-in the test put into the head goes, so the
    copy opens outside the viewer."""
    head = copy.index("<script>", copy.index("<head"))
    return copy[:head] + copy[copy.index("</script>", head) + len("</script>"):]


def _rows(frame, slug: str) -> dict:
    frame.evaluate(SHOW, slug)
    return dict(frame.evaluate(READ_ROWS))


def test_a_read_moves_the_closed_issue_recounts_its_groups_and_adds_the_new_rows(read) -> None:
    frame, errors = read
    rows = _rows(frame, "live")
    assert rows["note:widgets-3"] == "widgets-3 Done"
    assert rows["note:widgets-1"] == "widgets-1 Next"
    added = {key: text for key, text in rows.items() if key.startswith("note:live~")}
    assert sorted(added.values())[0].startswith("widgets-5 Next Widget 5")
    body = frame.locator(f"{SHELL} tbody").inner_text()
    assert "Next (3)" in body and "Done (2)" in body and "Running" not in body
    new = frame.locator(ROWS, has_text="widgets-5")
    new.locator(".data-table-tree-toggle, [data-table-detail-toggle]").first.click()
    expect(frame.locator(f"{SHELL} .data-table-detail-row")).to_contain_text("Issue 5's text.")
    assert errors == []


def test_hostile_text_in_a_read_item_stays_inert_text(read) -> None:
    frame, errors = read
    rows = _rows(frame, "live")
    hostile = next(text for key, text in rows.items() if "widgets-6" in text)
    assert "<script>" in hostile and "javascript:alert(1)" in hostile
    assert frame.evaluate("globalThis.hostile") is None
    shell = frame.locator(SHELL)
    assert shell.locator("tbody img:not([data-icon-asset]), script").count() == 0
    assert shell.locator("a[href^='javascript']").count() == 0
    assert errors == []


def test_a_register_whose_filter_excludes_the_new_item_does_not_show_it(read) -> None:
    frame, errors = read
    rows = _rows(frame, "register")
    assert sorted(rows) == [f"note:widgets-{number}" for number in range(1, 5)]
    assert rows["note:widgets-3"] == "widgets-3 Done"
    assert frame.locator(LINE).inner_text() == "Showing current data"
    assert errors == []


def test_a_live_table_has_a_refresh_key_and_a_plain_one_has_none(read) -> None:
    frame, _ = read
    frame.evaluate(SHOW, "live")
    key = frame.locator(f"{SHELL} [data-table-live-refresh]")
    expect(key).to_have_attribute("aria-label", "Check for updates")
    frame.evaluate(SHOW, "plain")
    assert frame.locator(f"{SHELL} [data-table-live-refresh], {SHELL} [data-table-live-status]").count() == 0


def test_print_shows_the_current_rows_and_the_line_without_the_button_or_the_key(read) -> None:
    frame, errors = read
    printed = frame.evaluate("""() => {
        const root = document.createElement("div");
        obsArtifact.renderStatic("live", root);
        return {text: root.innerText, line: root.querySelector("[data-table-live-status]")?.textContent,
            buttons: root.querySelectorAll("button, [data-table-live-refresh]").length};
    }""")
    assert "widgets-5" in printed["text"] and "Done (2)" in printed["text"]
    assert printed["line"] == "Showing current data"
    assert "Show current data" not in printed["text"] and "Check for updates" not in printed["text"]
    assert printed["buttons"] == 0
    assert errors == []


def test_the_read_since_is_an_hour_before_the_generation_timestamp_the_same_on_two_opens(
        read, artifact, reader_browser, tmp_path) -> None:
    frame, _ = read
    errors: list[str] = []
    _, again = open_viewer(tmp_path, reader_browser, errors, artifact, "light", init_script=stand_in())
    expect(again.locator("html")).to_have_attribute("data-artifact-status", "ready")
    again.wait_for_function("fakeClaude.calls.some(call => call.kind === 'watch')")
    seen = [opened.evaluate("fakeClaude.calls.filter(call => call.kind === 'watch').map(call => call.input.since)")
            for opened in (frame, again)]
    timestamp = frame.evaluate("JSON.parse(obsArtifact.serializeModel()).document.generation.timestamp")
    built = datetime.fromisoformat(timestamp).replace(microsecond=0)
    expected = (built - timedelta(hours=1)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert seen[0] == seen[1] == [expected] * len(seen[0]) and seen[0]
    assert errors == []


def test_a_read_is_never_saved(artifact, reader_browser, tmp_path) -> None:
    """In prompt, nothing is read until the button: the reviewed copy, the generation timestamp and
    readerState before and after the read are the same, and no changed-HTML notice appears."""
    errors: list[str] = []
    _, frame = open_viewer(tmp_path, reader_browser, errors, artifact, "light", init_script=stand_in(consent="prompt"))
    frame.evaluate(SHOW, "live")
    expect(frame.locator(f"{LINE} button")).to_have_text("Show current data")
    before = frame.evaluate(SAVED)
    frame.locator(f"{LINE} button").click()
    expect(frame.locator(LINE)).to_have_text("Showing current data")
    after = frame.evaluate(SAVED)
    assert after == before
    assert before["changed"] is False
    assert frame.evaluate("fakeClaude.calls.some(call => call.kind === 'call')")
    assert errors == []


def test_an_arrival_while_a_print_is_prepared_waits_until_it_ends(artifact, reader_browser, tmp_path) -> None:
    """A read that answers while a print or an export is prepared changes no row until it ends
    (generic-tables.md, Current data: Projection, Arrival); Export to PDF sets the class beforeprint does."""
    errors: list[str] = []
    _, frame = open_viewer(tmp_path, reader_browser, errors, artifact, "light", init_script=stand_in(consent="prompt"))
    frame.evaluate(SHOW, "live")
    assert dict(frame.evaluate(READ_ROWS))["note:widgets-3"] == "widgets-3 Running"
    frame.evaluate("dispatchEvent(new Event('beforeprint'))")
    assert frame.evaluate("document.documentElement.classList.contains('preparing-print')")
    frame.locator(f"{LINE} button").click()
    # The reader registers the watch after it applies the first call's answer.
    frame.wait_for_function("fakeClaude.calls.some(call => call.kind === 'watch')")
    rows = dict(frame.evaluate(READ_ROWS))
    assert rows["note:widgets-3"] == "widgets-3 Running", rows
    assert not any(key.startswith("note:live~") for key in rows), rows
    frame.evaluate("dispatchEvent(new Event('afterprint'))")
    expect(frame.locator(LINE)).to_have_text("Showing current data")
    rows = dict(frame.evaluate(READ_ROWS))
    assert rows["note:widgets-3"] == "widgets-3 Done", rows
    assert any(key.startswith("note:live~") for key in rows), rows
    assert errors == []


def test_the_comments_bar_shows_the_saved_rows_and_a_comment_there_survives_reopening(
        artifact, reader_browser, tmp_path) -> None:
    errors: list[str] = []
    _, frame = open_viewer(tmp_path, reader_browser, errors, artifact, "light", init_script=stand_in())
    frame.evaluate(SHOW, "register")
    expect(frame.locator(LINE)).to_have_text("Showing current data")
    assert dict(frame.evaluate(READ_ROWS))["note:widgets-3"] == "widgets-3 Done"
    frame.evaluate("obsArtifact.openBar('comments', 'right')")
    expect(frame.locator(LINE)).to_have_text("Showing the saved version while comments are open")
    rows = dict(frame.evaluate(READ_ROWS))
    assert rows["note:widgets-3"].endswith("widgets-3 Running")
    target = frame.evaluate("""async () => {
        const cell = [...document.querySelectorAll('[data-active-chapter] .data-table-shell tbody tr[data-row-key="note:widgets-3"] td')]
            .find(cell => cell.textContent.trim() === "Running");
        const text = [...cell.querySelectorAll("*"), cell].flatMap(node => [...node.childNodes])
            .find(node => node.nodeType === 3 && node.textContent.includes("Running"));
        const range = document.createRange();
        const start = text.textContent.indexOf("Running");
        range.setStart(text, start);
        range.setEnd(text, start + 7);
        getSelection().removeAllRanges();
        getSelection().addRange(range);
        await new Promise(resolve => setTimeout(resolve, 0));
        document.querySelector("[data-comment-add]").click();
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        return obsComments.data.annotations.at(-1).target;
    }""")
    assert "Running" in json.dumps(target)
    frame.evaluate("obsArtifact.closeBar('comments')")
    expect(frame.locator(LINE)).to_have_text("Showing current data")
    copy = _without_stand_in(frame.evaluate("obsComments.reviewedHtml()"))
    (tmp_path / "copy").mkdir()
    _, reopened = open_viewer(tmp_path / "copy", reader_browser, errors, copy, "light")
    assert reopened.evaluate("obsComments.data.annotations.map(item => item.target)") == [target]
    assert errors == []


def test_a_column_only_a_declared_target_has_reopens_without_the_route(artifact, reader_browser, tmp_path) -> None:
    """The register's view does not show where; the reader adds it and saves the copy, which reopens
    outside the viewer with the column and no presentation error."""
    errors: list[str] = []
    _, frame = open_viewer(tmp_path, reader_browser, errors, artifact, "light", init_script=stand_in())
    frame.evaluate(SHOW, "register")
    expect(frame.locator(LINE)).to_have_text("Showing current data")
    frame.locator(f'{SHELL} .data-table-options button[title="Show where"]').evaluate("button => button.click()")
    expect(frame.locator(f"{SHELL} thead")).to_contain_text("where")
    copy = _without_stand_in(frame.evaluate("obsComments.reviewedHtml()"))
    (tmp_path / "copy").mkdir()
    _, reopened = open_viewer(tmp_path / "copy", reader_browser, errors, copy, "light")
    reopened.evaluate(SHOW, "register")
    expect(reopened.locator(f"{SHELL} thead")).to_contain_text("where")
    expect(reopened.locator(f"{SHELL} [data-table-presentation-error]")).to_be_hidden()
    expect(reopened.locator(LINE)).to_be_hidden()
    assert errors == []


def test_the_refresh_key_reads_once_more_and_says_so(artifact, reader_browser, tmp_path) -> None:
    errors: list[str] = []
    _, frame = open_viewer(tmp_path, reader_browser, errors, artifact, "light", init_script=stand_in())
    frame.evaluate(SHOW, "live")
    expect(frame.locator(LINE)).to_have_text("Showing current data")
    calls = frame.evaluate("fakeClaude.calls.filter(call => call.kind === 'call').length")
    frame.locator(f"{SHELL} [data-table-live-refresh]").click()
    frame.wait_for_function(f"fakeClaude.calls.filter(call => call.kind === 'call').length === {calls + 1}")
    expect(frame.locator(f"{SHELL} [data-table-live-refresh]")).to_be_enabled()
    assert frame.evaluate("fakeClaude.calls.filter(call => call.kind === 'call').at(-1).options.cache.refresh") is True
    expect(frame.locator(LINE)).to_have_text("Showing current data")
    assert errors == []


def test_a_page_opened_without_the_viewer_reads_nothing_and_shows_no_line(artifact, reader_browser, tmp_path) -> None:
    errors: list[str] = []
    _, frame = open_viewer(tmp_path, reader_browser, errors, artifact, "light")
    frame.evaluate(SHOW, "live")
    assert frame.evaluate(READ_ROWS)
    expect(frame.locator(f"{SHELL} [data-table-live-refresh]")).to_be_hidden()
    expect(frame.locator(LINE)).to_be_hidden()
    assert errors == []
