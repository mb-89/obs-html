"""The page pool (test/conftest.py): a page goes back to the pool as a new context would show it.

Reader: whoever changes the pool or a browser test that leases its pages.
"""
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

# Stores a value in each storage the artifact or a test can reach, and asks before it unloads
# once the reader clicked, as the artifact's comments bar does with unsaved comments.
STATEFUL = """<!doctype html><meta charset="utf-8"><body><button id="b">Change</button><script>
localStorage.setItem("kept", "yes");
sessionStorage.setItem("kept", "yes");
document.cookie = "kept=yes";
document.getElementById("b").addEventListener("click", () => {
    window.addEventListener("beforeunload", (event) => { event.preventDefault(); event.returnValue = ""; });
});
</script>"""

STORED = """() => ({local: localStorage.getItem("kept"), session: sessionStorage.getItem("kept"), cookie: document.cookie,
    dark: matchMedia("(prefers-color-scheme: dark)").matches, print: matchMedia("print").matches,
    width: innerWidth})"""


def stateful(tmp_path: Path, name: str) -> str:
    path = tmp_path / name
    path.write_text(STATEFUL, encoding="utf-8")
    return path.as_uri()


def test_a_released_page_is_reused_as_a_new_context_shows_it(tmp_path: Path, page_pool) -> None:
    page = page_pool.lease({"width": 900, "height": 600})
    heard = []
    page.on("console", lambda message: heard.append(message.text))
    page.goto(stateful(tmp_path, "one.html"))
    page.click("#b")
    page.emulate_media(media="print", color_scheme="dark")
    page.context.new_page()
    page_pool.release(page)

    again = page_pool.lease(None)
    assert again is page, "test/conftest.py: the pool opened a new page instead of reusing the released one"
    assert again.context.pages == [again]
    blank = tmp_path / "blank.html"
    blank.write_text("<!doctype html><title>Blank</title>", encoding="utf-8")
    again.goto(blank.as_uri())
    assert again.evaluate(STORED) == {"local": None, "session": None, "cookie": "", "dark": False,
                                      "print": False, "width": 1280}
    again.evaluate("() => console.log('after release')")
    assert heard == []
    page_pool.release(again)


def test_a_page_with_a_setting_a_navigation_keeps_is_not_reused(tmp_path: Path, page_pool) -> None:
    page = page_pool.lease(None)
    page.route("**/*", lambda route: route.abort())
    page_pool.release(page)
    assert page.is_closed()

    other = page_pool.lease(None)
    assert other is not page
    other.goto(stateful(tmp_path, "one.html"))
    assert other.evaluate("() => localStorage.getItem('kept')") == "yes"
    page_pool.release(other)


def test_a_page_the_test_closed_is_replaced(page_pool) -> None:
    page = page_pool.lease(None)
    page.close()
    page_pool.release(page)
    other = page_pool.lease(None)
    assert not other.is_closed()
    page_pool.release(other)
