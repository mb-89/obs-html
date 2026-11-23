"""The fake browser keeps its contract: its facade, its stand-ins, its clock, its default answers and its network.

Reader: whoever changes test/browser/fake-browser.cjs, test/browser/fake_page.py or the ``fake_page``
fixture (test/browser/browser-door.md, The fake browser).

Each test opens a small page of its own, written into its temporary folder, in the fake browser,
happy-dom in Node; none starts a Chromium.
"""
import http.server
import threading
import types

import pytest

import network_guard
from browser.fake_page import NOTE, FakeBrowserUnsupported, FakeTimeoutError, expect
from conftest import FAKE_DEFAULTS_SECTION, fake_defaults

pytestmark = pytest.mark.dom


def _open(tmp_path, fake_page, body: str, head: str = ""):
    page = tmp_path / "page.html"
    page.write_text(f"<!doctype html><html><head>{head}</head><body>{body}</body></html>", encoding="utf-8")
    fake_page.goto(page.as_uri())
    return fake_page


def test_a_method_the_facade_lacks_names_itself_and_the_design_note(tmp_path, fake_page) -> None:
    page = _open(tmp_path, fake_page, "<p>Text</p>")
    for missing in (lambda: page.select_option("p", "x"), lambda: page.locator("p").select_text(),
                    lambda: page.keyboard.insert_paragraph(), lambda: expect(page.locator("p")).to_have_css("a", "b")):
        with pytest.raises(FakeBrowserUnsupported) as refused:
            missing()
        assert NOTE in str(refused.value)
    with pytest.raises(FakeBrowserUnsupported, match="select_option"):
        page.select_option("p", "x")
    # Playwright's own selector engines are no CSS: the refusal says how to write them instead.
    with pytest.raises(FakeBrowserUnsupported, match="text filter") as refused:
        page.locator("text=Text").count()
    assert NOTE in str(refused.value)


def test_a_request_to_anything_but_a_local_server_fails_and_fails_the_test(tmp_path, fake_page) -> None:
    class Answer(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"local answer")

        def do_OPTIONS(self):  # happy-dom asks before every cross-origin request (browser-door.md, As built)
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Answer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        page = _open(tmp_path, fake_page, "<p>Text</p>")
        requests: list[str] = []
        page.on("request", lambda request: requests.append(request.url))
        local = f"http://127.0.0.1:{server.server_address[1]}/data"
        assert page.evaluate("url => fetch(url).then(response => response.text())", local) == "local answer"
        assert network_guard.take() == []
        message = page.evaluate("fetch('https://example.org/data').then(() => 'answered', error => error.message)")
        assert "leaves the machine" in message and NOTE in message
        [recorded] = network_guard.take()
        assert "example.org:443" in recorded and "fake page" in recorded
        # Each request reaches the page's request listeners, the refused one too, as Playwright's do.
        assert requests == [local, "https://example.org/data"]
    finally:
        server.shutdown()
        server.server_close()


def test_the_tests_report_lists_the_default_answers_the_fake_gave(tmp_path, fake_page) -> None:
    page = _open(tmp_path, fake_page, '<div id="shown"><span>One</span></div><div id="folded" hidden><b>Two</b></div>')
    assert page.evaluate("""() => [document.querySelector('#shown span').getBoundingClientRect().width,
        document.querySelector('#shown span').offsetHeight, document.querySelector('#folded b').getClientRects().length,
        document.createElement('i').getBoundingClientRect().height]""") == [384, 24, 0, 0]
    report = types.SimpleNamespace(when="call", sections=[])
    fake_defaults(report)
    [(title, listed)] = report.sections
    assert title == f"{FAKE_DEFAULTS_SECTION} (call)"
    assert listed.splitlines() == ["getBoundingClientRect #shown > span:1 -> 384x24 (1x)",
                                   "getBoundingClientRect i:1 -> empty (1x)", "getClientRects #folded > b:1 -> empty (1x)",
                                   "offsetHeight #shown > span:1 -> 24 (1x)"]
    # Each default is listed once, in the phase that gave it.
    fake_defaults(report)
    assert len(report.sections) == 1


def test_the_stand_ins_answer_as_the_design_lists(tmp_path, fake_page) -> None:
    page = _open(tmp_path, fake_page, '<button id="open">Open</button><div id="menu" popover="auto">Menu</div>'
                                      '<select id="choice"></select><canvas id="canvas"></canvas>')
    assert page.evaluate("""async () => {
        const select = document.querySelector('#choice');
        select.append(new Option('First', 'one'));
        const clone = structuredClone({list: [1, {two: 2}], when: new Date(0)});
        const bytes = new TextEncoder().encode('obs '.repeat(50));
        const pack = (data, Stream) => new Response(new Blob([data]).stream().pipeThrough(new Stream('gzip'))).arrayBuffer();
        const round = new TextDecoder().decode(await pack(await pack(bytes, CompressionStream), DecompressionStream));
        const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)).length;
        const printed = [];
        addEventListener('beforeprint', () => printed.push('before'));
        addEventListener('afterprint', () => printed.push('after'));
        print();
        return [select.options[0].value, select.options[0].textContent, clone.constructor === Object,
                Array.isArray(clone.list) && clone.list[1].two, clone.when instanceof Date, round === 'obs '.repeat(50),
                digest, printed, document.querySelector('#canvas').getContext('2d').measureText('four').width,
                bytes instanceof Uint8Array];
    }""") == ["one", "First", True, 2, True, True, 32, ["before", "after"], 28, True]
    menu = page.locator("#menu")
    assert not menu.is_visible()
    page.evaluate("document.querySelector('#menu').showPopover()")
    assert menu.is_visible() and page.evaluate("document.querySelector('#menu').matches(':popover-open')")
    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    page.evaluate("document.querySelector('#menu').showPopover()")
    page.locator("#open").click()  # a pointerdown outside an auto popover closes it
    assert page.evaluate("document.querySelector('#menu').matches(':popover-open')") is False


def test_a_download_link_hands_its_file_to_expect_download(tmp_path, fake_page) -> None:
    page = _open(tmp_path, fake_page, '<a id="data" download="note.txt" href="data:text/plain,two%20words">Data</a>'
                                      '<a id="kept" download href="data:text/plain,kept">Kept</a>')
    with page.expect_download() as made:
        page.evaluate("""() => { const link = document.createElement('a');
            link.href = URL.createObjectURL(new Blob(['made in the page'], {type: 'text/html'}));
            link.download = 'copy.html'; document.body.append(link); link.click(); link.remove(); }""")
    made.value.save_as(tmp_path / "copy.html")
    assert made.value.suggested_filename == "copy.html"
    assert (tmp_path / "copy.html").read_text(encoding="utf-8") == "made in the page"
    with page.expect_download() as clicked:
        page.locator("#data").click()
    clicked.value.save_as(tmp_path / "note.txt")
    assert (clicked.value.suggested_filename, (tmp_path / "note.txt").read_text(encoding="utf-8")) == (
        "note.txt", "two words")
    # A prevented click downloads nothing, and the page stays where it is.
    page.evaluate("document.querySelector('#kept').addEventListener('click', event => event.preventDefault())")
    with pytest.raises(FakeTimeoutError, match="downloaded nothing"):
        with page.expect_download(timeout=1000):
            page.locator("#kept").click()
    assert page.url == (tmp_path / "page.html").as_uri()


def test_the_page_runs_on_its_own_clock_and_a_wait_that_cannot_hold_ends_at_once(tmp_path, fake_page) -> None:
    page = _open(tmp_path, fake_page, "<p>Text</p>")
    # A timer a minute away fires as soon as a wait needs it; no wall time passes for it.
    page.evaluate("window.ticks = 0; window.timer = setInterval(() => { window.ticks += 1; }, 60000)")
    page.wait_for_function("window.ticks === 2", timeout=180_000)
    page.evaluate("clearInterval(window.timer)")
    # With nothing left to run, a wait that cannot hold fails without waiting for its timeout.
    with pytest.raises(FakeTimeoutError, match="nothing left to run"):
        page.wait_for_function("window.never === true")
    with pytest.raises(FakeTimeoutError, match="matched no element"):
        page.locator("#missing").click(timeout=1000)
    # A promise evaluate returns settles as the page's frames run.
    assert page.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve('two'))))") \
        == "two"


def test_the_cascade_still_applies_every_rule_that_can_match(tmp_path, fake_page) -> None:
    """The host skips a style rule whose subject needs an id, class or tag the element lacks; each
    kind of selector below still applies where it matches, and only there."""
    styles = ("<style>.outer .inner { color: rgb(1, 0, 0); } div.box > span { color: rgb(2, 0, 0); }"
              " #named { color: rgb(3, 0, 0); } :is(.wrap) em { color: rgb(4, 0, 0); }"
              " [data-mark] { color: rgb(5, 0, 0); } p:not(.skip) b, i.alt { color: rgb(6, 0, 0); }</style>")
    page = _open(tmp_path, fake_page, '<div class="outer"><span class="inner">1</span></div><div class="box"><span>2</span>'
                                      '</div><span id="named">3</span><div class="wrap"><em>4</em></div><u data-mark>5</u>'
                                      '<p><b>6</b></p><p class="skip"><b>7</b></p><i class="alt">8</i><span class="inner">9</span>',
                 head=styles)
    colours = page.evaluate("""() => ['.outer .inner', '.box span', '#named', '.wrap em', 'u', 'p:first-of-type b',
        'p.skip b', 'i', 'body > .inner'].map(selector => getComputedStyle(document.querySelector(selector)).color)""")
    assert colours[:6] == [f"rgb({index}, 0, 0)" for index in range(1, 6)] + ["rgb(6, 0, 0)"]
    assert colours[7] == "rgb(6, 0, 0)"
    assert "rgb(6, 0, 0)" != colours[6] and colours[8] != "rgb(1, 0, 0)"
