"""The feature fixture's artifact held to features.md's reading rows, in Claude-preview-like frames.

Reader: whoever changes how the artifact reads, navigates or prints, and the dispatcher reading
[parity/features.md](parity/features.md), whose rows name these tests.

The feature fixture, in which every registered feature appears
(test/fixtures/build_documents.py, features; conftest.py, feature_artifact), is opened
in both preview-like frames (test/preview.py). One interaction script walks it: Home,
previous/next by pointer and keyboard, the contents menu, the filter, a view selection, a figure
reference, and icon counts per region in every chapter. Each step is held to what the design
notes and the artifact's own contents say: the arrows and keys walk the contents' chapters in
order, Home returns to the first, a contents link opens its chapter, a filter that matches
nothing disables both arrows, reader state is never a change, and every icon is painted. The
expectations were the interim adapter's observations on obs's spec until obs#3 deleted it; the
checks moved from the spec to the feature fixture so that the browser tier does not grow with the
spec (obs quality.md, Testing boundaries).

A second check sweeps the artifact in the same frames for covered controls
(test/browser/control-coverage.js) at four widths, one test per frame and width, in both views and
with the bars open and closed, the contents bar with its contents collapsed and expanded: a
covered control fails. Its matrix is owned by artifact-ui.md (chapter controls).

Each test opens the artifact once, in one page its checks reuse. Pointer and keyboard steps are
real input, one round trip each; every other observation is computed in the page and returned as
one structure (the icon counts of every chapter in one evaluation), and Python checks them.

A third check prints one chapter of obs's spec, as this adapter renders the core's Document of it
(test/spec_artifact.py), with --print-chapter, in both formats: the HTML form is the chapter as
the artifact stores it, and the text form is its blocks without markup. It needs the real spec:
the chapter's command fence captured the spec's own CLI help.

Run it alone with `uv run pytest test/test_parity_browser.py`; it renders each artifact once per
run, the spec without the network: the core's Document through the core's test/offline_obs_document.py.
Each test runs on its own worker in the complete suite: one per frame for the interaction
script and one per frame and width for the sweep.
"""
import json
import re
from pathlib import Path

import pytest

from artifacts import artifact_html
from obs_html.artifact_data import decode_artifact_data
from preview import READY, SANDBOXES, http_origin, load_preview, open_preview
from spec_artifact import spec_artifact
from obs_html.cli import main as obs_html

FILTER = "file.name == 'nothing'"

# The page helpers every evaluation below starts with: what each step observes, computed in the
# page and returned as one structure that Python compares.
HELPERS = """
const icons = () => {
    const regions = {};
    const region = (element) => {
        const bar = element.closest("[data-bar]");
        if (bar) return `bar ${bar.dataset.bar}`;
        // The notice center's own tests own its icons.
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
// image is decoded and one frame has been drawn: a task queued from the frame's callback runs
// after that frame's rendering step, so the artifact's requestAnimationFrame and ResizeObserver
// work is done, as control-coverage.js waits. No wall-clock wait.
const settle = async () => {
    await globalThis.obsArtifact.whenChapterReady();
    await Promise.all([...document.images].map((image) => image.decode().catch(() => {})));
    await new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve)));
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
# As POINTER, at the centre of the element's first line box: a link that wraps has no text at the
# centre of its bounding box.
FIRST_LINE_POINTER = POINTER.replace("element.getBoundingClientRect()", "element.getClientRects()[0]")

# A figure reference in the feature fixture and its figure's block anchor (obs input-model, Figure
# captions and references): the reference is in the equations chapter, the figure in the figures chapter.
FIGURE_REFERENCE = ("equations", "#figures/block-plot-figure", "figures--block-plot-figure")
# Opens a chapter the contents do not list by a click event on a link to it, which the
# artifact's own link handling routes as a reader's link; the link is removed again. Settles.
OPEN_CHAPTER = "async (slug) => {" + HELPERS + """
    const link = document.body.appendChild(Object.assign(document.createElement("a"), {href: `#${slug}`}));
    link.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true, composed: true}));
    link.remove();
    await settle();
    return chapter();
}"""
# Whether the element with this id starts within the visible part of the chapter's scroll area.
IN_VIEW = """(id) => {
    const element = document.getElementById(id);
    if (!element) return "missing";
    const box = element.getBoundingClientRect();
    const area = element.closest("[data-chapter-scroll]")?.getBoundingClientRect() ?? {top: 0, bottom: innerHeight};
    return box.height > 0 && box.top >= Math.max(0, area.top) - 1 && box.top < Math.min(innerHeight, area.bottom);
}"""


@pytest.fixture(scope="session")
def spec_html(tmp_path_factory) -> str:
    """obs's spec rendered by this adapter, the run's one shared build (test/spec_artifact.py)."""
    return spec_artifact(tmp_path_factory).read_text(encoding="utf-8")


def interact(page, frame) -> tuple[list[tuple[str, object]], list[str]]:
    """The interaction script: ordered (step, observation) pairs, and design-note violations.

    The first step, "chapters", is the chapter Home links to, then the contents' top-level
    chapters in order; the navigation steps are checked against it (expected_steps)."""
    from playwright.sync_api import expect

    steps: list[tuple[str, object]] = []
    violations: list[str] = []
    # Evaluated in the frame itself: a locator would resolve its element on every call.
    settle = lambda: frame.evaluate(SETTLE)
    chapter = lambda: frame.evaluate(CHAPTER)
    # The preview frame stays where open_preview put it: the wrapper page neither scrolls nor reflows.
    box = page.evaluate("document.getElementById('artifact').getBoundingClientRect().toJSON()")

    def pointer(selector: str, where: str = POINTER) -> str:
        """Click where the element is shown; report what covers it, if anything."""
        spot = frame.locator(selector).first.evaluate(where)
        page.mouse.click(box["x"] + spot["x"], box["y"] + spot["y"])
        then = settle()
        return f"covered by {spot['covered']}, then {then}" if spot["covered"] else then

    def visible(selector: str) -> bool:
        return frame.locator(selector).first.is_visible()

    def changed() -> bool:
        """Whether the notice center shows the changed-HTML notice."""
        return frame.locator('[data-notice="changed-html"]').count() > 0

    # The walk: Home, then the listed chapters; screens have no Home, and Home opens the first chapter
    # (artifact-ui.md, Screens).
    steps.append(("chapters", frame.evaluate("""() => {
        const home = document.querySelector(".chapter-home-link").getAttribute("href").slice(1);
        const listed = [...document.querySelectorAll("[data-toc-tree] a")].map((link) => link.getAttribute("href").slice(1));
        const chapters = listed.filter((slug) => !slug.includes("/") && slug !== home);
        return document.documentElement.classList.contains("screens-mode") ? chapters : [home, ...chapters];
    }""")))
    first = steps[-1][1][0]
    steps.append(("start", chapter()))
    steps.append(("icons on start", frame.evaluate(ICONS)))
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
        if home != first:
            violations.append(f"Home by pointer from {origin}: {home}, not {first}")
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
    steps.append(("icons with the contents open", frame.evaluate(ICONS)))

    frame.evaluate("() => globalThis.obsArtifact.openBar('filter')")
    frame.locator("[data-filter-input]").fill(FILTER)
    settle()
    expect(frame.locator('[data-filter-status]')).not_to_have_text(re.compile(r"^All "))
    steps.append(("filter applied", (
        frame.locator("[data-filter-status]").inner_text(), [
            button.is_disabled() for button in frame.locator("[data-step]").all()])))
    if changed():
        violations.append("applying a filter showed the changed-HTML notice")
    frame.evaluate("() => globalThis.obsFilter.setExpression('')")
    settle()
    steps.append(("filter cleared", (frame.locator("[data-filter-status]").inner_text(), chapter())))
    if changed():
        violations.append("clearing a filter showed the changed-HTML notice")
    frame.evaluate("() => globalThis.obsArtifact.setViewSelection('parity', ['a'], ['a', 'b'])")
    settle()
    if changed():
        violations.append("a view selection showed the changed-HTML notice; reader state is never a change "
                          "(artifact-ui.md, What counts as a change)")
    frame.evaluate("() => globalThis.obsArtifact.setViewSelection('parity', [], ['a', 'b'])")
    settle()

    source, href, anchor = FIGURE_REFERENCE
    frame.evaluate(OPEN_CHAPTER, source)
    reference = pointer(f'[data-chapter-body] a[href="{href}"]', FIRST_LINE_POINTER)
    shown = frame.evaluate(IN_VIEW, anchor)
    steps.append(("figure reference by pointer", (reference, shown)))
    if shown is not True:
        violations.append(f"the figure reference {href} in {source}: {reference}, and its anchor {anchor} "
                          f"is {'missing' if shown == 'missing' else 'not in view'}")

    steps += [(f"icons in {slug}", icons) for slug, icons in frame.evaluate(CHAPTER_ICONS)]
    return steps, violations


def observe(tmp_path: Path, reader_browser, artifact: str, frame_kind: str):
    """The interaction script on the artifact, opened once: its steps, design-note violations and
    page errors."""
    errors: list[str] = []
    if frame_kind == "same-origin":
        with http_origin(tmp_path) as origin:
            page, frame = load_preview(tmp_path, reader_browser, errors, artifact, frame_kind, origin)
            frame.evaluate(READY)
            return (*interact(page, frame), errors)
    page, frame = load_preview(tmp_path, reader_browser, errors, artifact, frame_kind, None)
    frame.evaluate(READY)
    return (*interact(page, frame), errors)


# The regions outside the chapter body: the same icons in every chapter.
CHROME = ("toolbar", "chapter arrows", "breadcrumbs", "bars menu")


def expected_steps(steps: list[tuple[str, object]]) -> dict[str, object]:
    """What each navigation step must observe, from the chapters in order (the first step): the
    arrows and keys walk them one by one, Home opens the first, a contents link opens the
    chapter it names, a filter matching nothing disables both arrows and clearing it keeps the
    chapter. Steps it does not name are checked in check_steps."""
    order = dict(steps)["chapters"]
    home = order[0]
    walk = {f"next {count} by pointer": order[count] for count in range(1, 5)}
    walk |= {"previous 1 by pointer": order[3], "previous 2 by pointer": order[2],
             "key 1 ArrowRight": order[3], "key 2 ArrowRight": order[4], "key 3 ArrowLeft": order[3]}
    expected: dict[str, object] = {"start": home, **walk}
    for step, _ in steps:
        if step.startswith("Home by keyboard"):
            expected[step] = home
        elif step.startswith("contents link #"):
            expected[step] = step.removeprefix("contents link #").split("/")[0].removesuffix(" by pointer")
    expected |= {"menu button by pointer": [home, True], "contents dock by pointer": home,
                 "contents shown": True, "filter applied": ["0 chapters.", [True, True]],
                 "filter cleared": ["All chapters.", home],
                 "figure reference by pointer": [FIGURE_REFERENCE[1].split("/")[0].lstrip("#"), True]}
    return expected


def check_steps(steps: list[tuple[str, object]]) -> list[str]:
    """Each step against expected_steps; every icon painted, and the chrome's icons the same in
    every chapter as on start."""
    expected = expected_steps(steps)
    observed = {step: json.loads(json.dumps(value)) for step, value in steps}
    problems = [f"{step}: observed {observed.get(step)!r}, expected {value!r}"
                for step, value in expected.items() if observed.get(step) != value]
    icons = {step: value for step, value in observed.items() if step.startswith("icons ")}
    if len(icons) < 3:
        problems.append(f"icons: observed in {sorted(icons)} only, not on start and in every chapter")
    start = icons.get("icons on start", {})
    for step, regions in icons.items():
        problems += [f"{step}: {region} has {counts['icons'] - counts['painted']} of {counts['icons']} icons unpainted"
                     for region, counts in regions.items() if counts["painted"] != counts["icons"]]
        problems += [f"{step}: {region} shows {regions.get(region)}, on start {start.get(region)}"
                     for region in CHROME if regions.get(region) != start.get(region)]
    problems += [f"icons on start: no icon in {region}" for region in CHROME if not start.get(region, {}).get("icons")]
    return problems


@pytest.mark.browser
@pytest.mark.parametrize("frame_kind", [
    pytest.param(frame_kind, marks=pytest.mark.xdist_group(f"parity-{frame_kind}")) for frame_kind in SANDBOXES])
def test_the_artifact_reads_as_its_contents_and_design_notes_say_in_preview_frames(
        tmp_path: Path, reader_browser, feature_artifact: str, frame_kind: str) -> None:
    steps, violations, errors = observe(tmp_path, reader_browser, feature_artifact, frame_kind)
    problems = check_steps(steps)
    problems += [f"design notes: {violation}" for violation in violations]
    problems += [f"page error: {error}" for error in errors]
    assert not problems, f"test/test_parity_browser.py, {frame_kind} frame:\n" + "\n".join(problems)


def test_the_step_check_names_a_step_that_went_elsewhere() -> None:
    """The check is not vacuous: an arrow that skips a chapter and an unpainted icon are named."""
    regions = {region: {"icons": 1, "painted": 1} for region in CHROME}
    steps = [("chapters", ["home", "a", "b", "c", "d"]), ("start", "home"), ("icons on start", regions),
             ("next 1 by pointer", "b"), ("icons in a", {**regions, "prose": {"icons": 2, "painted": 1}}),
             ("icons in b", regions)]
    problems = check_steps(steps)
    assert "next 1 by pointer: observed 'b', expected 'a'" in problems
    assert "icons in a: prose has 1 of 2 icons unpainted" in problems
    assert not any(problem.startswith("start:") for problem in problems)


COVERAGE = Path(__file__).parent / "browser" / "control-coverage.js"
# Each width is swept in its own opened artifact, so the widths run on parallel workers.
WIDTHS = (360, 700, 1100, 1600)
# Show as pages on and off; off, the feature fixture shows screens, the layout it opens in
# (artifact-ui.md, Screens), and an artifact that opens paged shows continuous reading.
VIEWS = ("pages", "continuous")


# The contents bar, which the sweep opens with its contents collapsed and expanded.
CONTENTS = "toc"


def layout_name(layout: list[str] | None) -> str:
    if not layout:
        return "no bar open"
    contents = f", its contents {layout[2]}" if len(layout) > 2 else ""
    return f"the {layout[0]} bar docked {layout[1]}{contents}"


def sweep_layouts(bars: list[str]) -> tuple[list, list]:
    """The bar layouts the sweep checks on every chapter, and those it checks on the first only.

    On every chapter: no bar, the Filter bar in each dock direction (bars of one side shape the
    reader alike) and the Comments bar, whose review mode reshapes the reader. On the first
    chapter, every other bar on its default side, the contents bar twice: with its contents
    collapsed and expanded.
    """
    docked = "filter" if "filter" in bars else bars[0]
    layouts = [None, *([docked, side] for side in ("right", "left", "top", "bottom")),
               *([bar, "right"] for bar in bars if bar == "comments")]
    first = [layout for bar in bars if [bar, "right"] not in layouts
             for layout in ([[bar, "right", state] for state in ("collapsed", "expanded")]
                            if bar == CONTENTS else [[bar, "right"]])]
    return layouts, first


def covered_controls(tmp_path: Path, browser, artifact: str, frame_kind: str, name: str,
                     width: int) -> dict[tuple[str, str], dict[str, list[str]]]:
    """Every covered control at the width, in every view and bar layout, in one preview frame.

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
        page.set_viewport_size({"width": max(WIDTHS) + 100, "height": 800})
        root = frame.locator("html")
        bars = root.evaluate("""() => [...new Set([...document.querySelectorAll("[data-dock-bar]")]
            .map((button) => button.dataset.dockBar))]""")
        layouts, first = sweep_layouts(bars)
        page.evaluate("width => document.getElementById('artifact').style.width = width", f"{width}px")
        results = root.evaluate(COVERAGE.read_text(encoding="utf-8"),
                                {"views": list(VIEWS), "layouts": layouts, "firstChapterLayouts": first})
        for result in results:
            for fault in result["faults"]:
                where = f"at {width}px in the {result['view']} view with {layout_name(result['layout'])}"
                faults.setdefault((fault["control"], where), {}).setdefault(
                    fault["covering"], []).append(result["chapter"])
    for error in errors:
        faults.setdefault(("page error", error), {})
    return faults


@pytest.mark.browser
@pytest.mark.parametrize(("frame_kind", "width"), [
    pytest.param(frame_kind, width, id=f"{frame_kind}-{width}",
                 marks=pytest.mark.xdist_group(f"coverage-{frame_kind}-{width}"))
    for frame_kind in SANDBOXES for width in WIDTHS])
def test_no_control_is_covered_in_preview_frames(
        tmp_path: Path, overlay_scrollbar_browser, feature_artifact: str, frame_kind: str, width: int) -> None:
    """No visible control lies under another element's pointer area (test/browser/control-coverage.js)."""
    ours = covered_controls(tmp_path, overlay_scrollbar_browser, feature_artifact, frame_kind, "adapter", width)
    problems = [
        f"page error: {where}" if control == "page error" else f"{control} is covered {where} by "
        + "; ".join(f"{covering} (in {', '.join(chapters)})" for covering, chapters in coverings.items())
        for (control, where), coverings in ours.items()
    ]
    assert not problems, (
        f"test/test_parity_browser.py: controls covered by another element's pointer area, {frame_kind} "
        "frame. Remedy: give the control clearance from what covers it (obs artifact-ui.md, chapter "
        "controls):\n" + "\n".join(problems))


def test_the_sweep_runs_one_test_per_frame_and_width_each_in_its_own_group() -> None:
    """Every frame and width is its own case with its own xdist group, so the workers sweep them
    side by side; none is left out."""
    params = next(mark for mark in test_no_control_is_covered_in_preview_frames.pytestmark
                  if mark.name == "parametrize").args[1]
    cases = [tuple(param.values) for param in params]
    groups = [mark.kwargs.get("name", mark.args[0] if mark.args else None)
              for param in params for mark in param.marks if mark.name == "xdist_group"]
    assert cases == [(frame_kind, width) for frame_kind in SANDBOXES for width in WIDTHS]
    assert all(isinstance(width, int) for _, width in cases), "one width per case, not a group of widths"
    assert len(groups) == len(cases) == len(set(groups))


def test_the_sweep_checks_the_contents_bar_collapsed_and_expanded() -> None:
    """In both views and at every width, the sweep opens the contents bar on the first chapter
    twice, once with its contents collapsed and once expanded; every other bar once."""
    bars = ["toc", "filter", "comments", "search", "settings"]
    layouts, first = sweep_layouts(bars)
    assert [layout for layout in first if layout[0] == "toc"] == [
        ["toc", "right", "collapsed"], ["toc", "right", "expanded"]]
    assert all(len(layout) == 2 for layout in [*layouts[1:], *first] if layout[0] != "toc")
    assert {layout[0] for layout in [*layouts[1:], *first]} == set(bars)


@pytest.mark.browser
def test_the_sweep_sets_the_contents_state_it_checks(tmp_path: Path, overlay_scrollbar_browser) -> None:
    """The contents' state is the one the layout names, whatever an earlier check left: opening
    a nested chapter expands its parent in the contents, and the next view's collapsed check
    still sees it collapsed."""
    from documents import chapter, document, heading, paragraph

    artifact = artifact_html(document("Sweep", chapter(
        "one", "One", heading(1, "One"), paragraph("Text."),
        children=(chapter("two", "Two", heading(1, "Two"), paragraph("Text.")),)),
        chapter("three", "Three", heading(1, "Three"), paragraph("Text."))))
    errors: list[str] = []
    page, frame = open_preview(tmp_path, overlay_scrollbar_browser, errors, artifact, "null-origin")
    states = [["toc", "right", "expanded"], ["toc", "right", "collapsed"]]
    results = frame.locator("html").evaluate(COVERAGE.read_text(encoding="utf-8"), {
        "views": list(VIEWS), "layouts": [None], "firstChapterLayouts": states})
    counts = {(result["view"], result["layout"][2]): result["controls"]
              for result in results if result["layout"]}
    for view in VIEWS:
        assert counts[(view, "collapsed")] < counts[(view, "expanded")], counts
    assert counts[("pages", "collapsed")] == counts[("continuous", "collapsed")], counts
    assert counts[("pages", "expanded")] == counts[("continuous", "expanded")], counts
    assert [fault for result in results for fault in result["faults"]] == []
    assert errors == []


@pytest.mark.browser
def test_the_sweep_names_a_covered_control_and_what_covers_it(tmp_path: Path, overlay_scrollbar_browser) -> None:
    """The sweep is not vacuous: a control under another element is a fault naming both."""
    from documents import chapter, document, heading, paragraph

    artifact = artifact_html(document("Sweep", chapter("one", "One", heading(1, "One"), paragraph("Text."))))
    errors: list[str] = []
    page, frame = open_preview(tmp_path, overlay_scrollbar_browser, errors, artifact, "null-origin")
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
    faults = {(fault["control"], fault["covering"]) for result in results for fault in result["faults"]}
    assert ('a.chapter-home-link "Home"', 'div.cover "Cover"') in faults, faults
    assert errors == []


@pytest.mark.browser
def test_the_sweep_reaches_a_self_link_whose_lines_lie_on_either_side_of_the_reader(
        tmp_path: Path, overlay_scrollbar_browser) -> None:
    """The fault #251 met in obs's spec, at 360 px with the Comments bar docked right: review mode
    makes the body wider than the reader, and the note's link to itself wraps with its first line
    right of the reader's view and its second left of it. Scrolled to as a whole, it shows neither;
    the sweep then scrolls to one line, as a reader does. The self-link fixture's link is made to
    wrap so, on every open: a spacer and a line break, and a link before it that scrolls the reader
    between the two lines."""

    artifact = artifact_html(json.loads((Path(__file__).parent / "fixtures" / "documents" / "self-link.json")
                                 .read_text(encoding="utf-8")))
    errors: list[str] = []
    page, frame = open_preview(tmp_path, overlay_scrollbar_browser, errors, artifact, "null-origin")
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
    assert [result["chapter"] for result in results] == ["long", "short"]
    assert [fault for result in results for fault in result["faults"]] == []
    assert errors == []


@pytest.mark.browser
def test_the_sweep_reaches_a_control_an_earlier_scroll_brought_into_view(tmp_path: Path, overlay_scrollbar_browser) -> None:
    """After a scroll the sweep looks again only at controls the scroll can have brought into view;
    one it brought there is still reached where it then stands. Button E, far down the chapter,
    is scrolled to the middle, under a cover; that scroll brings button B, below it in an
    absolutely positioned box (as the review gutter's buttons are), into view uncovered, so B is
    reached there. Scrolled to the middle itself, B would be under the cover too."""
    from documents import chapter, document, heading, paragraph

    artifact = artifact_html(document("Sweep", chapter("one", "One", heading(1, "One"), paragraph("Text."))))
    errors: list[str] = []
    page, frame = open_preview(tmp_path, overlay_scrollbar_browser, errors, artifact, "null-origin")
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
    faults = [(fault["control"], fault["covering"]) for result in results for fault in result["faults"]]
    assert faults == [('button "E"', 'div.cover "Cover"')], faults
    assert errors == []


# The spec chapter --print-chapter prints, and what its source note shows: its heading and the
# live help its command fence captured.
PRINTED_CHAPTER = "design-input-cli"
PRINTED_TEXT = ("CLI", "usage: obs-document")


@pytest.mark.parametrize("chapter_format", ["html", "text"])
def test_a_printed_spec_chapter_is_the_stored_chapter(spec_html: str, tmp_path: Path, chapter_format,
                                                      capsys) -> None:
    """obs-html --print-chapter prints a spec chapter as the artifact stores it: the HTML form is the
    stored HTML, the text form one line per block without markup, and both show the note's heading
    and its command fence's output."""
    artifact = tmp_path / "spec.html"
    artifact.write_text(spec_html, encoding="utf-8")
    assert obs_html(["--print-chapter", str(artifact), PRINTED_CHAPTER, "--chapter-format", chapter_format]) == 0
    printed = capsys.readouterr().out
    stored = next(note["html"] for note in decode_artifact_data(spec_html)["notes"] if note["slug"] == PRINTED_CHAPTER)
    if chapter_format == "html":
        assert printed == stored
        assert '<pre class="command-output"><code>' in printed
    else:
        assert not re.search(r"</?(p|h\d|pre|code|a)[ >]", printed), printed[:400]
        assert printed.count("\n") > 10
    lines = [line.strip() for line in re.sub(r"<[^>]+>", "\n", printed).splitlines()]
    assert all(any(line.startswith(text) for line in lines) for text in PRINTED_TEXT), printed[:400]
