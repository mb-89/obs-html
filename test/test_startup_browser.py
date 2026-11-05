"""Startup budget: obs's spec artifact shows its first chapter within a second of opening.

The spec is opened as a reader sees it in Claude's preview, in the null-origin frame
(test/preview.py), with the browser the other browser tests use. The test records three times
from the frame's own clock: first paint, first chapter painted, and fully interactive (the
artifact's `ready` status). It fails when the first chapter is painted later than
FIRST_CHAPTER_MILLISECONDS, and names the slowest startup steps up to then: the
"obs-startup <step>" measures artifact-data.js records.

Run it alone with `uv run pytest test/test_startup_browser.py`; it reuses the parity gate's
build of the spec (test/test_parity_browser.py), made once per run.
"""
from pathlib import Path

from preview import SANDBOXES, preview_wrapper
from test_parity_browser import parity_artifacts  # noqa: F401  (the spec, built once per run)

FIRST_CHAPTER_MILLISECONDS = 1000

# Recorded in the frame before the artifact's own scripts run.
TIMES = """(() => {
    const times = globalThis.obsStartupTimes = {};
    document.addEventListener("obs-chapter-change", () => requestAnimationFrame(() => setTimeout(() => {
        times.firstChapter ??= performance.now();
    })), {once: true});
    document.addEventListener("obs-html-ready", () => { times.ready = performance.now(); }, {once: true});
})();"""

READ = """() => ({
    ...globalThis.obsStartupTimes,
    firstPaint: performance.getEntriesByName("first-paint")[0]?.startTime,
    steps: performance.getEntriesByType("measure")
        .filter(entry => entry.name.startsWith("obs-startup "))
        .map(entry => ({name: entry.name.slice(12), start: entry.startTime, duration: entry.duration})),
})"""


def test_the_spec_artifact_shows_its_first_chapter_within_a_second(
        tmp_path: Path, reader_browser, parity_artifacts: dict[str, str], record_property) -> None:
    wrapper = tmp_path / "preview-null-origin.html"
    wrapper.write_text(preview_wrapper(parity_artifacts["adapter"], SANDBOXES["null-origin"]), encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": 1200, "height": 800})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_init_script(TIMES)
    page.goto(wrapper.as_uri())
    frame = page.locator("#artifact").element_handle().content_frame()
    frame.wait_for_function("globalThis.obsStartupTimes?.ready && globalThis.obsStartupTimes.firstChapter")
    measured = frame.evaluate(READ)
    assert not errors, f"test/test_startup_browser.py: the spec artifact raised errors while opening: {errors}"

    times = {name: round(measured[name]) for name in ("firstPaint", "firstChapter", "ready")}
    for name, value in times.items():
        record_property(f"startup {name} ms", value)
    print(f"spec artifact startup: first paint {times['firstPaint']} ms, first chapter "
          f"{times['firstChapter']} ms, fully interactive {times['ready']} ms")
    if times["firstChapter"] > FIRST_CHAPTER_MILLISECONDS:
        before = [step for step in measured["steps"] if step["start"] < measured["firstChapter"]]
        slowest = sorted(before, key=lambda step: -step["duration"])[:5]
        steps = "; ".join(f"{step['name']} {round(step['duration'])} ms" for step in slowest)
        raise AssertionError(
            f"test/test_startup_browser.py: the spec artifact painted its first chapter after "
            f"{times['firstChapter']} ms, over the {FIRST_CHAPTER_MILLISECONDS} ms budget (first paint "
            f"{times['firstPaint']} ms, fully interactive {times['ready']} ms). Slowest steps before it: "
            f"{steps or 'none recorded'}. Remedy: make those steps of the adapter's startup "
            "(src/obs_html/artifact-data.js and the scripts it starts) cheaper or defer them.")
