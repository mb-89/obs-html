"""The chapter sweep: open every chapter of a built artifact and scroll through it, in a process of its own.

Reader: a test that checks every chapter of an artifact opens and settles, and whoever compares
an artifact's screenshots before and after a change that should not change what it shows.

A ``Sweeper`` starts this file as a child process, which launches its own headless shell
(test/conftest.py, ``headless_shell``) and sweeps the artifacts it is sent one after another,
keeping its browser. The child opens
an artifact at each viewport (VIEWPORTS: a desktop and a phone) without and with
``prefers-reduced-motion: reduce`` (MOTIONS), each pair in a browser context of its own. For each chapter of
``obsArtifact.navigationChapters()`` it calls ``activateChapter``, awaits ``whenChapterReady()``
and scrolls the chapter scroller (``[data-chapter-scroll]``) one viewport at a time, waiting two
animation frames per step. Each console error and uncaught page error is reported. The child
prints one JSON line per step, so where the page's main thread locks and no Playwright call
returns, the parent's hard timeout ends the child's process tree and names the chapter, step,
viewport and motion preference it was on; the next sweep starts a fresh child. A hang in one
artifact therefore cannot outlast its timeout or touch another test's browser. The child also says
how long each page took to open, from its new browser context to its chapter list; with ``stall``,
a step after that which runs past ``stall`` times that time ends the child the same way, so a
locked page fails at a bound that a busy host stretches as it stretches the opening. obs quality.md, Testing boundaries, owns why the sweep does not lease the pool's pages.

With ``screenshots``, each step is saved as ``<folder>/<viewport>/<motion>/<NN>-<chapter>-<step>.png``;
``compare`` counts the pixels that differ between two such folders. From the adapter's folder:

    uv run python test/chapter_sweep.py <artifact.html>... --screenshots <folder> [--compare <before>]
"""
import argparse
import dataclasses
import functools
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# The emulated motion preferences the sweep opens an artifact with: none, and reduced motion.
MOTIONS = ("no-preference", "reduce")
# The viewports the sweep opens an artifact at, by name: each one's size and whether it is a phone,
# whose context is the phone pool's (test/conftest.py, PHONE_CONTEXT) at device scale 1
# (PHONE_SCALE). The phone is an iPhone 13's.
VIEWPORTS = {
    "desktop": ({"width": 1280, "height": 720}, False),
    "phone": ({"width": 390, "height": 844}, True),
}
# The sweep's phone draws at device scale 1, not the phone pool's 3: it looks for a page that
# stops answering and for console errors, not at pixels a person reads, and three times the
# scale draws nine times the pixels on every scroll step.
PHONE_SCALE = 1
# The multiple of a page's own opening time a sweep with a stall bound lets one step after it take.
STALL = 10
# How the child marks its output lines from anything else on its stdout.
LINE = "chapter-sweep "
# Resolves once the artifact has started, at once if it has; rejects on a failed startup.
READY = """() => new Promise((resolve, reject) => {
    if (document.documentElement.dataset.artifactStatus === "ready") return resolve();
    document.addEventListener("obs-html-ready", () => resolve(), {once: true});
    globalThis.obsHtmlReady?.catch((error) => reject(new Error(String(error))));
})"""
# Opens a chapter and waits until the reader says it is ready; returns the scroller's step count.
OPEN = """async (slug) => {
    await obsArtifact.activateChapter(slug);
    await obsArtifact.whenChapterReady();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const scroller = document.querySelector("[data-chapter-scroll]");
    return scroller ? Math.max(1, Math.ceil(scroller.scrollHeight / Math.max(1, scroller.clientHeight))) : 1;
}"""
# Scrolls the chapter scroller to its step-th viewport and lets two frames run.
SCROLL = """async (step) => {
    const scroller = document.querySelector("[data-chapter-scroll]");
    if (scroller) scroller.scrollTop = step * scroller.clientHeight;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}"""


@dataclasses.dataclass
class Swept:
    """What one sweep of an artifact saw: the chapters it finished and the errors the page reported,
    by (viewport, motion preference), and, where it did not finish, why and the step it was on."""
    artifact: Path
    chapters: dict[tuple[str, str], list[str]]
    errors: list[tuple[str, str, str]]
    failure: str | None

    def problems(self) -> list[str]:
        """Each thing that fails the sweep, as a message naming the artifact, the viewport and the
        motion preference."""
        where = f"test/chapter_sweep.py: {self.artifact.name}"
        found = [f"{where}: {self.failure}"] if self.failure else []
        return found + [f"{where} ({viewport}, prefers-reduced-motion: {motion}): console error: {error}"
                        for viewport, motion, error in self.errors]


class Sweeper:
    """A child process that sweeps artifacts one after another, launched at its first sweep and
    kept for the next: each sweep after the first starts no process and no browser.

    A sweep still running after its ``timeout`` ends the child with every process it started,
    and the next sweep starts a fresh child; so does a sweep the child could not finish, and, with
    ``stall``, one whose step after a page opened took ``stall`` times that page's opening time."""

    def __init__(self):
        self._process = None
        self._lines = None

    def sweep(self, artifact: Path, timeout: float, motions=MOTIONS, screenshots: Path | None = None,
              viewports=tuple(VIEWPORTS), stall: float | None = None) -> Swept:
        """Sweep ``artifact`` at each of ``viewports`` with each of ``motions``, in the child, within
        ``timeout`` seconds and, with ``stall``, each step after a page opened within ``stall`` times
        the seconds that page took to open."""
        import queue

        if self._process is None:
            self._start()
        job = {"artifact": str(Path(artifact).resolve()), "motions": list(motions), "viewports": list(viewports),
               "screenshots": str(screenshots) if screenshots else None}
        self._process.stdin.write(json.dumps(job) + "\n")
        self._process.stdin.flush()
        lines, timed_out, ended = [], False, False
        deadline = time.monotonic() + timeout
        # The current page's opening time and its step's deadline, once the page has opened.
        opening, step_deadline = None, None
        while True:
            until = deadline if step_deadline is None else min(deadline, step_deadline)
            try:
                line = self._lines.get(timeout=max(0.0, until - time.monotonic()))
            except queue.Empty:
                timed_out = True
                break
            if line is None:
                ended = True
                break
            lines.append(line)
            if "opening" in line:
                opening, step_deadline = None, None
            elif "opened" in line:
                opening = line["opened"]
            if stall is not None and opening is not None:
                step_deadline = time.monotonic() + stall * opening
            if "finished" in line:
                break
        returncode, error_output = None, ""
        if timed_out or ended:
            returncode, error_output = self._stop()
        chapters = {(viewport, motion): [line["done"] for line in lines if "done" in line
                                         and (line["viewport"], line["motion"]) == (viewport, motion)]
                    for viewport in viewports for motion in motions}
        errors = [(line["viewport"], line["motion"], line["error"]) for line in lines if "error" in line]
        at = next((line for line in reversed(lines) if "at" in line), None)
        place = (f"chapter {at['at']!r} ({at['viewport']}, prefers-reduced-motion: {at['motion']}), {at['doing']}"
                 if at else "opening the artifact")
        failure = None
        remedy = ("A loop or wait on the page's main thread never ended there. Remedy: open that chapter with the "
                  "same motion preference and pause the page in DevTools (CDP Debugger.pause) to see the stack")
        if timed_out and step_deadline is not None and step_deadline < deadline:
            failure = (f"the page stopped answering at {place}: no answer within {stall:g} times the page's opening "
                       f"time of {opening:.2f} s. {remedy}")
        elif timed_out:
            failure = f"did not finish within {timeout:g} s; the page stopped answering at {place}. {remedy}"
        elif ended:
            failure = (f"the sweep stopped at {place} (exit code {returncode}): "
                       f"{error_output.strip().splitlines()[-1] if error_output.strip() else 'no message'}")
        return Swept(Path(artifact), chapters, errors, failure)

    def close(self) -> None:
        """End the child, if one runs; it closes its browser as its input ends."""
        if self._process is not None:
            self._process.stdin.close()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            self._stop()

    def _start(self) -> None:
        import queue
        import threading

        options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
                   else {"start_new_session": True})
        self._errors = tempfile.TemporaryFile("w+", encoding="utf-8")
        self._process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child"],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._errors,
                                         text=True, encoding="utf-8", **options)
        self._lines = queue.Queue()

        def read(stdout, lines):
            for line in stdout:
                if line.startswith(LINE):
                    lines.put(json.loads(line[len(LINE):]))
            lines.put(None)
        threading.Thread(target=read, args=(self._process.stdout, self._lines), daemon=True).start()

    def _stop(self) -> tuple[int | None, str]:
        """End the child's process tree; its exit code and what it wrote to its standard error."""
        process, self._process = self._process, None
        _end_tree(process)
        returncode = process.wait()
        self._errors.seek(0)
        error_output = self._errors.read()
        self._errors.close()
        return returncode, error_output


def _end_tree(process: subprocess.Popen) -> None:
    """End the child and every process it started (its browser), without asking any of them."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _say(**fields) -> None:
    print(LINE + json.dumps(fields), flush=True)


def child() -> None:
    """The child's sweeps: one headless shell; for each job read from standard input (Sweeper),
    a page per (viewport, motion preference), every chapter, a line per step (``_say``)."""
    from playwright.sync_api import sync_playwright

    import conftest

    with sync_playwright() as playwright:
        browser = conftest.launcher(playwright, conftest.HEADLESS_SHELL_ENGINE,
                                    conftest.headless_shell(conftest.suite.playwright_browsers()))()
        for line in sys.stdin:
            job = json.loads(line)
            screenshots = Path(job["screenshots"]) if job["screenshots"] else None
            for name in job["viewports"]:
                size, phone = VIEWPORTS[name]
                context = {**conftest.PHONE_CONTEXT, "device_scale_factor": PHONE_SCALE} if phone else {}
                for motion in job["motions"]:
                    _say(opening=True, viewport=name, motion=motion)
                    started = time.monotonic()
                    _sweep_page(browser.new_context(reduced_motion=motion, viewport=size, **context).new_page(),
                                Path(job["artifact"]), name, motion, screenshots, started)
            _say(finished=True)
        browser.close()


def _sweep_page(page, artifact: Path, viewport: str, motion: str, screenshots: Path | None, started: float) -> None:
    """Open ``artifact`` in ``page`` and open and scroll each of its chapters, saying each step and,
    once its chapters are listed, the seconds since ``started`` (before its context was made) it took to open."""
    say = functools.partial(_say, viewport=viewport, motion=motion)
    page.on("console", lambda message: message.type == "error" and say(error=message.text))
    page.on("pageerror", lambda error: say(error=str(error)))
    page.goto(artifact.resolve().as_uri())
    page.evaluate(READY)
    slugs = [chapter["slug"] for chapter in page.evaluate("obsArtifact.navigationChapters()")]
    say(opened=time.monotonic() - started)
    for number, slug in enumerate(slugs, 1):
        say(at=slug, doing="opening it")
        steps = page.evaluate(OPEN, slug)
        for step in range(steps):
            say(at=slug, doing=f"scrolling to step {step + 1} of {steps}")
            page.evaluate(SCROLL, step)
            if screenshots:
                folder = screenshots / viewport / motion
                folder.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=folder / f"{number:02d}-{slug}-{step}.png", animations="disabled",
                                caret="hide")
        say(done=slug)
    page.context.close()


def compare(before: Path, after: Path) -> dict[str, int | None]:
    """For each screenshot in either folder, by its path below it, the number of differing pixels;
    None where only one folder holds it or the sizes differ."""
    from PIL import Image, ImageChops

    names = {path.relative_to(folder).as_posix() for folder in (before, after) for path in folder.rglob("*.png")}
    counts = {}
    for name in sorted(names):
        if not (before / name).is_file() or not (after / name).is_file():
            counts[name] = None
            continue
        with Image.open(before / name) as old, Image.open(after / name) as new:
            if old.size != new.size:
                counts[name] = None
                continue
            difference = ImageChops.difference(old.convert("RGB"), new.convert("RGB")).convert("L")
            counts[name] = sum(difference.point(lambda value: 255 if value else 0).histogram()[255:])
    return counts


def main(arguments: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("artifacts", nargs="*", type=Path)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--motion", choices=MOTIONS, action="append",
                        help="the motion preference to sweep with; both where none is named")
    parser.add_argument("--viewport", choices=VIEWPORTS, action="append",
                        help="the viewport to sweep at; each where none is named")
    parser.add_argument("--timeout", type=float, default=120, help="seconds one artifact's sweep may take")
    parser.add_argument("--screenshots", type=Path, help="save each step's screenshot below this folder")
    parser.add_argument("--compare", type=Path, help="count differing pixels against this earlier --screenshots folder")
    options = parser.parse_args(arguments)
    viewports = options.viewport or list(VIEWPORTS)
    motions = options.motion or list(MOTIONS)
    if options.child:
        child()
        return 0
    if not options.artifacts:
        parser.error("name at least one artifact")
    if options.compare and not options.screenshots:
        parser.error("--compare needs --screenshots")
    problems = []
    sweeper = Sweeper()
    try:
        for artifact in options.artifacts:
            folder = options.screenshots / artifact.stem if options.screenshots else None
            swept = sweeper.sweep(artifact, options.timeout, motions, folder, viewports)
            problems += swept.problems()
            print(f"{artifact.name}: " + ", ".join(f"{viewport} {motion} {len(done)} chapters"
                                                    for (viewport, motion), done in swept.chapters.items())
                  + (", failed" if swept.problems() else ""))
    finally:
        sweeper.close()
    if options.compare:
        counts = compare(options.compare, options.screenshots)
        differing = {name: count for name, count in counts.items() if count != 0}
        for name, count in differing.items():
            print(f"{name}: {'missing or resized' if count is None else f'{count} pixels differ'}")
        print(f"compared {len(counts)} screenshots, {len(differing)} differ")
        problems += ["screenshots differ"] if differing else []
    print("\n".join(problems), file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
