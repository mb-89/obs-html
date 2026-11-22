"""Judge the spec artifact's first chapter on CI: the median of RUNS runs alone against its second.

Reader: whoever reads or changes how CI checks that obs's spec artifact shows its first chapter
within a second (spec/artifact-ui.md), and CI's `first chapter` job (.github/workflows/test.yml),
which runs it outside the suite.

test/test_startup_browser.py proves the order of the startup in every run and judges
its second only where it runs alone, but one runner's speed varies too much for one run to judge it.
So this runs that one test RUNS times, each alone in its own pytest process, from this
repository's root, with the test's MEDIAN_VARIABLE set: each run then judges only the order and records its
painted time and its budget as junit properties (PAINTED, BUDGET). The runs share one build of
the spec (the core's test/spec_build.py, RUN_FOLDER). It prints every run's painted time and their median
(statistics.median: the middle time of an odd count), judges the median against the budget the
runs recorded (verdict: over it, not at it, misses), and names its own time. On GitHub Actions it
also writes one annotation titled TITLE.

While BLOCKING is false nothing it finds fails it: a missed median is a warning, and a run that
failed (the test's order or errors, which the suite's shards judge as well) or recorded no time is
an error annotation, and it exits 0. Once BLOCKING is true either fails it, and CI's `check`,
which needs its job, fails with it.

    uv run python test/first_chapter.py
"""
import os
import statistics
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ElementTree
from pathlib import Path

ADAPTER = Path(__file__).resolve().parents[1]
TEST = "test/test_startup_browser.py::test_the_spec_artifact_shows_its_first_chapter_within_a_second"
RUNS = 5
TITLE = "obs first chapter"
# test_startup_browser.py's MEDIAN_VARIABLE (test/test_first_chapter.py holds them equal).
MEDIAN_VARIABLE = "OBS_HTML_FIRST_CHAPTER_MEDIAN"
RUN_FOLDER = "OBS_SPEC_BUILD"  # the core's test/spec_build.py's RUN_FOLDER
PAINTED = "startup painted ms"
BUDGET = "startup first chapter budget ms"

# Warn-only for now. It becomes blocking (True) after five runs on main in a row whose median is
# under the budget; a later work issue flips it, nothing flips it on its own.
BLOCKING = False


def median(times: list[float]) -> float:
    """The median of the runs' painted times: the middle one of an odd count."""
    return statistics.median(times)


def verdict(median_ms: float, budget_ms: float, blocking: bool) -> str:
    """``pass`` at or under the budget; over it ``fail`` where blocking, else ``warn``."""
    if median_ms <= budget_ms:
        return "pass"
    return "fail" if blocking else "warn"


def properties(report: Path) -> dict[str, str]:
    """A JUnit report's test properties by name."""
    return {item.get("name"): item.get("value")
            for item in ElementTree.parse(report).getroot().iter("property")}


def measure(run: int, folder: Path, environment: dict[str, str]) -> tuple[float | None, float | None, str]:
    """One run of TEST alone: its painted time, its budget (None where not recorded) and its failure."""
    report = folder / f"run-{run}.xml"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", TEST, f"--junitxml={report}"],
        cwd=ADAPTER, env={**environment, MEDIAN_VARIABLE: "1", RUN_FOLDER: str(folder)},
        capture_output=True, text=True)
    recorded = properties(report) if report.is_file() else {}
    painted, budget = (float(recorded[name]) if name in recorded else None for name in (PAINTED, BUDGET))
    failure = "" if result.returncode == 0 else (result.stdout + result.stderr).strip()[-2000:]
    return painted, budget, failure


def judge(runs: list[tuple[float | None, float | None, str]], blocking: bool,
          seconds: float, actions: bool) -> tuple[list[str], int]:
    """The lines to print for the runs and the exit code; ``actions`` adds TITLE's annotation."""
    lines = [f"first chapter: run {index} painted {'no time' if painted is None else f'{painted:.0f} ms'}"
             for index, (painted, _budget, _failure) in enumerate(runs, 1)]
    failed = [index for index, (painted, budget, failure) in enumerate(runs, 1)
              if failure or painted is None or budget is None]
    for index in failed:
        lines.append(f"first chapter: run {index} failed: {runs[index - 1][2] or 'it recorded no time'}")
    if failed:
        summary = (f"test/first_chapter.py: runs {failed} of {TEST} failed or recorded no time, so "
                   f"no median is judged. Remedy: run `uv run pytest {TEST}` here.")
        state = "fail" if blocking else "error"
    else:
        times = [painted for painted, _budget, _failure in runs]
        middle, budget = median(times), max(budget for _painted, budget, _failure in runs)
        state = verdict(middle, budget, blocking)
        summary = (f"test/first_chapter.py: the spec artifact painted its first chapter in a median "
                   f"{middle:.0f} ms of {len(times)} runs alone ({', '.join(f'{t:.0f}' for t in times)} ms), "
                   f"{'within' if state == 'pass' else 'over'} its {budget:.0f} ms budget"
                   + ("" if state == "pass" else
                      f"; {'blocking' if blocking else 'warn-only'} (test/first_chapter.py, BLOCKING)"))
    summary += f"; the step took {seconds:.0f} s."
    lines.append(summary)
    if actions:
        level = {"pass": "notice", "warn": "warning", "error": "error", "fail": "error"}[state]
        lines.append(f"::{level} title={TITLE}::{summary}")
    return lines, 1 if state == "fail" else 0


def main(environment: dict[str, str] = os.environ, clock=time.monotonic, run=measure) -> int:
    started = clock()
    with tempfile.TemporaryDirectory(prefix="obs-first-chapter-") as folder:
        runs = [run(index, Path(folder), dict(environment)) for index in range(1, RUNS + 1)]
    lines, code = judge(runs, BLOCKING, clock() - started, environment.get("GITHUB_ACTIONS") == "true")
    print("\n".join(lines), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
