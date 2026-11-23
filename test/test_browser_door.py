"""The browser door's conformance: the fake browser computes what obs-html expects as the recorded
Chromium answered it, and answers the supplied calls from the recordings.

Reader: whoever changes the fake browser (test/browser/fake-browser.cjs), the runtime a state opens,
or an expectation (test/browser/expectations.yaml), and reads why this check failed.

It runs without a browser. For each state, test/browser/door.py opens the state's artifact in the
fake with its recording, takes each step and asks every computed expectation with the keys the
recording lists; an answer that differs from Chromium's fails, naming the state, the step, the key
and both answers. Where the state's artifact no longer builds to the recording's digest, the
failure says so too: the page changed since it was recorded, and `uv run pytest -m hot --record`
records it again (test/browser/browser-door.md, When hot tests run).
"""
import copy

import pytest

from browser import door

pytestmark = pytest.mark.dom

STATES = sorted(door.states())


def recorded(name: str) -> dict:
    recording = door.load_recording(name)
    assert recording is not None, (f"{door.OWNER}: the state {name} has no recording "
                                   f"{door.recording_path(name).relative_to(door.ROOT).as_posix()}. Remedy: run "
                                   f"`{door.REMEDY}` and commit it")
    return recording


@pytest.mark.parametrize("name", STATES)
def test_the_fake_computes_each_expectation_as_the_recorded_chromium_answered(name: str, door_artifact,
                                                                            fake_page) -> None:
    recording = recorded(name)
    artifact = door_artifact(name)
    found = door.conformance(fake_page, name, artifact, recording)
    stale = door.stale(name, artifact, recording)
    assert not found, "\n".join([f"{door.OWNER}: the fake browser answers otherwise than the recorded Chromium:",
                                 *found, *([f"Also, {stale}: record it again with `{door.REMEDY}`."] if stale else []),
                                 f"Remedy: make the fake answer as Chromium does ({door.NOTE}, Conformance)."])


def test_a_changed_computed_answer_is_named_with_its_state_step_key_and_both_answers() -> None:
    name = "features-desktop"
    recording = recorded(name)
    computed = {answer["step"]: {expectation["name"]: copy.deepcopy(answer[expectation["name"]])
                                 for expectation in door.asked_in(door.states()[name], "computed", answer["step"])}
                for answer in recording["answers"]}
    assert door.compare(name, recording, computed) == []
    key = sorted(computed[0]["cascade"])[0]
    computed[0]["cascade"][key] = "changed"
    computed[1]["frames"] = ["second", "first"]
    chromium = recording["answers"][0]["cascade"][key]
    assert door.compare(name, recording, computed) == [
        f"state {name}, step 0, cascade, key {key}: the fake answers \"changed\", Chromium answered "
        f"{door.json.dumps(chromium)}",
        f"state {name}, step 1, frames: the fake answers [\"second\", \"first\"], Chromium answered "
        f"{door.json.dumps(recording['answers'][1]['frames'])}"]


# A box, a client rect list and a text width as the page's runtime reads them.
LAYOUT = """(door) => {
    const element = door.element(door.asked.key);
    const rect = element.getBoundingClientRect();
    const context = document.createElement("canvas").getContext("2d");
    context.font = door.asked.font;
    return {border: [rect.x, rect.y, rect.width, rect.height],
            rects: [...element.getClientRects()].map((each) => [each.x, each.y, each.width, each.height]),
            width: context.measureText(door.asked.text).width};
}"""


def test_a_fake_page_answers_a_recorded_box_and_text_width_from_its_recording(door_artifact, fake_page) -> None:
    name = "features-desktop"
    recording = recorded(name)
    first = recording["answers"][0]
    key, box = next((key, box) for key, box in first["box"].items() if box["border"][2] and box["rects"])
    measured, width = next(iter(first["text-width"].items()))
    font, text = measured.split("|", 1)
    door.open_state(fake_page, name, door_artifact(name), recording, through=0)
    answered = fake_page.evaluate(door.page_function(LAYOUT), {"key": key, "font": font, "text": text})
    assert answered == {"border": box["border"], "rects": box["rects"], "width": width}


def test_a_fake_viewer_frame_refuses_as_the_recorded_chromium_refused(door_artifact, fake_page) -> None:
    name = "preview-viewer-frame"
    recording = recorded(name)
    door.open_state(fake_page, name, door_artifact(name), recording)
    viewer = next(each for each in door.expectations() if each["name"] == "viewer-frame")
    refusals = recording["answers"][0]["viewer-frame"]
    assert refusals["window.localStorage"] == {"throws": "SecurityError"}
    assert fake_page.evaluate(door.probe_function(viewer), {}) == refusals


def test_a_state_built_through_artifact_html_is_built_at_the_doors_instant(monkeypatch) -> None:
    """A state's artifact digest changes only with the page (browser-door.md, Recording and replay): a
    state whose function builds through test/artifacts.py's artifact_html is built at the instant
    SOURCE_DATE_EPOCH names, as the CLI builds, not at the moment it runs."""
    import artifacts
    from obs_html import build_time

    seen = {}
    monkeypatch.setattr(artifacts, "render", lambda document, config, **options: seen.update(options) or "built")
    monkeypatch.setenv(build_time.VARIABLE, door.BUILD_EPOCH)
    assert artifacts.artifact_html({"state": "a page no other test renders"}) == "built"
    assert seen["built"] == build_time.fixed({build_time.VARIABLE: door.BUILD_EPOCH})
