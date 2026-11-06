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


def _open(reader_browser, url: str):
    from playwright.sync_api import expect

    page = reader_browser.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
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


def test_elsewhere_the_answers_are_shown_as_text_with_a_copy_key(tmp_path: Path, reader_browser) -> None:
    from playwright.sync_api import expect

    page = _open(reader_browser, _write(tmp_path, artifact_html(with_bless())).as_uri())
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
