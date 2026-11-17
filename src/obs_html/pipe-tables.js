// Pipe tables, one line per row (generic-tables.md, Pipe tables; features.py, the pipe-tables feature's
// part pipe-table-rows-one-line, which artifact.tableRowsOneLine turns on): on screen each body cell's
// content sits in one box clamped to one line (base.css), a cut cell keeps its whole text as its title,
// and a row with a cut cell has a disclosure that shows its cells in full. Only the live reading view's
// tables change: the print book is drawn from the notes' HTML (pages.js), so it holds none of this.
(() => {
    "use strict";

    // The pure layer: measurements and states in, decisions out.

    // Whether a clamped box is cut: its content overflows it (its scroll and client sizes in).
    const isCut = ({scrollHeight, clientHeight, scrollWidth, clientWidth}) =>
        scrollHeight - clientHeight > 1 || scrollWidth - clientWidth > 1;
    // Whether a row has its disclosure: an open row keeps it, a closed row has it exactly while a cell
    // is cut, and a closed row whose cells could not be measured (cut null) keeps what it had.
    const rowDisclosure = ({open, cut, had}) => open || (cut === null ? had : cut);
    // A cell's whole text as its title: its lines (a line break or a block starts one), each with its
    // white space collapsed, the empty ones left out, one per title line.
    const wholeText = lines => lines.map(line => line.replace(/\s+/g, " ").trim()).filter(Boolean).join("\n");
    // The disclosure's accessible name: what it does and the row's first cell.
    const toggleLabel = (open, name) => `${open ? "Collapse" : "Expand"} ${name}`.trim();

    // The wiring: the chapter's pipe tables, their boxes, cuts and disclosures.

    const chapterBody = document.querySelector("[data-chapter-body]");
    const media = "img:not(.resource-icon *), svg:not(.resource-icon *), picture, video, .math.block";
    const blocks = new Set(["ADDRESS", "BLOCKQUOTE", "DD", "DIV", "DL", "DT", "FIGCAPTION", "FIGURE", "H1", "H2",
        "H3", "H4", "H5", "H6", "HR", "LI", "OL", "P", "PRE", "SECTION", "TABLE", "TR", "UL"]);
    const prepared = new WeakSet();
    // The tables render.py's _table wrote, in the chapter body outside a Base table, its details included.
    const pipeTables = () => chapterBody ? [...chapterBody.querySelectorAll("table")].filter(table =>
        !table.closest("[data-data-table], [data-review-table], figure, [data-artifact-figure]")) : [];
    const bodyRows = table => [...table.tBodies].flatMap(body => [...body.rows]);
    const boxes = row => [...row.cells].flatMap(cell => [...cell.children].filter(child =>
        child.matches(".pipe-table-box")));
    const textLines = root => {
        const lines = [""];
        const visit = node => {
            if (node.nodeType === 3) {
                lines[lines.length - 1] += node.textContent;
                return;
            }
            if (node.nodeType !== 1 || node.matches("button, [data-review-gutter]")) return;
            if (node.tagName === "BR") {
                lines.push("");
                return;
            }
            const block = blocks.has(node.tagName);
            if (block) lines.push("");
            node.childNodes.forEach(visit);
            if (block) lines.push("");
        };
        visit(root);
        return lines;
    };
    const shown = element => element.isConnected && element.getClientRects().length > 0;
    const observer = typeof ResizeObserver === "function"
        ? new ResizeObserver(entries => entries.forEach(entry => measure(entry.target))) : null;

    const prepare = table => {
        if (prepared.has(table)) return;
        prepared.add(table);
        table.dataset.pipeRowsOneLine = "";
        bodyRows(table).forEach(row => [...row.cells].forEach(cell => {
            if (cell.querySelector(media)) return;
            const box = document.createElement("div");
            box.className = "pipe-table-box";
            box.append(...[...cell.childNodes].filter(node => !node.matches?.("[data-review-gutter]")));
            cell.append(box);
        }));
        observer?.observe(table);
    };

    const toggleOf = row => row.cells[0]?.querySelector(":scope > [data-pipe-row-toggle]") || null;
    const showToggle = (row, toggle) => {
        const open = "pipeRowOpen" in row.dataset;
        toggle.setAttribute("aria-expanded", String(open));
        const first = row.cells[0]?.querySelector(":scope > .pipe-table-box") || row.cells[0];
        toggle.setAttribute("aria-label", toggleLabel(open, wholeText(textLines(first)).replace(/\n/g, " ")));
        globalThis.obsAssets.replace(toggle, open ? "expanded" : "collapsed");
    };
    // A cut cell takes its whole text as its title; a cell no longer cut loses the title it took.
    const markCuts = row => {
        let cut = false;
        boxes(row).forEach(box => {
            const cell = box.parentElement;
            if (isCut(box)) {
                cut = true;
                cell.dataset.pipeCellCut = "";
                cell.title = wholeText(textLines(box));
            } else if ("pipeCellCut" in cell.dataset) {
                delete cell.dataset.pipeCellCut;
                cell.removeAttribute("title");
            }
        });
        return cut;
    };
    const measureRow = row => {
        const open = "pipeRowOpen" in row.dataset;
        const cut = open || !shown(row) ? null : markCuts(row);
        const toggle = toggleOf(row);
        const wanted = rowDisclosure({open, cut, had: Boolean(toggle)});
        if (wanted && !toggle) {
            const added = document.createElement("button");
            added.type = "button";
            added.className = "disclosure-toggle pipe-table-row-toggle";
            added.dataset.pipeRowToggle = "";
            added.addEventListener("click", () => setOpen([row], !("pipeRowOpen" in row.dataset)));
            row.cells[0].prepend(added);
            showToggle(row, added);
            // The disclosure narrows the first cell, which may cut it: its title follows.
            markCuts(row);
        } else if (!wanted && toggle) toggle.remove();
    };
    function measure(table) {
        if (!prepared.has(table) || !shown(table)) return;
        bodyRows(table).forEach(measureRow);
    }
    // Opens or closes rows; a sheet shown as pages lays out again, as for a Base row's details.
    const setOpen = (rows, open) => {
        if (!rows.length) return;
        const table = rows[0].closest("table");
        table.dispatchEvent(new CustomEvent("obs-table-before-change", {bubbles: true}));
        rows.forEach(row => {
            if (open) row.dataset.pipeRowOpen = "";
            else delete row.dataset.pipeRowOpen;
            const toggle = toggleOf(row);
            if (toggle) showToggle(row, toggle);
            if (!open) measureRow(row);
        });
        table.dispatchEvent(new CustomEvent("obs-table-change", {bubbles: true, detail: {reason: "row-details"}}));
    };
    // Opens each closed row whose cut cell holds one of the nodes (a Search highlight, a comment's
    // text), so it shows; whether one opened.
    const reveal = nodes => {
        const rows = new Map();
        [...nodes].forEach(node => {
            const cell = (node?.nodeType === 1 ? node : node?.parentElement)?.closest("td, th");
            const row = cell?.parentElement;
            const table = row?.closest("table");
            if (!row || !prepared.has(table) || !("pipeCellCut" in cell.dataset) || "pipeRowOpen" in row.dataset) return;
            if (!rows.has(table)) rows.set(table, new Set());
            rows.get(table).add(row);
        });
        rows.forEach(tableRows => setOpen([...tableRows], true));
        return rows.size > 0;
    };

    const refresh = () => pipeTables().forEach(table => {
        prepare(table);
        measure(table);
    });
    ["obs-chapter-change", "obs-chapter-content-ready", "obs-pages-layout", "obs-section-toggle"]
        .forEach(type => document.addEventListener(type, refresh));

    globalThis.obsPipeTables = {isCut, rowDisclosure, wholeText, toggleLabel, reveal};
})();
