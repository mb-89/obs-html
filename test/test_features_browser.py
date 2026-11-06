"""Native-browser tier: decisive canaries in Claude's artifact viewer (test/browser/viewer.py).

The viewer frame hides its sandbox flags from the artifact, so the canaries that read them cannot
decide: they raise nothing at load, and a feature whose failure shows on use raises its warning
then (artifact-ui.md, notice center).
"""
import pytest

from browser.viewer import open_viewer
from obs_html.config import load_config
from obs_html.render import render
from test_features import plain, with_context_note


pytestmark = pytest.mark.browser
CONFIG = load_config()
# The canaries that read the frame's sandbox flags; the viewer hides them.
UNDECIDED = ("printing", "downloads", "popups")


def _capability_notices(frame) -> dict[str, str]:
    """Each capability warning entry's key and title, once the notice center has mounted them."""
    from playwright.sync_api import expect

    # History is refused in the viewer, so its entry shows the canaries' warnings are mounted.
    expect(frame.locator('[data-notice="capability-history"]')).to_have_count(1)
    return frame.locator('[data-notice^="capability-"]').evaluate_all(
        "(items) => Object.fromEntries(items.map((item) => [item.dataset.notice.slice(11),"
        " item.querySelector('[data-notice-title]').textContent]))")


def test_without_a_floating_window_no_popup_code_and_no_separate_windows_notice(tmp_path, reader_browser) -> None:
    errors: list[str] = []
    html = render(plain(), CONFIG)
    assert "window.open" not in html
    _page, frame = open_viewer(tmp_path, reader_browser, errors, html, "light")
    notices = _capability_notices(frame)
    assert "popups" not in notices and not any("Separate windows" in title for title in notices.values())
    assert errors == []


def test_a_host_that_hides_its_sandbox_flags_raises_nothing_at_load_for_them(tmp_path, reader_browser) -> None:
    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, render(with_context_note(), CONFIG), "light")
    notices = _capability_notices(frame)
    assert not set(UNDECIDED) & set(notices), f"undecided canaries warned at load: {notices}"
    undecided = frame.locator("html").evaluate("() => globalThis.obsCapabilities.results"
                                                ".filter((entry) => !entry.decided).map(({key}) => key)")
    assert sorted(undecided) == sorted(UNDECIDED)
    assert errors == []


def test_a_blocked_separate_window_shows_its_reason_inline_and_warns_once(tmp_path, reader_browser) -> None:
    from playwright.sync_api import expect

    errors: list[str] = []
    _page, frame = open_viewer(tmp_path, reader_browser, errors, render(with_context_note(), CONFIG), "light")
    _capability_notices(frame)
    frame.locator("html").evaluate("() => { obsPages.setPaged(false); obsArtifact.activateChapter('one'); }")
    link = frame.locator("[data-chapter-body] a[href='#aside']")
    for _ in range(2):
        link.click()
        card = frame.locator("[data-guided-card]")
        expect(card).to_be_visible()
        message = card.locator("[data-guided-card-message]")
        expect(message).to_contain_text("A separate window could not be opened here")
        expect(message).to_contain_text("Separate windows is limited here:")
        expect(message).to_contain_text("Open the HTML file directly in a browser to open cards in their own window.")
        card.locator("[data-guided-card-close]").click()
    warning = frame.locator('[data-notice="capability-popups"]')
    expect(warning).to_have_count(1)
    expect(warning.locator("[data-notice-title]")).to_have_text("Limited functionality: Separate windows")
    details = warning.locator("[data-notice-details]")
    for term, text in (("Feature", "Separate windows"), ("Why", "blocks new windows"),
                       ("Observed", "window.open returned no window"),
                       ("Remedy", "Open the HTML file directly in a browser")):
        expect(details.locator("dt", has_text=term)).to_have_count(1)
        assert text in details.locator("dt", has_text=term).evaluate("(term) => term.nextElementSibling.textContent")
    assert errors == []
