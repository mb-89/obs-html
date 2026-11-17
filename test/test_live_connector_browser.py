"""Browser tier: a live table's line for each answer of Claude's artifact viewer (generic-tables.md,
Current data: Reading, Status line).

Reader: whoever changes how the tables feature's live-source part reaches the viewer, asks for
consent or reads a failure.

A fake viewer stands in (live_viewer.py, ``stand_in``) for each case: consent granted, prompt then
allowed, prompt then declined (``not_in_manifest``, then ``denied``), denied, ``needs_reauth``,
``server_not_connected``, ``not_in_manifest``, ``blocked_by_policy``, a ``null`` from
``use("mcp")``, a retryable error followed by success, and a retryable error after a successful
read. Each shows its line; only ``blocked_by_policy`` posts a notice. No line holds the generation
timestamp, the time of a read or any time of day, and none names how the page is made
(test_reader_text.py, ``technical_words``).
"""
import re

import pytest
from playwright.sync_api import expect

from artifacts import artifact_html
from browser.viewer import open_viewer
from live_viewer import CHANGES, LINE, SHELL, SHOW, stand_in, tracker
from test_reader_text import technical_words

pytestmark = pytest.mark.browser
TRANSIENT = {"code": "server_unavailable", "retryable": True, "message": "The source did not answer."}
CURRENT = "Showing current data"
CASES = {
    "granted": ({}, None, CURRENT),
    "prompt then allowed": ({"consent": "prompt"}, "Show current data", CURRENT),
    "prompt then declined": ({"consent": "prompt", "call": [{"error": {"code": "not_in_manifest"},
                                                             "consentAfter": "denied"}]},
                             "Show current data", "Current data is turned off for this page"),
    "denied": ({"consent": "denied"}, None, "Current data is turned off for this page"),
    "needs_reauth": ({"watch": [[{"error": {"code": "needs_reauth"}}]]}, None,
                     "Sign in to Example Tracker again in Claude"),
    "server_not_connected": ({"watch": [[{"error": {"code": "server_not_connected"}}]]}, None,
                             "Connect Example Tracker in Claude to see current data"),
    "not_in_manifest": ({"watch": [[{"error": {"code": "not_in_manifest"}}]]}, None,
                        "Newer updates cannot be shown here"),
    "blocked_by_policy": ({"watch": [[{"error": {"code": "blocked_by_policy"}}]]}, None,
                          "Newer updates cannot be shown here"),
    "no mcp": ({"mcp": False}, None, "Newer updates cannot be shown here"),
    "retryable then success": ({"watch": [[{"error": TRANSIENT}, {"items": None}]]}, None, CURRENT),
    "retryable after a read": ({"watch": [[{"items": None}, {"error": TRANSIENT}]]}, None,
                               "Could not check for updates; showing the data read earlier"),
}
# Any time of day, date or relative time, in any form a line could hold one.
TIME = re.compile(r"\d{1,2}[:.h]\d{2}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}|"
                  r"\b(?:am|pm|today|yesterday|ago|minutes?|hours?|seconds?|o'clock)\b", re.IGNORECASE)


@pytest.fixture(scope="module")
def artifact() -> str:
    return artifact_html(tracker())


def _config(config: dict) -> dict:
    """The case's stand-in, a watch event without items reading the default changes."""
    watch = [[{**event, "items": CHANGES} if event.get("items", 0) is None else event for event in events]
             for events in config.get("watch", [])]
    return {**config, **({"watch": watch} if watch else {})}


@pytest.mark.parametrize("case", CASES, ids=list(CASES))
def test_each_answer_of_the_viewer_shows_its_line_and_only_a_policy_block_posts_a_notice(
        case, artifact, reader_browser, tmp_path) -> None:
    config, button, expected = CASES[case]
    errors: list[str] = []
    _, frame = open_viewer(tmp_path, reader_browser, errors, artifact, "light", init_script=stand_in(**_config(config)))
    frame.evaluate(SHOW, "live")
    line = frame.locator(LINE)
    texts = []
    if button:
        expect(line.locator("button")).to_have_text(button)
        texts.append(line.inner_text())
        assert texts[-1] == button
        line.locator("button").click()
    expect(line).to_contain_text(expected)
    texts.append(line.inner_text())
    assert texts[-1] == expected
    notice = frame.locator('[data-notice="live-source"] [data-notice-title]')
    if case == "blocked_by_policy":
        expect(notice).to_have_count(1)
        texts.append(notice.inner_text())
    else:
        assert notice.count() == 0
    timestamp = frame.evaluate("JSON.parse(obsArtifact.serializeModel()).document.generation.timestamp")
    for text in texts:
        assert not TIME.search(text), text
        assert timestamp[:10] not in text and timestamp[11:16] not in text
        assert technical_words(text) == [], text
    refresh = frame.locator(f"{SHELL} [data-table-live-refresh]")
    if case in {"denied", "no mcp", "prompt then declined"}:
        expect(refresh).to_be_hidden()
    else:
        expect(refresh).to_be_visible()
    assert errors == []
