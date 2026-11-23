"""The browser door's hot test that records each top-level state in the one Chromium.

Reader: whoever records the browser door's states (test/browser/browser-door.md, Recording and
replay) or adds a state to test/browser/expectations.yaml.

`uv run pytest -m hot --record` runs it: for each state whose frame is the top-level page, the fake
browser lists what the page asks at each step, then full Chromium opens the state's artifact at the
state's context, a phone's on full Chromium's phone pages (test/conftest.py, PHONE_CONTEXT), takes
each step and runs every expectation's probe after it, and test/browser/door.py writes
test/browser/recordings/<state>.yaml. Without --record it skips and starts no browser. The viewer frame's state is recorded by test_sandboxed_preview_browser.py.
"""
import pytest

from browser import door
from conftest import PHONE_CONTEXT

TOP_LEVEL = sorted(name for name, state in door.states().items() if state["context"]["frame"] == "top")


@pytest.mark.hot
@pytest.mark.browser
@pytest.mark.parametrize("name", TOP_LEVEL)
def test_a_top_level_state_is_recorded_in_the_one_chromium(name: str, recording, door_artifact, fake_page,
                                                           full_chromium_browser, request) -> None:
    state = door.states()[name]
    context = state["context"]
    artifact = door_artifact(name)
    phone = context["touch"]
    if phone:
        assert (context["scale"], context["touch"]) == (PHONE_CONTEXT["device_scale_factor"], PHONE_CONTEXT["has_touch"]), (
            f"{name}: a phone's state has the scale and touch of test/conftest.py's PHONE_CONTEXT, which the "
            "one Chromium's phone pages have")
    browser = request.getfixturevalue("full_phone_browser") if phone else full_chromium_browser

    def open_chromium():
        width, height = context["viewport"]
        page = browser.new_page(viewport={"width": width, "height": height}, color_scheme=context["scheme"])
        page.emulate_media(media=context["media"], reduced_motion=context["motion"])
        page.goto(artifact.as_uri())
        return page, page

    recorded = door.record_state(name, artifact, fake_page, open_chromium)
    assert [answer["step"] for answer in recorded["answers"]] == list(range(len(state["steps"])))
    assert recorded["answers"][0]["box"], f"{name}: the page asked no box, so nothing was measured"
