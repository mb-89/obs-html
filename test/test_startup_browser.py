"""Startup budget: obs's spec artifact shows its first chapter within a second of opening.

The spec is opened as a reader sees it in Claude's preview, in the null-origin frame
(test/preview.py), with the browser the other browser tests use. The test waits on the
artifact's obs-html-ready event (preview.open_preview) and on its "obs-startup first chapter
painted" mark, never on a poll. It reads three times from the frame's own clock, which starts
when the frame starts, so load on the machine before the page opens cannot count: first paint,
and the artifact's own marks for its first chapter painted and fully interactive (both set by
src/obs_html/artifact-data.js). No init script records them: in the sandboxed srcdoc frame, an
init script can run after the artifact's own scripts and miss their events. The test fails when
the first chapter is painted later than its budget, and names the slowest startup steps up to then:
the "obs-startup <step>" measures artifact-data.js records.

The budget is FIRST_CHAPTER_MILLISECONDS on an idle machine. Where load on the machine (the
complete suite's parallel workers) slows the page itself, the test measures that slowdown in the
same run, right after the startup, in the same frame: a fixed workload (sorting a fixed typed
array) is timed in many short samples; the fastest sample is the idle reference (a short sample
mostly runs without being preempted), and the samples' total over the idle reference's is the
load factor. The budget is
FIRST_CHAPTER_MILLISECONDS times that factor, never less; the test records both and its failure
message says so.

Run it alone with `uv run pytest test/test_startup_browser.py`; it reuses the parity gate's
build of the spec (test/test_parity_browser.py), made once per run.
"""
from pathlib import Path

from preview import open_preview
from test_parity_browser import parity_artifacts  # noqa: F401  (the spec, built once per run)

FIRST_CHAPTER_MILLISECONDS = 1000
FIRST_CHAPTER_MARK = "obs-startup first chapter painted"
READY_MARK = "obs-startup ready"

# The load reference's samples; each runs a fixed workload of about 1.5 ms on an idle machine.
REFERENCE_SAMPLES = 100

# Resolves once the first-chapter mark exists (buffered: at once if it was set already); the
# artifact is ready by then, so the mark is set within two frames. Then measures the load factor.
READ = """async ([firstChapterMark, readyMark, samples]) => {
    await new Promise(resolve => new PerformanceObserver((list, observer) => {
        if (list.getEntriesByName(firstChapterMark).length) { observer.disconnect(); resolve(); }
    }).observe({type: "mark", buffered: true}));
    // A builtin's work (sorting a fixed typed array), which no JIT tier changes, unlike a script loop.
    const values = new Float64Array(20000);
    for (let index = 0, seed = 1; index < values.length; index++) values[index] = seed = (seed * 16807) % 2147483647;
    const work = () => values.slice().sort();
    work();
    let idle = Infinity;
    const begin = performance.now();
    for (let index = 0; index < samples; index++) {
        const start = performance.now();
        work();
        idle = Math.min(idle, performance.now() - start);
    }
    const loadFactor = Math.max(1, (performance.now() - begin) / (samples * idle));
    return {
        loadFactor,
        firstPaint: performance.getEntriesByName("first-paint")[0]?.startTime,
        firstChapter: performance.getEntriesByName(firstChapterMark)[0].startTime,
        ready: performance.getEntriesByName(readyMark)[0].startTime,
        steps: performance.getEntriesByType("measure")
            .filter(entry => entry.name.startsWith("obs-startup "))
            .map(entry => ({name: entry.name.slice(12), start: entry.startTime, duration: entry.duration})),
    };
}"""


def test_the_spec_artifact_shows_its_first_chapter_within_a_second(
        tmp_path: Path, reader_browser, parity_artifacts: dict[str, str], record_property) -> None:
    errors: list[str] = []
    _page, frame = open_preview(tmp_path, reader_browser, errors, parity_artifacts["adapter"], "null-origin")
    measured = frame.evaluate(READ, [FIRST_CHAPTER_MARK, READY_MARK, REFERENCE_SAMPLES])
    assert not errors, f"test/test_startup_browser.py: the spec artifact raised errors while opening: {errors}"

    times = {name: round(measured[name]) for name in ("firstPaint", "firstChapter", "ready")}
    load_factor = round(measured["loadFactor"], 2)
    budget = round(FIRST_CHAPTER_MILLISECONDS * load_factor)
    for name, value in times.items():
        record_property(f"startup {name} ms", value)
    record_property("startup load factor", load_factor)
    record_property("startup first chapter budget ms", budget)
    print(f"spec artifact startup: first paint {times['firstPaint']} ms, first chapter "
          f"{times['firstChapter']} ms, fully interactive {times['ready']} ms; budget {budget} ms "
          f"({FIRST_CHAPTER_MILLISECONDS} ms idle times load factor {load_factor})")
    if times["firstChapter"] > budget:
        before = [step for step in measured["steps"] if step["start"] < measured["firstChapter"]]
        slowest = sorted(before, key=lambda step: -step["duration"])[:5]
        steps = "; ".join(f"{step['name']} {round(step['duration'])} ms" for step in slowest)
        raise AssertionError(
            f"test/test_startup_browser.py: the spec artifact painted its first chapter after "
            f"{times['firstChapter']} ms, over its {budget} ms budget ({FIRST_CHAPTER_MILLISECONDS} ms "
            f"idle times the load factor {load_factor} measured in this run; first paint "
            f"{times['firstPaint']} ms, fully interactive {times['ready']} ms). Slowest steps before it: "
            f"{steps or 'none recorded'}. Remedy: make those steps of the adapter's startup "
            "(src/obs_html/artifact-data.js and the scripts it starts) cheaper or defer them.")
