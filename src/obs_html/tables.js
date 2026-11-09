(() => {
    // The tables feature's reader code (features.py, tables): a note's Base tables, their saved
    // presentation and their rows in search. artifact.js calls attach once with what the tables
    // read of the reader, and reaches the tables only through what attach returns (architecture.md,
    // Rendering and runtime). activeFilter and visibleIndices change as the reader filters, so core
    // hands them as getters.
    globalThis.obsTables = {attach: core => {
    const {
        artifactData,
        records,
        notes,
        recordsBySlug,
        chapters,
        tocSlugs,
        chapterBody,
        queryProfile,
        queryPopulation,
        isDocument,
        artifactTableRows,
        baseFilterExpression,
        tableRecord,
        formatMetadataValue,
        meaningfulMetadata,
        appendTableCell,
        appendIconCell,
        appendTrustedHtml,
        permittedMetadata,
        hasSubjectContent,
        sourceHref,
        propertyEditor,
    } = core;
    const richTextElements = new Set((
        "p div span br strong b em i u s del sub sup blockquote pre code ul ol li " +
        "table thead tbody tfoot tr th td caption hr h1 h2 h3 h4 h5 h6 figure figcaption"
    ).split(" "));
    const appendRichHtml = (container, value) => {
        if (typeof value !== "string") throw new Error("Rich HTML metadata must be a string.");
        const inertFragment = source => {
            const template = document.createElement("template");
            template.innerHTML = source;
            return template.content;
        };
        let content = inertFragment(value);
        for (let layer = 0; layer < 2 && !content.children.length; layer++) {
            const decoded = content.textContent;
            const tag = /^\s*(?:<|&lt;)([a-z][a-z0-9]*)\b/i.exec(decoded)?.[1].toLowerCase();
            if (!richTextElements.has(tag) && !["html", "head", "body", "a", "img"].includes(tag)) break;
            content = inertFragment(decoded);
        }
        const append = (parent, source) => {
            if (source.nodeType === 3) {
                parent.append(document.createTextNode(source.textContent));
                return;
            }
            if (source.nodeType !== 1) return;
            const tag = source.localName.toLowerCase();
            if (["script", "style", "iframe", "object", "embed", "template", "base", "meta", "link"].includes(tag)) return;
            if (tag === "img") {
                const image = document.createElement("span");
                image.className = "rich-metadata-image";
                image.textContent = source.getAttribute("alt")?.trim()
                    ? `[Image: ${source.getAttribute("alt").trim()}]` : "[Source image not included]";
                image.dataset.hoverHelp = "The source image is not embedded in this HTML.";
                parent.append(image);
                return;
            }
            const href = source.getAttribute("href");
            const url = tag === "a" && href && URL.canParse(href) ? new URL(href) : null;
            if (!richTextElements.has(tag) && !(url && ["http:", "https:", "mailto:"].includes(url.protocol))) {
                [...source.childNodes].forEach(child => append(parent, child));
                return;
            }
            const element = document.createElement(tag);
            if (url) element.href = url.href;
            if (source.hasAttribute("title")) element.title = source.getAttribute("title");
            if (tag === "td" || tag === "th") {
                if (source.hasAttribute("colspan")) element.colSpan = source.colSpan;
                if (source.hasAttribute("rowspan")) element.rowSpan = source.rowSpan;
            }
            if (tag === "ol" && source.hasAttribute("start")) element.start = source.start;
            if (tag === "li" && source.hasAttribute("value")) element.value = source.value;
            [...source.childNodes].forEach(child => append(element, child));
            parent.append(element);
        };
        [...content.childNodes].forEach(node => append(container, node));
    };
    const richMetadata = (value, format, field) => {
        const container = document.createElement("div");
        container.className = "rich-metadata";
        if (format === "html") appendRichHtml(container, value);
        else {
            const scalar = cell => cell === null || typeof cell === "string" ||
                typeof cell === "boolean" || (typeof cell === "number" && Number.isFinite(cell));
            if (!value || !Array.isArray(value.headers) || !value.headers.every(header => typeof header === "string") ||
                    !Array.isArray(value.rows) || !value.rows.every(row => Array.isArray(row) && row.every(scalar))) {
                throw new Error(`Metadata table ${field} requires string headers and scalar cell rows.`);
            }
            if (!value.rows.length) return null;
            const table = document.createElement("table");
            if (value.headers.length) {
                const head = table.createTHead().insertRow();
                value.headers.forEach(header => {
                    const cell = document.createElement("th");
                    cell.scope = "col";
                    cell.textContent = header;
                    head.append(cell);
                });
            }
            const body = table.createTBody();
            value.rows.forEach(row => {
                const element = body.insertRow();
                row.forEach(value => {
                    const cell = element.insertCell();
                    if (typeof value === "string") appendRichHtml(cell, value);
                    else cell.textContent = value === null ? "" : String(value);
                });
            });
            container.append(table);
        }
        return container.textContent.trim() ? container : null;
    };

    // Each register's definition as rendered: a different one is the reader's edited query.
    const authoredDefinitions = new Map(records.flatMap(record => (record.tables || [])
        .filter(table => table.rows).map(table => [table.key, JSON.stringify(table.definition)])));
    const tableDefinition = (table, staticView = false) => {
        const definition = globalThis.obsBases.project(table.definition, records);
        const viewIndex = Math.min(table.view || 0, definition.views.length - 1);
        const view = definition.views[viewIndex];
        const fieldName = key => key.startsWith('note["') && key.endsWith('"]')
            ? key.slice(6, -2) : key.replace(/^note\./, "");
        const properties = Object.fromEntries(Object.entries(definition.properties || {})
            .map(([key, value]) => [fieldName(key), value]));
        view.order = view.order.map(fieldName);
        // Obsidian's columnSize pixels are relative weights over the available width (generic-tables).
        const columnSizes = Object.fromEntries(Object.entries(view.columnSize || {})
            .map(([key, size]) => [fieldName(key), size]));
        for (const key of ["groupBy", "sort"]) {
            if (!view[key]) continue;
            const normalize = item => ({...item, property: fieldName(item.property)});
            view[key] = Array.isArray(view[key]) ? view[key].map(normalize) : normalize(view[key]);
        }
        const allRows = artifactTableRows();
        const parts = [definition.filters, view.filters]
            .filter((item) => item !== undefined && item !== null);
        const filters = parts.length ? {and: parts} : undefined;
        const query = baseFilterExpression(filters);
        // Without obs.records a view selects canonical notes, as in Obsidian (generic-tables).
        const recordType = view.obs?.records ?? definition.obs?.records;
        const nativeNotes = !recordType;
        // Projected rows resolve their own fields first, then the owner note (generic-tables).
        const compiled = globalThis.obsBases.compileFilter(filters, (row, field) => {
            const owner = recordsBySlug.get(row.noteId);
            if (nativeNotes && owner) return globalThis.obsBases.recordValue(owner, field);
            if (Object.hasOwn(row.ownFields, field)) return row.ownFields[field];
            return owner ? globalThis.obsBases.recordValue(owner, field) : undefined;
        });
        // A register's rows are the core's selection (obs capabilities/registers): this view's, or,
        // under a reader-edited query, all of the register's, which that query narrows. A fence's
        // rows are selected here. Generation provenance is the adapter's own documentMetadata.
        const edited = table.rows && JSON.stringify(table.definition) !== authoredDefinitions.get(table.key);
        const coreKeys = !table.rows ? undefined : edited ? [...new Set(table.rows.flat())] : table.rows[viewIndex];
        const rowsByKey = coreKeys && new Map(allRows.map(row => [row.key, row]));
        let rows = coreKeys ? coreKeys.map(key => {
            if (!rowsByKey.has(key)) throw new Error(`Register ${table.key}: row ${key} is not in the HTML's embedded data; the HTML was built from inputs that disagree. Rebuild it with obs-document and obs-html.`);
            return rowsByKey.get(key);
        }).filter(row => row.values.recordType === (recordType || "note")) : allRows.filter(row => row.values.recordType === (recordType || "note"));
        if (coreKeys && recordType === "documentMetadata") {
            rows.push(...allRows.filter(row => row.key.startsWith("generation:") && compiled.match(row)));
        }
        const selection = coreKeys && !edited ? {empty: true, match: () => true} : compiled;
        if (nativeNotes) rows = rows.map(row => {
            const owner = recordsBySlug.get(row.noteId);
            const values = Object.fromEntries(Object.keys(row.values).flatMap(field => {
                const value = globalThis.obsBases.recordValue(owner, field);
                return value === undefined ? [] : [[field, formatMetadataValue(value)]];
            }));
            return tableRecord(row.key, values, {
                ...row, cells: Object.fromEntries(Object.entries(row.cells).filter(([field]) =>
                    globalThis.obsBases.recordValue(owner, field) !== undefined)),
            });
        });
        // A view's members label the core's rows (generic-tables); the core selected them and sent
        // them in member order, so a member names a row here or nothing, and the order stays.
        const members = view.obs?.members;
        if (coreKeys && members) {
            const notePath = (row) => recordsBySlug.get(row.noteId)?.sourcePath ?? row.values.sourcePath;
            const byPath = new Map(members.map(member => [member.path, member]));
            rows = rows.map(row => {
                const member = byPath.get(notePath(row));
                if (!member) return row;
                const label = member.label ?? "";
                const cells = {...row.cells};
                if (member.label !== undefined && row.noteId) {
                    cells["obsHtml.label"] = {type: "detail", href: `#${row.noteId}`, label};
                }
                return {
                    ...row,
                    values: {...row.values, "obsHtml.label": label},
                    ownFields: {...row.ownFields, "obsHtml.label": label},
                    fields: {...row.fields, "obshtml.label": [label]},
                    cells,
                };
            });
        }
        const matched = rows.filter((row) => selection.match(row));
        const fields = [...new Set([
            ...view.order,
            ...matched.flatMap((row) => Object.keys(row.values)),
        ])];
        const column = (key) => {
            const presentation = properties[key]?.obsHtml || {};
            const icons = presentation.icons || (presentation.icon ? [presentation.icon] : []);
            const metadata = presentation.reference?.metadata;
            const leadingLines = (presentation.leadingLines || []).map(fieldName);
            return {
                key,
                label: properties[key]?.displayName || key,
                hideLabel: properties[key]?.displayName === "" || icons.length === 1,
                detail: presentation.detail === true,
                hasDetail: (row) => {
                    if (!presentation.detail) return false;
                    const owner = recordsBySlug.get(row.noteId);
                    return Boolean(owner && globalThis.obsBases.referenceRecords(
                        owner, key, recordsBySlug,
                    ).some(({record}) => hasSubjectContent(record, metadata)));
                },
                fixed: icons.length > 0,
                weight: icons.length ? undefined : columnSizes[key],
                width: icons.length ? artifactData.tableIconWidthPixels * icons.length : undefined,
                render: (row, cell) => {
                    if (presentation.singleLine) cell.classList.add("data-table-cell--single-line");
                    if (icons.length) {
                        icons.forEach(icon => appendIconCell(cell, icon, row));
                        return;
                    }
                    const owner = recordsBySlug.get(row.noteId);
                    leadingLines.forEach(field => {
                        let value = row.values[field];
                        if (value === undefined && owner) {
                            const raw = globalThis.obsBases.recordValue(owner, field);
                            if (meaningfulMetadata(raw)) value = formatMetadataValue(raw);
                        }
                        if (!meaningfulMetadata(value) || !String(value).trim()) return;
                        const line = document.createElement("div");
                        line.className = "data-table-leading-line";
                        line.dataset.tableLeadingLine = field;
                        appendTableCell(line, row.cells[field], value);
                        cell.append(line);
                    });
                    if (presentation.editable && !staticView) {
                        const editor = propertyEditor(owner, key, presentation);
                        if (editor) {
                            cell.append(editor);
                            return;
                        }
                    }
                    if (presentation.reference) {
                        const owner = recordsBySlug.get(row.noteId);
                        const targets = owner ? globalThis.obsBases.referenceRecords(owner, key, recordsBySlug) : [];
                        targets.forEach(({record, href}, index) => {
                            if (index) cell.append(document.createElement("br"));
                            const values = presentation.reference.label.map(field =>
                                globalThis.obsBases.recordValue(record, field))
                                .filter(value => value !== undefined && value !== null && value !== "");
                            const sourceLink = sourceHref(record, presentation.reference.linkProperty);
                            const link = appendTableCell(cell, {
                                type: "link", href: sourceLink || href,
                                label: values.map(formatMetadataValue).join(" \u2014 ") || record.title,
                            });
                            if (presentation.singleLine) link.title = link.textContent;
                            if (!sourceLink && !staticView && view.obsHtml?.details === "columns" &&
                                    presentation.detail && hasSubjectContent(record, metadata)) {
                                link.dataset.tableReferenceColumn = key;
                            }
                        });
                        if (!targets.length) cell.append("\u2014");
                        return;
                    }
                    if (presentation.linkProperty && owner) {
                        const href = sourceHref(owner, presentation.linkProperty);
                        if (href) {
                            appendTableCell(cell, {type: "link", href, label: row.values[key] ?? ""});
                            return;
                        }
                    }
                    const descriptor = row.cells[key];
                    appendTableCell(cell, staticView && descriptor?.type === "detail"
                        ? {...descriptor, type: "link"} : descriptor, row.values[key]);
                },
            };
        };
        const directives = (value) => (Array.isArray(value) ? value : value ? [value] : []);
        return {
            properties,
            rows,
            query,
            baseQuery: selection,
            maxRows: definition.obsHtml?.maxRows,
            wide: view.obsHtml?.wide === true,
            compact: view.obsHtml?.compact === true,
            minimumColumnWidth: view.obsHtml?.compact
                ? artifactData.tableCompactColumnMinimumPixels : artifactData.tableColumnMinimumPixels,
            columnDetails: view.obsHtml?.details === "columns",
            showEmptyDetailTabs: view.obsHtml?.showEmptyDetailTabs === true,
            screenPageBreaks: view.obsHtml?.screenPageBreaks !== false,
            pagination: view.obsHtml?.pagination !== false,
            pageSize: view.obsHtml?.pageSize ?? artifactData.tablePageSize,
            columnSizing: view.obsHtml?.columnSizing,
            detailFontSize: view.obsHtml?.detailFontSize ?? artifactData.tableDetailFontSizePoints,
            fieldCatalog: queryProfile.scope === "records" && queryProfile.fields && matched.length &&
                matched.every(row => queryPopulation.match(recordsBySlug.get(row.noteId) || row))
                ? queryProfile.fields.map(({field, label}) => ({
                    ...column(field), label: label || properties[field]?.displayName || field,
                }))
                : undefined,
            columns: view.order.map(column),
            availableColumns: fields.map(column),
            initialGroup: directives(view.groupBy).map(group => view.obsHtml?.groupOrder
                ? {...group, order: view.obsHtml.groupOrder} : group),
            initialSort: directives(view.sort),
            name: view.name || "",
            views: definition.views.map(item => item.name || ""),
            view: viewIndex,
        };
    };

    const filterTableRows = (rows, respectFilter = true) => !respectFilter || queryProfile.scope !== "records"
        ? rows : rows.filter((row) => {
            const note = recordsBySlug.get(row.noteId);
            return !note || !queryPopulation.match(note) || core.activeFilter.match(note);
        });
    // Search and table filters read every row's reader-visible text from the model,
    // independent of which page, group or detail panel is currently rendered.
    let rowTextCache = new Map();
    ["obs-canonical-property-change", "obs-table-definition-change"].forEach(type =>
        document.addEventListener(type, () => {
            rowTextCache = new Map();
        }));
    const plainText = value => String(value ?? "").replace(/\s+/g, " ").trim();
    const renderedText = node => plainText([node.textContent,
        ...[...node.querySelectorAll("input, textarea")].map(field => field.value)].join(" "));
    const rowSearchText = (definition, tableKey, row) => {
        const columns = definition.columns.filter(column => !column.fixed);
        const cacheKey = JSON.stringify([tableKey, columns.map(column => column.key), row.key]);
        if (rowTextCache.has(cacheKey)) return rowTextCache.get(cacheKey);
        const cells = columns.map(column => {
            const cell = document.createElement("td");
            column.render(row, cell);
            return {column: column.key, text: renderedText(cell)};
        });
        const details = [];
        const owner = recordsBySlug.get(row.noteId);
        if (owner) {
            definition.columns.filter(column => column.detail).forEach(column => {
                const profile = definition.properties?.[column.key]?.obsHtml?.reference?.metadata;
                const text = plainText(globalThis.obsBases.referenceRecords(owner, column.key, recordsBySlug)
                    .filter(({record}) => hasSubjectContent(record, profile))
                    .flatMap(({record}) => [
                        ...permittedMetadata(record, profile).map(([, value]) => value), record.text,
                    ]).join(" "));
                if (text) details.push({column: column.key, text});
            });
            const ownerDetails = definition.columnDetails ? Boolean(owner.html.trim())
                : !tocSlugs.has(owner.slug) && isDocument(owner);
            if (ownerDetails) {
                const text = plainText([
                    ...(definition.columnDetails ? [] : permittedMetadata(owner).map(([, value]) => value)),
                    owner.text,
                ].join(" "));
                if (text) details.push({column: undefined, text});
            }
        }
        const label = cells.map(cell => cell.text).find(text => /[\p{L}\p{N}]/u.test(text)) || row.key;
        const all = [...cells, ...details].map(item => item.text).join(" ");
        const result = {cells, details, label, all};
        rowTextCache.set(cacheKey, result);
        return result;
    };
    const searchableRows = (definition, tableKey, rows) => rows.map(row => {
        if (!definition.baseQuery.match(row)) return row;
        const {all} = rowSearchText(definition, tableKey, row);
        return {...row, haystack: `${row.haystack} ${all}`, detail: `${row.detail} ${all}`};
    });
    const tableSearchHits = (record, table) => {
        const state = tableStates.get(table.key);
        const definition = tableDefinition({...table, definition: state?.definition || table.definition, view: state?.view});
        const groups = definition.initialGroup;
        return definition.rows.filter(row => definition.baseQuery.match(row))
            .map((row, index) => ({row, index}))
            .sort((left, right) => {
                for (const group of groups) {
                    const order = globalThis.obsDataTable.compareGroupLabels(group)(
                        String(left.row.values[group.property] ?? "Unspecified"),
                        String(right.row.values[group.property] ?? "Unspecified"));
                    if (order) return order;
                }
                return left.index - right.index;
            })
            .map(({row}) => {
                const text = rowSearchText(definition, table.key, row);
                const fields = {...row.fields, text: text.all, content: text.all, body: text.all};
                return {
                    kind: "row", slug: record.slug, chapter: record, table: table.key,
                    tableName: definition.name, row, text,
                    target: {haystack: `${row.haystack} ${text.all}`, detail: text.all, fields},
                };
            });
    };
    const tableDefinitions = notes.flatMap(note => note.tables || []);
    const tableKeys = new Set(tableDefinitions.map(table => table.key));
    const savedPresentations = artifactData.readerState?.tables;
    const invalidSavedPresentations = savedPresentations !== undefined &&
        (!savedPresentations || typeof savedPresentations !== "object" ||
        Array.isArray(savedPresentations) || Object.keys(savedPresentations).some(key => !tableKeys.has(key)));
    // The selected view is saved by name beside the visible-column presentation (generic-tables).
    const savedTableState = table => {
        if (invalidSavedPresentations) return {view: 0, presentation: null};
        const saved = savedPresentations?.[table.key];
        // The table runtime validates the presentation itself; only a saved view name is read here.
        if (!saved || typeof saved !== "object" || Array.isArray(saved) || saved.view === undefined) {
            return {view: 0, presentation: saved};
        }
        const {view: name, ...presentation} = saved;
        const view = table.definition.views.findIndex(item => item.name === name);
        if (view < 0) return {view: 0, presentation: null};
        return {view, presentation: Object.keys(presentation).length ? presentation : undefined};
    };
    const tableStates = new Map(tableDefinitions.map(table => [table.key, {
        definition: table.definition,
        ...savedTableState(table),
    }]));
    const renderChapterTables = (
        record, root = chapterBody, staticView = false, respectFilter = true, firstTableFilter = "",
        firstTableProjection = "",
    ) => {
        (record.tables || []).forEach((table) => {
            const placeholder = root.querySelector(`[data-base-table="${table.key}"]`);
            if (!placeholder) return;
            if (!tableStates.has(table.key)) {
                tableStates.set(table.key, {definition: table.definition, view: 0});
            }
            const state = tableStates.get(table.key);
            const mount = (previous) => {
                const definition = tableDefinition({...table, definition: state.definition, view: state.view}, staticView);
                const rendered = globalThis.obsDataTable.render({
                key: table.key,
                views: definition.views,
                activeView: definition.view,
                onViewChange: staticView ? undefined : index => {
                    state.view = index;
                    delete state.presentation;
                    delete state.widths;
                    mount(rendered.element);
                },
                columns: definition.columns,
                availableColumns: definition.availableColumns,
                fieldCatalog: definition.fieldCatalog,
                initialGroup: definition.initialGroup,
                initialSort: definition.initialSort,
                initialPageSize: staticView ? Number.MAX_SAFE_INTEGER : definition.pageSize,
                initialExpression: table.key === record.tables[0].key ? firstTableFilter : "",
                initialProjection: table.key === record.tables[0].key ? firstTableProjection : "",
                initialPresentation: state.presentation,
                onPresentationChange: staticView ? undefined : (presentation, defaults) => {
                    state.presentation = savedPresentations?.[table.key] === undefined &&
                        JSON.stringify(presentation) === JSON.stringify(defaults) ? undefined : presentation;
                },
                // Resized widths are session-only view state: not reader state, not an artifact change.
                initialColumnWidths: state.widths,
                onColumnWidthsChange: staticView ? undefined : widths => {state.widths = widths;},
                initialDetailState: definition.columnDetails ? state.details : undefined,
                initialRowKeys: state.rowKeys,
                onRowKeysChange: staticView ? undefined : keys => {state.rowKeys = keys;},
                onDetailStateChange: !staticView && definition.columnDetails ? details => {
                    state.details = details;
                } : undefined,
                rows: filterTableRows(staticView && respectFilter ? definition.rows.filter((row) =>
                    row.values.recordType !== "chapter" ||
                    core.visibleIndices.some((index) => chapters[index].slug === row.key),
                ) : searchableRows(definition, table.key, definition.rows), respectFilter),
                baseExpression: definition.query,
                baseQuery: definition.baseQuery,
                maxRows: definition.maxRows,
                wide: definition.wide,
                compact: definition.compact,
                minimumColumnWidth: definition.minimumColumnWidth,
                columnDetails: definition.columnDetails,
                showEmptyDetailTabs: definition.showEmptyDetailTabs,
                screenPageBreaks: definition.screenPageBreaks,
                pagination: definition.pagination,
                columnSizing: definition.columnSizing,
                detailFontSize: definition.detailFontSize,
                hasDetails: (row) => {
                    if (!row.noteId) return false;
                    const owner = recordsBySlug.get(row.noteId);
                    if (definition.columnDetails) {
                        return Boolean(owner?.html.trim() || definition.columns.some(
                            column => column.detail && column.hasDetail(row),
                        ));
                    }
                    return !staticView && !tocSlugs.has(row.noteId) &&
                        (typeof isDocument !== "function" || isDocument(owner));
                },
                renderDetails: (row, container, columnKey) => {
                    const owner = recordsBySlug.get(row.noteId);
                    if (!owner) throw new Error(`Missing canonical note: ${row.noteId}`);
                    const profile = columnKey === undefined ? undefined
                        : definition.properties?.[columnKey]?.obsHtml?.reference?.metadata;
                    const targets = columnKey === undefined ? [{record: owner}]
                        : globalThis.obsBases.referenceRecords(owner, columnKey, recordsBySlug)
                            .filter(({record}) => hasSubjectContent(record, profile));
                    if (!targets.length) {
                        const empty = document.createElement("p");
                        empty.className = "data-table-detail-empty";
                        empty.textContent = "No linked item.";
                        container.append(empty);
                    }
                    targets.forEach(({record: note}) => {
                        const subject = document.createElement("section");
                        subject.className = "data-table-detail-subject";
                        subject.dataset.referenceNote = note.slug;
                        const metadata = document.createElement("dl");
                        metadata.className = "note-detail-metadata";
                        const metadataEntries = permittedMetadata(note, profile);
                        metadataEntries.forEach(([field, value]) => {
                            const reference = definition.properties?.[columnKey]?.obsHtml?.reference;
                            const formatting = reference?.metadataFormats?.[field];
                            const raw = formatting
                                ? globalThis.obsBases.recordValue(note, formatting.source || field) : undefined;
                            const formatted = formatting && raw !== undefined && raw !== null &&
                                (typeof raw !== "string" || raw.trim())
                                ? richMetadata(raw, formatting.format, field) : undefined;
                            if (formatted === null) return;
                            const prefix = profile?.find(name => field === name || field.startsWith(`${name}.`));
                            const term = document.createElement("dt");
                            term.textContent = prefix && field.startsWith(`${prefix}.`)
                                ? field.slice(prefix.length + 1) : prefix === field ? field.split(".").at(-1) : field;
                            const description = document.createElement("dd");
                            const href = reference?.label[0] === field
                                ? sourceHref(note, reference.linkProperty) : undefined;
                            if (formatted) description.append(formatted);
                            else appendTableCell(description, href ? {type: "link", href, label: value}
                                : note.frontmatterHtml?.[field]
                                    ? {type: "html", html: note.frontmatterHtml[field]} : null, value);
                            metadata.append(term, description);
                        });
                        subject.append(metadata);
                        appendTrustedHtml(subject, note.html);
                        container.append(subject);
                        renderChapterTables(note, subject, staticView, respectFilter);
                    });
                },
                renderOwnerDetails: definition.columnDetails ? (row, container) => {
                    const owner = recordsBySlug.get(row.noteId);
                    if (!owner?.html.trim()) return;
                    const content = document.createElement("section");
                    content.className = "data-table-owner-content";
                    appendTrustedHtml(content, owner.html);
                    container.append(content);
                    renderChapterTables(owner, content, staticView, respectFilter);
                } : undefined,
                definitionText: state.draft ?? globalThis.obsBases.dump(state.definition),
                queryView: state.draft !== undefined,
                onDefinitionDraft: (text) => { state.draft = text; },
                onDefinitionChange: (text) => {
                    const edited = globalThis.obsBases.parse(text);
                    tableDefinition({definition: edited});
                    const oldDefinition = state.definition;
                    const oldDraft = state.draft;
                    const oldPresentation = state.presentation;
                    const oldWidths = state.widths;
                    const oldView = state.view;
                    state.definition = edited;
                    delete state.draft;
                    delete state.presentation;
                    delete state.widths;
                    state.view = 0;
                    try {
                        mount(rendered.element);
                        if (JSON.stringify(oldDefinition) !== JSON.stringify(edited)) {
                            document.dispatchEvent(new CustomEvent("obs-table-definition-change", {
                                detail: {key: table.key},
                            }));
                        }
                    } catch (error) {
                        state.definition = oldDefinition;
                        state.draft = oldDraft;
                        state.presentation = oldPresentation;
                        state.widths = oldWidths;
                        state.view = oldView;
                        throw error;
                    }
                },
                });
                previous.replaceWith(rendered.element);
                if (!staticView) {
                    const refreshRows = (event) => {
                        if (!rendered.element.isConnected) {
                            document.removeEventListener("obs-canonical-property-change", refreshRows);
                            document.removeEventListener("obs-artifact-filter", refreshRows);
                            return;
                        }
                        if (queryProfile.scope === "records" && event.type === "obs-canonical-property-change") return;
                        const refreshed = tableDefinition({...table, definition: state.definition, view: state.view});
                        rendered.setRows(filterTableRows(
                            searchableRows(refreshed, table.key, refreshed.rows), respectFilter));
                    };
                    document.addEventListener("obs-canonical-property-change", refreshRows);
                    if (queryProfile.scope === "records") {
                        document.addEventListener("obs-artifact-filter", refreshRows);
                    }
                }
                // The table's core node id keys its rows' review items (bars/comments.js).
                if (table.node) rendered.element.dataset.nodeId = table.node;
                if (staticView) {
                    const plainTable = rendered.element.querySelector("table");
                    if (table.node) plainTable.dataset.nodeId = table.node;
                    plainTable.querySelectorAll(".data-table-detail-panel[hidden]").forEach(panel => panel.remove());
                    if (definition.wide) plainTable.dataset.tableWide = "true";
                    if (!definition.screenPageBreaks) plainTable.dataset.screenPageBreaks = "false";
                    plainTable.style.setProperty("--table-icon-width", `${artifactData.tableIconWidthPixels}px`);
                    plainTable.style.tableLayout = "fixed";
                    const columns = [...plainTable.querySelector("colgroup").children];
                    const weights = rendered.fittedWidths();
                    const sum = weights.reduce((sum, width) => sum + width, 0);
                    columns.forEach((column, index) => {
                        column.style.width = `${100 * weights[index] / sum}%`;
                    });
                    // Pages refit content-sized columns once the table sits in its paper container.
                    if (definition.columnSizing !== "equal") {
                        plainTable.dataset.columnPlan = JSON.stringify(rendered.columnPlan());
                    }
                    plainTable.style.minWidth = "0";
                    plainTable.style.width = "100%";
                    plainTable.dataset.reviewTable = table.key;
                    plainTable.querySelectorAll(
                        ".data-table-controls, .data-table-column-resize, .data-table-tree-toggle, .data-table-group-toggle",
                    ).forEach((element) => element.remove());
                    plainTable.querySelectorAll("button").forEach((button) => {
                        if (button.getAttribute("role") === "tab" || button.hasAttribute("data-unavailable")
                            || button.classList.contains("data-table-icon-action")) {
                            const label = document.createElement(
                                button.getAttribute("aria-selected") === "true" ? "strong" : "span",
                            );
                            if (button.classList.contains("data-table-icon-action")) {
                                label.append(...button.childNodes);
                            } else label.textContent = button.textContent;
                            ["id", "title", "aria-label"].forEach(attribute => {
                                if (button.hasAttribute(attribute)) {
                                    label.setAttribute(attribute, button.getAttribute(attribute));
                                }
                            });
                            button.replaceWith(label);
                        } else button.replaceWith(document.createTextNode(button.textContent));
                    });
                    rendered.element.replaceWith(plainTable);
                }
            };
            mount(placeholder);
        });
    };

    return {
        definition: tableDefinition,
        states: tableStates,
        render: renderChapterTables,
        searchHits: tableSearchHits,
        shown: row => filterTableRows([row]).length > 0,
    };
    }};
})();
