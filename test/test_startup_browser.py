"""Startup: obs's spec artifact shows its first chapter before the rest loads, within a second.

The spec is opened as a reader sees it in Claude's preview, in the null-origin frame
(test/preview.py), on full Chromium (conftest.py, full_chromium_browser), not the headless
shell the bulk of the browser tests use. The test waits on the artifact's obs-html-ready event
(preview.open_preview) and reads the artifact's own marks and startup measures, all set by
src/obs_html/artifact-data.js on the frame's own clock: "obs-startup first chapter shown",
"obs-startup first chapter painted", "obs-startup interactive" (every startup script has run;
the deferred work starts after it) and "obs-startup ready", and the "obs-startup <step>"
measures. No init script records them: in the sandboxed srcdoc frame, an init script can run
after the artifact's own scripts and miss their events.

The promise is proved by order, which no runner's speed changes (spec/design_input/quality.md,
Testing boundaries): the first chapter is shown before the artifact is interactive, so before
any deferred step, and no startup step starts between its being shown and its being painted.
A first chapter held back behind the rest fails, naming the steps that came first.

The second is judged by the clock only where the test runs alone, as
`uv run pytest test/test_startup_browser.py` runs it: the first chapter is painted within
FIRST_CHAPTER_MILLISECONDS of the frame's start, and a miss names the slowest startup steps up to
then. Under the complete suite's parallel workers (pytest-xdist) the runner sets the clock: CI's
runners painted the same commit's first chapter between 0.4 s and 1.8 s, while its share of the
whole startup stayed between a quarter and two fifths, so there the test records the times and
does not judge them.

It reuses the parity gate's build of the spec (test/test_parity_browser.py), made once per run.
"""
import os
from pathlib import Path

import pytest

from preview import open_preview
from test_parity_browser import spec_html  # noqa: F401  (the spec, built once per run)

FIRST_CHAPTER_MILLISECONDS = 1000
MARKS = {
    "shown": "obs-startup first chapter shown",
    "painted": "obs-startup first chapter painted",
    "interactive": "obs-startup interactive",
    "ready": "obs-startup ready",
}

# The artifact is ready (open_preview), so every mark it sets is set by then; the first chapter's
# paint follows its showing by two frames, so its mark is awaited (buffered: at once if set).
READ = """async (marks) => {
    await new Promise(resolve => new PerformanceObserver((list, observer) => {
        if (list.getEntriesByName(marks.painted).length) { observer.disconnect(); resolve(); }
    }).observe({type: "mark", buffered: true}));
    const mark = name => performance.getEntriesByName(name, "mark")[0]?.startTime ?? null;
    return {
        firstPaint: performance.getEntriesByName("first-paint")[0]?.startTime ?? null,
        ...Object.fromEntries(Object.entries(marks).map(([key, name]) => [key, mark(name)])),
        steps: performance.getEntriesByType("measure")
            .filter(entry => entry.name.startsWith("obs-startup "))
            .map(entry => ({name: entry.name.slice(12), start: entry.startTime, duration: entry.duration})),
    };
}"""


def alone(config: pytest.Config) -> bool:
    """Whether this test process runs without parallel workers beside it."""
    return not hasattr(config, "workerinput") and not os.environ.get("PYTEST_XDIST_WORKER")


@pytest.mark.browser
def test_the_spec_artifact_shows_its_first_chapter_within_a_second(
        request, tmp_path: Path, full_chromium_browser, spec_html: str, record_property) -> None:
    errors: list[str] = []
    _page, frame = open_preview(tmp_path, full_chromium_browser, errors, spec_html, "null-origin")
    measured = frame.evaluate(READ, MARKS)
    assert not errors, f"test/test_startup_browser.py: the spec artifact raised errors while opening: {errors}"
    missing = [MARKS[key] for key in MARKS if measured[key] is None]
    assert not missing, (
        f"test/test_startup_browser.py: the spec artifact set no {missing} mark while opening. Remedy: "
        "set them in src/obs_html/artifact-data.js as adapters/html/spec/artifact-ui.md says.")

    times = {name: round(measured[name]) for name in ("firstPaint", *MARKS) if measured[name] is not None}
    for name, value in times.items():
        record_property(f"startup {name} ms", value)
    print(f"spec artifact startup: first paint {times.get('firstPaint')} ms, first chapter shown "
          f"{times['shown']} ms, painted {times['painted']} ms, interactive {times['interactive']} ms, "
          f"ready {times['ready']} ms")

    steps = measured["steps"]
    if measured["shown"] > measured["interactive"]:
        before = [step["name"] for step in steps if step["start"] < measured["shown"]]
        raise AssertionError(
            f"test/test_startup_browser.py: the spec artifact showed its first chapter after "
            f"{times['shown']} ms, after it was interactive ({times['interactive']} ms): the first "
            f"chapter waited for the rest. Steps started before it: {'; '.join(before)}. Remedy: show "
            "the first chapter as the startup scripts run (src/obs_html/artifact.js), not in work "
            "deferred to after obs-html-interactive (adapters/html/spec/artifact-ui.md).")
    between = [step["name"] for step in steps
               if measured["shown"] <= step["start"] < measured["painted"]]
    assert not between, (
        f"test/test_startup_browser.py: the spec artifact started {between} after showing its first "
        f"chapter ({times['shown']} ms) and before painting it ({times['painted']} ms). Remedy: the "
        "startup paints the first chapter before its next step (src/obs_html/artifact-data.js, "
        "yieldSlice).")

    if not alone(request.config):
        return  # under parallel workers the runner sets the clock (module docstring)
    if measured["painted"] > FIRST_CHAPTER_MILLISECONDS:
        before = [step for step in steps if step["start"] < measured["painted"]]
        slowest = sorted(before, key=lambda step: -step["duration"])[:5]
        named = "; ".join(f"{step['name']} {round(step['duration'])} ms" for step in slowest)
        raise AssertionError(
            f"test/test_startup_browser.py: run alone, the spec artifact painted its first chapter "
            f"after {times['painted']} ms, over its {FIRST_CHAPTER_MILLISECONDS} ms budget (first "
            f"paint {times.get('firstPaint')} ms, ready {times['ready']} ms). Slowest steps before "
            f"it: {named or 'none recorded'}. Remedy: make those steps of the adapter's startup "
            "(src/obs_html/artifact-data.js and the scripts it starts) cheaper or defer them.")
