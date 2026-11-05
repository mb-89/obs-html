"""Parity gate: this adapter's artifact against the interim reference, in Claude-preview-like frames.

Until obs removes its interim adapter, obs's spec is built both ways: the Document from the
core of this repository rendered by this adapter, and the same spec sources rendered by the
interim adapter in the same tree (`obs-html-interim`). One interaction script then runs against both
artifacts in both preview-like frames (test/preview.py): Home, previous/next by pointer and
keyboard, the contents menu, the filter, and icon counts per region in every chapter. Any
difference fails and names the step and both observations.

KNOWN_DIFFERENCES lists the differences that are accepted for now, each with its reason. It only
shrinks: a listed step that no longer differs fails too, so its entry is removed with the fix.
Where the reference itself is wrong by obs's design notes, the step is checked against the notes
for this adapter alone: Home by pointer (the reference's arrow area covers Home) and the filter
(the reference marks the HTML changed).

A second check sweeps both artifacts in the same frames for covered controls
(test/browser/control-coverage.js) at four widths, in both views and with the bars open and
closed. It holds this adapter to the design notes alone: a covered control fails, and the failure
says where the reference has the same fault, which is not a parity difference.

Run it alone with `uv run pytest test/test_parity_browser.py`; it builds the artifacts once per
session.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import CORE_ROOT
from obs_html.cli import main as obs_html
from preview import SANDBOXES, http_origin, open_preview

# step -> why this adapter may still differ from the interim reference there.
KNOWN_DIFFERENCES: dict[str, str] = {}

FILTER = "file.name == 'nothing'"

ICONS = """() => {
    const regions = {};
    const region = (element) => {
        const bar = element.closest("[data-bar]");
        if (bar) return `bar ${bar.dataset.bar}`;
        // The notice center is newer than the interim reference; its own tests own its icons.
        if (element.closest("[data-header-notices]")) return null;
        if (element.closest("[data-bars-menu]")) return "bars menu";
        if (element.closest(".chapter-nav-zone")) return "chapter arrows";
        if (element.closest(".chapter-breadcrumbs")) return "breadcrumbs";
        if (!element.closest("[data-chapter-body]")) return "toolbar";
        if (element.closest("table")) return "tables";
        if (element.closest("[class*=mark]")) return "mark rails";
        if (element.closest("[class*=card]")) return "cards";
        return "prose";
    };
    const painted = (element) => {
        const image = element.querySelector("img");
        if (!image) return element.textContent.trim() !== "";
        const masked = !element.classList.contains("resource-icon--monochrome") ||
            getComputedStyle(element).maskImage.includes("url(");
        return image.complete && image.naturalWidth > 0 && masked;
    };
    for (const icon of document.querySelectorAll(".resource-icon")) {
        const name = region(icon);
        if (!name) continue;
        const counts = regions[name] ||= {icons: 0, painted: 0};
        counts.icons += 1;
        if (painted(icon)) counts.painted += 1;
    }
    return Object.fromEntries(Object.entries(regions).sort());
}"""

POINTER = """(element) => {
    element.scrollIntoView({block: "nearest"});
    const box = element.getBoundingClientRect();
    const x = box.x + box.width / 2, y = box.y + box.height / 2;
    const top = document.elementFromPoint(x, y);
    const owner = top && !element.contains(top)
        ? (top.closest("[data-step], [data-bar], button, a, summary") || top) : null;
    return {x, y, covered: owner ? (owner.getAttribute("aria-label") || owner.className || owner.tagName) : ""};
}"""


def run(command: list[str], cwd: Path, what: str) -> None:
    """Run a build step; on failure name the step, its command and its output."""
    environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    result = subprocess.run(command, cwd=cwd, env=environment, text=True, encoding="utf-8",
                            capture_output=True, timeout=900)
    if result.returncode:
        pytest.fail(f"test/test_parity_browser.py: {what} failed: {' '.join(command)} (in {cwd})\n"
                    f"{result.stdout[-2000:]}{result.stderr[-2000:]}", pytrace=False)


def require_reference(core: Path) -> Path:
    """obs still carries the interim adapter; once obs removes it, this gate goes too."""
    if not (core / "src" / "obs_html_interim" / "cli.py").is_file():
        pytest.fail(
            f"test/test_parity_browser.py: interim reference not found, no "
            f"{core / 'src' / 'obs_html_interim' / 'cli.py'}. obs no longer carries the interim "
            "adapter; remedy: remove this parity gate and its line in AGENTS.md.",
            pytrace=False,
        )
    return core


@pytest.fixture(scope="session")
def parity_artifacts(tmp_path_factory) -> dict[str, str]:
    """obs's spec built by this adapter and by the interim reference."""
    core = CORE_ROOT
    reference = require_reference(core)
    uv = shutil.which("uv")
    if not uv:
        pytest.fail("test/test_parity_browser.py: uv not found on PATH. Remedy: install uv "
                    "(https://docs.astral.sh/uv/).", pytrace=False)
    folder = tmp_path_factory.mktemp("parity")
    capabilities, document = folder / "capabilities.json", folder / "spec.json"
    run([uv, "run", "--project", str(core), "python", "-m", "obs.capabilities",
         "--notes", str(core / "spec" / "capabilities"), "--output", str(capabilities)],
        core, "building the capability reference with the core")
    run([uv, "run", "--project", str(core), "obs-document", "--document", str(document),
         "--source", str(core / "spec" / "manifest.md"), "--capability-reference", str(capabilities)],
        core, "building obs's spec Document with the core")
    adapter = folder / "adapter.html"
    assert obs_html([str(document), str(adapter), "--execute-commands",
                     "--command-root", str(core / "spec")]) == 0, \
        "test/test_parity_browser.py: obs-html could not render obs's spec Document"
    interim = folder / "reference.html"
    run([uv, "run", "--project", str(reference), "obs-html-interim", "--source", str(core / "spec"),
         "--output", str(interim), "--execute-commands"],
        reference, "rendering obs's spec with the interim reference")
    return {"adapter": adapter.read_text(encoding="utf-8"),
            "reference": interim.read_text(encoding="utf-8")}


def interact(page, frame) -> tuple[list[tuple[str, object]], list[str]]:
    """The interaction script: ordered (step, observation) pairs, and design-note violations."""
    from playwright.sync_api import expect

    steps: list[tuple[str, object]] = []
    violations: list[str] = []
    root = frame.locator("html")
    chapter = lambda: frame.locator("[data-active-chapter]").get_attribute("data-chapter")
    settle = lambda: page.wait_for_timeout(250)

    def pointer(selector: str) -> str:
        """Click where the element is shown; report what covers it, if anything."""
        element = frame.locator(selector).first
        spot = element.evaluate(POINTER)
        box = page.locator("#artifact").bounding_box()
        page.mouse.click(box["x"] + spot["x"], box["y"] + spot["y"])
        settle()
        return f"covered by {spot['covered']}, then {chapter()}" if spot["covered"] else chapter()

    def visible(selector: str) -> bool:
        return frame.locator(selector).first.is_visible()

    def changed() -> bool:
        """The changed-HTML notice, in this adapter's notice center or the reference's banner."""
        return frame.locator('[data-notice="changed-html"]').count() > 0 or visible("[data-artifact-warning]")

    steps.append(("start", chapter()))
    steps.append(("icons on start", root.evaluate(ICONS)))
    for count in range(1, 5):
        steps.append((f"next {count} by pointer", pointer('[data-step="1"] .chapter-nav-icon')))
    for count in range(1, 3):
        steps.append((f"previous {count} by pointer", pointer('[data-step="-1"] .chapter-nav-icon')))
    frame.locator("[data-chapter-scroll]").focus()
    for count, key in enumerate(["ArrowRight", "ArrowRight", "ArrowLeft"], 1):
        page.keyboard.press(key)
        settle()
        steps.append((f"key {count} {key}", chapter()))
    for count in range(1, 4):
        for _ in range(count):
            pointer('[data-step="1"] .chapter-nav-icon')
        origin = chapter()
        frame.locator(".chapter-home-link").first.focus()
        page.keyboard.press("Enter")
        settle()
        steps.append((f"Home by keyboard from {origin}", chapter()))
    for count in range(1, 4):
        for _ in range(count):
            pointer('[data-step="1"] .chapter-nav-icon')
        origin = chapter()
        home = pointer(".chapter-home-link")
        if home != "home":
            violations.append(f"Home by pointer from {origin}: {home}, not home")
    frame.locator(".chapter-home-link").first.focus()
    page.keyboard.press("Enter")
    settle()
    steps.append(("Home by keyboard after the pointer checks", chapter()))
    menu = pointer("[data-menu-button]")
    steps.append(("menu button by pointer", (menu, visible("[data-bars-menu]"))))
    steps.append(("contents dock by pointer", pointer('[data-dock-bar="toc"]')))
    steps.append(("contents shown", visible('[data-bar="toc"]')))
    links = frame.locator("[data-toc-tree] a")
    for index in (1, 3, 5):
        href = links.nth(index).get_attribute("href")
        steps.append((f"contents link {href} by pointer", pointer(f'[data-toc-tree] a[href="{href}"]')))
    frame.locator(".chapter-home-link").first.focus()
    page.keyboard.press("Enter")
    settle()
    steps.append(("Home by keyboard from the contents", chapter()))
    steps.append(("icons with the contents open", root.evaluate(ICONS)))

    root.evaluate("() => globalThis.obsArtifact.openBar('filter')")
    frame.locator("[data-filter-input]").fill(FILTER)
    settle()
    expect(frame.locator('[data-filter-status]')).not_to_have_text(re.compile(r"^All "))
    steps.append(("filter applied", (
        frame.locator("[data-filter-status]").inner_text(), [
            button.is_disabled() for button in frame.locator("[data-step]").all()])))
    if changed():
        violations.append("applying a filter showed the changed-HTML notice")
    root.evaluate("() => globalThis.obsFilter.setExpression('')")
    settle()
    steps.append(("filter cleared", (frame.locator("[data-filter-status]").inner_text(), chapter())))
    if changed():
        violations.append("clearing a filter showed the changed-HTML notice")

    slugs = root.evaluate("""() => [...document.querySelectorAll("[data-toc-tree] a")]
        .map((link) => link.getAttribute("href").slice(1)).filter((slug) => !slug.includes("/"))""")
    for slug in slugs:
        frame.locator(f'[data-toc-tree] a[href="#{slug}"]').first.dispatch_event("click")
        expect(frame.locator("[data-active-chapter]")).to_have_attribute("data-chapter", slug)
        settle()
        steps.append((f"icons in {slug}", root.evaluate(ICONS)))
    return steps, violations


def observe(tmp_path: Path, reader_browser, artifact: str, frame_kind: str, name: str):
    errors: list[str] = []
    folder = tmp_path / name
    folder.mkdir()
    with http_origin(folder) as origin:
        page, frame = open_preview(folder, reader_browser, errors, artifact, frame_kind,
                                   origin if frame_kind == "same-origin" else None)
        try:
            steps, violations = interact(page, frame)
        finally:
            page.close()
    return steps, violations, errors


@pytest.mark.browser
@pytest.mark.parametrize("frame_kind", SANDBOXES)
def test_the_artifact_behaves_as_the_interim_reference_in_preview_frames(
        tmp_path: Path, reader_browser, parity_artifacts: dict[str, str], frame_kind: str) -> None:
    adapter, violations, errors = observe(tmp_path, reader_browser, parity_artifacts["adapter"],
                                          frame_kind, "adapter")
    reference, _reference_violations, _reference_errors = observe(
        tmp_path, reader_browser, parity_artifacts["reference"], frame_kind, "reference")
    assert [step for step, _ in adapter] == [step for step, _ in reference], (
        "test/test_parity_browser.py: the script took different steps; first steps differ at "
        + next((f"{a!r} / {r!r}" for (a, _), (r, _) in zip(adapter, reference) if a != r), "the end"))
    problems = []
    for (step, ours), (_, theirs) in zip(adapter, reference):
        differs = json.dumps(ours, sort_keys=True) != json.dumps(theirs, sort_keys=True)
        if differs and step not in KNOWN_DIFFERENCES:
            if isinstance(ours, dict) and isinstance(theirs, dict):
                keys = sorted(key for key in ours.keys() | theirs.keys() if ours.get(key) != theirs.get(key))
                ours, theirs = ({key: side.get(key) for key in keys} for side in (ours, theirs))
            problems.append(f"{step}: this adapter observed {ours!r}; the interim reference observed {theirs!r}")
        if not differs and step in KNOWN_DIFFERENCES:
            problems.append(f"{step}: no longer differs; remove it from KNOWN_DIFFERENCES")
    problems += [f"design notes: {violation}" for violation in violations]
    problems += [f"page error: {error}" for error in errors]
    assert not problems, f"Parity gate, {frame_kind} frame:\n" + "\n".join(problems)


COVERAGE = Path(__file__).parent / "browser" / "control-coverage.js"
WIDTHS = (360, 700, 1100, 1600)
VIEWS = ("pages", "continuous")


@pytest.fixture(scope="module")
def coverage_browser():
    """Chromium with overlay scrollbars, as on touch devices and macOS: scrollbars take no room,
    so the reader's clearance for the chapter arrows is at its narrowest."""
    from obs_html.pdf import _executable
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=_executable(),
                                             args=["--enable-features=OverlayScrollbar"])
        try:
            yield browser
        finally:
            browser.close()


def layout_name(layout: list[str] | None) -> str:
    return f"the {layout[0]} bar docked {layout[1]}" if layout else "no bar open"


def covered_controls(tmp_path: Path, browser, artifact: str, frame_kind: str,
                     name: str) -> dict[tuple[str, str], dict[str, list[str]]]:
    """Every covered control at every width, view and bar layout, in one preview frame.

    Maps each fault, (control, "at <width>px in the <view> view with <layout>"), to what covers
    it and the chapters where it does; a page error is a fault too.
    """
    errors: list[str] = []
    folder = tmp_path / name
    folder.mkdir()
    faults: dict[tuple[str, str], dict[str, list[str]]] = {}
    with http_origin(folder) as origin:
        page, frame = open_preview(folder, browser, errors, artifact, frame_kind,
                                   origin if frame_kind == "same-origin" else None)
        try:
            page.set_viewport_size({"width": max(WIDTHS) + 100, "height": 800})
            root = frame.locator("html")
            bars = root.evaluate("""() => [...new Set([...document.querySelectorAll("[data-dock-bar]")]
                .map((button) => button.dataset.dockBar))]""")
            # On every chapter: no bar, the Filter bar in each dock direction (bars of one side
            # shape the reader alike) and the Comments bar, whose review mode reshapes the reader.
            # Every other bar on its default side, on the first chapter.
            docked = "filter" if "filter" in bars else bars[0]
            layouts = [None, *([docked, side] for side in ("right", "left", "top", "bottom")),
                       *([bar, "right"] for bar in bars if bar == "comments")]
            first = [[bar, "right"] for bar in bars if [bar, "right"] not in layouts]
            for width in WIDTHS:
                page.evaluate("width => document.getElementById('artifact').style.width = width", f"{width}px")
                results = root.evaluate(COVERAGE.read_text(encoding="utf-8"),
                                        {"views": list(VIEWS), "layouts": layouts, "firstChapterLayouts": first})
                for result in results:
                    for fault in result["faults"]:
                        where = f"at {width}px in the {result['view']} view with {layout_name(result['layout'])}"
                        faults.setdefault((fault["control"], where), {}).setdefault(
                            fault["covering"], []).append(result["chapter"])
        finally:
            page.close()
    for error in errors:
        faults.setdefault(("page error", error), {})
    return faults


@pytest.mark.browser
@pytest.mark.parametrize("frame_kind", SANDBOXES)
def test_no_control_is_covered_in_preview_frames(
        tmp_path: Path, coverage_browser, parity_artifacts: dict[str, str], frame_kind: str) -> None:
    """No visible control lies under another element's pointer area (test/browser/control-coverage.js).

    The interim reference is swept in the same frames. Its faults are not parity differences:
    where this adapter shares one, the failure says so.
    """
    ours = covered_controls(tmp_path, coverage_browser, parity_artifacts["adapter"], frame_kind, "adapter")
    theirs = covered_controls(tmp_path, coverage_browser, parity_artifacts["reference"], frame_kind, "reference")
    problems = [
        (f"page error: {where}" if control == "page error" else f"{control} is covered {where} by "
         + "; ".join(f"{covering} (in {', '.join(chapters)})" for covering, chapters in coverings.items()))
        + ("; the interim reference has the same fault" if (control, where) in theirs else "")
        for (control, where), coverings in ours.items()
    ]
    assert not problems, (
        f"test/test_parity_browser.py: controls covered by another element's pointer area, {frame_kind} "
        "frame. Remedy: give the control clearance from what covers it (obs artifact-ui.md, chapter "
        "controls):\n" + "\n".join(problems))
