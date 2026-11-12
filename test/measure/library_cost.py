"""What the packaged browser libraries cost a page's start on a throttled phone.

Reader: whoever decides whether, or how, obs-html evaluates its libraries (architecture.md, Library
doors): Plotly, math.js and pdf-lib.

    uv run python adapters/html/test/measure/library_cost.py [--runs 5] [--output DIRECTORY]

It builds real pages with this checkout's core and adapter, each with the real libraries (never
the tests' fakes):

- ``deck``: a decision deck, the phone deck (test/fixtures/phone-deck) in the screens layout,
  as se's deck build lays one out;
- ``report``: a report with figures (test/fixtures/documents/figures.json);
- ``plain``: a page with no figure, formula or PDF (test/fixtures/documents/structural.json);
- ``plain-archive``: a plain page with its source archive (test/fixtures/documents/source-archive.json),
  whose PDF library serves only the Attach source ZIP to PDF action.

and two harness variants, so what a library costs a page that does not use it is a direct difference:

- ``plain+libraries``: ``plain`` with all three libraries embedded as the renderer embeds them, inert
  runtime scripts the bootstrap evaluates (artifact-data.js);
- ``plain-archive-stripped``: ``plain-archive`` without the PDF library (its door stays).

Each page opens ``--runs`` times, each in a fresh context, in Playwright's iPhone 13 emulation with
CDP ``Emulation.setCPUThrottlingRate`` 4. Every time is read from the page's own clock (origin:
navigation start) and its own performance entries; the script sets no mark and adds no script:

- FCP: the ``first-contentful-paint`` paint entry;
- interactive: the end of the last ``obs-startup start <script>`` measure, the moment the bootstrap
  has evaluated every runtime script and, in the same task, lifts the shell's ``inert`` and sends
  ``obs-html-interactive``, so the page answers input;
- first chapter: the ``obs-startup first chapter painted`` mark;
- ready: the ``obs-startup ready`` mark (``obs-html-ready``: the deferred startup work done);
- per library: the duration of ``obs-startup start <element id>``, its evaluation on the throttled
  main thread, in CPU-ms;
- script: CDP ``Performance.getMetrics`` ScriptDuration at ready, every script's CPU-ms.

It prints the medians as a Markdown table and writes it and every run's numbers to DIRECTORY
(default ``data/data_output/library-cost``, ignored).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from obs_html import cli, libraries
from obs_html.artifact_data import prepare_artifact_scripts
from obs_html.pdf import _executable

ADAPTER = Path(__file__).resolve().parents[2]
ROOT = ADAPTER.parents[1]
DOCUMENTS = ADAPTER / "test" / "fixtures" / "documents"
DECK = ADAPTER / "test" / "fixtures" / "phone-deck"
LIBRARY_ELEMENTS = {key: library.element for key, library in libraries.LIBRARIES.items()}
DEVICE = "iPhone 13"
THROTTLING = 4
COLUMNS = ("fcp", "first chapter", "interactive", "ready", "script", *LIBRARY_ELEMENTS)


def build(folder: Path) -> dict[str, Path]:
    """Every page and variant, built into ``folder``."""
    deck = folder / "deck-vault"
    shutil.copytree(DECK, deck)
    manifest = deck / "manifest.md"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        "---\n", "---\nobsHtml: {layout: screens}\n", 1), encoding="utf-8")
    subprocess.run([sys.executable, "-m", "obs.document", "--source", str(manifest),
                    "--document", str(folder / "deck.json")], check=True)
    sources = {"deck": folder / "deck.json", "report": DOCUMENTS / "figures.json",
               "plain": DOCUMENTS / "structural.json", "plain-archive": DOCUMENTS / "source-archive.json"}
    pages = {}
    for name, document in sources.items():
        pages[name] = folder / f"{name}.html"
        if cli.main([str(document), str(pages[name])]) != 0:
            raise SystemExit(f"library_cost.py: obs-html could not build {document}")
    plain = pages["plain"].read_text(encoding="utf-8")
    assert not any(f'id="{element}"' in plain for element in LIBRARY_ELEMENTS.values()), "plain embeds a library"
    for anchor, keys in (('<script id="artifact-script"', ("pdf",)),  # where render.py places each
                         ('<script id="pages-script"', ("plotting", "maths"))):
        embedded = prepare_artifact_scripts("".join(libraries.element(key) for key in keys))
        plain = plain.replace(anchor, embedded + anchor, 1)
    assert all(plain.count(f'id="{element}"') == 1 for element in LIBRARY_ELEMENTS.values())
    pages["plain+libraries"] = folder / "plain+libraries.html"
    pages["plain+libraries"].write_text(plain, encoding="utf-8")
    archive = pages["plain-archive"].read_text(encoding="utf-8")
    stripped, count = re.subn(r'<script id="pdf-library-script"[^>]*>.*?</script>', "", archive, flags=re.S)
    assert count == 1, "plain-archive embeds no PDF library"
    pages["plain-archive-stripped"] = folder / "plain-archive-stripped.html"
    pages["plain-archive-stripped"].write_text(stripped, encoding="utf-8")
    return pages


READ = """() => {
    const measures = performance.getEntriesByType("measure");
    const mark = (name) => performance.getEntriesByName(name, "mark")[0]?.startTime ?? null;
    const starts = measures.filter((entry) => entry.name.startsWith("obs-startup start "));
    const library = Object.fromEntries(starts.map((entry) => [entry.name.slice(18), entry.duration]));
    return {
        fcp: performance.getEntriesByName("first-contentful-paint")[0]?.startTime ?? null,
        interactive: Math.max(...starts.map((entry) => entry.startTime + entry.duration)),
        "first chapter": mark("obs-startup first chapter painted"),
        ready: mark("obs-startup ready"),
        library,
    };
}"""


def measure(browser, playwright, page_path: Path) -> dict[str, float | None]:
    """One run of ``page_path``: its timings in ms."""
    context = browser.new_context(**playwright.devices[DEVICE])
    try:
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        session = context.new_cdp_session(page)
        session.send("Emulation.setCPUThrottlingRate", {"rate": THROTTLING})
        session.send("Performance.enable")
        page.goto(page_path.as_uri())
        page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready' && "
                               "performance.getEntriesByName('obs-startup first chapter painted').length > 0",
                               timeout=120_000)
        found = page.evaluate(READ)
        metrics = {metric["name"]: metric["value"] for metric in session.send("Performance.getMetrics")["metrics"]}
        if errors:
            raise SystemExit(f"library_cost.py: {page_path.name} raised {errors}")
        library = found.pop("library")
        found["script"] = metrics["ScriptDuration"] * 1000
        for key, element in LIBRARY_ELEMENTS.items():
            found[key] = library.get(element)
        return found
    finally:
        context.close()


def median(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return statistics.median(present) if present else None


def table(medians: dict[str, dict[str, float | None]], runs: int) -> str:
    head = ("page", *COLUMNS)
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for name, row in medians.items():
        lines.append(f"| {name} | " + " | ".join("–" if row[column] is None else f"{row[column]:.0f}"
                                                 for column in COLUMNS) + " |")
    return (f"Medians of {runs} runs, ms on the page's clock ({DEVICE}, CPU throttling {THROTTLING}×; "
            "library columns: CPU-ms evaluating it; – where the page embeds none).\n\n" + "\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "data_output" / "library-cost")
    arguments = parser.parse_args(argv)
    arguments.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        pages = build(Path(scratch))
        sizes = {name: path.stat().st_size for name, path in pages.items()}
        runs: dict[str, list[dict]] = {name: [] for name in pages}
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=_executable())
            try:
                for _ in range(arguments.runs):  # interleaved, so a slow moment hits every page alike
                    for name, path in pages.items():
                        runs[name].append(measure(browser, playwright, path))
            finally:
                browser.close()
    medians = {name: {column: median([run[column] for run in found]) for column in COLUMNS}
               for name, found in runs.items()}
    report = table(medians, arguments.runs)
    (arguments.output / "library-cost.md").write_text(report, encoding="utf-8")
    (arguments.output / "library-cost.json").write_text(json.dumps(
        {"device": DEVICE, "throttling": THROTTLING, "bytes": sizes, "runs": runs, "medians": medians},
        indent=2, sort_keys=True), encoding="utf-8")
    print(report)
    print("bytes: " + ", ".join(f"{name} {size}" for name, size in sizes.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
