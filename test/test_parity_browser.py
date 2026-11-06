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

A second check sweeps this adapter's artifact in the same frames for covered controls
(test/browser/control-coverage.js) at four widths, in both views and with the bars open and
closed. It holds this adapter to the design notes alone: a covered control fails, and the failure
says where the reference, swept then in the same frame, has the same fault, which is not a parity
difference.

Each test opens each artifact once, in one page its checks reuse. Pointer and keyboard steps are
real input, one round trip each; every other observation is computed in the page and returned as
one structure (the icon counts of every chapter in one evaluation), and Python compares them.

A third check prints one spec chapter from both artifacts with --print-chapter, in both formats,
and compares them; PRINTED_FORMS and PRINTED_LINES list the accepted differences with their reasons.

Run it alone with `uv run pytest test/test_parity_browser.py`; it builds the artifacts once per
run, without the network: the core's Document through the core's test/offline_obs_document.py.
Each test runs on its own worker in the complete suite: one per frame for the interaction
script and one per frame and pair of widths for the sweep.
"""
import contextlib
import difflib
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from conftest import CORE_ROOT, FAST_FRAMES, built_once
from preview import READY, SANDBOXES, http_origin, load_preview, open_preview
from spec_artifact import run, spec_artifact, uv
from obs_html.cli import main as obs_html

# step -> why this adapter may still differ from the interim reference there.
KNOWN_DIFFERENCES: dict[str, str] = {
    "a view selection marks the HTML changed": (
        "https://github.com/mb-89/obs/issues/148: reader state is never a change "
        "(artifact-ui.md \"What counts as a change\"); the interim reference still marks it changed"),
}

FILTER = "file.name == 'nothing'"

# The page helpers every evaluation below starts with: what each step observes, computed in the
# page and returned as one structure that Python compares.
HELPERS = """
const icons = () => {
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
};
// The active chapter's slug; exactly one chapter is active.
const chapter = () => {
    const active = document.querySelectorAll("[data-active-chapter]");
    if (active.length !== 1) {
        throw new Error(`test/test_parity_browser.py: ${active.length} elements carry data-active-chapter, not one`);
    }
    return active[0].getAttribute("data-chapter");
};
// After an input the artifact has settled once the chapter's deferred content is in, every
// image is decoded and two frames have been drawn; no wall-clock wait.
const settle = async () => {
    await globalThis.obsArtifact.whenChapterReady();
    await Promise.all([...document.images].map((image) => image.decode().catch(() => {})));
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
};
"""

ICONS = "() => {" + HELPERS + "return icons(); }"
# Settles, then returns the active chapter.
SETTLE = "async () => {" + HELPERS + "await settle(); return chapter(); }"
CHAPTER = "() => {" + HELPERS + "return chapter(); }"
# Every top-level chapter opened from the contents in turn, by a click event on its link: once
# the chapter is active (within 5 s, as Playwright's expect waits) and settled, its icon counts.
CHAPTER_ICONS = "async () => {" + HELPERS + """
    const slugs = [...document.querySelectorAll("[data-toc-tree] a")]
        .map((link) => link.getAttribute("href").slice(1)).filter((slug) => !slug.includes("/"));
    const observed = [];
    for (const slug of slugs) {
        const link = document.querySelector(`[data-toc-tree] a[href="#${CSS.escape(slug)}"]`);
        if (!link) throw new Error(`test/test_parity_browser.py: the contents lost the link to ${slug}`);
        link.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true, composed: true}));
        const deadline = performance.now() + 5000;
        while (document.querySelector("[data-active-chapter]")?.getAttribute("data-chapter") !== slug) {
            if (performance.now() > deadline) {
                throw new Error(`test/test_parity_browser.py: chapter ${slug} did not become active ` +
                    `within 5 s of a click on its contents link; active: ${chapter()}`);
            }
            await new Promise((resolve) => requestAnimationFrame(resolve));
        }
        await settle();
        observed.push([slug, icons()]);
    }
    return observed;
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
    """obs's spec built by this adapter (test/spec_artifact.py) and by the interim reference, once per run."""
    core = CORE_ROOT
    reference = require_reference(core)

    def build(folder: Path) -> None:
        # The interim reference builds alongside this adapter's spec artifact.
        with ThreadPoolExecutor(1) as alongside:
            reference_built = alongside.submit(
                run, [uv(), "run", "--offline", "--project", str(reference), "obs-html-interim", "--source",
                      str(core / "spec"), "--output", str(folder / "reference.html"), "--execute-commands"],
                reference, "rendering obs's spec with the interim reference")
            spec_artifact(tmp_path_factory)
            reference_built.result()

    folder = built_once(tmp_path_factory, "parity", build)
    return {"adapter": spec_artifact(tmp_path_factory).read_text(encoding="utf-8"),
            "reference": (folder / "reference.html").read_text(encoding="utf-8")}


def interact(page, frame) -> tuple[list[tuple[str, object]], list[str]]:
    """The interaction script: ordered (step, observation) pairs, and design-note violations."""
    from playwright.sync_api import expect

    steps: list[tuple[str, object]] = []
    violations: list[str] = []
    root = frame.locator("html")
    settle = lambda: root.evaluate(SETTLE)
    chapter = lambda: root.evaluate(CHAPTER)
    # The preview frame stays where open_preview put it: the wrapper page neither scrolls nor reflows.
    box = page.evaluate("document.getElementById('artifact').getBoundingClientRect().toJSON()")

    def pointer(selector: str) -> str:
        """Click where the element is shown; report what covers it, if anything."""
        spot = frame.locator(selector).first.evaluate(POINTER)
        page.mouse.click(box["x"] + spot["x"], box["y"] + spot["y"])
        then = settle()
        return f"covered by {spot['covered']}, then {then}" if spot["covered"] else then

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
        steps.append((f"key {count} {key}", settle()))
    for count in range(1, 4):
        for _ in range(count):
            pointer('[data-step="1"] .chapter-nav-icon')
        origin = chapter()
        frame.locator(".chapter-home-link").first.focus()
        page.keyboard.press("Enter")
        steps.append((f"Home by keyboard from {origin}", settle()))
    for count in range(1, 4):
        for _ in range(count):
            pointer('[data-step="1"] .chapter-nav-icon')
        origin = chapter()
        home = pointer(".chapter-home-link")
        if home != "home":
            violations.append(f"Home by pointer from {origin}: {home}, not home")
    frame.locator(".chapter-home-link").first.focus()
    page.keyboard.press("Enter")
    steps.append(("Home by keyboard after the pointer checks", settle()))
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
    steps.append(("Home by keyboard from the contents", settle()))
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
    root.evaluate("() => globalThis.obsArtifact.setViewSelection('parity', ['a'], ['a', 'b'])")
    settle()
    steps.append(("a view selection marks the HTML changed", changed()))
    root.evaluate("() => globalThis.obsArtifact.setViewSelection('parity', [], ['a', 'b'])")
    settle()

    steps += [(f"icons in {slug}", icons) for slug, icons in root.evaluate(CHAPTER_ICONS)]
    return steps, violations


def observe(tmp_path: Path, reader_browser, artifacts: dict[str, str], frame_kind: str):
    """The interaction script on each artifact, each opened once in its own page.

    Every artifact starts loading at once, so the interim reference's slower startup runs while
    the script runs on this adapter's artifact. Returns, per artifact, its steps, design-note
    violations and page errors.
    """
    observed = {}
    with contextlib.ExitStack() as stack:
        opened = {}
        for name, artifact in artifacts.items():
            folder = tmp_path / name
            folder.mkdir()
            origin = stack.enter_context(http_origin(folder)) if frame_kind == "same-origin" else None
            errors: list[str] = []
            page, frame = load_preview(folder, reader_browser, errors, artifact, frame_kind, origin)
            stack.callback(page.close)
            opened[name] = page, frame, errors
        for name, (page, frame, errors) in opened.items():
            frame.evaluate(READY)
            observed[name] = (*interact(page, frame), errors)
    return observed


@pytest.mark.browser
@pytest.mark.parametrize("frame_kind", [
    pytest.param(frame_kind, marks=pytest.mark.xdist_group(f"parity-{frame_kind}")) for frame_kind in SANDBOXES])
def test_the_artifact_behaves_as_the_interim_reference_in_preview_frames(
        tmp_path: Path, reader_browser, parity_artifacts: dict[str, str], frame_kind: str) -> None:
    observed = observe(tmp_path, reader_browser, parity_artifacts, frame_kind)
    (adapter, violations, errors), (reference, _reference_violations, _reference_errors) = (
        observed["adapter"], observed["reference"])
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
# Swept in pairs, each pair in one opened artifact: opening the spec artifact takes seconds.
WIDTHS = ((360, 700), (1100, 1600))
VIEWS = ("pages", "continuous")


@pytest.fixture(scope="session")
def coverage_browser(worker_playwright):
    """Chromium with overlay scrollbars, as on touch devices and macOS: scrollbars take no room,
    so the reader's clearance for the chapter arrows is at its narrowest."""
    from obs_html.pdf import _executable

    browser = worker_playwright.chromium.launch(executable_path=_executable(),
                                                args=["--enable-features=OverlayScrollbar", *FAST_FRAMES])
    try:
        yield browser
    finally:
        browser.close()


def layout_name(layout: list[str] | None) -> str:
    return f"the {layout[0]} bar docked {layout[1]}" if layout else "no bar open"


def covered_controls(tmp_path: Path, browser, artifact: str, frame_kind: str, name: str,
                     widths: tuple[int, ...]) -> dict[tuple[str, str], dict[str, list[str]]]:
    """Every covered control at the widths, in every view and bar layout, in one preview frame.

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
            page.set_viewport_size({"width": max(width for pair in WIDTHS for width in pair) + 100,
                                    "height": 800})
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
            for width in widths:
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
@pytest.mark.parametrize(("frame_kind", "widths"), [
    pytest.param(frame_kind, widths, id=f"{frame_kind}-{'-'.join(map(str, widths))}",
                 marks=pytest.mark.xdist_group(f"coverage-{frame_kind}-{widths[0]}"))
    for frame_kind in SANDBOXES for widths in WIDTHS])
def test_no_control_is_covered_in_preview_frames(
        tmp_path: Path, coverage_browser, parity_artifacts: dict[str, str], frame_kind: str,
        widths: tuple[int, ...]) -> None:
    """No visible control lies under another element's pointer area (test/browser/control-coverage.js).

    Where this adapter has a fault, the interim reference is swept in the same frame too: its
    faults are not parity differences, and the failure says which ones this adapter shares.
    """
    ours = covered_controls(tmp_path, coverage_browser, parity_artifacts["adapter"], frame_kind, "adapter", widths)
    theirs = covered_controls(tmp_path, coverage_browser, parity_artifacts["reference"], frame_kind,
                              "reference", widths) if ours else {}
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


@pytest.mark.browser
def test_the_sweep_names_a_covered_control_and_what_covers_it(tmp_path: Path, coverage_browser) -> None:
    """The sweep is not vacuous: a control under another element is a fault naming both."""
    from documents import chapter, document, heading, paragraph
    from obs_html.config import load_config
    from obs_html.render import render

    artifact = render(document("Sweep", chapter("one", "One", heading(1, "One"), paragraph("Text."))),
                      load_config())
    errors: list[str] = []
    page, frame = open_preview(tmp_path, coverage_browser, errors, artifact, "null-origin")
    try:
        frame.evaluate("""() => {
            const box = document.querySelector(".chapter-home-link").getBoundingClientRect();
            const cover = document.createElement("div");
            cover.className = "cover";
            cover.setAttribute("aria-label", "Cover");
            Object.assign(cover.style, {position: "fixed", left: `${box.left}px`, top: `${box.top}px`,
                width: `${box.width}px`, height: `${box.height}px`, zIndex: "2147483647"});
            document.body.append(cover);
        }""")
        results = frame.locator("html").evaluate(COVERAGE.read_text(encoding="utf-8"),
                                                 {"views": ["pages"], "layouts": [None], "firstChapterLayouts": []})
    finally:
        page.close()
    faults = {(fault["control"], fault["covering"]) for result in results for fault in result["faults"]}
    assert ('a.chapter-home-link "Home"', 'div.cover "Cover"') in faults, faults
    assert errors == []


@pytest.mark.browser
def test_the_sweep_reaches_a_self_link_whose_lines_lie_on_either_side_of_the_reader(
        tmp_path: Path, coverage_browser) -> None:
    """The fault #251 met in obs's spec, at 360 px with the Comments bar docked right: review mode
    makes the body wider than the reader, and the note's link to itself wraps with its first line
    right of the reader's view and its second left of it. Scrolled to as a whole, it shows neither;
    the sweep then scrolls to one line, as a reader does. The self-link fixture's link is made to
    wrap so, on every open: a spacer and a line break, and a link before it that scrolls the reader
    between the two lines."""
    from obs_html.config import load_config
    from obs_html.render import render

    artifact = render(json.loads((Path(__file__).parent / "fixtures" / "documents" / "self-link.json")
                                 .read_text(encoding="utf-8")), load_config())
    errors: list[str] = []
    page, frame = open_preview(tmp_path, coverage_browser, errors, artifact, "null-origin")
    try:
        page.set_viewport_size({"width": 460, "height": 800})
        page.evaluate("() => document.getElementById('artifact').style.width = '360px'")
        frame.evaluate("""() => {
            const open = obsArtifact.activateChapter;
            obsArtifact.activateChapter = async (...request) => {
                const opened = await open(...request);
                const link = document.querySelector('[data-chapter-body] a.internal-link[href="#long"]');
                if (link) {
                    link.innerHTML = "Lo<br>ng";
                    link.insertAdjacentHTML("beforebegin", '<span style="display:inline-block;width:1200px"></span>');
                    link.closest("p").insertAdjacentHTML("beforebegin",
                        '<p><span style="display:inline-block;width:700px"></span><a href="#short">Short</a></p>');
                }
                return opened;
            };
        }""")
        results = frame.locator("html").evaluate(COVERAGE.read_text(encoding="utf-8"), {
            "views": ["continuous"], "layouts": [["comments", "right"]], "firstChapterLayouts": []})
    finally:
        page.close()
    assert [result["chapter"] for result in results] == ["long", "short"]
    assert [fault for result in results for fault in result["faults"]] == []
    assert errors == []


@pytest.mark.browser
def test_the_sweep_reaches_a_control_an_earlier_scroll_brought_into_view(tmp_path: Path, coverage_browser) -> None:
    """After a scroll the sweep looks again only at controls the scroll can have brought into view;
    one it brought there is still reached where it then stands. Button E, far down the chapter,
    is scrolled to the middle, under a cover; that scroll brings button B, below it in an
    absolutely positioned box (as the review gutter's buttons are), into view uncovered, so B is
    reached there. Scrolled to the middle itself, B would be under the cover too."""
    from documents import chapter, document, heading, paragraph
    from obs_html.config import load_config
    from obs_html.render import render

    artifact = render(document("Sweep", chapter("one", "One", heading(1, "One"), paragraph("Text."))),
                      load_config())
    errors: list[str] = []
    page, frame = open_preview(tmp_path, coverage_browser, errors, artifact, "null-origin")
    try:
        frame.evaluate("""() => {
            const open = obsArtifact.activateChapter;
            obsArtifact.activateChapter = async (...request) => {
                const opened = await open(...request);
                document.querySelector("[data-chapter-body]").insertAdjacentHTML("beforeend",
                    '<div style="height:2000px"></div>' +
                    '<button style="display:block;width:120px" aria-label="E">E</button>' +
                    `<div style="height:${innerHeight * 0.3}px"></div>` +
                    '<div style="position:relative;height:24px"><div style="position:absolute;top:0;left:0">' +
                    '<button style="display:block;width:120px" aria-label="B">B</button></div></div>' +
                    '<div style="height:2000px"></div>');
                const box = document.querySelector('[aria-label="E"]').getBoundingClientRect();
                if (!document.querySelector(".cover")) {
                    const cover = document.createElement("div");
                    cover.className = "cover";
                    cover.setAttribute("aria-label", "Cover");
                    Object.assign(cover.style, {position: "fixed", left: `${box.left - 4}px`,
                        top: `${innerHeight / 2 - 60}px`, width: `${box.width + 8}px`, height: "120px",
                        zIndex: "2147483647"});
                    document.body.append(cover);
                }
                return opened;
            };
        }""")
        results = frame.locator("html").evaluate(COVERAGE.read_text(encoding="utf-8"),
                                                 {"views": ["continuous"], "layouts": [None], "firstChapterLayouts": []})
    finally:
        page.close()
    faults = [(fault["control"], fault["covering"]) for result in results for fault in result["faults"]]
    assert faults == [('button "E"', 'div.cover "Cover"')], faults
    assert errors == []




# The spec chapter whose printed form is compared with the interim reference's --print-chapter.
PRINTED_CHAPTER = "design-input-cli"
# A difference in form, not content: pattern -> (replacement, why). Both printed chapters are
# brought to the same form by each substitution before they are compared.
PRINTED_FORMS: dict[str, tuple[str, str]] = {
    "&#x27;": ("'", "this adapter escapes apostrophes in text (html.escape); the text is the same"),
    ' class="internal-link"': ("", "this adapter marks a link to a chapter of the artifact for its runtime"),
    r'(?s)(<pre class="command-output">)<code>(.*?)</code></pre>': (
        r"\1\2</pre>", "the reference wraps command output in <code> inside its <pre>; this adapter does not"),
    r'(?m)^(<pre class="command-output">)?warning: .*\n': (
        r"\1", "the interim reference runs a fence through its own uv and captures uv's warnings (only "
        "where uv warns, as for a deprecated UV_* variable); the core captures the command's output alone"),
}
# A printed line that differs in content: pattern -> why. Each is a rendering difference; the print
# path itself copies the stored chapter unchanged.
PRINTED_LINES: dict[str, str] = {}


@pytest.mark.parametrize("chapter_format", ["html", "text"])
def test_a_printed_chapter_is_the_interim_references(parity_artifacts, tmp_path: Path, chapter_format,
                                                     capsys) -> None:
    """obs-html --print-chapter prints a spec chapter as obs-html-interim --print-chapter does,
    up to the differences PRINTED_FORMS and PRINTED_LINES list."""
    for name, text in parity_artifacts.items():
        (tmp_path / f"{name}.html").write_text(text, encoding="utf-8")
    environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    reference = subprocess.run(
        [uv(), "run", "--offline", "--quiet", "--project", str(CORE_ROOT), "obs-html-interim", "--print-chapter",
         str(tmp_path / "reference.html"), PRINTED_CHAPTER, "--chapter-format", chapter_format],
        cwd=CORE_ROOT, env=environment, capture_output=True, text=True, encoding="utf-8", check=False)
    assert reference.returncode == 0, f"obs-html-interim --print-chapter failed: {reference.stderr}"
    assert obs_html(["--print-chapter", str(tmp_path / "adapter.html"), PRINTED_CHAPTER,
                     "--chapter-format", chapter_format]) == 0
    ours, theirs = capsys.readouterr().out, reference.stdout
    assert ours and theirs
    for pattern, (replacement, _why) in PRINTED_FORMS.items():
        ours, theirs = re.sub(pattern, replacement, ours), re.sub(pattern, replacement, theirs)
    unexplained = [line for line in difflib.ndiff(ours.splitlines(), theirs.splitlines())
                   if line[:2] in {"- ", "+ "}
                   and not any(re.match(pattern, line[2:]) for pattern in PRINTED_LINES)]
    assert not unexplained, "\n".join(unexplained)
