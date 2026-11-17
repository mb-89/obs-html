"""Browser tier: a live table's web route on a served page, a page opened from disk and in Claude's
artifact viewer (generic-tables.md, Current data: Reading, The web route).

Reader: whoever changes how the tables feature's live-source part reads a web route.

No test reaches the network: Playwright's routing serves the page from the made-up host
``pages.example.test`` and answers the declared endpoint ``api.example.test`` (``Endpoint``), or
aborts it. The tracker is live_viewer.py's, whose Base declares the capability note's example: a
connector route and then a web route. On a served page the web route reads, both pages a readable
``Link`` names are laid over the table, and without it only the first; a next page or a redirect to
another origin is not followed, an answer over 8 MiB or not in JSON is a failed read, and each
shows its line. A rate limit says so without a time and keeps the page from asking again before
the reset time; a reopen within ``refreshMinutes`` applies the kept result without a request; the
kept entry holds only what the declaration maps; with storage blocked the page still reads. A page
opened from disk uses the web route only. In the viewer stand-in a Base whose only route is a web
route asks nothing, and a page whose Content Security Policy refuses the origin posts one notice.
The pure layer is live-data.test.js's, the print's test_pdf.py's.
"""
import copy
import json
import re
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from artifacts import artifact_html
from browser.viewer import open_viewer
from live_viewer import LINE, SHOW, stand_in, tracker

pytestmark = pytest.mark.browser
PAGE = "https://pages.example.test/tracker.html"
API = "https://api.example.test/"
SECOND = "https://api.example.test/repos/example-org/widgets/issues?page=2"
ELSEWHERE = "https://elsewhere.example.test/"
EXPOSED = "Link, x-ratelimit-remaining, x-ratelimit-reset, Retry-After"
UPDATED = "2026-11-17T08:00:00Z"
# The REST list's items: issue 3 closed since the build on the first page, a new issue 5 on the second.
FIRST = [{"number": 3, "state": "closed", "labels": [{"name": "running"}], "title": "Widget 3", "body": "Closed now",
          "updated_at": UPDATED, "user": {"login": "someone"}, "pull_request": None}]
LATER = [{"number": 5, "state": "open", "labels": [{"name": "ready"}], "title": "Widget 5", "body": "Issue 5's text.",
          "updated_at": UPDATED, "user": {"login": "someone"}, "pull_request": None}]
ROWS = """() => Object.fromEntries([...document.querySelectorAll('[data-active-chapter] .data-table-shell tbody tr[data-row-key]')]
    .map(row => [row.querySelector('td')?.innerText.replace(/[\\u25b8\\u25be]/g, '').trim(), row.innerText.replace(/[\\u25b8\\u25be]/g, '').replace(/\\s+/g, ' ').trim()]))"""
TIME = r"\d{1,2}:\d{2}|\d{4}-\d{2}-\d{2}"


def _with_routes(document: dict, providers: tuple[str, ...]) -> dict:
    """``document`` with each live declaration's routes kept to ``providers``."""
    document = copy.deepcopy(document)

    def walk(value):
        if isinstance(value, dict):
            live = value.get("obsHtml", {}).get("liveSource") if isinstance(value.get("obsHtml"), dict) else None
            if live:
                live["changes"] = [route for route in live["changes"] if route["provider"] in providers]
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(document)
    return document


@pytest.fixture(scope="module")
def artifact() -> str:
    return artifact_html(tracker())


@pytest.fixture(scope="module")
def web_only() -> str:
    return artifact_html(_with_routes(tracker(), ("web",)))


class Endpoint:
    """The made-up endpoint: each request answered by the next of ``answers`` (the last repeats),
    each ``{status, body, headers, redirect}``, or aborted; every request recorded."""

    def __init__(self, *answers: dict, expose: str = EXPOSED, abort: bool = False):
        self.answers = list(answers) or [{}]
        self.expose = expose
        self.abort = abort
        self.requests = []

    def __call__(self, route) -> None:
        request = route.request
        self.requests.append({"url": request.url, "headers": request.headers, "method": request.method})
        if self.abort:
            route.abort()
            return
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        headers = {"Access-Control-Allow-Origin": "*", "Access-Control-Expose-Headers": self.expose,
                   "Content-Type": answer.get("type", "application/json; charset=utf-8"), **answer.get("headers", {})}
        body = answer.get("body", [])
        route.fulfill(status=answer.get("status", 200), headers=headers,
                      body=body if isinstance(body, str) else json.dumps(body))


def _serve(page, artifact: str, endpoint: Endpoint, headers: dict | None = None) -> list[str]:
    """Route the page's host and the endpoint; return the list every other request outside the page is added to."""
    others: list[str] = []
    page.route("https://pages.example.test/**", lambda route: route.fulfill(
        status=200, headers={"Content-Type": "text/html; charset=utf-8", **(headers or {})}, body=artifact))
    page.route("https://api.example.test/**", endpoint)
    page.on("request", lambda request: others.append(request.url) if not request.url.startswith(
        (PAGE, API, "blob:", "data:")) else None)
    return others


def _open(page, url: str = PAGE):
    page.goto(url)
    expect(page.locator("html")).to_have_attribute("data-artifact-status", "ready")
    page.evaluate(SHOW, "live")
    return page


def _rows(page) -> dict:
    return page.evaluate(ROWS)


def _line(page):
    return page.locator(LINE)


def _first_page(next_url: str = SECOND) -> dict:
    return {"body": FIRST, "headers": {"Link": f'<{next_url}>; rel="next"'}}


@pytest.mark.parametrize("expose", [EXPOSED, "x-ratelimit-remaining"], ids=["link-exposed", "link-hidden"])
def test_both_pages_a_readable_link_names_are_laid_over_the_table_and_without_it_only_the_first(
        artifact, reader_browser, expose) -> None:
    page = reader_browser.new_page(viewport={"width": 1280, "height": 900})
    errors: list[str] = []
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    endpoint = Endpoint(_first_page(), {"body": LATER}, expose=expose)
    others = _serve(page, artifact, endpoint)
    _open(page)
    expect(_line(page)).to_have_text("Showing current data")
    rows = _rows(page)
    assert rows["widgets-3"].startswith("widgets-3 Done")
    linked = expose == EXPOSED
    assert [request["url"] for request in endpoint.requests][1:] == ([SECOND] if linked else [])
    assert ("widgets-5" in rows) is linked
    if linked:
        assert rows["widgets-5"].startswith("widgets-5 Next Widget 5")
    assert others == []
    assert errors == []


@pytest.mark.parametrize("answer, expected", [
    (_first_page(ELSEWHERE + "issues?page=2"), "Showing current data · showing the first 1 changes"),
    ({"status": 302, "headers": {"Location": ELSEWHERE + "issues"}}, "Could not check for updates now"),
    ({"body": "[" + " " * (8 * 1024 * 1024) + "]"}, "Could not check for updates now"),
    ({"body": "[]", "type": "text/html"}, "Could not check for updates now"),
], ids=["foreign-next", "foreign-redirect", "over-8-mib", "not-json"])
def test_another_origin_is_never_followed_and_an_oversized_or_non_json_answer_is_a_failed_read(
        artifact, reader_browser, answer, expected) -> None:
    page = reader_browser.new_page(viewport={"width": 1280, "height": 900})
    endpoint = Endpoint(answer, {"body": LATER})
    others = _serve(page, artifact, endpoint)
    _open(page)
    expect(_line(page)).to_have_text(expected)
    assert len(endpoint.requests) == 1
    assert others == []
    status = "Done" if expected.startswith("Showing") else "Running"
    assert _rows(page)["widgets-3"].startswith(f"widgets-3 {status}")


def test_the_request_asks_since_an_hour_before_the_generation_timestamp_with_no_credentials(
        artifact, reader_browser) -> None:
    page = reader_browser.new_page(viewport={"width": 1280, "height": 900})
    page.context.add_cookies([{"name": "session", "value": "secret", "url": API}])
    endpoint = Endpoint({"body": []})
    _serve(page, artifact, endpoint)
    _open(page)
    expect(_line(page)).to_have_text("Showing current data")
    stamp = page.evaluate("JSON.parse(obsArtifact.serializeModel()).document.generation.timestamp")
    expected = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(page.evaluate(
        "stamp => Math.floor(Date.parse(stamp) / 1000)", stamp)) - 3600))
    [request] = endpoint.requests
    query = urlsplit(request["url"]).query
    assert f"since={expected.replace(':', '%3A')}" in query.split("&")
    assert parse_qs(query)["since"] == [expected]
    assert request["method"] == "GET"
    assert request["headers"]["accept"] == "application/json"
    assert not {"cookie", "referer", "authorization"} & set(request["headers"])


def test_a_rate_limit_says_to_wait_without_a_time_and_a_reopen_before_its_reset_asks_nothing(
        artifact, reader_browser) -> None:
    page = reader_browser.new_page(viewport={"width": 1280, "height": 900})
    reset = "4102444800"  # 1 Jan 2100: a reset time no run of this test reaches.
    endpoint = Endpoint({"status": 403, "body": {"message": "API rate limit exceeded"},
                         "headers": {"x-ratelimit-remaining": "0", "x-ratelimit-reset": reset}})
    _serve(page, artifact, endpoint)
    _open(page)
    expect(_line(page)).to_have_text("Example Tracker asks to wait before the next check")
    assert len(endpoint.requests) == 1
    _open(page)
    expect(_line(page)).to_have_text("Example Tracker asks to wait before the next check")
    assert len(endpoint.requests) == 1
    expect(_line(page)).not_to_have_text(re.compile(TIME))


def test_a_reopen_within_refresh_minutes_applies_the_kept_result_and_asks_nothing(artifact, reader_browser) -> None:
    page = reader_browser.new_page(viewport={"width": 1280, "height": 900})
    endpoint = Endpoint(_first_page(), {"body": LATER})
    _serve(page, artifact, endpoint)
    _open(page)
    expect(_line(page)).to_have_text("Showing current data")
    assert len(endpoint.requests) == 2
    _open(page)
    expect(_line(page)).to_have_text("Showing current data")
    rows = _rows(page)
    assert rows["widgets-3"].startswith("widgets-3 Done") and rows["widgets-5"].startswith("widgets-5 Next")
    assert len(endpoint.requests) == 2


def test_the_kept_entry_holds_no_value_the_declaration_does_not_map(artifact, reader_browser) -> None:
    page = reader_browser.new_page(viewport={"width": 1280, "height": 900})
    _serve(page, artifact, Endpoint(_first_page(), {"body": LATER}))
    _open(page)
    expect(_line(page)).to_have_text("Showing current data")
    kept = page.evaluate("""() => Object.keys(localStorage).filter(key => key.startsWith('obs-live:'))
        .map(key => [key, localStorage.getItem(key)])""")
    assert len(kept) == 1
    key, value = kept[0]
    assert key.startswith('obs-live:Tracker{"bodyPath":"body","changes":[')
    entry = json.loads(value)
    assert sorted(entry) == ["read", "results"]
    assert [item["path"] for item in entry["results"][0]["items"]] == ["issues/widgets-3.md", "issues/widgets-5.md"]
    for absent in ("updated_at", UPDATED, "someone", "user", "pull_request"):
        assert absent not in value


def test_with_storage_blocked_the_page_still_reads_and_shows_the_rows(artifact, reader_browser) -> None:
    """A sandboxed page has an opaque origin, whose storage throws on every access."""
    page = reader_browser.new_page(viewport={"width": 1280, "height": 900})
    endpoint = Endpoint({"body": FIRST})
    _serve(page, artifact, endpoint, {"Content-Security-Policy": "sandbox allow-scripts"})
    _open(page)
    assert page.evaluate("() => { try { localStorage.length; return 'open'; } catch { return 'blocked'; } }") == "blocked"
    expect(_line(page)).to_have_text("Showing current data")
    assert _rows(page)["widgets-3"].startswith("widgets-3 Done")
    _open(page)
    expect(_line(page)).to_have_text("Showing current data")
    assert len(endpoint.requests) == 2


def test_a_page_opened_from_disk_uses_only_the_web_route_and_says_when_it_could_not_check(
        artifact, reader_browser, tmp_path) -> None:
    path = tmp_path / "tracker.html"
    path.write_text(artifact, encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": 1280, "height": 900})
    requests: list[str] = []
    page.on("request", lambda request: requests.append(request.url) if not request.url.startswith(
        (path.as_uri(), "blob:", "data:")) else None)
    endpoint = Endpoint(abort=True)
    page.route("https://api.example.test/**", endpoint)
    _open(page, path.as_uri())
    expect(_line(page)).to_have_text("Could not check for updates now")
    assert page.evaluate("typeof globalThis.claude") == "undefined"
    assert [urlsplit(url).netloc for url in requests] == ["api.example.test"]


def test_in_the_viewer_a_base_with_a_web_route_only_asks_nothing_and_says_so(
        web_only, reader_browser, tmp_path) -> None:
    errors: list[str] = []
    page, frame = open_viewer(tmp_path, reader_browser, errors, web_only, "light", init_script=stand_in())
    requests: list[str] = []
    page.on("request", lambda request: requests.append(request.url))
    frame.evaluate(SHOW, "live")
    expect(frame.locator(LINE)).to_have_text("Newer updates cannot be shown here")
    assert frame.evaluate("fakeClaude.calls") == []
    assert [url for url in requests if not url.startswith(("blob:", "data:", "about:"))] == []
    assert errors == []


def test_a_policy_that_refuses_the_origin_says_so_and_posts_one_notice_in_reader_words(
        artifact, reader_browser) -> None:
    page = reader_browser.new_page(viewport={"width": 1280, "height": 900})
    endpoint = Endpoint({"body": FIRST})
    _serve(page, artifact, endpoint, {"Content-Security-Policy": "connect-src 'self' blob: data:"})
    _open(page)
    expect(_line(page)).to_have_text("Newer updates cannot be shown here")
    notice = page.locator('[data-notice="live-source"] [data-notice-title]')
    expect(notice).to_have_count(1)
    assert notice.inner_text() == "Newer updates from Example Tracker cannot be shown on this page."
    assert endpoint.requests == []
