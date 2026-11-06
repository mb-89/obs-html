(() => {
    const renderFilterFields = ({container, facets, onSelect, isSelected = () => false}) => {
        container.replaceChildren();
        facets.forEach(({field, label, values, counts}) => {
            const wrapper = document.createElement("div");
            wrapper.className = "filter-field";
            wrapper.dataset.field = field;
            const trigger = document.createElement("button");
            trigger.type = "button";
            trigger.className = "filter-pill filter-field-button";
            trigger.setAttribute("aria-expanded", "false");
            trigger.setAttribute("aria-label", `${label}; ${values.length} unique values`);
            trigger.textContent = label;
            const distinct = document.createElement("small");
            distinct.textContent = String(values.length);
            trigger.append(distinct);
            const menu = document.createElement("div");
            menu.className = "filter-values";
            menu.setAttribute("popover", "auto");
            menu.setAttribute("role", "menu");
            menu.setAttribute("aria-label", `${field} values`);
            values.forEach(value => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "filter-value";
                button.dataset.filterValue = value;
                button.setAttribute("role", "menuitemcheckbox");
                button.setAttribute("aria-checked", String(isSelected(field, value)));
                const text = document.createElement("span");
                text.textContent = value;
                const count = document.createElement("small");
                count.textContent = String(counts[value]);
                button.append(text, count);
                button.addEventListener("click", () => {
                    onSelect(field, value);
                    container.querySelectorAll("[data-filter-value]").forEach(candidate =>
                        candidate.setAttribute("aria-checked", String(isSelected(
                            candidate.closest(".filter-field").dataset.field,
                            candidate.dataset.filterValue,
                        ))));
                });
                menu.append(button);
            });
            let wasOpen = false;
            trigger.addEventListener("pointerdown", () => {wasOpen = menu.matches(":popover-open");});
            trigger.addEventListener("click", () => {
                if (wasOpen || menu.matches(":popover-open")) {
                    wasOpen = false;
                    menu.hidePopover();
                    return;
                }
                wasOpen = false;
                menu.style.maxWidth = `${window.innerWidth - 16}px`;
                menu.style.minWidth = `${trigger.offsetWidth}px`;
                menu.showPopover();
                trigger.setAttribute("aria-expanded", "true");
                const bounds = trigger.getBoundingClientRect();
                const size = menu.getBoundingClientRect();
                menu.style.left = `${Math.max(8, Math.min(bounds.left, window.innerWidth - size.width - 8))}px`;
                menu.style.top = `${bounds.bottom + 4 + size.height <= window.innerHeight - 8
                    ? bounds.bottom + 4 : Math.max(8, bounds.top - size.height - 4)}px`;
            });
            menu.addEventListener("toggle", event => {
                if (event.newState === "closed") trigger.setAttribute("aria-expanded", "false");
            });
            wrapper.append(trigger, menu);
            container.append(wrapper);
        });
    };
    // Automatic column sizing derives every width from content; there are no per-column constants.
    const blockElements = new Set([
        "ADDRESS", "BLOCKQUOTE", "BR", "DD", "DIV", "DL", "DT", "FIGCAPTION", "FIGURE", "H1", "H2", "H3",
        "H4", "H5", "H6", "HR", "LI", "OL", "P", "PRE", "SECTION", "TABLE", "TR", "UL",
    ]);
    // Unwrapped text lines of rendered cell content; editors contribute their current value.
    const contentLines = (root) => {
        const lines = [""];
        let editor = null;
        const visit = (node) => {
            if (node.nodeType === 3) {
                lines[lines.length - 1] += node.textContent.replace(/\s+/g, " ");
                return;
            }
            if (node.nodeType !== 1 || node.hidden || node.matches("button.disclosure-toggle, svg")) return;
            if (node.matches("input, textarea")) {
                editor ||= node;
                String(node.value).split("\n").forEach((line, index) => {
                    if (index) lines.push("");
                    lines[lines.length - 1] += line;
                });
                return;
            }
            const block = blockElements.has(node.tagName);
            if (block) lines.push("");
            if (node.tagName === "PRE") {
                node.textContent.split("\n").forEach((line, index) => {
                    if (index) lines.push("");
                    lines[lines.length - 1] += line;
                });
            } else node.childNodes.forEach(visit);
            if (block) lines.push("");
        };
        visit(root);
        return {lines: lines.map((line) => line.trim()).filter(Boolean), editor};
    };
    const textCanvas = document.createElement("canvas").getContext("2d");
    const widestLine = (lines, font) => {
        textCanvas.font = font;
        return lines.reduce((widest, line) => Math.max(widest, textCanvas.measureText(line).width), 0);
    };
    const inlineChrome = (style) => parseFloat(style.paddingInlineStart) + parseFloat(style.paddingInlineEnd) +
        parseFloat(style.borderInlineStartWidth) + parseFloat(style.borderInlineEndWidth);

    // Columns with an explicit `width` (icon slots or a reader's session resize) keep it. Every
    // other column wants its unwrapped content width (`max`): short columns receive it in full,
    // and the columns that cannot fit share the remainder equally, never below their `floor`.
    // Columns with an authored `weight` (a view's columnSize) share what the others leave in
    // proportion to it, never below their `floor`; without an available width they get `max`.
    // Unused width goes to the flexible column. Without an available width, all columns get `max`.
    const fitColumns = (specs, available, flexible = specs.length - 1) => {
        const widths = specs.map((spec) => spec.width ?? null);
        const weighted = specs.flatMap((spec, index) => widths[index] === null && spec.weight ? [index] : []);
        const reserved = weighted.reduce((total, index) => total + specs[index].floor, 0);
        let pending = specs.flatMap((spec, index) => widths[index] === null && !spec.weight ? [index] : []);
        let budget = (available > 0 ? available : Infinity) - reserved -
            widths.reduce((total, width) => total + (width ?? 0), 0);
        while (pending.length) {
            const share = budget / pending.length;
            const fitting = pending.filter((index) => specs[index].max <= share);
            if (!fitting.length) break;
            fitting.forEach((index) => {
                widths[index] = specs[index].max;
                budget -= specs[index].max;
            });
            pending = pending.filter((index) => widths[index] === null);
        }
        while (pending.length) {
            const share = Math.max(0, Math.floor(budget / pending.length));
            const floored = pending.filter((index) => specs[index].floor > share);
            if (!floored.length) {
                pending.forEach((index) => { widths[index] = share; });
                break;
            }
            floored.forEach((index) => {
                widths[index] = specs[index].floor;
                budget -= specs[index].floor;
            });
            pending = pending.filter((index) => widths[index] === null);
        }
        let remaining = budget + reserved;
        let open = weighted;
        while (open.length) {
            if (remaining === Infinity) {
                open.forEach((index) => { widths[index] = specs[index].max; });
                break;
            }
            const weight = open.reduce((total, index) => total + specs[index].weight, 0);
            const share = (index) => Math.floor(Math.max(0, remaining) * specs[index].weight / weight);
            const floored = open.filter((index) => specs[index].floor > share(index));
            if (!floored.length) {
                open.forEach((index) => { widths[index] = share(index); });
                break;
            }
            floored.forEach((index) => {
                widths[index] = specs[index].floor;
                remaining -= specs[index].floor;
            });
            open = open.filter((index) => widths[index] === null);
        }
        const total = widths.reduce((sum, width) => sum + width, 0);
        if (available > total && specs[flexible] && !specs[flexible].fixed) {
            widths[flexible] += available - total;
        }
        return widths;
    };

    // Static (print/PDF) tables are sized once they are laid out in their actual paper container.
    const fitStaticTable = (table) => {
        const plan = JSON.parse(table.dataset.columnPlan || "null");
        const columns = [...(table.querySelector(":scope > colgroup")?.children || [])];
        const headers = [...(table.querySelector(":scope > thead > tr")?.children || [])];
        if (!plan || !table.isConnected || !table.clientWidth ||
            columns.length !== plan.columns.length || headers.length !== columns.length) return null;
        const rows = [...table.querySelectorAll(":scope > tbody > tr")]
            .filter((row) => row.children.length === columns.length);
        const specs = plan.columns.map((column, index) => {
            if (column.width) return column;
            const header = headers[index];
            const headerStyle = getComputedStyle(header);
            const label = column.hideLabel ? 0 : Math.ceil(widestLine(contentLines(header).lines,
                headerStyle.font) + inlineChrome(headerStyle)) + 1;
            let max = label;
            if (column.weight) return {weight: column.weight, max: Math.max(column.weight, label), floor: label};
            rows.forEach((row) => {
                const cell = row.children[index];
                const style = getComputedStyle(cell);
                max = Math.max(max, widestLine(contentLines(cell).lines, style.font) + inlineChrome(style));
            });
            max = Math.ceil(max) + 1;
            return {max, floor: Math.min(max, Math.max(plan.minimum, label))};
        });
        const flexible = specs.findLastIndex((spec) => !spec.fixed);
        const widths = fitColumns(specs, table.clientWidth, flexible);
        const total = widths.reduce((sum, width) => sum + width, 0);
        const percentages = widths.map((width) => `${100 * width / total}%`);
        columns.forEach((column, index) => { column.style.width = percentages[index]; });
        delete table.dataset.columnPlan;
        return percentages;
    };

    const anchorSlug = (value) => String(value).toLocaleLowerCase()
        .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "value";

    // Group labels follow a reader sort on the grouped property, else the authored groupOrder
    // (unlisted labels last), else the groupBy direction (generic-tables).
    const compareGroupLabels = (level, sort) => (left, right) => {
        if (!sort && level.order) {
            const rank = label => {
                const index = level.order.indexOf(label);
                return index < 0 ? level.order.length : index;
            };
            const ranked = rank(left) - rank(right);
            if (ranked) return ranked;
        }
        const result = left.localeCompare(right, undefined, {numeric: true});
        return (sort?.direction || level.direction) === "DESC" ? -result : result;
    };

    const retainMatchesAndAncestors = (rows, query) => {
        if (query.empty) return rows;
        const byKey = new Map(rows.map((row) => [row.key, row]));
        const retained = new Set();
        rows.filter((row) => query.match(row)).forEach((row) => {
            let current = row;
            while (current && !retained.has(current.key)) {
                retained.add(current.key);
                current = byKey.get(current.parentKey);
            }
        });
        return rows.filter((row) => retained.has(row.key));
    };

    const render = ({
        key, columns: initialColumns, availableColumns = initialColumns, fieldCatalog, rows,
        views = [], activeView = 0, onViewChange,
        maxRows, wide = false, columnDetails = false, pagination = true,
        compact = false, minimumColumnWidth = JSON.parse(
            document.querySelector("[data-artifact-data]").textContent,
        )[compact ? "tableCompactColumnMinimumPixels" : "tableColumnMinimumPixels"],
        showEmptyDetailTabs = false, screenPageBreaks = true,
        initialRowKeys, onRowKeysChange,
        columnSizing, detailFontSize = JSON.parse(
            document.querySelector("[data-artifact-data]").textContent,
        ).tableDetailFontSizePoints,
        baseExpression = "", initialExpression = "", initialGroup = [], initialSort = [],
        baseQuery = globalThis.obsQuery.compile(baseExpression),
        definitionText = "", queryView = false, onDefinitionDraft, onDefinitionChange,
        initialPresentation, onPresentationChange, initialColumnWidths, onColumnWidthsChange,
        initialDetailState, onDetailStateChange,
        hasDetails: computeHasDetails = () => false, renderDetails, renderOwnerDetails,
        initialPageSize = JSON.parse(
            document.querySelector("[data-artifact-data]").textContent,
        ).tablePageSize,
    }) => {
        const detailAvailability = new Map();
        const hasDetails = row => {
            if (!detailAvailability.has(row.key)) {
                detailAvailability.set(row.key, computeHasDetails(row));
            }
            return detailAvailability.get(row.key);
        };
        if (!Number.isSafeInteger(initialPageSize) || initialPageSize < 1) {
            throw new Error("Initial table page size must be a positive whole number.");
        }
        if (maxRows !== undefined && (!Number.isInteger(maxRows) || maxRows < 1)) {
            throw new Error("Table viewport row threshold must be a positive whole number.");
        }
        const shell = document.createElement("section");
        shell.className = "data-table-shell";
        shell.dataset.dataTable = key;
        if (wide) shell.dataset.tableWide = "true";
        if (!screenPageBreaks) shell.dataset.screenPageBreaks = "false";
        if (compact) shell.dataset.compact = "true";
        const iconColumn = availableColumns.find(column => column.fixed);
        if (iconColumn) shell.style.setProperty("--table-icon-width", `${iconColumn.width}px`);

        const controls = document.createElement("div");
        controls.className = "data-table-controls";
        const optionsToggle = document.createElement("button");
        optionsToggle.className = "icon-button data-table-options-toggle";
        optionsToggle.type = "button";
        optionsToggle.setAttribute("aria-label", "Table options");
        optionsToggle.setAttribute("aria-expanded", "false");
        optionsToggle.title = "Table options";
        globalThis.obsAssets.replace(optionsToggle, "options");
        const filterBadge = globalThis.obsAssets.create("filter");
        filterBadge.classList.add("filter-status-icon");
        optionsToggle.append(filterBadge);
        const options = document.createElement("div");
        options.className = "data-table-options";
        options.setAttribute("popover", "manual");
        options.hidden = true;
        const input = document.createElement("input");
        input.className = "data-table-filter";
        input.type = "search";
        input.setAttribute("aria-label", "Filter table");
        input.placeholder = "Filter table";
        input.dataset.hoverHelp = 'Use field:value, /regex/ (/regex/c matches case), AND, OR, NOT, and nested parentheses.';
        const status = document.createElement("span");
        status.className = "data-table-status";
        status.setAttribute("aria-live", "polite");
        status.hidden = true;
        const panelTabs = document.createElement("div");
        panelTabs.className = "filter-pills";
        const panels = new Map();
        const panelButtons = new Map();
        const makePanel = (name, label) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "filter-pill";
            button.textContent = label;
            button.title = label;
            button.setAttribute("aria-expanded", "false");
            const panel = document.createElement("section");
            panel.className = "data-table-panel";
            panel.setAttribute("aria-label", label);
            panel.hidden = true;
            button.addEventListener("click", () => {
                const open = panel.hidden;
                panels.forEach((other, key) => {
                    other.hidden = key !== name || !open;
                    panelButtons.get(key).setAttribute(
                        "aria-expanded", String(key === name && open),
                    );
                });
            });
            panels.set(name, panel);
            panelButtons.set(name, button);
            panelTabs.append(button);
            return panel;
        };
        const filterPanel = makePanel("filter", "Filter");
        filterPanel.append(input, status);
        const orderPanel = makePanel("order", "Group / Sort");
        const propertyPanel = makePanel("properties", "Properties");
        const propertyInput = document.createElement("input");
        propertyInput.type = "search";
        propertyInput.placeholder = "Find a property";
        propertyInput.className = "data-table-filter";
        propertyInput.setAttribute("aria-label", "Find a property");
        const propertyList = document.createElement("div");
        propertyList.className = "filter-pills";
        propertyPanel.append(propertyInput, propertyList);
        options.append(panelTabs, ...panels.values());
        const queryEditor = document.createElement("textarea");
        queryEditor.className = "data-table-query-editor";
        queryEditor.setAttribute("aria-label", "Table base YAML definition");
        queryEditor.spellcheck = false;
        queryEditor.value = definitionText;
        queryEditor.hidden = !queryView;
        const queryError = document.createElement("p");
        queryError.className = "data-table-status";
        queryError.setAttribute("role", "alert");
        queryError.hidden = true;
        const presentationError = document.createElement("p");
        presentationError.className = "data-table-status";
        presentationError.setAttribute("role", "alert");
        presentationError.dataset.tablePresentationError = "";
        presentationError.hidden = true;
        shell.dataset.queryView = String(queryView);
        const commitDefinition = () => {
            try {
                onDefinitionChange(queryEditor.value);
                return true;
            } catch (error) {
                queryError.textContent = error.message;
                queryError.hidden = false;
                queryEditor.setAttribute("aria-invalid", "true");
                return false;
            }
        };
        if (onDefinitionChange) {
            const queryToggle = document.createElement("button");
            queryToggle.type = "button";
            queryToggle.className = "filter-pill";
            queryToggle.textContent = "Query view";
            queryToggle.setAttribute("aria-pressed", String(queryView));
            queryToggle.addEventListener("click", () => {
                if (!queryEditor.hidden) {
                    commitDefinition();
                    return;
                }
                queryEditor.hidden = false;
                shell.dataset.queryView = "true";
                queryToggle.setAttribute("aria-pressed", "true");
                closeOptions();
                queryEditor.focus();
            });
            options.prepend(queryToggle);
            queryEditor.addEventListener("input", () => onDefinitionDraft(queryEditor.value));
            queryEditor.addEventListener("blur", commitDefinition);
        }
        controls.append(optionsToggle);
        controls.addEventListener("pointerdown", (event) => event.stopPropagation());
        controls.addEventListener("keydown", (event) => event.stopPropagation());
        controls.addEventListener("dragstart", (event) => {
            event.preventDefault();
            event.stopPropagation();
        });
        const closeOptions = () => {
            if (!options.hidden) options.hidePopover();
            options.hidden = true;
            optionsToggle.setAttribute("aria-expanded", "false");
        };
        optionsToggle.addEventListener("click", () => {
            if (!options.hidden) {
                closeOptions();
                return;
            }
            options.hidden = false;
            options.showPopover();
            const anchor = optionsToggle.getBoundingClientRect();
            const bounds = options.getBoundingClientRect();
            options.style.left = `${Math.max(8, Math.min(
                anchor.right - bounds.width, window.innerWidth - bounds.width - 8,
            ))}px`;
            options.style.top = `${anchor.bottom + 4}px`;
            options.style.setProperty(
                "--table-options-available-height",
                `${Math.max(0, window.innerHeight - anchor.bottom - 12)}px`,
            );
            optionsToggle.setAttribute("aria-expanded", "true");
        });
        const outsideClick = (event) => {
            if (!shell.isConnected) {
                document.removeEventListener("pointerdown", outsideClick);
                document.removeEventListener("keydown", escapeOptions);
                document.removeEventListener("pointerdown", handleResizePointerDown, true);
                document.removeEventListener("keydown", handleResizeKeydown, true);
                document.removeEventListener("click", handleClearFilter);
                return;
            }
            if (!controls.contains(event.target) && !options.contains(event.target)) closeOptions();
        };
        const escapeOptions = (event) => {
            if (event.key === "Escape") closeOptions();
        };
        document.addEventListener("pointerdown", outsideClick);
        document.addEventListener("keydown", escapeOptions);

        const scroller = document.createElement("div");
        scroller.className = "data-table-scroll";
        if (maxRows !== undefined) {
            scroller.dataset.maxRows = String(maxRows);
            scroller.tabIndex = 0;
        }
        const table = document.createElement("table");
        const columnGroup = document.createElement("colgroup");
        const head = document.createElement("thead");
        const body = document.createElement("tbody");
        table.append(columnGroup, head, body);
        scroller.append(table);
        const footer = document.createElement("footer");
        footer.className = "data-table-footer";
        footer.hidden = !pagination;
        const count = document.createElement("span");
        count.className = "data-table-count";
        count.setAttribute("aria-live", "polite");
        const pageLabel = document.createElement("button");
        pageLabel.type = "button";
        pageLabel.title = "Choose table page";
        pageLabel.className = "data-table-page";
        pageLabel.setAttribute("aria-live", "polite");
        const pageInput = document.createElement("input");
        pageInput.type = "number";
        pageInput.min = "1";
        pageInput.step = "1";
        pageInput.hidden = true;
        pageInput.setAttribute("aria-label", "Table page");
        const sizeLabel = document.createElement("label");
        sizeLabel.className = "data-table-page-size";
        sizeLabel.append("Per page ");
        const sizeInput = document.createElement("input");
        sizeInput.type = "number";
        sizeInput.min = "1";
        sizeInput.step = "1";
        sizeInput.value = String(initialPageSize);
        sizeInput.setAttribute("aria-label", "Items per page");
        sizeLabel.append(sizeInput);
        const pageButton = (label, icon) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "icon-button data-table-page-button";
            button.title = label;
            button.setAttribute("aria-label", label);
            globalThis.obsAssets.replace(button, icon);
            return button;
        };
        const previousPage = pageButton("Previous table page", "previous");
        const nextPage = pageButton("Next table page", "next");
        const firstPage = pageButton("First table page", "first");
        const lastPage = pageButton("Last table page", "last");
        footer.append(count, sizeLabel, firstPage, previousPage, pageLabel, pageInput, nextPage, lastPage);
        const filterWarning = document.createElement("aside");
        filterWarning.className = "data-table-filter-warning";
        filterWarning.dataset.tableFilterWarning = "";
        filterWarning.hidden = true;
        const filterIcon = document.createElement("span");
        filterIcon.className = "bar-icon bar-icon--filter";
        filterIcon.setAttribute("aria-hidden", "true");
        globalThis.obsAssets.append(filterIcon, "filter");
        const filterLabel = document.createElement("span");
        filterLabel.textContent = "Filtered";
        const clearFilter = document.createElement("button");
        clearFilter.type = "button";
        clearFilter.className = "filter-warning-clear";
        clearFilter.dataset.clearTableFilter = key;
        clearFilter.setAttribute("aria-label", "Clear table filter");
        clearFilter.title = "Clear table filter";
        globalThis.obsAssets.replace(clearFilter, "close");
        filterWarning.append(filterIcon, filterLabel, clearFilter);
        shell.append(filterWarning, scroller, queryEditor, queryError, presentationError, footer, options);
        // Several authored views of one base: a pill per view name; the owner remounts the chosen view.
        if (views.length > 1) {
            const selector = document.createElement("div");
            selector.className = "filter-pills data-table-views";
            selector.dataset.tableViews = "";
            selector.setAttribute("role", "group");
            selector.setAttribute("aria-label", "Table views");
            selector.append(...views.map((name, index) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "filter-pill";
                button.textContent = name;
                button.setAttribute("aria-pressed", String(index === activeView));
                button.addEventListener("click", () => {
                    if (index !== activeView) onViewChange?.(index);
                });
                return button;
            }));
            shell.prepend(selector);
        }
        let pageIndex = 0;
        let pageTotal = 1;
        let paginationRows = [];
        let pageSize = initialPageSize;
        let revealKey = "";
        const updateViewportHeight = () => {
            if (maxRows === undefined) return;
            const rowHeights = [...body.querySelectorAll("tr[data-row-key]:not([hidden])")]
                .map((row) => row.getBoundingClientRect().height)
                .filter((height) => height > 0)
                .sort((left, right) => left - right);
            const middle = Math.floor(rowHeights.length / 2);
            const rowHeight = rowHeights.length
                ? rowHeights.length % 2 ? rowHeights[middle]
                    : (rowHeights[middle - 1] + rowHeights[middle]) / 2
                : 0;
            const headerHeight = head.getBoundingClientRect().height;
            if (!rowHeight || !headerHeight) {
                scroller.style.removeProperty("--table-viewport-max-height");
                return;
            }
            scroller.style.setProperty(
                "--table-viewport-max-height",
                `${headerHeight + rowHeight * maxRows}px`,
            );
        };

        const catalog = [...new Map(
            [...availableColumns, ...initialColumns].map((column) => [column.key, column]),
        ).values()];
        const catalogByKey = new Map(catalog.map((column) => [column.key, column]));
        const suggestionCatalog = fieldCatalog ? [...new Map(
            [...initialColumns, ...fieldCatalog].map(column => [column.key, column]),
        ).values()].map(column => fieldCatalog.find(item => item.key === column.key) || column) : catalog;
        const propertyCatalog = [...initialColumns, ...suggestionCatalog.filter(
            column => !initialColumns.some(initial => initial.key === column.key),
        )];
        const isMapping = value => value !== null && typeof value === "object" && !Array.isArray(value);
        let restoredPresentation;
        if (initialPresentation !== undefined) {
            // Older reviewed copies also saved resized `widths`; widths are no longer artifact state.
            const valid = isMapping(initialPresentation) &&
                Object.keys(initialPresentation).every(name => name === "columns" || name === "widths") &&
                Array.isArray(initialPresentation.columns) && initialPresentation.columns.length > 0 &&
                new Set(initialPresentation.columns).size === initialPresentation.columns.length &&
                initialPresentation.columns.every(column => typeof column === "string" && catalogByKey.has(column)) &&
                (initialPresentation.widths === undefined || isMapping(initialPresentation.widths));
            if (valid) restoredPresentation = initialPresentation;
            else {
                presentationError.textContent = "Saved table presentation is invalid: use unique known columns.";
                presentationError.hidden = false;
            }
        }
        const columns = restoredPresentation
            ? restoredPresentation.columns.map(column => catalogByKey.get(column)) : [...initialColumns];
        // Authored columns, or a trusted runtime's derived projection; neither is reader state.
        let projectedColumnKeys = initialColumns.map(column => column.key);
        const groups = initialGroup.map((item) => ({...item}));
        const sorts = initialSort.map((item) => ({...item}));
        // Reader-resized widths are session view state only: never an artifact change.
        const resizedWidths = new Map(Object.entries(isMapping(initialColumnWidths) ? initialColumnWidths : {})
            .filter(([column, width]) => catalogByKey.has(column) && !catalogByKey.get(column).fixed &&
                Number.isSafeInteger(width) && width >= minimumColumnWidth));
        const explicitWidth = (column) => column.fixed ? column.width : resizedWidths.get(column.key);
        const equalSizing = columnSizing === "equal";
        const syncContinuationWidths = () => {
            const widths = [...columnGroup.children].map(element => element.style.width);
            document.querySelectorAll("[data-data-table]").forEach(projection => {
                if (projection.dataset.dataTable !== key || projection === shell) return;
                projection.querySelectorAll(":scope > .data-table-scroll > table > colgroup").forEach(group => {
                    [...group.children].forEach((element, index) => {
                        element.style.width = widths[index] || "";
                    });
                });
                projection.querySelectorAll(":scope > .data-table-scroll > table").forEach(projectedTable => {
                    projectedTable.style.minWidth = table.style.minWidth;
                    projectedTable.style.width = table.style.width;
                });
            });
        };
        const publishPresentation = () => {
            presentationError.hidden = true;
            onPresentationChange?.({
                columns: columns.map(column => column.key),
            }, {columns: [...projectedColumnKeys]});
        };
        let appliedQuery = globalThis.obsQuery.compile("");
        let rowKeys = initialRowKeys ? new Set(initialRowKeys) : null;
        const scopedRows = () => rowKeys ? rows.filter(row => rowKeys.has(row.key)) : rows;
        let baseRows = retainMatchesAndAncestors(scopedRows(), baseQuery);
        const expanded = new Set(rows.map((row) => row.key));
        const collapsedGroups = new Set();
        const expandedDetails = new Set(initialDetailState?.expanded || []);
        const selectedDetailColumns = new Map(Object.entries(initialDetailState?.selected || {}));
        const publishDetailState = () => onDetailStateChange?.({
            expanded: [...expandedDetails], selected: Object.fromEntries(selectedDetailColumns),
        });
        const detailPrefix = item => `table-detail-${encodeURIComponent(key)}-${encodeURIComponent(item.key)}`;
        let rowGroupParents = new WeakMap();
        let activeGroupRows = [];
        let suppressHeaderClick = false;
        let visibleRows = baseRows;
        let metrics = {
            padding: 28, indent: 0, toggle: 0, headerControlExtra: 0,
            font: getComputedStyle(document.body).font, headerFont: getComputedStyle(document.body).font,
            editorChrome: 0, editorFont: "",
        };
        const parentKeys = new Set(baseRows.map((row) => row.parentKey).filter(Boolean));
        // Unwrapped rendered content of every base row, not just the current page, so widths are
        // stable across pages, filters and edits.
        const contentWidths = new Map();
        const contentWidth = (column, tree = false) => {
            if (column.fixed) return column.width;
            if (!contentWidths.has(column.key)) {
                let plain = 0;
                let nested = 0;
                baseRows.forEach((row) => {
                    const target = document.createElement("div");
                    if (column.render) column.render(row, target);
                    else target.append(String(row.values[column.key] ?? ""));
                    const {lines, editor} = contentLines(target);
                    const width = (editor && metrics.editorFont
                        ? widestLine(lines, metrics.editorFont) + metrics.editorChrome
                        : widestLine(lines, metrics.font)) + metrics.padding;
                    const controls = (row.depth || 0) * metrics.indent +
                        (parentKeys.has(row.key) || hasDetails(row) ? metrics.toggle : 0);
                    plain = Math.max(plain, width);
                    nested = Math.max(nested, width + controls);
                });
                contentWidths.set(column.key, {plain, nested});
            }
            const widths = contentWidths.get(column.key);
            return tree ? widths.nested : widths.plain;
        };
        const headerWidth = (column, controls) => (column.hideLabel ? 0
            : widestLine([column.label], metrics.headerFont)) + metrics.padding +
            (controls ? metrics.headerControlExtra : 0);
        let measuredStyle = "";
        const filterFields = document.createElement("div");
        filterFields.className = "filter-pills";
        filterFields.setAttribute("aria-label", "Filter fields");
        const facetCatalog = fieldCatalog || catalog;
        const filterSelections = new Map();
        let selectionBase = "";
        const renderFacets = () => renderFilterFields({
            container: filterFields,
            facets: globalThis.obsArtifact?.facetFields(baseRows, facetCatalog.map(column => ({
                field: column.key, label: column.label,
            }))) || [],
            isSelected: (field, value) => (filterSelections.get(field) || []).includes(value),
            onSelect: (field, value) => {
                if (!filterSelections.size) selectionBase = appliedQuery.source.trim();
                const values = filterSelections.get(field) || [];
                const index = values.indexOf(value);
                if (index < 0) values.push(value);
                else values.splice(index, 1);
                if (values.length) filterSelections.set(field, values);
                else filterSelections.delete(field);
                input.value = [selectionBase, ...[...filterSelections].map(([key, items]) => {
                    const clauses = items.map(item => globalThis.obsQuery.exactClause(key, item, true));
                    return clauses.length > 1 ? `(${clauses.join(" OR ")})` : clauses[0];
                })].filter(Boolean).join(" AND ");
                apply();
            },
        });
        filterPanel.append(filterFields);

        const renderProperties = () => {
            propertyList.replaceChildren();
            propertyCatalog.filter((column) => `${column.label} ${column.key}`.toLocaleLowerCase()
                .includes(propertyInput.value.toLocaleLowerCase())).forEach((column) => {
                const selected = columns.some((item) => item.key === column.key);
                const button = document.createElement("button");
                button.type = "button";
                button.className = "filter-pill";
                button.textContent = column.label;
                button.title = `${selected ? "Hide" : "Show"} ${column.key}`;
                button.setAttribute("aria-pressed", String(selected));
                button.disabled = selected && columns.length === 1;
                button.addEventListener("click", () => {
                    const index = columns.findIndex((item) => item.key === column.key);
                    if (index < 0) columns.push(column);
                    else if (columns.length > 1) columns.splice(index, 1);
                    draw();
                    renderProperties();
                    publishPresentation();
                });
                propertyList.append(button);
            });
        };
        const renderOrder = () => {
            orderPanel.replaceChildren();
            [["Group by", groups], ["Sort by", sorts]].forEach(([label, levels]) => {
                const section = document.createElement("section");
                const heading = document.createElement("h3");
                heading.textContent = label;
                const selected = document.createElement("div");
                selected.className = "filter-pills";
                levels.forEach((level, index) => {
                    const button = document.createElement("button");
                    button.type = "button";
                    button.className = "filter-pill";
                    button.textContent = `${index + 1}. ${catalog.find(
                        (column) => column.key === level.property,
                    )?.label || level.property} `;
                    globalThis.obsAssets.append(button,
                        level.direction === "DESC" ? "sort.descending" : "sort.ascending");
                    button.title = `Reverse direction for ${level.property}`;
                    button.addEventListener("click", () => {
                        level.direction = level.direction === "DESC" ? "ASC" : "DESC";
                        draw();
                        renderOrder();
                    });
                    const remove = document.createElement("button");
                    remove.type = "button";
                    remove.className = "filter-pill";
                    globalThis.obsAssets.replace(remove, "close");
                    remove.title = `Remove ${label.toLocaleLowerCase()} ${level.property}`;
                    remove.setAttribute("aria-label", remove.title);
                    remove.addEventListener("click", () => {
                        levels.splice(index, 1);
                        draw();
                        renderOrder();
                    });
                    selected.append(button, remove);
                });
                const fields = document.createElement("div");
                fields.className = "filter-pills";
                fields.setAttribute("aria-label", `${label} fields`);
                suggestionCatalog.forEach((column) => {
                    const button = document.createElement("button");
                    button.type = "button";
                    button.className = "filter-pill";
                    button.textContent = column.label;
                    button.title = `${label} ${column.key}`;
                    button.setAttribute("aria-pressed", String(
                        levels.some((level) => level.property === column.key),
                    ));
                    button.addEventListener("click", () => {
                        const index = levels.findIndex((level) => level.property === column.key);
                        if (index < 0) levels.push({property: column.key, direction: "ASC"});
                        else levels.splice(index, 1);
                        draw();
                        renderOrder();
                    });
                    fields.append(button);
                });
                section.append(heading, selected, fields);
                orderPanel.append(section);
            });
        };

        let fittedWidths = [];
        const renderColumnWidths = () => {
            if (table.isConnected) {
                const style = getComputedStyle(table);
                const fontSize = parseFloat(getComputedStyle(document.documentElement).fontSize);
                const header = head.querySelector(".data-table-last-header");
                const controls = header?.querySelector(".data-table-controls");
                const resize = header?.querySelector(".data-table-column-resize");
                const headerStyle = header && getComputedStyle(header);
                const controlBounds = controls?.getBoundingClientRect();
                const resizeBounds = resize?.getBoundingClientRect();
                const headerBounds = header?.getBoundingClientRect();
                const controlToResizeGap = controlBounds && resizeBounds
                    ? Math.max(0, resizeBounds.left - controlBounds.right) : 0;
                const basePadding = Number(style.getPropertyValue("--table-cell-padding")) * fontSize;
                const rightReservation = headerStyle && controlBounds &&
                    resizeBounds && headerBounds ? Math.max(
                    parseFloat(headerStyle.paddingInlineEnd),
                    headerBounds.right - controlBounds.left,
                    resizeBounds.width + controlToResizeGap,
                ) : basePadding;
                const nextMetrics = {
                    padding: Number(style.getPropertyValue("--table-cell-padding")) * fontSize * 2 + 2,
                    indent: Number(style.getPropertyValue("--table-tree-indent")) * fontSize,
                    toggle: (Number(style.getPropertyValue("--table-toggle-size")) +
                        Number(style.getPropertyValue("--table-toggle-gap"))) * fontSize,
                    headerControlExtra: Math.max(0, rightReservation - basePadding),
                    font: style.font,
                    headerFont: headerStyle?.font || style.font,
                    editorChrome: metrics.editorChrome,
                    editorFont: metrics.editorFont,
                };
                const editor = body.querySelector("input[data-property-editor], textarea[data-property-editor]");
                if (editor) {
                    const editorStyle = getComputedStyle(editor);
                    nextMetrics.editorChrome = inlineChrome(editorStyle);
                    nextMetrics.editorFont = editorStyle.font;
                }
                const signature = JSON.stringify(nextMetrics);
                if (signature !== measuredStyle) {
                    measuredStyle = signature;
                    metrics = nextMetrics;
                    contentWidths.clear();
                }
            }
            if (compact && table.isConnected) {
                columns.filter(column => column.fixed).forEach(column => {
                    const index = columns.indexOf(column);
                    const cell = body.querySelector("tr[data-row-key]")?.children[index];
                    const header = head.querySelector("tr")?.children[index];
                    if (!cell || !header) return;
                    const style = getComputedStyle(cell);
                    const headerStyle = getComputedStyle(header);
                    const actions = [...cell.querySelectorAll(".data-table-icon-action")];
                    const actionWidth = actions.reduce((sum, action) =>
                        sum + action.getBoundingClientRect().width, 0);
                    const padding = parseFloat(style.paddingInlineStart) + parseFloat(style.paddingInlineEnd) + 2;
                    const headerWidth = widestLine([column.hideLabel ? "" : column.label], headerStyle.font) +
                        parseFloat(headerStyle.paddingInlineStart) + parseFloat(headerStyle.paddingInlineEnd) + 2;
                    if (!actions.length || !actionWidth) return;
                    column.width = Math.ceil(Math.max(actionWidth + padding, headerWidth));
                    [...body.children].forEach(row =>
                        row.children[index]?.style.setProperty("--table-icon-width", `${column.width}px`));
                    header.style.setProperty("--table-icon-width", `${column.width}px`);
                });
            }
            const tableStyle = table.isConnected ? getComputedStyle(table) : null;
            const collapsed = tableStyle?.borderCollapse === "collapse";
            const edges = collapsed && head.firstElementChild
                ? [head.firstElementChild.firstElementChild, head.firstElementChild.lastElementChild]
                : [table, table];
            const borderWidth = tableStyle && edges.every(Boolean) ? (
                parseFloat(getComputedStyle(edges[0]).borderLeftWidth) +
                parseFloat(getComputedStyle(edges[1]).borderRightWidth)
            ) / (collapsed ? 2 : 1) : 0;
            // `clientWidth` rounds a fractional container to the nearest pixel and borders may be
            // snapped thinner than their CSS width; round down and keep one pixel of slack so
            // fitted columns never exceed the container they fill.
            const fittingWidth = scroller.clientWidth
                ? Math.max(0, Math.floor(scroller.clientWidth - borderWidth) - 1) : 0;
            const controlColumn = columns.at(-1);
            const specs = columns.map((column, index) => {
                const width = explicitWidth(column);
                if (width) return {width, fixed: Boolean(column.fixed)};
                const header = Math.ceil(headerWidth(column, column === controlColumn));
                if (column.weight) return {weight: column.weight, max: Math.max(column.weight, header), floor: header};
                const max = Math.max(Math.ceil(contentWidth(column, index === 0)), header);
                // Labels stay unwrapped unless the reader explicitly narrows a column.
                return {max, floor: Math.min(max, Math.max(minimumColumnWidth, header))};
            });
            if (equalSizing) {
                const subjectColumns = columns.filter(column => !column.fixed);
                const fixedWidth = columns.filter(column => column.fixed)
                    .reduce((total, column) => total + column.width, 0);
                const available = fittingWidth || subjectColumns.length *
                    Math.max(minimumColumnWidth, ...specs.map(spec => spec.max || minimumColumnWidth));
                const resizedTotal = subjectColumns.reduce(
                    (total, column) => total + (resizedWidths.get(column.key) || 0), 0,
                );
                const automatic = subjectColumns.filter(column => !resizedWidths.has(column.key));
                const sharedWidth = Math.max(minimumColumnWidth, Math.floor(
                    (available - fixedWidth - resizedTotal) / Math.max(1, automatic.length),
                ));
                let totalWidth = fixedWidth;
                fittedWidths = [];
                columnGroup.replaceChildren(...columns.map(column => {
                    const element = document.createElement("col");
                    if (column.fixed) element.style.width = `${column.width}px`;
                    else {
                        const width = resizedWidths.get(column.key) ||
                            sharedWidth;
                        element.style.width = `${width}px`;
                        totalWidth += width;
                    }
                    fittedWidths.push(parseFloat(element.style.width));
                    return element;
                }));
                table.style.minWidth = `${Math.ceil(totalWidth + borderWidth)}px`;
                table.style.width = columns.every(column => column.fixed) ? `${totalWidth}px` : "100%";
                syncContinuationWidths();
                return;
            }
            // The flexible (last non-icon) column has no <col> width so it absorbs later changes.
            const flexible = specs.findLastIndex(spec => !spec.fixed);
            const widths = fitColumns(specs, fittingWidth, flexible);
            fittedWidths = widths;
            const totalWidth = widths.reduce((total, width) => total + width, 0);
            columnGroup.replaceChildren(...columns.map((column, index) => {
                const element = document.createElement("col");
                if (index !== flexible) element.style.width = `${widths[index]}px`;
                return element;
            }));
            // The flexible column's surplus and weighted shares are fill, not requirements: only
            // their own minimums count, so a fitted table can never be wider than its container.
            const requiredWidth = flexible < 0 ? totalWidth : widths.reduce((total, width, index) =>
                total + (index === flexible || specs[index].weight
                    ? specs[index].width ?? specs[index].floor : width), 0);
            table.style.minWidth = `${Math.ceil(requiredWidth + borderWidth)}px`;
            table.style.width = flexible < 0 ? `${totalWidth}px` : "100%";
            syncContinuationWidths();
        };
        // Static (print) projections refit this plan inside their actual paper container.
        const columnPlan = () => ({
            minimum: minimumColumnWidth,
            columns: columns.map((column) => {
                const width = explicitWidth(column);
                return width ? {width, fixed: Boolean(column.fixed)}
                    : {hideLabel: Boolean(column.hideLabel), ...(column.weight ? {weight: column.weight} : {})};
            }),
        });

        const resizeColumn = (column, width) => {
            if (column.fixed) return;
            const resized = Math.max(minimumColumnWidth, Math.round(width));
            resizedWidths.set(column.key, resized);
            renderColumnWidths();
            onColumnWidthsChange?.(Object.fromEntries(resizedWidths));
        };
        const handleResizePointerDown = (event) => {
            if (!shell.isConnected) return;
            const handle = event.target.closest(".data-table-column-resize");
            if (handle?.dataset.tableKey !== key) return;
            const column = catalogByKey.get(handle.dataset.columnKey);
            if (!column || column.fixed) return;
            event.preventDefault();
            event.stopPropagation();
            suppressHeaderClick = true;
            const startX = event.clientX;
            const startWidth = handle.parentElement.getBoundingClientRect().width;
            const pointerMove = (moveEvent) => {
                resizeColumn(column, startWidth + moveEvent.clientX - startX);
            };
            const pointerUp = () => {
                window.removeEventListener("pointermove", pointerMove);
                window.removeEventListener("pointerup", pointerUp);
                globalThis.setTimeout(() => { suppressHeaderClick = false; }, 0);
            };
            window.addEventListener("pointermove", pointerMove);
            window.addEventListener("pointerup", pointerUp);
        };
        const handleResizeKeydown = (event) => {
            if (!shell.isConnected) return;
            const handle = event.target.closest(".data-table-column-resize");
            if (handle?.dataset.tableKey !== key) return;
            const column = catalogByKey.get(handle.dataset.columnKey);
            if (!column || column.fixed || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
            event.preventDefault();
            resizeColumn(column, handle.parentElement.getBoundingClientRect().width +
                (event.key === "ArrowRight" ? 16 : -16));
        };
        document.addEventListener("pointerdown", handleResizePointerDown, true);
        document.addEventListener("keydown", handleResizeKeydown, true);
        const handleClearFilter = event => {
            if (!shell.isConnected) return;
            if (event.target.closest("[data-clear-table-filter]")?.dataset.clearTableFilter !== key) return;
            input.value = "";
            apply();
        };
        document.addEventListener("click", handleClearFilter);

        const moveColumn = (sourceKey, targetKey) => {
            const source = columns.findIndex((column) => column.key === sourceKey);
            const target = columns.findIndex((column) => column.key === targetKey);
            if (source < 0 || target < 0 || source === target) return;
            const [column] = columns.splice(source, 1);
            columns.splice(target, 0, column);
            draw();
            publishPresentation();
        };

        const renderHead = () => {
            const row = document.createElement("tr");
            columns.forEach((column, index) => {
                const cell = document.createElement("th");
                cell.scope = "col";
                cell.draggable = true;
                cell.tabIndex = 0;
                cell.dataset.columnKey = column.key;
                if (column.fixed) {
                    cell.classList.add("data-table-icon-cell");
                    cell.style.setProperty("--table-icon-width", `${column.width}px`);
                }
                cell.setAttribute("aria-label", column.hideLabel ? column.label
                    : `${column.label}; drag to move column`);
                const activeSort = sorts.find((level) => level.property === column.key);
                cell.setAttribute("aria-sort", activeSort
                    ? activeSort.direction === "DESC" ? "descending" : "ascending"
                    : "none");
                cell.dataset.hoverHelp = `${column.label}: click to sort; Shift-click for another sort level`;
                const sortHeader = (secondary = false) => {
                    const existing = sorts.find((level) => level.property === column.key);
                    const direction = existing?.direction === "ASC" ? "DESC" : "ASC";
                    if (!secondary) sorts.splice(0, sorts.length);
                    const level = sorts.find((item) => item.property === column.key);
                    if (level) level.direction = direction;
                    else sorts.push({property: column.key, direction});
                    pageIndex = 0;
                    draw();
                    renderOrder();
                };
                cell.addEventListener("click", (event) => {
                    if (event.target.closest(".data-table-controls, .data-table-column-resize")) return;
                    if (suppressHeaderClick) {
                        suppressHeaderClick = false;
                        return;
                    }
                    sortHeader(event.shiftKey);
                });
                const label = document.createElement("span");
                label.textContent = column.hideLabel ? "" : column.label;
                const resize = document.createElement("span");
                resize.className = "data-table-column-resize";
                resize.dataset.tableKey = key;
                resize.dataset.columnKey = column.key;
                resize.tabIndex = 0;
                resize.setAttribute("role", "separator");
                resize.setAttribute("aria-label", `Resize ${column.label}`);
                resize.setAttribute("aria-orientation", "vertical");
                cell.addEventListener("dragstart", (event) => {
                    suppressHeaderClick = true;
                    event.dataTransfer.effectAllowed = "move";
                    event.dataTransfer.setData("text/plain", column.key);
                    cell.dataset.dragging = "";
                });
                cell.addEventListener("dragend", () => {
                    delete cell.dataset.dragging;
                    globalThis.setTimeout(() => { suppressHeaderClick = false; }, 0);
                });
                cell.addEventListener("dragover", (event) => {
                    event.preventDefault();
                    event.dataTransfer.dropEffect = "move";
                });
                cell.addEventListener("drop", (event) => {
                    event.preventDefault();
                    moveColumn(event.dataTransfer.getData("text/plain"), column.key);
                });
                cell.addEventListener("keydown", (event) => {
                    if (event.target !== cell) return;
                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        sortHeader(event.shiftKey);
                        return;
                    }
                    if (!event.altKey || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
                    const target = index + (event.key === "ArrowRight" ? 1 : -1);
                    if (!columns[target]) return;
                    event.preventDefault();
                    moveColumn(column.key, columns[target].key);
                });
                cell.append(label);
                if (!column.fixed) cell.append(resize);
                const controlColumn = columns.at(-1);
                if (column === controlColumn) {
                    cell.classList.add("data-table-last-header");
                    cell.append(controls);
                }
                row.append(cell);
            });
            head.replaceChildren(row);
        };

        const orderedRows = () => {
            const retained = new Set(visibleRows.map((row) => row.key));
            const children = new Map();
            visibleRows.forEach((row) => {
                const parent = retained.has(row.parentKey) ? row.parentKey : "";
                if (!children.has(parent)) children.set(parent, []);
                children.get(parent).push(row);
            });
            const flatten = (parent = "", hidden = false) => {
                const siblings = [...(children.get(parent) || [])];
                siblings.sort((left, right) => {
                    for (const level of sorts) {
                        const result = String(left.values[level.property] ?? "").localeCompare(
                            String(right.values[level.property] ?? ""), undefined, {numeric: true},
                        );
                        if (result) return level.direction === "DESC" ? -result : result;
                    }
                    return 0;
                });
                return siblings.flatMap((row) => [
                    {...row, hidden},
                    ...flatten(row.key, hidden || !expanded.has(row.key)),
                ]);
            };
            return flatten();
        };

        const rowHydrators = new WeakMap();
        const appendDataRow = (item, childKeys) => {
            const row = document.createElement("tr");
            row.dataset.rowKey = item.key;
            row.hidden = item.hidden;
            rowGroupParents.set(row, [...activeGroupRows]);
            const hasChildren = childKeys.has(item.key);
            const showDetails = !hasChildren && hasDetails(item);
            const isExpanded = hasChildren
                ? expanded.has(item.key) : expandedDetails.has(item.key);
            const toggleRow = () => {
                const state = hasChildren ? expanded : expandedDetails;
                if (state.has(item.key)) state.delete(item.key);
                else state.add(item.key);
                if (!hasChildren) publishDetailState();
                if (hasChildren) renderBody();
                else updateDetails();
            };
            const renderCells = () => columns.forEach((column, index) => {
                const cell = document.createElement("td");
                if (column.fixed) cell.style.setProperty("--table-icon-width", `${column.width}px`);
                if (column.fixed) cell.classList.add("data-table-icon-cell");
                let target = cell;
                if (index === 0) {
                    cell.classList.add("data-table-tree-cell");
                    cell.style.setProperty("--data-table-depth", String(item.depth || 0));
                    const content = document.createElement("div");
                    content.className = "data-table-tree-content";
                    target = document.createElement("div");
                    target.className = "data-table-tree-value";
                    cell.append(content);
                    if (hasChildren || showDetails) {
                        const toggle = document.createElement("button");
                        toggle.className = "disclosure-toggle data-table-tree-toggle";
                        toggle.type = "button";
                        toggle.setAttribute("aria-expanded", String(isExpanded));
                        toggle.setAttribute(
                            "aria-label",
                            `${isExpanded ? "Collapse" : "Expand"} ${item.values[column.key]}${showDetails ? " details" : ""}`,
                        );
                        globalThis.obsAssets.replace(toggle, isExpanded ? "expanded" : "collapsed");
                        toggle.addEventListener("click", toggleRow);
                        content.append(toggle);
                    }
                    content.append(target);
                }
                if (column.render) column.render(item, target);
                else target.append(String(item.values[column.key] ?? ""));
                if (columnDetails) cell.querySelectorAll("[data-table-reference-column]").forEach(link => {
                    const selected = columns.find(subject =>
                        subject.detail && subject.key === selectedDetailColumns.get(item.key))
                        || columns.find(subject => subject.detail);
                    link.setAttribute("aria-expanded", String(isExpanded &&
                        selected?.key === column.key));
                    link.addEventListener("click", event => {
                        event.preventDefault();
                        event.stopPropagation();
                        selectedDetailColumns.set(item.key, column.key);
                        expandedDetails.add(item.key);
                        publishDetailState();
                        const tabId = `${detailPrefix(item)}-tab-${encodeURIComponent(column.key)}`;
                        const tab = document.getElementById(tabId);
                        if (tab && detailRow?.isConnected) tab.click();
                        else updateDetails();
                        document.getElementById(tabId)?.focus();
                    });
                });
                cell.querySelectorAll("[data-table-detail-toggle]").forEach((button) => {
                    button.setAttribute("aria-expanded", String(isExpanded));
                    button.setAttribute("aria-label",
                        `${isExpanded ? "Collapse" : "Expand"} ${button.textContent} details`);
                    button.title = button.getAttribute("aria-label");
                    button.addEventListener("click", (event) => {
                        event.stopPropagation();
                        toggleRow();
                    });
                });
                row.append(cell);
            });
            body.append(row);
            let detailRow;
            const renderDetail = () => {
                if (item.hidden || childKeys.has(item.key) ||
                    !expandedDetails.has(item.key) || !hasDetails(item)) return;
                if (detailRow) {
                    row.after(detailRow);
                    return;
                }
                const detail = document.createElement("tr");
                detailRow = detail;
                detail.className = "data-table-detail-row";
                detail.dataset.detailOwner = item.key;
                if (row.dataset.reviewState) detail.dataset.reviewOwnerState = row.dataset.reviewState;
                const cell = document.createElement("td");
                cell.colSpan = columns.length;
                const content = document.createElement("div");
                content.className = "data-table-detail-content";
                content.style.setProperty("--table-detail-font-size", `${detailFontSize}pt`);
                cell.append(content);
                detail.append(cell);
                row.after(detail);
                if (columnDetails) {
                    const available = column => !column.hasDetail || column.hasDetail(item);
                    const subjects = columns.filter(column => column.detail &&
                        (showEmptyDetailTabs || available(column)));
                    if (subjects.length) {
                        const tablist = document.createElement("div");
                        tablist.className = "data-table-detail-tabs";
                        tablist.setAttribute("role", "tablist");
                        tablist.setAttribute("aria-label", "Linked items");
                        const panelGroup = document.createElement("div");
                        panelGroup.className = "data-table-detail-panels";
                        const prefix = detailPrefix(item);
                        const subjectPanels = subjects.map((column, index) => {
                            const panel = document.createElement("section");
                            panel.className = "data-table-detail-panel";
                            panel.setAttribute("role", "tabpanel");
                            panel.id = `${prefix}-panel-${index}`;
                            panel.dataset.detailColumn = column.key;
                            return panel;
                        });
                        const buttons = subjects.map((column, index) => {
                            const button = document.createElement("button");
                            button.type = "button";
                            button.disabled = !available(column);
                            button.id = `${prefix}-tab-${encodeURIComponent(column.key)}`;
                            button.textContent = column.label;
                            button.setAttribute("role", "tab");
                            button.setAttribute("aria-controls", subjectPanels[index].id);
                            subjectPanels[index].setAttribute("aria-labelledby", button.id);
                            button.addEventListener("click", () => select(index, true));
                            button.addEventListener("keydown", event => {
                                let next;
                                const enabled = subjects.map((column, position) => position)
                                    .filter(position => available(subjects[position]));
                                const position = enabled.indexOf(index);
                                if (event.key === "ArrowRight") next = enabled[(position + 1) % enabled.length];
                                if (event.key === "ArrowLeft") next = enabled[(position + enabled.length - 1) % enabled.length];
                                if (event.key === "Home") next = enabled[0];
                                if (event.key === "End") next = enabled.at(-1);
                                if (next === undefined) return;
                                event.preventDefault();
                                select(next, true);
                            });
                            return button;
                        });
                        const select = (index, notify = false) => {
                            if (index < 0 || !available(subjects[index])) {
                                buttons.forEach((button, position) => {
                                    button.setAttribute("aria-selected", "false");
                                    button.tabIndex = -1;
                                    subjectPanels[position].hidden = true;
                                    subjectPanels[position].inert = true;
                                });
                                return;
                            }
                            selectedDetailColumns.set(item.key, subjects[index].key);
                            publishDetailState();
                            buttons.forEach((button, position) => {
                                button.setAttribute("aria-selected", String(position === index));
                                button.tabIndex = position === index ? 0 : -1;
                                subjectPanels[position].hidden = position !== index;
                                subjectPanels[position].inert = position !== index;
                                subjectPanels[position].tabIndex = position === index ? 0 : -1;
                            });
                            row.querySelectorAll("[data-table-reference-column]").forEach(link =>
                                link.setAttribute("aria-expanded",
                                    String(link.dataset.tableReferenceColumn === subjects[index].key)));
                            if (notify) {
                                buttons[index].focus();
                                shell.dispatchEvent(new CustomEvent("obs-table-change", {
                                    bubbles: true, detail: {reason: "detail-selection"},
                                }));
                            }
                        };
                        tablist.append(...buttons);
                        panelGroup.append(...subjectPanels);
                        content.append(tablist, panelGroup);
                        subjectPanels.forEach((panel, index) => {
                            if (available(subjects[index])) renderDetails(item, panel, subjects[index].key);
                        });
                        const active = subjects.findIndex(column =>
                            available(column) && column.key === selectedDetailColumns.get(item.key));
                        select(active < 0 ? subjects.findIndex(available) : active);
                    } else {
                        const empty = document.createElement("p");
                        empty.className = "data-table-detail-empty";
                        empty.textContent = "No subject columns selected.";
                        content.append(empty);
                    }
                    renderOwnerDetails?.(item, content);
                } else renderDetails(item, content);
            };
            const updateDetails = () => {
                if (shell.isConnected) shell.dispatchEvent(
                    new CustomEvent("obs-table-before-change", {bubbles: true}),
                );
                detailRow?.remove();
                renderDetail();
                const open = expandedDetails.has(item.key);
                row.querySelectorAll(".data-table-tree-toggle, [data-table-detail-toggle]").forEach(button => {
                    button.setAttribute("aria-expanded", String(open));
                    const label = button.getAttribute("aria-label")?.replace(
                        /^(Expand|Collapse)/, open ? "Collapse" : "Expand",
                    );
                    if (label) button.setAttribute("aria-label", label);
                    if (button.matches(".data-table-tree-toggle")) globalThis.obsAssets.replace(button, open ? "expanded" : "collapsed");
                    else if (label) button.title = label;
                });
                row.querySelectorAll("[data-table-reference-column]").forEach(link =>
                    link.setAttribute("aria-expanded", String(open &&
                        link.dataset.tableReferenceColumn === selectedDetailColumns.get(item.key))));
                paginate(orderedRows(), "row-details");
            };
            if (pagination) rowHydrators.set(row, () => {
                renderCells();
                renderDetail();
            });
            else {
                renderCells();
                renderDetail();
            }
        };

        const renderBody = () => {
            if (shell.isConnected) shell.dispatchEvent(
                new CustomEvent("obs-table-before-change", {bubbles: true}),
            );
            body.replaceChildren();
            rowGroupParents = new WeakMap();
            activeGroupRows = [];
            const ordered = orderedRows();
            const revealChain = new Set();
            const byKey = new Map(ordered.map((item) => [item.key, item]));
            let revealItem = byKey.get(revealKey);
            while (revealItem && !revealChain.has(revealItem.key)) {
                revealChain.add(revealItem.key);
                revealItem = byKey.get(revealItem.parentKey);
            }
            const childKeys = new Set(ordered.map((row) => row.parentKey).filter(Boolean));
            if (!groups.length) {
                ordered.forEach((item) => appendDataRow(item, childKeys));
                paginationRows = [...body.children];
                paginate(ordered);
                return;
            }
            const renderGroup = (items, depth = 0, path = [], branchKey = "") => {
                if (depth === groups.length) {
                    items.forEach(appendBranch);
                    return;
                }
                const level = groups[depth];
                const buckets = new Map();
                items.forEach((item) => {
                    const value = String(item.values[level.property] ?? "Unspecified");
                    if (!buckets.has(value)) buckets.set(value, []);
                    buckets.get(value).push(item);
                });
                const compare = compareGroupLabels(level, sorts.find((sort) => sort.property === level.property));
                [...buckets].sort(([left], [right]) => compare(left, right)).forEach(([label, entries]) => {
                    const groupPath = [...path, [level.property, label]];
                    const groupKey = JSON.stringify([branchKey, groupPath]);
                    const heading = document.createElement("tr");
                    heading.className = "data-table-group-row";
                    heading.id = `table-group--${anchorSlug(key)}`
                        + (branchKey ? `--row--${anchorSlug(branchKey)}` : "")
                        + `--${groupPath.flatMap(([property, value]) => [
                            anchorSlug(property), anchorSlug(value),
                        ]).join("--")}`;
                    heading.dataset.groupKey = groupKey;
                    if (entries.some((item) => revealChain.has(item.key))) {
                        collapsedGroups.delete(groupKey);
                    }
                    const collapsed = collapsedGroups.has(groupKey);
                    heading.dataset.groupCollapsed = String(collapsed);
                    rowGroupParents.set(heading, [...activeGroupRows]);
                    const cell = document.createElement("th");
                    cell.colSpan = columns.length;
                    cell.scope = "rowgroup";
                    const toggle = document.createElement("button");
                    toggle.type = "button";
                    toggle.className = "disclosure-toggle data-table-group-toggle";
                    globalThis.obsAssets.replace(toggle, collapsed ? "collapsed" : "expanded");
                    const groupColumn = catalogByKey.get(level.property);
                    // An empty displayName shows the bare group value, as it hides a column header.
                    const groupLabel = !groupColumn ? level.property : groupColumn.hideLabel ? "" : groupColumn.label;
                    const caption = groupLabel ? `${groupLabel}: ${label}` : label;
                    toggle.title = `${collapsed ? "Expand" : "Collapse"} ${caption}`;
                    toggle.setAttribute("aria-label", toggle.title);
                    toggle.setAttribute("aria-expanded", String(!collapsed));
                    toggle.addEventListener("click", () => {
                        if (collapsedGroups.has(groupKey)) collapsedGroups.delete(groupKey);
                        else collapsedGroups.add(groupKey);
                        renderBody();
                    });
                    cell.append(toggle, `${caption} (${entries.length})`);
                    cell.style.paddingInlineStart = `${0.6 + activeGroupRows.length * 1.2}rem`;
                    heading.append(cell);
                    body.append(heading);
                    if (!collapsed) {
                        activeGroupRows.push(heading);
                        renderGroup(entries, depth + 1, groupPath, branchKey);
                        activeGroupRows.pop();
                    }
                });
            };
            const retainedKeys = new Set(ordered.map((item) => item.key));
            const descendants = new Map();
            ordered.filter((item) => !item.hidden && retainedKeys.has(item.parentKey))
                .forEach((item) => {
                    if (!descendants.has(item.parentKey)) descendants.set(item.parentKey, []);
                    descendants.get(item.parentKey).push(item);
                });
            const appendBranch = (item) => {
                appendDataRow(item, childKeys);
                const children = descendants.get(item.key) || [];
                if (children.length) renderGroup(children, 0, [], item.key);
            };
            // Group siblings while retaining their source-tree descendants.
            renderGroup(ordered.filter(
                (item) => !item.hidden && !retainedKeys.has(item.parentKey),
            ));
            paginationRows = [...body.children];
            paginate(ordered);
        };

        const paginate = (ordered, reason = "") => {
            if (!pagination) {
                updateViewportHeight();
                shell.dispatchEvent(new CustomEvent("obs-table-change", {bubbles: true, detail: {reason}}));
                return;
            }
            const details = new Map([...body.children].filter(row => row.dataset.detailOwner)
                .map(row => [row.dataset.detailOwner, row]));
            const allRows = paginationRows.filter(row => !row.dataset.detailOwner).flatMap(row => {
                const detail = details.get(row.dataset.rowKey);
                return detail ? [row, detail] : [row];
            });
            const dataRows = allRows.filter((row) => !row.hidden
                && (row.dataset.rowKey || row.dataset.groupCollapsed === "true"));
            const pages = Math.max(1, Math.ceil(dataRows.length / pageSize));
            pageTotal = pages;
            if (revealKey) {
                const index = dataRows.findIndex((row) => row.dataset.rowKey === revealKey);
                if (index >= 0) pageIndex = Math.floor(index / pageSize);
                revealKey = "";
            }
            pageIndex = Math.min(pageIndex, pages - 1);
            const selected = new Set(dataRows.slice(
                pageIndex * pageSize, (pageIndex + 1) * pageSize,
            ));
            const byKey = new Map(dataRows.map((row) => [row.dataset.rowKey, row]));
            const records = new Map(ordered.map((item) => [item.key, item]));
            [...selected].forEach((row) => {
                let parent = records.get(row.dataset.rowKey)?.parentKey;
                while (parent && byKey.has(parent)) {
                    selected.add(byKey.get(parent));
                    parent = records.get(parent)?.parentKey;
                }
            });
            const keep = new Set(selected);
            selected.forEach((row) => rowGroupParents.get(row)?.forEach((group) => keep.add(group)));
            allRows.forEach((row) => {
                if (row.dataset.detailOwner && selected.has(byKey.get(row.dataset.detailOwner))) {
                    keep.add(row);
                }
            });
            body.replaceChildren(...allRows.filter(row => keep.has(row)));
            [...body.children].forEach((row) => {
                if (rowHydrators.has(row)) {
                    rowHydrators.get(row)();
                    rowHydrators.delete(row);
                }
            });
            updateViewportHeight();
            count.textContent = `${visibleRows.length} of ${baseRows.length} items`;
            pageLabel.textContent = `Page ${pageIndex + 1} of ${pages}`;
            previousPage.disabled = pageIndex === 0;
            nextPage.disabled = pageIndex >= pages - 1;
            firstPage.disabled = previousPage.disabled;
            lastPage.disabled = nextPage.disabled;
            pageInput.max = String(pages);
            pageInput.value = String(pageIndex + 1);
            // Controls stay while filtering shrinks a larger table or the reader enlarged the page.
            footer.dataset.singlePage = String(baseRows.length <= Math.min(pageSize, initialPageSize));
            shell.dispatchEvent(new CustomEvent("obs-table-change", {bubbles: true, detail: {reason}}));
        };

        const draw = () => {
            renderHead();
            renderColumnWidths();
            renderBody();
        };

        const apply = () => {
            let query;
            try {
                query = globalThis.obsQuery.compile(input.value);
            } catch (error) {
                status.textContent = error.message;
                status.hidden = false;
                return;
            }
            visibleRows = retainMatchesAndAncestors(baseRows, query);
            appliedQuery = query;
            shell.dataset.filterActive = String(!query.empty);
            filterWarning.hidden = query.empty;
            optionsToggle.dataset.filterActive = String(!query.empty);
            const label = query.empty ? "Table options" : "Table options; filter active";
            optionsToggle.setAttribute("aria-label", label);
            optionsToggle.title = label;
            status.hidden = true;
            pageIndex = 0;
            renderBody();
        };

        previousPage.addEventListener("click", () => {
            pageIndex = Math.max(0, pageIndex - 1);
            renderBody();
        });
        nextPage.addEventListener("click", () => {
            pageIndex += 1;
            renderBody();
        });
        firstPage.addEventListener("click", () => {pageIndex = 0; renderBody();});
        lastPage.addEventListener("click", () => {pageIndex = pageTotal - 1; renderBody();});
        pageLabel.addEventListener("click", () => {
            pageLabel.hidden = true;
            pageInput.hidden = false;
            pageInput.focus();
            pageInput.select();
        });
        const selectPage = () => {
            const requested = Number(pageInput.value);
            if (!Number.isSafeInteger(requested) || requested < 1 || requested > pageTotal) {
                pageInput.setCustomValidity(`Choose a page from 1 to ${pageTotal}.`);
                pageInput.reportValidity();
                return;
            }
            pageInput.setCustomValidity("");
            pageInput.hidden = true;
            pageLabel.hidden = false;
            if (pageIndex === requested - 1) return;
            pageIndex = requested - 1;
            renderBody();
        };
        pageInput.addEventListener("change", selectPage);
        pageInput.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();
                selectPage();
                pageLabel.focus();
            } else if (event.key === "Escape") {
                pageInput.hidden = true;
                pageLabel.hidden = false;
                pageLabel.focus();
            }
        });
        sizeInput.addEventListener("change", () => {
            const value = Number(sizeInput.value);
            if (!Number.isSafeInteger(value) || value < 1) {
                status.textContent = "Items per page must be a positive whole number.";
                status.hidden = false;
                if (options.hidden) optionsToggle.click();
                panels.forEach((panel, name) => {
                    panel.hidden = name !== "filter";
                    panelButtons.get(name).setAttribute("aria-expanded", String(name === "filter"));
                });
                sizeInput.setAttribute("aria-invalid", "true");
                return;
            }
            pageSize = value;
            pageIndex = 0;
            sizeInput.removeAttribute("aria-invalid");
            status.hidden = true;
            renderBody();
        });
        input.addEventListener("input", () => {
            filterSelections.clear();
            apply();
            renderFacets();
        });
        shell.addEventListener("obs-table-set-filter", (event) => {
            filterSelections.clear();
            input.value = event.detail.expression;
            apply();
            renderFacets();
        });
        shell.addEventListener("obs-table-set-row-keys", event => {
            const keys = event.detail.keys;
            if (keys !== null && (!Array.isArray(keys) ||
                    keys.some(key => typeof key !== "string"))) {
                throw new TypeError("Table presentation row keys must be an array or null.");
            }
            rowKeys = keys === null ? null : new Set(keys);
            onRowKeysChange?.(keys);
            baseRows = retainMatchesAndAncestors(scopedRows(), baseQuery);
            visibleRows = retainMatchesAndAncestors(baseRows, appliedQuery);
            renderBody();
            renderFacets();
        });
        shell.addEventListener("obs-table-set-columns", event => {
            const keys = event.detail.columns;
            if (!Array.isArray(keys) || !keys.length || new Set(keys).size !== keys.length ||
                    keys.some(column => !catalogByKey.has(column))) {
                throw new TypeError("Visible table columns must be unique known column keys.");
            }
            if (shell.isConnected) shell.dispatchEvent(
                new CustomEvent("obs-table-before-change", {bubbles: true}),
            );
            columns.splice(0, columns.length, ...keys.map(column => catalogByKey.get(column)));
            projectedColumnKeys = [...keys];
            draw();
            renderProperties();
            publishPresentation();
        });
        shell.addEventListener("obs-table-reveal-row", (event) => {
            const byKey = new Map(baseRows.map((row) => [row.key, row]));
            let target = byKey.get(event.detail.key);
            if (!target) return;
            revealKey = target.key;
            if (event.detail.details && hasDetails(target)) expandedDetails.add(target.key);
            const subject = catalogByKey.get(event.detail.column);
            let revealColumn = false;
            if (subject?.detail) {
                selectedDetailColumns.set(target.key, subject.key);
                if (!columns.some(column => column.key === subject.key)) {
                    columns.push(subject);
                    revealColumn = true;
                }
                publishDetailState();
            }
            while (target?.parentKey) {
                expanded.add(target.parentKey);
                target = byKey.get(target.parentKey);
            }
            if (revealColumn) {
                draw();
                publishPresentation();
            } else renderBody();
        });
        propertyInput.addEventListener("input", renderProperties);
        input.value = initialExpression;
        renderHead();
        renderColumnWidths();
        apply();
        renderFacets();
        renderProperties();
        renderOrder();
        const observer = new ResizeObserver(() => {
            if (!shell.isConnected) {
                observer.disconnect();
                document.fonts?.removeEventListener("loadingdone", refitAfterFontLoad);
                return;
            }
            updateViewportHeight();
            renderColumnWidths();
        });
        // A loaded web font changes text metrics under an unchanged font string and often
        // without resizing the table, so measured content widths are discarded explicitly.
        function refitAfterFontLoad() {
            if (!shell.isConnected) return;
            measuredStyle = "";
            renderColumnWidths();
        }
        document.fonts?.addEventListener("loadingdone", refitAfterFontLoad);
        observer.observe(scroller);
        observer.observe(table);
        return {
            element: shell,
            columnPlan,
            fittedWidths: () => [...fittedWidths],
            setRows: (updated) => {
                detailAvailability.clear();
                rows = updated;
                baseRows = retainMatchesAndAncestors(scopedRows(), baseQuery);
                visibleRows = retainMatchesAndAncestors(baseRows, appliedQuery);
                renderBody();
                renderFacets();
            },
            setExpression: (value) => {
                input.value = value;
                apply();
            },
        };
    };

    globalThis.obsDataTable = {render, renderFilterFields, fitColumns, fitStaticTable, compareGroupLabels};
})();