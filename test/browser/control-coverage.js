// The control-coverage sweep: a function expression that Playwright evaluates inside an opened
// artifact (this adapter's or the interim reference's), used by test/test_parity_browser.py.
//
// For the given views and bar layouts it opens every chapter and finds every visible
// interactive control (links, buttons, inputs, selects, summaries and ARIA buttons, links,
// checkboxes, switches and tabs). A control is fine when `document.elementFromPoint` at the
// centre of one of its visible parts returns the control, one of its descendants or its label, either
// where it stands or once scrolled to the middle of its scroller (horizontally only as far as
// needed, as a reader would scroll). A control that wraps onto several lines, as a link at a line
// end does, is scrolled to as a whole first; where its lines lie on either side of the scroller's
// view (a review-mode body wider than the reader), that shows none of them, so it is then scrolled
// to one line at a time, as a reader scrolls to the part they point at. Anything else is a fault
// naming the control and what lies over it. A control covered where it stands but uncovered once
// scrolled is not a fault: the reader reaches it, as with any scrolled content.
//
// One exception, from obs's artifact-ui.md: on narrow screens an open bar overlays the reader on
// purpose, so a reader control the bar overlays, even in part, is hidden, not covered. The
// chapter controls (previous and next) are not exempt: they stay reachable.
//
// Argument: {views: ["pages", "continuous"], layouts: [null | [bar, direction], ...],
// firstChapterLayouts: [...]}; the latter run on the first chapter only. Returns a list of
// {view, layout, chapter, controls, faults: [{control, covering}]}.
async (_, {views, layouts, firstChapterLayouts}) => {
    const CONTROLS = 'a[href], button, input:not([type="hidden"]), select, textarea, summary, ' +
        '[role="button"], [role="link"], [role="checkbox"], [role="switch"], [role="tab"], ' +
        '[contenteditable="true"]';
    const OWNERS = `${CONTROLS}, [data-dock-resize], [data-bar], [data-dock-region], .chapter-nav-zone`;

    const name = (element) => {
        const text = (element.getAttribute("aria-label") || element.getAttribute("title") ||
            element.textContent || element.getAttribute("placeholder") || "")
            .trim().replace(/\s+/g, " ").slice(0, 40);
        const kind = element.tagName.toLowerCase() + (element.classList[0] ? `.${element.classList[0]}` : "");
        return text ? `${kind} "${text}"` : kind;
    };
    const lines = (element) => [...element.getClientRects()].filter((rect) => rect.width >= 2 && rect.height >= 2);
    const box = (element) => lines(element)[0];
    const shown = (element) => element.checkVisibility({visibilityProperty: true}) && Boolean(box(element));

    // One check runs synchronously: no script, style or layout change happens during it, only
    // the scrolling it does itself. So what does not depend on scrolling is computed once per
    // check, and forgotten when the next check starts: each element's style, each control's
    // clipping ancestors and the overlaying bars.
    const memos = [];
    const memo = (compute) => {
        const known = new Map();
        memos.push(known);
        return (element) => {
            if (!known.has(element)) known.set(element, compute(element));
            return known.get(element);
        };
    };
    const style = memo((element) => getComputedStyle(element));
    // The ancestors that clip a control's overflow, up to its first fixed ancestor.
    const clippers = memo((element) => {
        const found = [];
        for (let parent = element.parentElement; parent; parent = parent.parentElement) {
            const {overflowX, overflowY, position} = style(parent);
            if (overflowX !== "visible" || overflowY !== "visible") found.push(parent);
            if (position === "fixed") break;
        }
        return found;
    });
    // The ancestors a control's scrollIntoView may scroll.
    const scrollers = memo((element) => {
        const found = [];
        for (let parent = element.parentElement; parent; parent = parent.parentElement) found.push(parent);
        return found;
    });
    // Scrolls the control's line (one of its boxes) into view in each ancestor that clips it,
    // innermost first: to the middle vertically, horizontally only as far as needed.
    const revealLine = (control, line) => {
        for (const parent of clippers(control)) {
            const rect = lines(control)[line];
            const own = parent.getBoundingClientRect();
            const view = {left: Math.max(own.left, 0), right: Math.min(own.right, innerWidth),
                top: Math.max(own.top, 0), bottom: Math.min(own.bottom, innerHeight)};
            parent.scrollTop += (rect.top + rect.bottom - view.top - view.bottom) / 2;
            if (rect.left < view.left) parent.scrollLeft -= view.left - rect.left;
            else if (rect.right > view.right) parent.scrollLeft += Math.min(rect.right - view.right, rect.left - view.left);
        }
    };
    const offsets = (elements) => elements.map((element) => [element.scrollLeft, element.scrollTop]);
    // The scrollers among the elements that scrolled between the two offsets, with how far.
    const moved = (elements, before, after) => elements.flatMap((element, index) =>
        after[index][0] !== before[index][0] || after[index][1] !== before[index][1]
            ? [[element, after[index][0] - before[index][0], after[index][1] - before[index][1]]] : []);

    // Each control's boxes when `seen` last looked at it, and how far the scrolls since have moved
    // it: {rects, dx, dy}.
    const boxes = new Map();
    // Whether an element moves exactly with every scroller around it, and only with them: neither
    // it nor an ancestor is fixed or sticky (which move otherwise or not at all), transformed or
    // zoomed (which scale a scroll), or laid out by its distance to the viewport
    // (content-visibility: auto), and no absolutely positioned one has a scroller between itself
    // and its positioned ancestor (which it would not scroll with).
    const linear = memo((element) => {
        const {position, transform, scale, rotate, zoom, contentVisibility, offsetPath} = style(element);
        if (!["static", "relative", "absolute"].includes(position) || transform !== "none" || scale !== "none" ||
            rotate !== "none" || zoom !== "1" || contentVisibility === "auto" || offsetPath !== "none") return false;
        if (position === "absolute") {
            for (let parent = element.parentElement; parent && parent !== document.documentElement &&
                style(parent).position === "static"; parent = parent.parentElement) {
                if (style(parent).overflowX !== "visible" || style(parent).overflowY !== "visible") return false;
            }
        }
        return !element.parentElement || linear(element.parentElement);
    });
    // Whether the scrolls since the control was last looked at cannot have brought any of its
    // boxes into the viewport, so `seen` would still find no part of it: the control moves exactly
    // with the scrollers around it (`linear`), and its last boxes, moved as far as those scrollers
    // scrolled, stay further than CLEARANCE outside the viewport. Layout places a box to a fraction
    // of a pixel; the clearance is far wider.
    const CLEARANCE = 4;
    const outOfView = (control, scrolled) => {
        const known = boxes.get(control);
        if (!known || !linear(control)) return false;
        for (const [scroller, dx, dy] of scrolled) {
            if (scroller !== control && scroller.contains(control)) {
                known.dx += dx;
                known.dy += dy;
            }
        }
        return known.rects.every((rect) =>
            rect.right - known.dx < -CLEARANCE || rect.left - known.dx > innerWidth + CLEARANCE ||
            rect.bottom - known.dy < -CLEARANCE || rect.top - known.dy > innerHeight + CLEARANCE);
    };

    // The visible parts of a control, largest first: each of its boxes (a wrapped link has one
    // per line) cut by the viewport and by every ancestor that clips its overflow. Their centres
    // are where a reader points. A box outside the viewport has no visible part.
    const seen = (element) => {
        const all = lines(element);
        boxes.set(element, {rects: all, dx: 0, dy: 0});
        const rects = all.filter((rect) =>
            Math.min(rect.right, innerWidth) - Math.max(rect.left, 0) >= 1 &&
            Math.min(rect.bottom, innerHeight) - Math.max(rect.top, 0) >= 1);
        if (!rects.length) return [];
        const clips = [{left: 0, top: 0, right: innerWidth, bottom: innerHeight},
            ...clippers(element).map((parent) => parent.getBoundingClientRect())];
        const parts = [];
        for (const rect of rects) {
            const left = Math.max(rect.left, ...clips.map((clip) => clip.left));
            const top = Math.max(rect.top, ...clips.map((clip) => clip.top));
            const right = Math.min(rect.right, ...clips.map((clip) => clip.right));
            const bottom = Math.min(rect.bottom, ...clips.map((clip) => clip.bottom));
            if (right - left < 1 || bottom - top < 1) continue;
            parts.push({
                area: (right - left) * (bottom - top), x: (left + right) / 2, y: (top + bottom) / 2,
                whole: left === rect.left && top === rect.top && right === rect.right && bottom === rect.bottom,
            });
        }
        return parts.sort((one, other) => other.area - one.area);
    };

    // Whether an open bar overlays (part of) the control, as narrow screens do on purpose.
    let bars = null;
    const overlaid = (control) => {
        bars ??= [...document.querySelectorAll("[data-dock-region]")]
            .filter((region) => style(region).position === "fixed" && region.checkVisibility());
        const own = control.getBoundingClientRect();
        return bars.some((region) => {
            const bar = region.getBoundingClientRect();
            return own.left < bar.right && own.right > bar.left && own.top < bar.bottom && own.bottom > bar.top;
        });
    };

    // What lies over the control at that point; "" when the control (or its label) is on top.
    const covering = (control, spot) => {
        const hit = document.elementFromPoint(spot.x, spot.y);
        if (!hit) return "nothing: the point is outside the viewport";
        if (control.contains(hit) || [...(control.labels || [])].some((label) => label.contains(hit))) return "";
        if (control.closest(".reader-shell") && !control.matches("[data-step]") && overlaid(control)) return "";
        return name(hit.closest(OWNERS) || hit);
    };

    // A control is reachable when the reader can point at one of its visible parts. A control
    // not reachable where it stands is scrolled to the middle of its scroller; once anything
    // scrolled, every control still pending is looked at again where it now stands, unless that
    // scroll cannot have brought it into the viewport (`outOfView`): then it still has no visible
    // part, and looking again would find what the last look found.
    const check = () => {
        memos.forEach((known) => known.clear());
        boxes.clear();
        bars = null;
        const controls = [...document.querySelectorAll(CONTROLS)].filter(shown);
        const pending = new Set(controls);
        const sweep = (scrolled = []) => {
            for (const control of pending) {
                if (scrolled.length && outOfView(control, scrolled)) continue;
                if (seen(control).some((part) => part.whole && !covering(control, part))) pending.delete(control);
            }
        };
        const faults = [];
        sweep();
        for (const control of controls) {
            if (!pending.has(control)) continue;
            const before = offsets(scrollers(control));
            control.scrollIntoView({block: "center", inline: "nearest", behavior: "instant"});
            let parts = seen(control);
            for (let line = 0; !parts.length && line < lines(control).length; line++) {
                revealLine(control, line);
                parts = seen(control);
            }
            const over = parts.length ? parts.map((part) => covering(control, part)) : ["nothing: it cannot be scrolled into view"];
            pending.delete(control);
            if (over.every(Boolean)) faults.push({control: name(control), covering: over[0]});
            const scrolled = moved(scrollers(control), before, offsets(scrollers(control)));
            if (scrolled.length) sweep(scrolled);
        }
        return {controls: controls.length, faults};
    };

    const frame = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const open = async (slug) => {
        await obsArtifact.activateChapter(slug);
        await obsArtifact.whenChapterReady();
        for (let wait = 0; wait < 200 && document.querySelector(".reader-pending"); wait++) {
            await new Promise((resolve) => setTimeout(resolve, 25));
        }
    };
    const chapters = [...document.querySelectorAll("[data-toc-tree] a")]
        .map((link) => link.getAttribute("href").slice(1)).filter((slug) => !slug.includes("/"));
    const results = [];
    for (const view of views) {
        obsPages.setPaged(view === "pages");
        for (const [index, chapter] of chapters.entries()) {
            await open(chapter);
            for (const layout of index ? layouts : [...layouts, ...firstChapterLayouts]) {
                if (layout) obsArtifact.openBar(...layout);
                await frame();
                results.push({view, layout, chapter, ...check()});
                if (layout) obsArtifact.closeBar(layout[0]);
            }
        }
    }
    return results;
}
