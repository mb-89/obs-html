(() => {
    const artifact = globalThis.obsArtifact;
    const data = JSON.parse(document.querySelector("[data-artifact-data]").textContent);
    const reader = document.querySelector("[data-chapter-scroll]");
    const chapter = document.querySelector("[data-active-chapter]");
    const body = chapter.querySelector("[data-chapter-body]");
    const screen = document.createElement("div");
    screen.className = "paged-reader chapter-body";
    screen.dataset.transientView = "";
    screen.hidden = true;
    body.append(screen);
    const printed = document.createElement("div");
    printed.className = "print-book chapter-body";
    printed.dataset.transientView = "";
    document.body.append(printed);
    let paged = false;
    let printing = false;
    let exportPending = null;
    let liveNodes = [];
    let originalChildren = new Map();
    let measuredStarts = new Map();
    let measuredCounts = new Map();
    let measuredTableAllocations = new Map();
    let measuredTotal = 0;
    // Current-chapter page slots measured synchronously while whole-artifact numbering is pending,
    // so the live screen gets its final layout at once and numbering later updates in place.
    let provisionalCounts = new Map();
    let provisionalAllocations = new Map();
    let measurementEpoch = 0;
    let measurementScheduled = false;
    let printMediaBoxes = [];
    const root = document.documentElement;
    const paper = data.paper;
    root.style.setProperty("--paper-width", `${paper.widthMillimeters}mm`);
    root.style.setProperty("--paper-height", `${paper.heightMillimeters}mm`);
    root.style.setProperty("--paper-margin", `${paper.marginMillimeters}mm`);
    root.style.setProperty("--paper-code-font", `${data.reading.codeFontPoints}pt`);
    root.style.setProperty("--heading-space-before", `${data.reading.headingSpaceBeforeEm}em`);
    root.style.setProperty("--heading-space-after", `${data.reading.headingSpaceAfterEm}em`);
    root.style.setProperty("--paragraph-minimum-lines", data.reading.paragraphMinimumLines);
    const printStyle = document.createElement("style");
    printStyle.textContent = `
        @page { size: ${paper.widthMillimeters}mm ${paper.heightMillimeters}mm; margin: 0; }
        @page artifact-portrait { size: ${paper.widthMillimeters}mm ${paper.heightMillimeters}mm; margin: 0; }
        @page artifact-landscape { size: ${paper.heightMillimeters}mm ${paper.widthMillimeters}mm; margin: 0; }
    `;
    document.head.append(printStyle);

    const sourceFor = (slug) => {
        const source = document.createElement("div");
        artifact.renderStatic(slug, source, true,
            ...(chapter.dataset.chapter === slug
                ? [chapter.dataset.tableFilter || "", chapter.dataset.tableProjection || ""] : []));
        return source;
    };
    // Front-page groups ("@abstract", "@contents", ...) are projections of the manifest note.
    const notesBySlug = new Map(data.notes.map((record) => [record.slug, record]));
    const authorClasses = (slug) => notesBySlug.get(slug.startsWith("@") ? "home" : slug)?.cssClasses || [];
    const groups = (chapters, liveHome = null, includeChapters = true) => {
        const home = liveHome || sourceFor("home");
        const cover = home.querySelector(".document-heading");
        cover?.remove();
        const pageHeading = (text) => {
            const heading = document.createElement("h1");
            heading.textContent = text;
            return heading;
        };
        // Front pages are the manifest's obsHtml.pages declaration, in its order and with its titles.
        const builders = {
            cover: () => {
                const title = document.createElement("section");
                title.className = "title-page";
                title.append(cover);
                return [{slug: "home", source: title, title: ""}];
            },
            abstract: (declaration) => {
                const abstract = document.createElement("section");
                if (declaration.title) abstract.append(pageHeading(declaration.title));
                const sections = [{slug: "@abstract", source: abstract, title: declaration.title || ""}];
                for (const node of [...home.childNodes]) {
                    const heading = node.nodeType === 1 && (node.matches("h2") ? node
                        : node.matches(".collapsible-heading") ? node.querySelector(":scope > h2") : null);
                    if (heading) {
                        const source = document.createElement("section");
                        sections.push({slug: `@${heading.id.replace(/^home--/, "")}`, source,
                            title: heading.textContent.trim()});
                    }
                    sections.at(-1).source.append(node);
                }
                // A heading never ends a sheet: a heading-only group, such as the declared Abstract
                // title before the first second-level heading, opens the following group instead.
                const heading = (node) => node.nodeType === 1 &&
                    (node.matches(".collapsible-heading") || /^H[1-6]$/.test(node.tagName));
                const headingOnly = (section) => {
                    const nodes = [...section.source.childNodes]
                        .filter((node) => node.nodeType === 1 || node.textContent.trim());
                    return nodes.length && nodes.every(heading);
                };
                for (let index = sections.length - 2; index >= 0; index -= 1) {
                    if (!headingOnly(sections[index])) continue;
                    sections[index + 1].source.prepend(...sections[index].source.childNodes);
                    sections.splice(index, 1);
                }
                return sections.filter((section, index) => index || declaration.title ||
                    [...section.source.childNodes].some((node) => node.nodeType === 1 || node.textContent.trim()));
            },
            contents: (declaration) => {
                const contents = document.createElement("section");
                if (declaration.title) contents.append(pageHeading(declaration.title));
                const list = document.createElement("ol");
                list.className = "page-contents";
                artifact.navigationChapters().forEach((record) => {
                    const item = document.createElement("li");
                    item.style.setProperty("--chapter-depth", record.depth);
                    const link = document.createElement("a");
                    link.href = `#${record.slug}`;
                    link.textContent = record.title;
                    const number = document.createElement("span");
                    number.className = "contents-page-number";
                    number.dataset.contentsChapter = record.slug;
                    link.append(number);
                    item.append(link);
                    list.append(item);
                });
                contents.append(list);
                return [{slug: "@contents", source: contents, title: declaration.title || ""}];
            },
        };
        const front = data.document.pages.flatMap((declaration) => builders[declaration.page](declaration));
        // A compact heading is never a sheet of its own; it opens the first front page.
        if (cover?.matches(".document-heading--compact")) front[0]?.source.prepend(cover);
        return [
            ...front,
            ...(includeChapters ? chapters.map((record) => ({slug: record.slug, source: sourceFor(record.slug)})) : []),
        ];
    };

    // Split overflowing containers recursively, retaining semantic wrappers on each sheet.
    const paginate = (source, destination, slug, live = false, logical = false) => {
        if (live && !originalChildren.has(source)) originalChildren.set(source, [...source.childNodes]);
        const pageOffset = destination.children.length;
        const pageIndex = () => destination.children.length - pageOffset - 1;
        const logicalPages = live ? (measuredStarts.size ? measuredCounts.get(slug)
            : provisionalCounts.get(slug)) || null : null;
        const tableAllocations = new Map();
        let activeTableAllocation = null;
        let content;
        let containers;
        let pageHasContent;
        let expanded = false;
        let orientation = "portrait";
        let wideDepth = 0;
        let widePrelude = false;
        let pendingPortrait = false;
        const path = [];
        const listPositions = new Map();
        const usedLiveContainers = new Set();
        const newPage = () => {
            // Numbered screen sheets grow within their original allocation instead of stealing later slots.
            if (live && ((logicalPages && pageIndex() >= logicalPages - 1) ||
                    (activeTableAllocation && pageIndex() >= activeTableAllocation.last))) {
                content.closest(".paper-sheet").classList.add("paper-sheet-flexible");
                expanded = false;
                return;
            }
            if (containers) {
                [...containers].reverse().forEach(([original, copy]) => {
                    if (!copy.childNodes.length) copy.remove();
                    if (original.tagName === "TABLE" && !copy.querySelector("tbody tr")) copy.remove();
                });
                if (!pageHasContent && !content.closest(".paper-sheet").hasAttribute("data-logical-reserved")) {
                    content.closest(".paper-sheet").remove();
                }
            }
            const sheet = document.createElement("section");
            sheet.className = "paper-sheet";
            sheet.classList.add(...authorClasses(slug));
            sheet.dataset.pageChapter = slug;
            sheet.dataset.pageOrientation = orientation;
            content = document.createElement("div");
            content.className = "paper-content";
            sheet.append(content);
            destination.append(sheet);
            containers = new Map();
            pageHasContent = false;
            expanded = false;
        };
        newPage();
        // A local filter can leave allocated slots empty without moving subsequent content.
        const reserveUntil = (last) => {
            while (pageIndex() < last) {
                if (!pageHasContent) content.closest(".paper-sheet").dataset.logicalReserved = "";
                newPage();
            }
            if (!pageHasContent) content.closest(".paper-sheet").dataset.logicalReserved = "";
        };
        const orient = (value, force = false) => {
            if (orientation === value && !force) return;
            orientation = value;
            newPage();
        };
        const parent = () => {
            let current = content;
            path.forEach((original) => {
                if (!containers.has(original)) {
                    const retain = live && !usedLiveContainers.has(original);
                    const columns = original.tagName === "TABLE" && original.querySelector("colgroup");
                    const header = original.tagName === "TABLE" && original.querySelector("thead");
                    const warning = original.matches(".data-table-shell") &&
                        original.querySelector(":scope > [data-table-filter-warning]");
                    const copy = retain ? original : original.cloneNode(false);
                    if (retain) {
                        if (!originalChildren.has(original)) {
                            originalChildren.set(original, [...original.childNodes]);
                        }
                        copy.replaceChildren();
                        usedLiveContainers.add(original);
                    } else if (live) {
                        copy.dataset.pageContinuation = "";
                    }
                    if (original.tagName === "OL" && listPositions.has(original)) {
                        copy.start = listPositions.get(original);
                    }
                    if (original.tagName === "TABLE") {
                        if (columns) copy.append(retain ? columns : columns.cloneNode(true));
                        if (header) copy.append(retain ? header : header.cloneNode(true));
                    }
                    if (warning) copy.append(retain ? warning : warning.cloneNode(true));
                    current.append(copy);
                    containers.set(original, copy);
                }
                current = containers.get(original);
            });
            return current;
        };
        const fits = () => (live && content.closest(".paper-sheet").classList.contains("paper-sheet-flexible")) ||
            content.scrollHeight <= content.clientHeight + 1;
        const overflowingContainer = (node) => node.nodeType === 1 &&
            node.matches("section, div, table, tbody, ol, ul, blockquote, p, li, pre, code, a, span, strong, em") &&
            !node.matches(".collapsible-heading");
        const isHeading = (node) => node.nodeType === 1 &&
            (node.matches(".collapsible-heading") || /^H[1-6]$/.test(node.tagName));
        // Retain semantic wrappers and heading chains down to the first content block.
        const leading = (nodes) => {
            const copies = [];
            let complete = false;
            for (const node of nodes) {
                if ((node.nodeType === 3 && !node.textContent.trim()) || node.hidden) continue;
                let copy = node.cloneNode(true);
                if (isHeading(node)) {
                    copies.push(copy);
                    continue;
                }
                if (node.nodeType === 1 && node.matches("section, div, blockquote") &&
                        !node.matches(".data-table-shell, .content-card, figure")) {
                    const start = leading([...node.childNodes]);
                    copy = node.cloneNode(false);
                    copy.append(...start.copies);
                    complete = start.complete;
                } else {
                    complete = true;
                    if (!live && copy.nodeType === 1) {
                        if (copy.matches("ol, ul")) {
                            [...copy.children].slice(1).forEach((child) => child.remove());
                        } else if (copy.matches("table")) {
                            [...copy.querySelectorAll("tbody tr")].slice(1).forEach((row) => row.remove());
                        } else if (copy.matches("p") && !copy.querySelector("img:not(.resource-icon *), svg:not(.resource-icon *)")) {
                            copy.dataset.leadingParagraph = "";
                        }
                    }
                }
                copies.push(copy);
                if (complete) break;
            }
            return {copies, complete};
        };
        const textRange = (element, count) => {
            const range = document.createRange();
            range.setStart(element, 0);
            const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
                if (count <= walker.currentNode.length) {
                    range.setEnd(walker.currentNode, count);
                    return range;
                }
                count -= walker.currentNode.length;
            }
            range.setEnd(element, element.childNodes.length);
            return range;
        };
        const lineCount = (element) => {
            const tops = [];
            for (const rect of textRange(element, element.textContent.length).getClientRects()) {
                if (rect.width && rect.height && !tops.some((top) => Math.abs(top - rect.top) < 2)) {
                    tops.push(rect.top);
                }
            }
            return tops.length;
        };
        const splitParagraph = (node) => {
            const remaining = node.cloneNode(true);
            const minimum = data.reading.paragraphMinimumLines;
            while (remaining.textContent.length) {
                const fragment = remaining.cloneNode(false);
                parent().append(fragment);
                let low = 0;
                let high = remaining.textContent.length;
                while (low < high) {
                    const middle = Math.ceil((low + high) / 2);
                    fragment.replaceChildren(textRange(remaining, middle).cloneContents());
                    if (fits()) low = middle;
                    else high = middle - 1;
                }
                if (low === remaining.textContent.length) {
                    fragment.replaceChildren(...remaining.childNodes);
                    pageHasContent = true;
                    return;
                }
                const words = [...remaining.textContent.matchAll(/\s+/g)]
                    .map((match) => match.index + match[0].length).filter((end) => end <= low);
                let count = 0;
                for (const end of words.reverse()) {
                    fragment.replaceChildren(textRange(remaining, end).cloneContents());
                    if (lineCount(fragment) < minimum) break;
                    const tail = remaining.cloneNode(false);
                    const range = textRange(remaining, end);
                    range.setStart(range.endContainer, range.endOffset);
                    range.setEnd(remaining, remaining.childNodes.length);
                    tail.append(range.cloneContents());
                    parent().append(tail);
                    const tailLines = lineCount(tail);
                    tail.remove();
                    if (tailLines >= minimum) {
                        count = end;
                        break;
                    }
                }
                if (!count && !pageHasContent) count = low;
                if (!count) {
                    fragment.remove();
                    if (!pageHasContent) throw new Error("Paper area is too small to fit text.");
                    newPage();
                    continue;
                }
                fragment.replaceChildren(textRange(remaining, count).extractContents());
                pageHasContent = true;
                if (remaining.textContent.length) newPage();
            }
        };
        const place = (node) => {
            const wide = node.nodeType === 1 && node.matches('[data-table-wide="true"]') && !wideDepth;
            const key = node.dataset?.dataTable || node.dataset?.reviewTable;
            const allocation = wide && logicalPages ? (measuredStarts.size ? measuredTableAllocations
                : provisionalAllocations).get(slug)?.get(key) : null;
            let first;
            if (wide) {
                orient("landscape", !widePrelude && pageHasContent);
                if (allocation) reserveUntil(allocation.first);
                first = pageIndex();
                activeTableAllocation = allocation;
                pendingPortrait = false;
                widePrelude = false;
                wideDepth += 1;
            }
            try {
                placeNode(node);
            } finally {
                if (wide) {
                    if (allocation) reserveUntil(allocation.last);
                    if (logical && key) tableAllocations.set(key, {first, last: pageIndex()});
                    activeTableAllocation = null;
                    wideDepth -= 1;
                    pendingPortrait = true;
                }
            }
        };
        const placeNode = (node) => {
            if (node.nodeType === 3 && !node.textContent.trim()) {
                if (live) parent().append(node);
                return;
            }
            if (expanded) newPage();
            const copy = live ? node : node.cloneNode(true);
            parent().append(copy);
            // A figure whose kind draws its body in the page is drawn now, so its page holds its height.
            if (copy.nodeType === 1 && copy.matches("figure")) globalThis.obsFigures?.place(copy);
            if (copy.nodeType === 1 && copy.matches("figure")) {
                const image = copy.querySelector(":scope > img, :scope > svg.figure-visual");
                if (image && getComputedStyle(image).display !== "none") {
                    const style = getComputedStyle(copy);
                    const chrome = copy.getBoundingClientRect().height -
                        image.getBoundingClientRect().height +
                        parseFloat(style.marginBlockStart) + parseFloat(style.marginBlockEnd);
                    const available = content.clientHeight - chrome - 1;
                    if (available <= 0) throw new Error("Figure caption cannot fit the configured paper area.");
                    copy.style.setProperty("--figure-paper-image-height", `${available}px`);
                }
            }
            if (!live && node.nodeName === "PRE" && copy.scrollWidth > copy.clientWidth) {
                copy.style.fontSize = `${parseFloat(getComputedStyle(copy).fontSize) *
                    copy.clientWidth / copy.scrollWidth}px`;
                node.style.fontSize = copy.style.fontSize;
            }
            if (!live && node.nodeName === "TABLE") {
                node.style.minWidth = "0";
                copy.style.minWidth = "0";
            }
            if (copy.nodeType === 1) {
                const planned = (root) => [
                    ...(root.matches("table[data-column-plan]") ? [root] : []),
                    ...root.querySelectorAll("table[data-column-plan]"),
                ];
                const sources = planned(node);
                planned(copy).forEach((table, index) => {
                    // Wide tables are only fitted once they are placed on their landscape pages.
                    if (table.dataset.tableWide === "true" && !wideDepth) return;
                    const widths = globalThis.obsDataTable.fitStaticTable(table);
                    const source = sources[index];
                    if (!widths || !source || source === table) return;
                    [...source.querySelector(":scope > colgroup").children].forEach((column, position) => {
                        column.style.width = widths[position];
                    });
                    delete source.dataset.columnPlan;
                });
            }
            if (!live && node.nodeName === "TABLE" && !node.querySelector("colgroup")) {
                const cells = [...copy.querySelectorAll("thead tr:first-child > th")];
                const total = cells.reduce((sum, cell) => sum + cell.getBoundingClientRect().width, 0);
                if (total) {
                    const columns = document.createElement("colgroup");
                    cells.forEach((cell) => {
                        const column = document.createElement("col");
                        column.style.width = `${100 * cell.getBoundingClientRect().width / total}%`;
                        columns.append(column);
                    });
                    node.prepend(columns.cloneNode(true));
                    node.style.tableLayout = "fixed";
                    copy.prepend(columns);
                    copy.style.tableLayout = "fixed";
                }
            }
            const mixed = node.nodeType === 1 && !wideDepth &&
                node.querySelector('[data-table-wide="true"]');
            if (fits() && !mixed) {
                pageHasContent = true;
                return;
            }
            copy.remove();
            const whole = (live || logical) && node.nodeType === 1 &&
                node.matches(".data-table-shell, table, ol, ul, pre, p, .content-card") &&
                (!(wideDepth && node.matches(".data-table-shell, table")) ||
                    node.matches('[data-screen-page-breaks="false"]')) && !mixed;
            if (whole) {
                if (pageHasContent && !node.matches(".data-table-shell, table, ol, ul, pre")) newPage();
                parent().append(copy);
                pageHasContent = true;
                if (!fits()) {
                    content.closest(".paper-sheet").classList.add("paper-sheet-flexible");
                    expanded = true;
                }
                return;
            }
            if (pageHasContent && node.nodeType !== 3 && !overflowingContainer(node) &&
                    !(live && node.nodeName === "TR")) {
                newPage();
                parent().append(copy);
                if (fits()) {
                    pageHasContent = true;
                    return;
                }
                copy.remove();
            }
            if (live && node.nodeName === "TR") {
                const table = path.find((ancestor) => ancestor.nodeName === "TABLE");
                if (pageHasContent && containers.get(table)?.querySelector("tbody tr")) newPage();
                parent().append(copy);
                pageHasContent = true;
                if (!fits()) {
                    content.closest(".paper-sheet").classList.add("paper-sheet-flexible");
                    expanded = true;
                }
            } else if (!live && node.nodeName === "P" && !node.querySelector("img:not(.resource-icon *), svg:not(.resource-icon *)") && node.textContent.trim()) {
                splitParagraph(node);
            } else if (!live && node.nodeName === "TR") {
                splitRow(node);
            } else if (node.nodeType === 3) {
                if (live) {
                    parent().append(node);
                    pageHasContent = true;
                    return;
                }
                let remaining = node.textContent;
                while (remaining) {
                    const text = document.createTextNode("");
                    parent().append(text);
                    let low = 0;
                    let high = remaining.length;
                    while (low < high) {
                        const middle = Math.ceil((low + high) / 2);
                        text.textContent = remaining.slice(0, middle);
                        if (fits()) low = middle;
                        else high = middle - 1;
                    }
                    if (!low) {
                        text.remove();
                        if (!pageHasContent) throw new Error("Paper area is too small to fit text.");
                        newPage();
                        continue;
                    }
                    const boundary = remaining.slice(0, low).lastIndexOf(" ");
                    const count = low < remaining.length && boundary > 0 ? boundary + 1 : low;
                    text.textContent = remaining.slice(0, count);
                    pageHasContent = true;
                    remaining = remaining.slice(count);
                    if (remaining) newPage();
                }
            } else if (node.childNodes.length && !node.matches("img, svg")) {
                if (live && !originalChildren.has(node)) {
                    originalChildren.set(node, [...node.childNodes]);
                }
                path.push(node);
                placeChildren([...node.childNodes].filter((child) =>
                    !(node.tagName === "TABLE" && ["THEAD", "COLGROUP"].includes(child.nodeName)) &&
                    !child.matches?.("[data-table-filter-warning]"),
                ));
                path.pop();
            } else {
                throw new Error(`Content cannot fit the configured paper area: ${node.nodeName}`);
            }
        };
        const splitRow = (row) => {
            const cells = [...row.children];
            const remaining = cells.map((cell) => cell.cloneNode(true));
            while (remaining.some((cell) => cell.childNodes.length)) {
                const fragment = row.cloneNode(false);
                cells.forEach((cell) => fragment.append(cell.cloneNode(false)));
                parent().append(fragment);
                let advanced = false;
                remaining.forEach((cell, index) => {
                    const target = fragment.children[index];
                    const textNodes = [];
                    const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
                    while (walker.nextNode()) textNodes.push(walker.currentNode);
                    const length = textNodes.reduce((sum, text) => sum + text.length, 0);
                    const rangeFor = (count) => {
                        const range = document.createRange();
                        range.setStart(cell, 0);
                        let offset = count;
                        for (const text of textNodes) {
                            if (offset <= text.length) {
                                range.setEnd(text, offset);
                                return range;
                            }
                            offset -= text.length;
                        }
                        range.setEnd(cell, cell.childNodes.length);
                        return range;
                    };
                    let low = 0;
                    let high = length;
                    while (low < high) {
                        const middle = Math.ceil((low + high) / 2);
                        target.replaceChildren(rangeFor(middle).cloneContents());
                        if (fits()) low = middle;
                        else high = middle - 1;
                    }
                    if (low === length) {
                        target.replaceChildren(...cell.childNodes);
                        advanced ||= length > 0 || target.childNodes.length > 0;
                    } else {
                        const boundary = cell.textContent.slice(0, low).lastIndexOf(" ");
                        const count = boundary > 0 ? boundary + 1 : low;
                        const range = rangeFor(count);
                        target.replaceChildren(range.extractContents());
                        advanced ||= count > 0;
                    }
                });
                if (!advanced || !fits()) {
                    throw new Error("A table row cannot fit the configured paper area.");
                }
                pageHasContent = true;
                if (remaining.some((cell) => cell.childNodes.length)) newPage();
            }
        };
        const firstIsWide = (nodes) => {
            for (const node of nodes) {
                if ((node.nodeType === 3 && !node.textContent.trim()) || node.hidden || isHeading(node)) continue;
                if (node.nodeType !== 1) return false;
                if (node.matches('[data-table-wide="true"]')) return true;
                return node.matches("section, div, blockquote") && firstIsWide([...node.childNodes]);
            }
            return false;
        };
        const placeChildren = (nodes) => nodes.forEach((node, index) => {
            if (node.nodeType === 3 && !node.textContent.trim()) {
                place(node);
                return;
            }
            if (!wideDepth && pendingPortrait) {
                orient("portrait");
                pendingPortrait = false;
            }
            if (!wideDepth && isHeading(node) && firstIsWide(nodes.slice(index))) {
                orient("landscape");
                widePrelude = true;
            }
            const list = path[path.length - 1];
            if (node.nodeName === "LI" && list?.tagName === "OL") {
                listPositions.set(list, (Number(list.getAttribute("start")) || 1) +
                    nodes.slice(0, index).filter((item) => item.nodeName === "LI").length);
            }
            if (isHeading(node)) {
                const preview = leading(nodes.slice(index)).copies;
                parent().append(...preview);
                preview.forEach((copy) => {
                    if (copy.nodeType !== 1) return;
                    const paragraphs = copy.matches("[data-leading-paragraph]")
                        ? [copy] : [...copy.querySelectorAll("[data-leading-paragraph]")];
                    paragraphs.forEach((paragraph) => {
                        if (lineCount(paragraph) < 2 * data.reading.paragraphMinimumLines) return;
                        paragraph.style.maxHeight = `${parseFloat(getComputedStyle(paragraph).lineHeight) *
                            data.reading.paragraphMinimumLines}px`;
                        paragraph.style.overflow = "hidden";
                    });
                });
                const needsBreak = !fits() && pageHasContent;
                preview.forEach((copy) => copy.remove());
                if (needsBreak) newPage();
            }
            place(node);
        });
        placeChildren([...source.childNodes]);
        if (logicalPages) reserveUntil(logicalPages - 1);
        return tableAllocations;
    };
    const fixLinks = (destination, forPrint) => {
        const ids = new Set();
        destination.querySelectorAll("[id]").forEach((element) => {
            if (ids.has(element.id)) element.removeAttribute("id");
            else {
                ids.add(element.id);
                element.id = `${forPrint ? "pdf" : "page"}-${element.id}`;
            }
        });
        const companion = decodeURIComponent(window.location.pathname || "").split("/").pop() || "artifact.html";
        // A distinct document URL keeps Chromium from dropping unprinted same-file destinations.
        const companionLink = (fragment) => `${encodeURIComponent(companion)}?#${fragment}`;
        destination.querySelectorAll("a[href]").forEach((link) => {
            const href = link.getAttribute("href");
            if (forPrint && (link.hasAttribute("data-source-download") ||
                    /^(?:blob:|data:|obs-asset:)/i.test(href))) {
                const row = link.closest("[data-row-key]")?.dataset.rowKey;
                const owner = row?.startsWith("note:") ? row.slice(5)
                    : link.closest(".paper-sheet")?.dataset.pageChapter;
                link.setAttribute("href", companionLink(
                    !link.hasAttribute("data-source-download") && owner && !owner.startsWith("@")
                        ? owner : "home"));
                link.removeAttribute("download");
                return;
            }
            if (!href.startsWith("#")) return;
            const rawFragment = href.slice(1);
            const fragment = decodeURIComponent(rawFragment.split("?", 1)[0]);
            const sourceChapter = link.dataset.sourceChapter;
            const [slug, heading] = fragment.split("/", 2);
            const target = sourceChapter ? fragment : heading ? `${slug}--${heading}` : slug;
            if (forPrint) {
                const internal = ids.has(target);
                link.setAttribute("href", internal ? `#pdf-${target}`
                    : companionLink(sourceChapter ? `${sourceChapter}/@${fragment}` : rawFragment));
            }
        });
    };
    const layout = (destination, entries, forPrint, live = false, logical = false, allocations = null) => {
        destination.replaceChildren();
        destination.classList.toggle("logical-pages", logical);
        const sectionTitles = new Map(entries.filter((entry) => entry.title !== undefined)
            .map((entry) => [entry.slug, entry.title]));
        entries.forEach(({slug, source}) => {
            const start = destination.children.length;
            const tables = paginate(source, destination, slug, live, logical);
            if (logical) allocations?.set(slug, tables);
            const first = destination.children[start];
            if (!live) first.id = slug;
            if (slug === "@history") first.dataset.documentHistory = "";
            if (slug === "@metadata") first.dataset.documentMetadata = "";
        });
        if (!live) fixLinks(destination, forPrint);
        const starts = new Map();
        [...destination.children].forEach((sheet, index) => {
            if (!starts.has(sheet.dataset.pageChapter)) starts.set(sheet.dataset.pageChapter, index + 1);
        });
        destination.querySelectorAll("[data-contents-chapter]").forEach((number) => {
            number.textContent = String((live ? measuredStarts : starts).get(number.dataset.contentsChapter) || "");
        });
        [...destination.children].forEach((sheet, index) => {
            const metadataHtml = data.document.metadataHtml;
            const joined = (...keys) => keys.map((key) => metadataHtml[key]).filter(Boolean).join(" · ");
            const header = document.createElement("header");
            header.className = "paper-header";
            const identity = document.createElement("span");
            const section = document.createElement("span");
            const slug = sheet.dataset.pageChapter;
            const sectionTitle = data.notes.find((record) => record.slug === slug)?.title ||
                sectionTitles.get(slug) || "";
            // No text twice in one view: the title sheet's cover already shows the identity,
            // confidentiality and legal lines, and a sheet that shows its section's heading
            // leaves the section out of its running header.
            if (slug !== "home") {
                const headings = new Set([...sheet.querySelectorAll("h1, h2, h3, h4, h5, h6")]
                    .map((heading) => heading.textContent.trim()));
                [identity, section].forEach((line, index) => {
                    line.innerHTML = globalThis.obsRunningHeader.content(metadataHtml, slug, sectionTitle)[index];
                    if (headings.has(line.textContent.trim())) line.replaceChildren();
                });
            }
            header.append(identity, section);
            const footer = document.createElement("footer");
            footer.className = "paper-footer";
            const legal = document.createElement("div");
            legal.className = "paper-legal";
            legal.innerHTML = slug === "home" ? "" : joined("copyright", "confidentiality");
            const author = document.createElement("span");
            author.innerHTML = joined("authors", "organization");
            const reference = document.createElement("span");
            reference.innerHTML = joined("document number", "template");
            const number = document.createElement("span");
            number.className = "paper-page-number";
            const previous = [...destination.children].slice(0, index)
                .filter((item) => item.dataset.pageChapter === slug).length;
            number.textContent = live && !measuredStarts.size ? "Calculating pages…" :
                `Page ${live ? (measuredStarts.get(slug) || 1) + previous : index + 1} of ${
                    live ? measuredTotal : destination.children.length}`;
            if (live && !measuredStarts.size) {
                number.setAttribute("role", "status");
                number.setAttribute("aria-busy", "true");
            }
            footer.append(legal, author, reference, number);
            const pageIndex = live ? (measuredStarts.get(slug) || 1) + previous - 1 : index;
            sheet.dataset.pageSide = pageIndex % 2 ? "even" : "odd";
            sheet.prepend(header);
            sheet.append(footer);
        });
        if (forPrint) {
            printMediaBoxes = [...destination.children].map((sheet) => ({
                widthMillimeters: sheet.dataset.pageOrientation === "landscape"
                    ? paper.heightMillimeters : paper.widthMillimeters,
                heightMillimeters: sheet.dataset.pageOrientation === "landscape"
                    ? paper.widthMillimeters : paper.heightMillimeters,
            }));
        }
        return starts;
    };
    const showError = (error) => {
        const status = document.querySelector("[data-export-status]");
        status.textContent = `Page layout failed: ${error.message}`;
        status.hidden = false;
        console.error(status.textContent);
    };
    const showExportError = (error) => {
        const status = document.querySelector("[data-export-status]");
        status.textContent = `PDF export failed: ${error.message}`;
        status.hidden = false;
        console.error(status.textContent);
        // Ctrl+P has no visible control; a limited host's notice entry carries the reason instead.
        if (globalThis.obsCapabilities?.limit("printing")) globalThis.obsNotices.reveal("capability-printing");
    };
    const restoreLive = () => {
        const tables = new Map([...screen.querySelectorAll(
            "[data-data-table]:not([data-page-continuation])",
        )].map(
            (table) => [table.dataset.dataTable, table],
        ));
        const current = (node) => tables.get(node.dataset?.dataTable) ||
            globalThis.obsFigures?.pageNode(node) || node;
        [...originalChildren].reverse().forEach(([node, children]) => {
            if (node.dataset?.headingSection) {
                const fragment = [...screen.querySelectorAll("[data-heading-section]")].find(
                    (item) => item.dataset.headingSection === node.dataset.headingSection,
                );
                if (fragment) node.hidden = fragment.hidden;
            }
            node.replaceChildren(...children.map(current));
        });
        originalChildren.clear();
        if (liveNodes.length) body.replaceChildren(...liveNodes.map(current));
        liveNodes = [];
    };
    const refreshSheets = (reason = "") => {
        if (!paged) return;
        const hasVisibleContent = (node) => {
            if (node.nodeType === 3) return Boolean(node.textContent.trim());
            if (node.nodeType !== 1 || node.hidden ||
                    getComputedStyle(node).display === "none" ||
                    node.matches("[data-review-gutter]")) return false;
            if (node.matches("img, svg, math, input, textarea, hr")) return true;
            return [...node.childNodes].some(hasVisibleContent);
        };
        screen.querySelectorAll(".paper-sheet").forEach((sheet) => {
            sheet.hidden = !hasVisibleContent(sheet.querySelector(".paper-content"));
        });
        document.dispatchEvent(new CustomEvent("obs-pages-layout", {
            detail: reason ? {reason} : null,
        }));
    };
    const invalidateMeasurements = () => {
        measuredStarts.clear();
        measuredTableAllocations.clear();
        provisionalCounts = new Map();
        provisionalAllocations = new Map();
        measurementEpoch++;
    };
    const measureProvisionally = (slug) => {
        if (measuredStarts.size || provisionalCounts.has(slug) || slug === "home" ||
                !artifact.exportChapters().some(record => record.slug === slug)) return;
        printed.classList.add("measuring-pages");
        try {
            layout(printed, [{slug, source: sourceFor(slug)}], false, false, true, provisionalAllocations);
            provisionalCounts.set(slug, printed.children.length);
        } finally {
            printed.replaceChildren();
            printed.classList.remove("measuring-pages");
        }
    };
    const scheduleMeasurements = () => {
        if (measurementScheduled || printing) return;
        measurementScheduled = true;
        const measure = async () => {
            const epoch = measurementEpoch;
            const counts = new Map();
            const allocations = new Map();
            try {
                const entries = groups(artifact.exportChapters(), null, false);
                const chapters = artifact.exportChapters();
                for (const entry of [...entries, ...chapters.map(record => ({slug: record.slug}))]) {
                    await globalThis.obsStartup.yield();
                    if (printing || epoch !== measurementEpoch) return;
                    printed.classList.add("measuring-pages");
                    try {
                        layout(printed, [{slug: entry.slug, source: entry.source || sourceFor(entry.slug),
                            title: entry.title}],
                            false, false, true, allocations);
                        counts.set(entry.slug, printed.children.length);
                    } finally {
                        printed.replaceChildren();
                        printed.classList.remove("measuring-pages");
                    }
                }
                if (epoch !== measurementEpoch) return;
                measuredCounts = counts;
                measuredTableAllocations = allocations;
                let total = 0;
                measuredCounts.forEach((count, slug) => {
                    measuredStarts.set(slug, total + 1);
                    total += count;
                });
                measuredTotal = total;
                renderScreen("measurement");
            } finally {
                measurementScheduled = false;
                if (!measuredStarts.size && !printing && epoch !== measurementEpoch) scheduleMeasurements();
            }
        };
        globalThis.obsStartup.defer("Page numbering", measure);
    };
    let screenSlug = null;
    // Page counts and wide-table slots each live chapter was laid out with.
    let screenBasis = new Map();
    const allocationKey = (allocation) => JSON.stringify([...(allocation || [])]);
    // Measurement only changes the live layout when its page counts or wide-table slots differ
    // from those the shown sheets were laid out with; otherwise renumber in place so live
    // tables stay attached.
    const renumberScreen = () => {
        if (!screen.isConnected || screenSlug !== chapter.dataset.chapter) return false;
        const sheets = [...screen.children].filter(sheet => sheet.matches(".paper-sheet"));
        if (!sheets.length) return false;
        const bySlug = new Map();
        sheets.forEach(sheet => {
            const slug = sheet.dataset.pageChapter;
            if (!bySlug.has(slug)) bySlug.set(slug, []);
            bySlug.get(slug).push(sheet);
        });
        for (const [slug, chapterSheets] of bySlug) {
            const basis = screenBasis.get(slug);
            if (!basis || measuredCounts.get(slug) !== chapterSheets.length ||
                    basis.count !== chapterSheets.length ||
                    basis.allocation !== allocationKey(measuredTableAllocations.get(slug))) return false;
        }
        screen.querySelectorAll("[data-contents-chapter]").forEach(number => {
            number.textContent = String(measuredStarts.get(number.dataset.contentsChapter) || "");
        });
        bySlug.forEach((chapterSheets, slug) => chapterSheets.forEach((sheet, previous) => {
            const pageIndex = (measuredStarts.get(slug) || 1) + previous - 1;
            const number = sheet.querySelector(":scope > .paper-footer .paper-page-number");
            if (number) {
                number.textContent = `Page ${pageIndex + 1} of ${measuredTotal}`;
                number.removeAttribute("role");
                number.removeAttribute("aria-busy");
            }
            sheet.dataset.pageSide = pageIndex % 2 ? "even" : "odd";
        }));
        return true;
    };
    const renderScreen = (reason = "") => {
        if (!paged || printing) return;
        if (reason === "measurement" && renumberScreen()) {
            refreshSheets(reason);
            return;
        }
        try {
            if (screen.isConnected) restoreLive();
            else {
                originalChildren.clear();
                liveNodes = [];
            }
            const slug = chapter.dataset.chapter;
            screenSlug = slug;
            const selected = artifact.exportChapters();
            if (!measuredStarts.size) {
                if (globalThis.obsStartup) scheduleMeasurements();
                else {
                    printed.classList.add("measuring-pages");
                    try {
                        measuredTableAllocations = new Map();
                        measuredStarts = layout(printed, groups(selected), false, false, true,
                            measuredTableAllocations);
                        measuredCounts = new Map();
                        [...printed.children].forEach(sheet => {
                            const slug = sheet.dataset.pageChapter;
                            measuredCounts.set(slug, (measuredCounts.get(slug) || 0) + 1);
                        });
                        measuredTotal = printed.children.length;
                    } finally {
                        printed.replaceChildren();
                        printed.classList.remove("measuring-pages");
                    }
                }
            }
            if (!measuredStarts.size && globalThis.obsStartup) measureProvisionally(slug);
            liveNodes = [...body.childNodes].filter((node) => node !== screen);
            const source = document.createElement("div");
            source.append(...liveNodes);
            const entries = slug === "home" ? groups(selected, source, false)
                : [{slug, source}];
            body.replaceChildren(screen);
            screen.classList.add("laying-out");
            screenBasis = new Map();
            const counts = measuredStarts.size ? measuredCounts : provisionalCounts;
            const allocations = measuredStarts.size ? measuredTableAllocations : provisionalAllocations;
            entries.forEach(entry => {
                if (counts.has(entry.slug)) screenBasis.set(entry.slug, {
                    count: counts.get(entry.slug), allocation: allocationKey(allocations.get(entry.slug)),
                });
            });
            try {
                layout(screen, entries, false, true);
            } finally {
                screen.classList.remove("laying-out");
            }
            refreshSheets(reason);
        } catch (error) {
            showError(error);
            setPaged(false);
        }
    };
    const setPaged = (enabled) => {
        paged = enabled;
        chapter.hidden = false;
        screen.hidden = !enabled;
        root.classList.toggle("paged-mode", enabled);
        root.classList.toggle("screens-mode", !enabled && data.reading.layout === "screens");
        const toggle = document.querySelector("[data-pages-toggle]");
        if (toggle) toggle.checked = enabled;
        if (enabled) renderScreen();
        else {
            restoreLive();
            screen.replaceChildren();
        }
        document.dispatchEvent(new CustomEvent("obs-pages-layout"));
    };
    const preparePrint = () => {
        printing = true;
        root.classList.add("preparing-print");
        layout(printed, groups(artifact.exportChapters()), true);
    };
    const finishPrint = () => {
        printing = false;
        root.classList.remove("preparing-print");
        printed.replaceChildren();
        renderScreen();
    };
    const waitForPrintAssets = async (container) => {
        const controller = new AbortController();
        let timeout;
        const prepare = async () => {
            globalThis.obsAssets?.hydrate(container);
            if (globalThis.obsPayload) {
                globalThis.obsPayload.hydrate(container);
                await globalThis.obsPayload.ready();
            }
            if (window.obsFigures) await window.obsFigures.preparePrint(container);
            const readiness = [...container.querySelectorAll("img")].map(async (image) => {
                image.loading = "eager";
                const label = image.alt || image.getAttribute("src") || "unnamed image";
                if (!image.complete) {
                    await new Promise((resolve, reject) => {
                        image.addEventListener("load", resolve, {once: true, signal: controller.signal});
                        image.addEventListener("error", () => reject(
                            new Error(`Image could not load: ${label}`),
                        ), {once: true, signal: controller.signal});
                    });
                }
                if (!image.naturalWidth) throw new Error(`Image could not load: ${label}`);
                if (image.decode) {
                    try {
                        await image.decode();
                    } catch (error) {
                        throw new Error(`Image could not decode: ${label}: ${error.message}`);
                    }
                }
            });
            if (document.fonts) readiness.push(document.fonts.ready);
            await Promise.all(readiness);
        };
        try {
            await Promise.race([
                prepare(),
                new Promise((_resolve, reject) => {
                    timeout = globalThis.setTimeout(() => reject(new Error(
                        "Timed out waiting for print images or fonts. Check image access and retry.",
                    )), data.printReadyTimeoutMilliseconds);
                }),
            ]);
        } finally {
            globalThis.clearTimeout(timeout);
            controller.abort();
        }
    };
    const exportPDF = () => {
        if (exportPending) return exportPending;
        exportPending = (async () => {
            // Canary: a host that refuses the print dialog never prints, so do not prepare.
            if (globalThis.obsCapabilities?.limit("printing")) {
                throw new Error(globalThis.obsCapabilities?.explain("printing"));
            }
            await globalThis.obsHtmlReady;
            await artifact.whenChapterReady?.();
            document.dispatchEvent(new CustomEvent("obs-print-start"));
            printing = true;
            root.classList.add("preparing-print");
            try {
                const entries = groups(artifact.exportChapters());
                printed.replaceChildren(...entries.map(({source}) => source));
                await waitForPrintAssets(printed);
                layout(printed, entries, true);
                await waitForPrintAssets(printed);
                await new Promise((resolve, reject) => {
                    requestAnimationFrame(() => {
                        try {
                            // Where the canary could not tell, a print dialog that never opened
                            // (no beforeprint) means the host ignored the call: undo the preparation.
                            let opened = false;
                            const open = () => { opened = true; };
                            window.addEventListener("beforeprint", open, {once: true});
                            window.print();
                            window.removeEventListener("beforeprint", open);
                            if (!opened && globalThis.obsCapabilities?.undecided("printing")) {
                                finishPrint();
                                reject(new Error(globalThis.obsCapabilities?.fail("printing",
                                    "window.print() returned without opening the print dialog (no beforeprint)")));
                            } else resolve();
                        } catch (error) {
                            finishPrint();
                            reject(error);
                        }
                    });
                });
            } catch (error) {
                finishPrint();
                throw error;
            }
        })().finally(() => {
            exportPending = null;
        });
        return exportPending;
    };
    document.addEventListener("obs-chapter-change", () => renderScreen());
    document.addEventListener("obs-chapter-content-changing", () => {
        if (!paged) return;
        restoreLive();
        screen.replaceChildren();
    });
    document.addEventListener("obs-chapter-content-ready", () => renderScreen());
    document.addEventListener("obs-artifact-filter", () => {
        invalidateMeasurements();
        renderScreen();
    });
    let tableLayoutRestored = false;
    document.addEventListener("obs-table-before-change", (event) => {
        if (!paged || !screen.contains(event.target)) return;
        tableLayoutRestored = true;
        restoreLive();
        screen.replaceChildren();
    });
    document.addEventListener("obs-table-change", (event) => {
        if (event.detail?.reason === "detail-selection") return;
        if (tableLayoutRestored) {
            tableLayoutRestored = false;
            renderScreen(event.detail?.reason === "row-details" ? "row-details" : "");
        } else refreshSheets("table-change");
    });
    document.addEventListener("obs-table-definition-change", () => {
        renderScreen();
    });
    document.addEventListener("obs-section-toggle", refreshSheets);
    reader.addEventListener("load", (event) => {
        if (event.target.tagName === "IMG" && !event.target.closest(".resource-icon") && paged) {
            renderScreen();
        }
    }, true);
    window.addEventListener("resize", refreshSheets);
    document.addEventListener("keydown", event => {
        if (!(event.ctrlKey || event.metaKey) || event.altKey || event.key.toLowerCase() !== "p") return;
        event.preventDefault();
        exportPDF().catch(showExportError);
    });
    window.addEventListener("beforeprint", () => {
        if (!printing) {
            try {
                preparePrint();
            } catch (error) {
                finishPrint();
                showError(error);
            }
        }
    });
    window.addEventListener("afterprint", finishPrint);
    globalThis.obsPages = {
        setPaged, exportPDF,
        get printMediaBoxes() {
            return printMediaBoxes.map((box) => ({...box}));
        },
    };
    setPaged(data.reading.layout === "paged");
})();
