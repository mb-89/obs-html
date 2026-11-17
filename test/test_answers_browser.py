"""Native-browser tier: the page hands its answers to a sink (spec/capabilities/answers.md).

The sink ships with a chapter that asks for a bless (features.py, answers), so each artifact here
has one. The served page posts to obs-html serve, which writes answers.json and exits with the payload; a
sink a trusted bundle registers takes the payload in place of the built-in sinks; elsewhere the
payload is shown as text to copy. A bundle that registers no action registers a sink all the same. obs-html serve runs as the real command (test/serving.py), on
loopback only, every wait bounded.
"""
import json
from pathlib import Path

import pytest

import serving
from artifacts import artifact_html
from test_bless_browser import WIDTHS
from test_features import with_bless

pytestmark = pytest.mark.browser

PAYLOAD = {"verdicts": [{"id": "one", "verdict": "bless"}, {"id": "two", "verdict": "rework"}]}
APPLICATION = """globalThis.obsArtifact.registerApplication({id: "sink-v1", actions: [
    {id: "noop", accept: ".txt", help: "Nothing.", handle: async () => true}]});
"""
SINK = """globalThis.received = [];
globalThis.obsArtifact.trustedExtension("obsHtml.answers").register({id: "host-save",
    send: async payload => { globalThis.received.push(payload); return "saved by the host"; }});"""
BUNDLE = APPLICATION + SINK
SEND = """async payload => {
    try { return await globalThis.obsArtifact.sendAnswers(payload); }
    catch (error) { return {error: error.message}; }
}"""
CANARY = "() => globalThis.obsCapabilities.results.find(item => item.key === 'answers')"


def _write(tmp_path: Path, html: str) -> Path:
    artifact = tmp_path / "artifact.html"
    artifact.write_text(html, encoding="utf-8")
    return artifact


def _open(reader_browser, url: str, viewport: dict | None = None, console: list | None = None):
    """Open the page at the viewport given, collecting every console message into ``console`` where given."""
    from playwright.sync_api import expect

    page = reader_browser.new_page(viewport=viewport)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    if console is not None:
        page.on("console", lambda message: console.append((message.type, message.text)))
    page.goto(url)
    expect(page.locator("html")).to_have_attribute("data-artifact-status", "ready")
    assert errors == []
    return page


def test_the_served_page_posts_its_answers_and_serve_wait_exits_with_them(tmp_path: Path, reader_browser) -> None:
    artifact = _write(tmp_path, artifact_html(with_bless()))
    served = serving.started(artifact, "--wait", "--timeout", serving.WAIT)
    try:
        page = _open(reader_browser, served.url)
        canary = page.evaluate(CANARY)
        assert canary["allowed"] and canary["observation"].startswith("served by obs-html serve at http://127.0.0.1:")
        assert page.evaluate(SEND, PAYLOAD) == {"sink": "server", "written": "answers.json"}
        code, out, err = served.finished()
    finally:
        served.stop()
    assert code == 0, err
    assert json.loads(out.strip().splitlines()[-1]) == PAYLOAD
    assert json.loads((tmp_path / "answers.json").read_text(encoding="utf-8")) == PAYLOAD
    assert page.locator('[data-notice^="capability-"]').count() == 0

    # The server is gone: the page names it and the remedy, and shows the answers to copy.
    failed = page.evaluate(SEND, PAYLOAD)
    assert failed["error"].startswith("obsHtml.answers: obs-html serve at http://127.0.0.1:")
    assert json.loads(page.locator('[data-notice="answers"] [data-answers-text]').text_content()) == PAYLOAD


def test_a_sink_the_trusted_bundle_registers_takes_the_answers_in_place_of_the_server(
        tmp_path: Path, reader_browser) -> None:
    artifact = _write(tmp_path, artifact_html(with_bless(), trusted_runtime=("sink-v1", BUNDLE)))
    served = serving.started(artifact)
    try:
        page = _open(reader_browser, served.url)
        assert page.evaluate(SEND, PAYLOAD) == {"sink": "host-save", "result": "saved by the host"}
        assert page.evaluate("() => globalThis.received") == [PAYLOAD]
        again = page.evaluate("""() => { try { globalThis.obsArtifact.trustedExtension("obsHtml.answers")
            .register({id: "second", send: () => null}); } catch (error) { return error.message; } }""")
        assert again.startswith("Trusted extension obsHtml.answers: sink host-save")
    finally:
        served.stop()
    assert not (tmp_path / "answers.json").exists()


def test_a_bundle_without_actions_registers_a_sink_that_takes_sends_payload(tmp_path: Path, reader_browser) -> None:
    bundle = 'globalThis.obsArtifact.registerApplication({id: "sink-v1", actions: []});\n' + SINK
    artifact = _write(tmp_path, artifact_html(with_bless(), trusted_runtime=("sink-v1", bundle)))
    page = _open(reader_browser, artifact.as_uri() + "#one")
    page.locator('[data-bless-key="bless"]').click()
    page.locator("[data-bless-send]").click()
    page.wait_for_function("globalThis.received.length > 0")
    assert page.evaluate("() => globalThis.received") == [
        {"verdicts": [{"chapter": "one", "version": "0" * 64, "verdict": "bless"}]}]
    assert page.locator("[data-artifact-action]").count() == 0


def test_a_bundle_without_an_actions_array_is_refused_and_names_its_owner(tmp_path: Path, reader_browser) -> None:
    from playwright.sync_api import expect

    bundle = 'globalThis.obsArtifact.registerApplication({id: "sink-v1"});\n' + SINK
    page = reader_browser.new_page()
    page.goto(_write(tmp_path, artifact_html(with_bless(), trusted_runtime=("sink-v1", bundle))).as_uri())
    expect(page.locator("html")).to_have_attribute("data-artifact-status", "error")
    expect(page.get_by_role("alert")).to_contain_text("obsArtifact.registerApplication")


@pytest.mark.parametrize("viewport", WIDTHS, ids=["phone", "desktop"])
def test_elsewhere_the_answers_are_shown_as_text_with_a_copy_key(tmp_path: Path, reader_browser, viewport: dict) -> None:
    from playwright.sync_api import expect

    console: list = []
    page = _open(reader_browser, _write(tmp_path, artifact_html(with_bless())).as_uri(), viewport, console)
    canary = page.evaluate(CANARY)
    assert canary["decided"] is False and page.locator('[data-notice="capability-answers"]').count() == 0
    untrusted = page.evaluate("""() => { try { globalThis.obsArtifact.trustedExtension("obsHtml.answers"); }
        catch (error) { return error.message; } }""")
    assert untrusted.startswith("Trusted extension obsHtml.answers:") and "--trusted-runtime-bundle" in untrusted
    assert page.evaluate(SEND, [1])["error"].startswith("obsHtml.answers: obsArtifact.sendAnswers: ")

    assert page.evaluate(SEND, PAYLOAD) == {"sink": "text"}
    notice = page.locator('[data-notice="answers"]')
    expect(notice.locator("[data-notice-title]")).to_have_text("Answers: sending is not available here")
    expect(notice.locator("[data-answers-text]")).to_be_visible()
    assert json.loads(notice.locator("[data-answers-text]").text_content()) == PAYLOAD
    expect(notice.locator("[data-answers-copy]")).to_have_text("Copy answers")
    # Plain words: the title says what happened, the first detail only the remedy (answers.md, Sinks).
    expect(notice.locator("[data-notice-details] > p").first).to_have_text("Copy the answers and hand them over.")
    assert console == []  # Sending is not available: nothing failed, so nothing goes to the console.


NAMED = """globalThis.received = [];
globalThis.obsArtifact.trustedExtension("obsHtml.answers").register({id: "host-save", name: "Claude",
    send: async payload => { globalThis.received.push(payload); return "saved by the host"; }});"""
REGISTER = """(name) => { try { globalThis.obsArtifact.trustedExtension("obsHtml.answers")
    .register({id: "host-save", name, send: () => null}); return "registered"; }
    catch (error) { return error.message; } }"""


def test_a_named_sink_gives_its_name_in_the_result(tmp_path: Path, reader_browser) -> None:
    """Requirement 4: a registered sink's name, the reader's words for where the answers go, comes
    back with the sink's confirmation."""
    page = _open(reader_browser, _write(tmp_path, artifact_html(with_bless(), trusted_runtime=(
        "sink-v1", APPLICATION + NAMED))).as_uri())
    assert page.evaluate(SEND, PAYLOAD) == {"sink": "host-save", "name": "Claude", "result": "saved by the host"}


@pytest.mark.parametrize("name", ["", " Claude", "x" * 41, "Two\nlines", 7], ids=[
    "empty", "padded", "too-long", "control", "number"])
def test_a_malformed_sink_name_is_refused_with_its_remedy(tmp_path: Path, reader_browser, name) -> None:
    """Requirement 4: a name that is not plain text of 1 to 40 characters is refused, as a malformed
    id is: the message names the extension, register's name and the remedy."""
    page = _open(reader_browser, _write(tmp_path, artifact_html(with_bless(), trusted_runtime=(
        "sink-v1", APPLICATION))).as_uri())
    refused = page.evaluate(REGISTER, name)
    assert refused.startswith("Trusted extension obsHtml.answers: register: name"), refused
    assert "; " in refused, refused  # The remedy follows what is wrong.
    assert page.evaluate(REGISTER, "Claude") == "registered"


FAILING = """globalThis.obsArtifact.trustedExtension("obsHtml.answers").register({id: "host-save", %s
    send: async () => { throw new Error("quota_exceeded: no room"); }});"""
"""A registered sink, named or not, whose send rejects."""
MACHINERY = ("obshtml", "obs-html", "host-save", "quota_exceeded", "sink", "bundle", "registered", "server", "http",
             "127.0.0.1", "localhost")
"""What no reader entry names (answers.md, Contract; artifact-ui.md, Sent means sent), lowercased."""
REJECTED = "obsHtml.answers: registered sink host-save: send failed (quota_exceeded: no room)"
"""The start of the rejection's message, the caller's and the console's."""


@pytest.mark.parametrize("viewport", WIDTHS, ids=["phone", "desktop"])
@pytest.mark.parametrize(("name", "words"), [
    ("Claude", "They did not reach Claude. Copy the answers and give them to Claude."),
    (None, "They could not be sent from this page. Copy the answers and hand them over.")], ids=["named", "unnamed"])
def test_a_failing_sink_tells_the_reader_in_plain_words_and_the_console_its_message(
        tmp_path: Path, reader_browser, viewport: dict, name: str | None, words: str) -> None:
    """Where a registered sink fails, the rejection keeps the builder's message, the console gets it
    once, and the reader's two entries say in plain words what was not sent and where it was meant to
    go, naming no machinery."""
    from playwright.sync_api import expect

    bundle = APPLICATION + FAILING % (f"name: {json.dumps(name)}," if name else "")
    console: list = []
    page = _open(reader_browser, _write(tmp_path, artifact_html(with_bless(), trusted_runtime=(
        "sink-v1", bundle))).as_uri() + "#one", viewport, console)

    rejected = page.evaluate(SEND, PAYLOAD)["error"]
    assert rejected.startswith(REJECTED), rejected
    assert console == [("warning", rejected)]
    console.clear()

    page.locator('[data-bless-key="bless"]').click()
    page.locator("[data-bless-send]").click()
    sent = page.locator('[data-notice="bless-send"]')
    expect(sent.locator("[data-notice-details] > p")).to_have_text(
        "1 verdict and 0 comments were not sent. Your verdicts and comments are kept in the deck; send again.")
    assert [kind for kind, _ in console] == ["warning"] and console[0][1].startswith(REJECTED), console
    answers = page.locator('[data-notice="answers"]')
    expect(answers.locator("[data-notice-title]")).to_have_text("Answers were not sent")
    expect(answers.locator("[data-notice-details] > p").first).to_have_text(words)
    assert json.loads(answers.locator("[data-answers-text]").text_content()) == {
        "verdicts": [{"chapter": "one", "version": "0" * 64, "verdict": "bless"}]}
    expect(answers.locator("[data-answers-copy]")).to_have_text("Copy answers")
    for entry in (sent, answers.locator("[data-notice-title], [data-notice-details] > p")):
        text = " ".join(entry.all_text_contents()).lower()
        assert not [word for word in MACHINERY if word in text], text
