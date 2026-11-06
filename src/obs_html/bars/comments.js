(() => {
    "use strict";

    const island = document.querySelector("[data-comment-island]");
    const authorInput = document.querySelector("[data-comment-author]");
    const addButton = document.querySelector("[data-comment-add]");
    const saveButton = document.querySelector("[data-comment-save]");
    const loadButton = document.querySelector("[data-comment-load]");
    const copyButton = document.querySelector("[data-comment-copy]");
    const fileInput = document.querySelector("[data-comment-files]");
    const filterInput = document.querySelector("[data-comment-filter-input]");
    const filterState = document.querySelector("[data-comment-filter-state]");
    const reviewSummary = document.querySelector("[data-review-summary]");
    const list = document.querySelector("[data-comment-list]");
    const announcer = document.querySelector("[data-comment-announcer]");
    const saveGuidance = document.querySelector("[data-review-save-guidance]");
    const chapterBody = document.querySelector("[data-chapter-body]");
    const activeChapter = chapterBody?.closest("[data-active-chapter]");
    if (!island || !authorInput || !addButton || !saveButton || !copyButton ||
            !loadButton || !fileInput || !filterInput || !filterState || !reviewSummary ||
            !list || !saveGuidance || !chapterBody) {
        return;
    }

    const usedIds = new Set();
    const reviewItemsCache = new Map();
    let nextId = 1;
    let activeFilter = globalThis.obsQuery.compile("");
    let activeReviewFilter = globalThis.obsQuery.compile("");
    let savedSnapshot = null;
    let savedArtifactSnapshot = null;
    let modelSnapshot;
    let modelSnapshotRevision = -1;
    let archiveSnapshot = "";
    let archiveSnapshotRevision = -1;

    const currentSnapshot = () => {
        const revision = globalThis.obsArtifact?.revision ?? 0;
        if (modelSnapshotRevision !== revision) {
            const artifact = globalThis.obsArtifact?.serializeModel
                ? JSON.parse(globalThis.obsArtifact.serializeModel()) : "";
            artifact.notes?.forEach((note) => delete note.frontmatterHtml);
            delete artifact.readerState;
            modelSnapshot = JSON.stringify(artifact);
            modelSnapshotRevision = revision;
        }
        return JSON.stringify(data) + modelSnapshot;
    };

    const isDirty = () => savedSnapshot !== null && currentSnapshot() !== savedSnapshot;
    const currentArtifactSnapshot = () => {
        const revision = globalThis.obsArtifact.revision;
        if (archiveSnapshotRevision !== revision) {
            archiveSnapshot = document.getElementById("obs-source-archive")?.textContent || "";
            archiveSnapshotRevision = revision;
        }
        // Reader state is never a change (artifact-ui.md "What counts as a change"): the saved
        // HTML still keeps it, but no reader action marks the HTML changed.
        return {semantic: currentSnapshot(), archive: archiveSnapshot};
    };
    const isArtifactDirty = () => {
        if (savedArtifactSnapshot === null) return false;
        const snapshot = currentArtifactSnapshot();
        return Object.keys(snapshot).some(key => snapshot[key] !== savedArtifactSnapshot[key]);
    };

    // Changed HTML is an information entry of the notice center; its details download the changed HTML.
    const artifactDownload = document.createElement("button");
    artifactDownload.type = "button";
    artifactDownload.dataset.artifactDownload = "";
    artifactDownload.textContent = "Download changed HTML";
    // A blocked download cannot be observed, so where the canary could not decide, the help names the remedy.
    const downloadHint = globalThis.obsCapabilities?.hint("downloads");
    if (downloadHint) artifactDownload.dataset.hoverHelp = downloadHint;
    const changedHtmlNotice = {
        id: "changed-html", severity: "information", title: "This HTML has changed",
        details: [
            "Comments or edits changed since this HTML was last saved. " +
                "Download the changed HTML to keep them; leaving the page asks first.",
            artifactDownload,
        ],
    };

    const updateSaveGuidance = () => {
        const dirty = isDirty();
        saveGuidance.dataset.dirty = String(dirty);
        saveGuidance.textContent = dirty
            ? "Unsaved review changes. Download HTML to keep review comments, decisions, and property edits before leaving."
            : "No unsaved review changes. Download HTML to keep review comments, decisions, and property edits.";
        const artifactDirty = isArtifactDirty();
        saveGuidance.dataset.artifactDirty = String(artifactDirty);
        if (artifactDirty) {
            if (!globalThis.obsNotices.has(changedHtmlNotice.id)) globalThis.obsNotices.post(changedHtmlNotice);
        } else globalThis.obsNotices.remove(changedHtmlNotice.id);
        document.dispatchEvent(new CustomEvent("obs-artifact-state-change", {
            detail: {dirty: artifactDirty},
        }));
    };

    window.addEventListener("beforeunload", (event) => {
        if (!isArtifactDirty()) return;
        event.preventDefault();
        event.returnValue = "";
    });

    const freshId = () => {
        let candidate;
        do {
            candidate = `comment-${nextId}`;
            nextId += 1;
        } while (usedIds.has(candidate));
        usedIds.add(candidate);
        return candidate;
    };

    const claimId = (value) => {
        const candidate = typeof value === "string" && value.trim() ? value.trim() : "";
        if (candidate && !usedIds.has(candidate)) {
            usedIds.add(candidate);
            return candidate;
        }
        return freshId();
    };

    const normalizeNode = (value) => {
        if (!value || typeof value !== "object" ||
                typeof value.author !== "string" || typeof value.text !== "string" ||
                !["open", "resolved"].includes(value.status) ||
                !Array.isArray(value.replies)) {
            throw new Error("The reviewed HTML contains an invalid comment.");
        }
        return {
            id: claimId(value.id),
            author: value.author.trim(),
            text: value.text,
            status: value.status,
            replies: value.replies.map(normalizeNode),
        };
    };

    const normalizeAnnotation = (value) => {
        if (!value || typeof value !== "object" || !value.target ||
                typeof value.target.chapter !== "string") {
            throw new Error("The reviewed HTML contains an invalid annotation target.");
        }
        const node = normalizeNode(value);
        const scope = {};
        if (value.target.table !== undefined || value.target.row !== undefined ||
                value.target.detail !== undefined || value.target.column !== undefined) {
            if (typeof value.target.table !== "string" || !value.target.table ||
                typeof value.target.row !== "string" || !value.target.row ||
                typeof value.target.detail !== "boolean") {
                throw new Error("The reviewed HTML contains an invalid table comment target.");
            }
            Object.assign(scope, {
                table: value.target.table, row: value.target.row, detail: value.target.detail,
            });
            if (value.target.column !== undefined) {
                if (!value.target.detail || typeof value.target.column !== "string" ||
                        !value.target.column.trim()) {
                    throw new Error("The reviewed HTML contains an invalid detail column target.");
                }
                scope.column = value.target.column;
            }
        }
        const anchor = {};
        if (value.target.item !== undefined) {
            if (typeof value.target.item !== "string" || !value.target.item) {
                throw new Error("The reviewed HTML contains an invalid review-item anchor.");
            }
            anchor.item = value.target.item;
        }
        if (value.target.section !== undefined) {
            if (typeof value.target.section !== "string") {
                throw new Error("The reviewed HTML contains an invalid section anchor.");
            }
            anchor.section = value.target.section;
        }
        if (value.target.wholeItem !== undefined) {
            if (typeof value.target.wholeItem !== "boolean") {
                throw new Error("The reviewed HTML contains an invalid whole-item anchor.");
            }
            anchor.wholeItem = value.target.wholeItem;
        }
        return {
            ...node,
            ...(value.batch === undefined ? {} : {batch: normalizeBatch(value.batch)}),
            target: {
                chapter: value.target.chapter,
                quote: typeof value.target.quote === "string" ? value.target.quote : "",
                prefix: typeof value.target.prefix === "string" ? value.target.prefix : "",
                suffix: typeof value.target.suffix === "string" ? value.target.suffix : "",
                start: Number.isInteger(value.target.start) ? value.target.start : null,
                end: Number.isInteger(value.target.end) ? value.target.end : null,
                ...anchor,
                ...scope,
            },
        };
    };

    const normalizeReview = (value) => {
        if (!value || typeof value !== "object" ||
                typeof value.chapter !== "string" || !value.chapter ||
                typeof value.item !== "string" || !/^(item-\d+|row-[^:]+:.+)$/.test(value.item) ||
                typeof value.reviewer !== "string" || !value.reviewer.trim() ||
                !["accepted", "rejected"].includes(value.state)) {
            throw new Error("The reviewed HTML contains an invalid review decision.");
        }
        return {
            chapter: value.chapter,
            item: value.item,
            reviewer: value.reviewer.trim(),
            state: value.state,
        };
    };

    const normalizeBatch = (value) => {
        if (!value || !["section", "chapter", "document"].includes(value.scope) ||
                !Array.isArray(value.items) || !value.items.length) {
            throw new Error("The reviewed HTML contains an invalid batch association.");
        }
        const seen = new Set();
        const items = value.items.map((item) => {
            const identity = normalizeReview({...item, reviewer: "Reviewer", state: "rejected"});
            const key = JSON.stringify([identity.chapter, identity.item]);
            if (seen.has(key)) throw new Error("The reviewed HTML contains duplicate batch items.");
            seen.add(key);
            return {chapter: identity.chapter, item: identity.item};
        });
        return {scope: value.scope, items};
    };

    const parseData = (value) => {
        if (!value || typeof value !== "object" || value.version !== 2 ||
            !Array.isArray(value.annotations)) {
            throw new Error("The reviewed HTML has an invalid comment island.");
        }
        if (value.reviews !== undefined && !Array.isArray(value.reviews)) {
            throw new Error("The reviewed HTML has invalid review decisions.");
        }
        if (value.reviewers !== undefined && !Array.isArray(value.reviewers)) {
            throw new Error("The reviewed HTML has invalid reviewers.");
        }
        const reviewers = (value.reviewers || []).map((reviewer) => {
            if (typeof reviewer !== "string" || !reviewer.trim()) {
                throw new Error("The reviewed HTML contains an invalid reviewer.");
            }
            return reviewer.trim();
        });
        return {
            annotations: value.annotations.map(normalizeAnnotation),
            reviewers: [...new Set(reviewers)],
            reviews: (value.reviews || []).map(normalizeReview),
        };
    };

    const reportFailure = (message) => {
        announcer.textContent = message;
        announcer.classList.remove("visually-hidden");
        announcer.setAttribute("role", "alert");
        console.error(message);
    };
    let data;
    try {
        const parsed = JSON.parse(island.textContent || "{}");
        data = {version: 2, ...parseData(parsed)};
    } catch (error) {
        reportFailure(`Comments could not be loaded: ${error.message}. The original review data was preserved.`);
        [addButton, saveButton, loadButton, copyButton].forEach((button) => { button.disabled = true; });
        return;
    }

    const authorKey = "obs-html-reviewer";
    authorInput.value = globalThis.obsStorage.read(authorKey, "reviewer") || "";
    authorInput.addEventListener("input", () => {
        globalThis.obsStorage.write(authorKey, authorInput.value, "reviewer");
    });
    authorInput.addEventListener("change", () => {
        syncReviewFields();
        updateReviewSummary();
        updateReviewMode();
        refreshReviewFilter();
    });

    const escapeJson = (value) => JSON.stringify(value)
        .replaceAll("&", "\\u0026")
        .replaceAll("<", "\\u003c")
        .replaceAll(">", "\\u003e");

    const persist = () => {
        island.textContent = escapeJson(data);
        updateSaveGuidance();
    };

    const currentAuthor = () => authorInput.value.trim() || "Reviewer";

    const registerReviewer = (reviewer = currentAuthor()) => {
        if (!data.reviewers.includes(reviewer)) data.reviewers.push(reviewer);
        return reviewer;
    };

    const walk = (nodes, visit) => {
        nodes.forEach((node) => {
            visit(node);
            walk(node.replies, visit);
        });
    };

    const findNode = (id, nodes = data.annotations, parent = null) => {
        for (const node of nodes) {
            if (node.id === id) {
                return {node, nodes, parent};
            }
            const found = findNode(id, node.replies, node);
            if (found) {
                return found;
            }
        }
        return null;
    };

    const targetLabel = (target) => target.quote || target.chapter;

    const recordFor = (annotation) => {
        const authors = [];
        const statuses = [];
        const texts = [];
        const ids = [];
        walk([annotation], (node) => {
            authors.push(node.author);
            statuses.push(node.status);
            texts.push(node.text);
            ids.push(node.id);
        });
        return {
            fields: {
                author: authors,
                status: statuses,
                chapter: annotation.target.chapter,
                quote: annotation.target.quote,
                text: texts,
                id: ids,
            },
            haystack: [annotation.target.chapter, annotation.target.quote, ...authors, ...texts].join("\n"),
            detail: [annotation.target.prefix, annotation.target.suffix].join("\n"),
        };
    };

    const addField = (container, key, value) => {
        const row = document.createElement("div");
        row.className = "comment-field";
        const label = document.createElement("span");
        label.className = "comment-key";
        label.textContent = key;
        const content = document.createElement("div");
        content.className = "comment-value";
        if (value instanceof Node) {
            content.append(value);
        } else {
            content.textContent = value;
        }
        row.append(label, content);
        container.append(row);
        return content;
    };

    const navigateTo = async (annotation) => {
        const opened = await globalThis.obsArtifact?.activateChapter(annotation.target.chapter);
        if (opened === false) return;
        if (annotation.target.table) {
            const table = [...chapterBody.querySelectorAll("[data-data-table]")].find(
                (element) => element.dataset.dataTable === annotation.target.table,
            );
            table?.dispatchEvent(new CustomEvent("obs-table-reveal-row", {
                detail: {
                    key: annotation.target.row, details: annotation.target.detail,
                    column: annotation.target.column,
                },
            }));
        }
        requestAnimationFrame(() => {
            repaintHighlights();
            const range = rangeForTarget(annotation.target);
            range?.startContainer.parentElement?.scrollIntoView({block: "center"});
        });
    };

    const renderNode = (node, annotation, depth = 0) => {
        const wrapper = document.createElement("div");
        wrapper.className = "comment-node";
        wrapper.style.setProperty("--comment-depth", String(depth));
        wrapper.dataset.commentId = node.id;

        const card = document.createElement("article");
        card.className = "comment-card";
        const fields = document.createElement("div");
        fields.className = "comment-fields";

        const targetButton = document.createElement("button");
        targetButton.type = "button";
        targetButton.className = "comment-target";
        const scope = annotation.batch ? `[Full ${annotation.batch.scope}] ` : "";
        targetButton.textContent = scope + targetLabel(annotation.target);
        targetButton.title = targetButton.textContent;
        targetButton.addEventListener("click", () => navigateTo(annotation));
        addField(fields, "Target", targetButton);
        addField(fields, "Author", node.author);
        addField(fields, "Status", node.status);

        const editor = document.createElement("textarea");
        editor.className = "comment-text-editor";
        editor.rows = Math.max(2, node.text.split("\n").length);
        editor.value = node.text;
        editor.setAttribute("aria-label", "Comment text");
        editor.addEventListener("input", () => {
            node.text = editor.value;
            persist();
        });
        addField(fields, "Text", editor);

        const actions = document.createElement("div");
        actions.className = "comment-card-actions";
        const reply = document.createElement("button");
        reply.type = "button";
        reply.textContent = "Reply";
        reply.addEventListener("click", () => {
            const id = freshId();
            node.replies.push({
                id,
                author: registerReviewer(),
                text: "",
                status: "open",
                replies: [],
            });
            persist();
            renderComments();
            updateReviewMode();
            requestAnimationFrame(() => {
                list.querySelector(`[data-comment-id="${CSS.escape(id)}"] .comment-text-editor`)?.focus();
            });
        });
        actions.append(reply);

        const resolve = document.createElement("button");
        resolve.type = "button";
        resolve.textContent = node.status === "open" ? "Resolve" : "Reopen";
        resolve.addEventListener("click", () => {
            node.status = node.status === "open" ? "resolved" : "open";
            persist();
            renderComments();
            repaintHighlights();
        });
        actions.append(resolve);

        const remove = document.createElement("button");
        remove.type = "button";
        remove.textContent = "Delete";
        remove.addEventListener("click", () => {
            const found = findNode(node.id);
            if (!found) {
                return;
            }
            found.nodes.splice(found.nodes.indexOf(found.node), 1);
            persist();
            renderComments();
            updateReviewMode();
            repaintHighlights();
        });
        actions.append(remove);
        addField(fields, "Actions", actions);

        card.append(fields);
        wrapper.append(card);

        if (node.replies.length) {
            const children = document.createElement("div");
            children.className = "comment-children";
            node.replies.forEach((child) => children.append(renderNode(child, annotation, depth + 1)));
            wrapper.append(children);
        }
        return wrapper;
    };

    const renderComments = () => {
        list.replaceChildren();
        const visible = data.annotations.filter((annotation) => activeFilter.match(recordFor(annotation)));
        filterState.textContent = `${visible.length} of ${data.annotations.length} comments`;
        visible.forEach((annotation) => list.append(renderNode(annotation, annotation)));
    };

    filterInput.addEventListener("input", () => {
        try {
            activeFilter = globalThis.obsQuery.compile(filterInput.value);
            filterInput.removeAttribute("aria-invalid");
            delete filterInput.dataset.hoverHelp;
            renderComments();
        } catch (error) {
            filterInput.setAttribute("aria-invalid", "true");
            filterInput.dataset.hoverHelp = error instanceof Error ? error.message : String(error);
        }
    });

    const tableScope = (element) => {
        const row = element?.closest("tr[data-row-key], tr[data-detail-owner]");
        const table = row?.closest("[data-data-table]");
        if (!table) return {};
        const panel = element.closest("[data-detail-column]");
        return {
            table: table.dataset.dataTable,
            row: row.dataset.rowKey || row.dataset.detailOwner,
            detail: Boolean(row.dataset.detailOwner),
            ...(row.dataset.detailOwner && panel && row.contains(panel)
                ? {column: panel.dataset.detailColumn} : {}),
        };
    };
    const targetRoot = (target) => {
        if (!target.table) return chapterBody;
        const table = [...chapterBody.querySelectorAll("[data-data-table]")].find(
            (element) => element.dataset.dataTable === target.table,
        );
        const row = table && [...table.querySelectorAll(
            target.detail ? "[data-detail-owner]" : "[data-row-key]",
        )].find((element) =>
            (target.detail ? element.dataset.detailOwner : element.dataset.rowKey) === target.row &&
            element.closest("[data-data-table]") === table,
        );
        if (!row || target.column === undefined) return row;
        return [...row.querySelectorAll("[data-detail-column]")].find(panel =>
            panel.dataset.detailColumn === target.column &&
            panel.closest("[data-detail-owner]") === row);
    };
    const canonicalText = (node) => {
        const copy = node.cloneNode(true);
        copy.querySelectorAll(".paper-header, .paper-footer").forEach((item) => item.remove());
        return copy.textContent || "";
    };
    const rangeText = (range) => canonicalText(range.cloneContents());
    const selectedTarget = () => {
        const selection = globalThis.getSelection();
        if (!selection || selection.rangeCount !== 1 || selection.isCollapsed) {
            return null;
        }
        const range = selection.getRangeAt(0);
        if (!chapterBody.contains(range.commonAncestorContainer)) {
            return null;
        }
        const quote = rangeText(range);
        if (!quote.trim()) {
            return null;
        }
        const scope = tableScope(range.startContainer.parentElement);
        const scopeRoot = targetRoot(scope);
        if (!scopeRoot?.contains(range.endContainer)) return null;
        const before = range.cloneRange();
        before.selectNodeContents(scopeRoot);
        before.setEnd(range.startContainer, range.startOffset);
        const start = rangeText(before).length;
        const complete = canonicalText(scopeRoot);
        const startNode = range.startContainer.nodeType === Node.ELEMENT_NODE
            ? range.startContainer : range.startContainer.parentElement;
        const section = sectionForElement(startNode);
        return {
            chapter: activeChapter?.dataset.chapter || "",
            quote,
            prefix: complete.slice(Math.max(0, start - 40), start),
            suffix: complete.slice(start + quote.length, start + quote.length + 40),
            start,
            end: start + quote.length,
            ...(reviewItemForRange(range) ? {item: reviewItemForRange(range)} : {}),
            ...(section ? {section} : {}),
            ...scope,
        };
    };

    const targetForElement = (element) => {
        const scope = tableScope(element);
        const scopeRoot = targetRoot(scope);
        const range = document.createRange();
        range.selectNodeContents(element);
        const before = range.cloneRange();
        before.selectNodeContents(scopeRoot);
        before.setEnd(range.startContainer, range.startOffset);
        const start = rangeText(before).length;
        const quote = rangeText(range);
        const complete = canonicalText(scopeRoot);
        const section = sectionForElement(element);
        return {
            chapter: activeChapter?.dataset.chapter || "",
            quote,
            prefix: complete.slice(Math.max(0, start - 40), start),
            suffix: complete.slice(start + quote.length, start + quote.length + 40),
            start,
            end: start + quote.length,
            ...(element.dataset.reviewItem ? {item: element.dataset.reviewItem} : {}),
            ...(section ? {section} : {}),
            wholeItem: true,
            ...scope,
        };
    };

    const sectionForElement = (element) => {
        const heading = element?.closest("[data-heading-section]")?.previousElementSibling;
        return heading?.querySelector("[data-heading-toggle]")?.dataset.label ||
            heading?.textContent.trim() || "";
    };

    const reviewItemForRange = (range) => {
        const node = range.startContainer.nodeType === Node.ELEMENT_NODE
            ? range.startContainer : range.startContainer.parentElement;
        const item = node?.closest("[data-review-item]");
        return item?.contains(range.endContainer) ? item.dataset.reviewItem : "";
    };

    const markdownFence = (value) => {
        const longest = Math.max(0, ...[...value.matchAll(/`+/g)].map(([run]) => run.length));
        const fence = "`".repeat(Math.max(3, longest + 1));
        return `${fence}text\n${value}${value.endsWith("\n") ? "" : "\n"}${fence}`;
    };

    const chapterRecord = (slug) =>
        globalThis.obsArtifact?.records?.find((record) => record.slug === slug);

    const pageForTarget = (target) => {
        if (target.chapter !== activeChapter?.dataset.chapter ||
                !document.documentElement.classList.contains("paged-mode")) return null;
        const range = rangeForTarget(target);
        if (!range || !target.quote || rangeText(range) !== target.quote) return null;
        // A range can start at the preceding text node's end, outside the marked item.
        let offset = 0;
        const node = textNodes(targetRoot(target)).find((candidate) => {
            offset += candidate.data.length;
            return target.start < offset;
        });
        const element = node?.parentElement;
        if (!element?.getClientRects().length ||
                ["hidden", "collapse"].includes(getComputedStyle(element).visibility)) return null;
        const sheet = element?.closest(".paper-sheet[data-page-chapter]");
        if (!sheet || sheet.dataset.pageChapter !== target.chapter) return null;
        const label = sheet.querySelector(".paper-page-number")?.textContent || "";
        return /^\s*Page (\d+) of \d+\s*$/.exec(label)?.[1] || null;
    };

    const tableColumnLabel = (target) => {
        if (target.chapter !== activeChapter?.dataset.chapter ||
                !target.table || !target.column) return "";
        const table = [...chapterBody.querySelectorAll("[data-data-table]")].find(
            (element) => element.dataset.dataTable === target.table,
        );
        return [...(table?.querySelectorAll("[data-column-key]") || [])]
            .find((element) => element.dataset.columnKey === target.column)?.textContent.trim() || "";
    };

    const anchorDescription = (target) => {
        if (target.table) {
            const anchor = `table key "${target.table}", row identity "${target.row}"`;
            if (!target.detail) return anchor;
            const column = target.column
                ? `, subject column "${target.column}"${tableColumnLabel(target)
                    ? ` (${tableColumnLabel(target)})` : ""}`
                : ", subject column unavailable";
            return `${anchor}, expanded detail${column}`;
        }
        const position = Number.isInteger(target.start) && Number.isInteger(target.end)
            ? `text positions ${target.start}-${target.end}` : "text positions unavailable";
        return `${target.item ? `review item "${target.item}"` : "paragraph anchor"}, ${position}`;
    };

    const formatComments = () => {
        const artifact = JSON.parse(document.querySelector("[data-artifact-data]").textContent);
        const metadata = artifact.document?.metadata || {};
        const identity = [
            document.title,
            metadata.product?.name,
            metadata["document type"],
            metadata["sap number"],
        ].filter(Boolean).join(" · ");
        const lines = [
            `# Comments — ${identity || "Untitled"}`,
            "",
            `Root comments: ${data.annotations.length}`,
        ];
        data.annotations.forEach((annotation, index) => {
            const target = annotation.target;
            const record = chapterRecord(target.chapter);
            const page = pageForTarget(target);
            const section = target.section || (() => {
                if (target.chapter !== activeChapter?.dataset.chapter) return "";
                const root = target.table ? targetRoot(target) : null;
                const range = target.table ? null : rangeForTarget(target);
                const node = root || range?.startContainer;
                const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
                return sectionForElement(element);
            })();
            lines.push(
                "",
                `## Thread ${index + 1}`,
                `- Root comment: ${annotation.id}`,
                `- Chapter: ${record?.title || target.chapter} (${target.chapter})`,
                `- Section: ${section || "unavailable"}`,
                `- Page: ${page || "unavailable (target is not on a currently rendered page)"}`,
                `- Anchor: ${anchorDescription(target)}`,
                `- Marked context${target.wholeItem ? " (whole-item context)" : ""}:`,
                "",
                markdownFence(target.quote),
            );
            if (annotation.batch) {
                lines.push(
                    `- Batch scope: full ${annotation.batch.scope}`,
                    "- Affected review items:",
                    ...annotation.batch.items.map((item) =>
                        `  - ${item.chapter} ${item.item}`),
                );
            }
            const appendNode = (node, parentId, depth) => {
                lines.push(
                    "",
                    `### ${parentId ? `Reply ${node.id} to ${parentId} (depth ${depth})`
                        : `Root comment ${node.id}`}`,
                    `- Author: ${node.author}`,
                    `- Status: ${node.status}`,
                    "- Text:",
                    "",
                    markdownFence(node.text),
                );
                node.replies.forEach((reply) => appendNode(reply, node.id, depth + 1));
            };
            appendNode(annotation, "", 0);
        });
        return `${lines.join("\n")}\n`;
    };

    const showCopyFeedback = (message, isError = false) => {
        announcer.textContent = message;
        announcer.setAttribute("role", isError ? "alert" : "status");
        announcer.classList.remove("visually-hidden");
    };

    const copyComments = async () => {
        if (!data.annotations.length) {
            showCopyFeedback("There are no comments to copy.", true);
            return;
        }
        const clipboard = globalThis.navigator?.clipboard;
        const clipboardLimit = globalThis.obsCapabilities?.limit("clipboard");
        if (clipboardLimit?.refused) {
            showCopyFeedback(`Comments were not copied. ${globalThis.obsCapabilities.explain("clipboard")}`, true);
            return;
        }
        if (typeof clipboard?.writeText !== "function") {
            showCopyFeedback("Clipboard is unavailable; comments were not copied.", true);
            return;
        }
        let contents;
        try {
            contents = formatComments();
        } catch (error) {
            const detail = error instanceof Error ? error.message : String(error);
            showCopyFeedback(`Comments could not be prepared for copying: ${detail}`, true);
            console.error("Comments could not be prepared for copying.", error);
            return;
        }
        try {
            showCopyFeedback("Copying comments…");
            await clipboard.writeText(contents);
            showCopyFeedback("Comments copied to clipboard.");
        } catch (error) {
            const detail = error instanceof Error ? error.message : String(error);
            // Where the canary could not decide, a rejected write is the observed refusal.
            const reason = globalThis.obsCapabilities?.fail("clipboard",
                `navigator.clipboard.writeText rejected: ${detail}`);
            showCopyFeedback(`Comments could not be copied to clipboard: ${detail}${reason ? ` ${reason}` : ""}`, true);
            console.error("Comments could not be copied to clipboard.", error);
        }
    };

    const createAnnotation = (target, batch) => {
        const id = freshId();
        data.annotations.push({
            id,
            target,
            ...(batch ? {batch} : {}),
            author: registerReviewer(),
            text: "",
            status: "open",
            replies: [],
        });
        persist();
        renderComments();
        updateReviewMode();
        repaintHighlights();
        requestAnimationFrame(() => {
            list.querySelector(`[data-comment-id="${CSS.escape(id)}"] .comment-text-editor`)?.focus();
        });
    };

    let pendingTarget = null;

    const updateSelectedTarget = () => {
        pendingTarget = selectedTarget();
        addButton.disabled = !pendingTarget;
        addButton.title = pendingTarget ? "Add comment" : "Select chapter text to add a comment";
    };

    document.addEventListener("selectionchange", updateSelectedTarget);

    addButton.addEventListener("click", () => {
        if (!pendingTarget) return;
        const target = pendingTarget;
        pendingTarget = null;
        addButton.disabled = true;
        globalThis.getSelection()?.removeAllRanges();
        createAnnotation(target);
    });

    const textNodes = (root = chapterBody) => {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) {
            if (!walker.currentNode.parentElement.closest(".paper-header, .paper-footer")) {
                nodes.push(walker.currentNode);
            }
        }
        return nodes;
    };

    const rangeForTarget = (target) => {
        if (target.chapter !== activeChapter?.dataset.chapter ||
                !Number.isInteger(target.start) || !Number.isInteger(target.end)) {
            return null;
        }
        const range = document.createRange();
        const root = targetRoot(target);
        if (!root) return null;
        let offset = 0;
        let startSet = false;
        for (const node of textNodes(root)) {
            const next = offset + node.data.length;
            if (!startSet && target.start >= offset && target.start <= next) {
                range.setStart(node, target.start - offset);
                startSet = true;
            }
            if (startSet && target.end >= offset && target.end <= next) {
                range.setEnd(node, target.end - offset);
                return range;
            }
            offset = next;
        }
        return null;
    };

    const reviewElements = (root) => [...root.querySelectorAll("p, li, tr, pre, figure")]
        .filter((element) => {
            if (element.closest(".data-table-detail-row")) return false;
            if (element.matches("tr")) return !element.closest("thead") &&
                (!element.closest("[data-data-table], [data-review-table]") || element.hasAttribute("data-row-key"));
            if (element.closest("tr")) return false;
            if (element.matches("li")) return true;
            if (element.matches("figure")) return !element.closest("li");
            if (element.matches("p[data-figure-caption-review]")) return !element.closest("li");
            return !element.closest("li, figure");
        });

    const reviewId = (element, index) => {
        const table = element.closest("[data-data-table], [data-review-table]");
        return element.matches("tr[data-row-key]") && table
            ? `row-${encodeURIComponent(table.dataset.dataTable || table.dataset.reviewTable)}:${encodeURIComponent(element.dataset.rowKey)}`
            : `item-${index + 1}`;
    };
    const identifiedReviewElements = (root) => {
        let ordinaryIndex = 0;
        return reviewElements(root).map((element) => {
            const id = reviewId(element, ordinaryIndex);
            if (id.startsWith("item-")) ordinaryIndex += 1;
            return {element, id};
        });
    };
    const reviewItems = () => chapterBody.dataset.generatedView
        ? []
        : identifiedReviewElements(chapterBody).map(({element, id}) => ({
        element, id,
    }));

    const reviewDecision = (chapter, item, reviewer) => data.reviews.find((decision) =>
        decision.chapter === chapter && decision.item === item && decision.reviewer === reviewer
    );

    const aggregateState = (chapter, item) => {
        const reviewers = new Set([
            ...data.reviewers,
            ...data.reviews.map((decision) => decision.reviewer),
        ]);
        if (!reviewers.size) return "waiting";
        const states = [...reviewers].map((reviewer) =>
            reviewDecision(chapter, item, reviewer)?.state || "waiting"
        );
        if (states.includes("rejected")) return "rejected";
        if (states.includes("accepted")) return "accepted";
        return "waiting";
    };

    const reviewerState = (chapter, item) => reviewDecision(
        chapter,
        item,
        currentAuthor(),
    )?.state || "waiting";

    const refreshReviewFilter = () => {
        if (activeReviewFilter.fields.includes("review")) globalThis.obsFilter?.refresh();
    };

    const rangesIntersect = (first, second) =>
        first.chapter === second.chapter && first.table === second.table &&
        first.row === second.row && (first.table && !first.detail ||
            first.detail === second.detail && first.column === second.column &&
            first.start < second.end && first.end > second.start);

    const nodeCount = (node) => 1 + node.replies.reduce(
        (total, reply) => total + nodeCount(reply),
        0,
    );

    const commentCount = (target) => data.annotations.reduce((total, annotation) =>
        total + (!annotation.batch && rangesIntersect(target, annotation.target) ? nodeCount(annotation) : 0),
        0,
    );

    const commentCountForItem = (element, chapter, item) => {
        const associated = data.annotations.reduce((total, annotation) =>
            total + (annotation.batch?.items.some((identity) =>
                identity.chapter === chapter && identity.item === item) ? nodeCount(annotation) : 0), 0);
        const scope = tableScope(element);
        if (scope.table) return associated + commentCount({chapter, ...scope});
        return associated + (data.annotations.length ? commentCount(targetForElement(element)) : 0);
    };

    const setReviewDecision = (chapter, item, requestedState, target) => {
        const reviewer = registerReviewer();
        const index = data.reviews.findIndex((decision) =>
            decision.chapter === chapter && decision.item === item && decision.reviewer === reviewer
        );
        const removing = index >= 0 && data.reviews[index].state === requestedState;
        if (removing) {
            data.reviews.splice(index, 1);
        } else {
            const decision = {chapter, item, reviewer, state: requestedState};
            if (index < 0) data.reviews.push(decision);
            else data.reviews[index] = decision;
        }
        persist();
        syncReviewFields();
        updateReviewSummary();
        updateReviewMode();
        refreshReviewFilter();
        if (requestedState === "rejected" && !removing) createAnnotation(target);
    };

    const reviewButton = (kind, label) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `review-action review-action--${kind}`;
        globalThis.obsAssets.append(button, kind === "comment" ? "comments" : kind);
        button.setAttribute("aria-label", label);
        button.title = label;
        return button;
    };

    const reviewItemsForRecord = (record) => {
        const isDocument = globalThis.obsArtifact.isDocument(record);
        const cached = reviewItemsCache.get(record.slug);
        if (cached && cached.html === record.html && cached.isDocument === isDocument) return cached.items;
        if (!isDocument || (!record.html.trim() && !record.tables?.length)) {
            reviewItemsCache.set(record.slug, {html: record.html, isDocument, items: []});
            return [];
        }
        const root = document.createElement("div");
        globalThis.obsArtifact.renderStatic(record.slug, root, false);
        const identities = new Map(identifiedReviewElements(root).map((item) => [item.element, item.id]));
        const items = [];
        let headings = [];
        let headingIndex = 0;
        root.querySelectorAll("h1, h2, h3, h4, h5, h6, p, li, tr, pre, figure").forEach((element) => {
            if (/^H[1-6]$/.test(element.tagName)) {
                const level = Number(element.tagName.slice(1));
                headings = headings.filter((heading) => heading.level < level);
                headings.push({key: `heading-${headingIndex++}`, level});
            }
            if (identities.has(element)) items.push({
                chapter: record.slug, id: identities.get(element),
                sections: headings.map((heading) => heading.key),
                scope: headings.at(-1)?.level === 1 ? "chapter" : "section",
            });
        });
        reviewItemsCache.set(record.slug, {html: record.html, isDocument, items});
        return items;
    };

    const chapterSlugs = new Set(JSON.parse(
        document.querySelector("[data-artifact-data]").textContent,
    ).toc);
    const allReviewItems = () => globalThis.obsArtifact.records
        .filter((record) => chapterSlugs.has(record.slug)).flatMap(reviewItemsForRecord);

    const setBatchDecision = (chapter, item, state, target, documentScope) => {
        const chapterItems = reviewItemsForRecord(
            globalThis.obsArtifact.records.find((record) => record.slug === chapter),
        );
        const anchor = chapterItems.find((candidate) => candidate.id === item);
        if (!anchor) throw new Error("The review item is not in the canonical chapter.");
        const scope = documentScope ? "document" : anchor.scope;
        const section = anchor.sections.at(-1);
        const candidates = documentScope ? allReviewItems() : chapterItems.filter((candidate) =>
            scope === "chapter" || (section ? candidate.sections.includes(section) : !candidate.sections.length));
        const affected = candidates.filter((candidate) =>
            reviewerState(candidate.chapter, candidate.id) === "waiting");
        if (!affected.length) return;
        const reviewer = registerReviewer();
        const items = affected.map((candidate) => ({chapter: candidate.chapter, item: candidate.id}));
        items.forEach((identity) => data.reviews.push({...identity, reviewer, state}));
        persist();
        syncReviewFields();
        updateReviewSummary();
        updateReviewMode();
        refreshReviewFilter();
        if (state === "rejected") createAnnotation(target, {scope, items});
    };

    const syncReviewFields = () => {
        globalThis.obsArtifact.records.forEach((record) => {
            const states = [...new Set(reviewItemsForRecord(record).map((item) =>
                reviewerState(item.chapter, item.id)
            ))];
            record.fields.review = states;
            record.filterAttributes.review = states;
        });
    };

    const updateReviewSummary = () => {
        const counts = {accepted: 0, rejected: 0, waiting: 0};
        allReviewItems().forEach((item) => {
            counts[reviewerState(item.chapter, item.id)] += 1;
        });
        Object.entries(counts).forEach(([state, count]) => {
            reviewSummary.querySelector(
                `[data-review-summary-state="${state}"] [data-review-summary-count]`
            ).textContent = count;
        });
    };

    const applyReviewFilter = (items) => {
        chapterBody.querySelectorAll("[data-review-filter-hidden]").forEach((element) => {
            element.hidden = false;
            element.removeAttribute("data-review-filter-hidden");
        });
        if (!activeReviewFilter.fields.includes("review")) return;
        const chapter = activeChapter?.dataset.chapter;
        const record = globalThis.obsArtifact.records.find((candidate) => candidate.slug === chapter);
        if (!record) return;
        items.forEach((item) => {
            const state = reviewerState(chapter, item.id);
            const matches = activeReviewFilter.match({
                ...record,
                fields: {...record.fields, review: state},
            });
            if (!matches) {
                item.element.hidden = true;
                item.element.dataset.reviewFilterHidden = "";
                const details = item.element.nextElementSibling;
                if (details?.hasAttribute("data-detail-owner") &&
                        details.dataset.detailOwner === item.element.dataset.rowKey) {
                    details.hidden = true;
                    details.dataset.reviewFilterHidden = "";
                }
            }
        });
    };

    const positionReviewRails = () => {
        chapterBody.querySelectorAll("[data-review-item]").forEach((element) => {
            if (!element.getClientRects().length) return;
            const sheet = element.closest(".paper-sheet");
            const origin = sheet || chapterBody;
            const left = origin.getBoundingClientRect().left;
            const itemLeft = (element.matches("tr") ? element.firstElementChild : element)
                .getBoundingClientRect().left;
            const gap = parseFloat(getComputedStyle(document.documentElement).fontSize) / 2;
            const inset = sheet ? 0 : parseFloat(getComputedStyle(chapterBody).paddingLeft);
            element.style.setProperty("--review-rail-offset", `${left + inset - gap - itemLeft}px`);
        });
    };

    const updateReviewMode = () => {
        const commentsBar = list.closest("[data-bar]");
        const isOpen = commentsBar && !commentsBar.hidden && Boolean(commentsBar.dataset.dock);
        chapterBody.classList.toggle("review-mode", Boolean(isOpen));
        chapterBody.querySelectorAll("[data-review-gutter]").forEach((gutter) => gutter.remove());
        chapterBody.querySelectorAll("[data-review-item]").forEach((item) => {
            item.removeAttribute("data-review-item");
            item.removeAttribute("data-review-state");
            item.style.removeProperty("--review-rail-offset");
        });

        const items = reviewItems();
        applyReviewFilter(items);
        if (!isOpen) return;
        const reviewer = currentAuthor();
        items.forEach((item) => {
            const chapter = activeChapter?.dataset.chapter || "";
            const current = reviewDecision(chapter, item.id, reviewer)?.state || "waiting";
            const state = aggregateState(chapter, item.id);
            item.element.dataset.reviewItem = item.id;
            item.element.dataset.reviewState = state;
            const gutter = document.createElement("span");
            gutter.className = "review-gutter";
            gutter.dataset.reviewGutter = "";
            gutter.setAttribute("aria-label", `Review item: ${state}`);

            const modifiers = "; Shift-click: waiting items in section/chapter; Ctrl+Shift-click: all waiting items";
            const decide = (state, event) => {
                if (event.shiftKey && event.detail !== 0) {
                    setBatchDecision(chapter, item.id, state, targetForElement(item.element), event.ctrlKey);
                } else {
                    setReviewDecision(chapter, item.id, state,
                        state === "rejected" ? targetForElement(item.element) : null);
                }
            };
            const accept = reviewButton("accept", "Accept item" + modifiers);
            accept.setAttribute("aria-pressed", String(current === "accepted"));
            accept.addEventListener("click", (event) => decide("accepted", event));

            const reject = reviewButton("reject", "Reject item" + modifiers);
            reject.setAttribute("aria-pressed", String(current === "rejected"));
            reject.addEventListener("click", (event) => decide("rejected", event));

            const count = commentCountForItem(item.element, chapter, item.id);
            const comment = reviewButton("comment", `Add comment; ${count} comments`);
            comment.dataset.count = String(count);
            comment.addEventListener("click", () => createAnnotation(targetForElement(item.element)));

            gutter.append(accept, reject, comment);
            if (item.element.matches("tr")) {
                item.element.firstElementChild.prepend(gutter);
                const details = item.element.nextElementSibling;
                if (details?.hasAttribute("data-detail-owner") &&
                        details.dataset.detailOwner === item.element.dataset.rowKey) {
                    details.dataset.reviewOwnerState = state;
                }
            } else item.element.prepend(gutter);
        });
        positionReviewRails();
    };

    const hasOpenComment = (node) =>
        node.status === "open" || node.replies.some(hasOpenComment);

    const setHoveredAnnotation = (annotation) => {
        chapterBody.classList.toggle("comment-highlight-hover", Boolean(annotation));
        if (!globalThis.CSS?.highlights || typeof Highlight === "undefined") return;
        if (!annotation) {
            CSS.highlights.delete("obs-comments-hover");
            return;
        }
        const range = rangeForTarget(annotation.target);
        if (range) CSS.highlights.set("obs-comments-hover", new Highlight(range));
    };

    const annotationAtPoint = (event) => data.annotations.find((annotation) => {
        if (!hasOpenComment(annotation) ||
                annotation.target.chapter !== activeChapter?.dataset.chapter) {
            return false;
        }
        const range = rangeForTarget(annotation.target);
        return range && [...range.getClientRects()].some((rect) =>
            event.clientX >= rect.left && event.clientX <= rect.right &&
            event.clientY >= rect.top && event.clientY <= rect.bottom
        );
    });

    const repaintHighlights = () => {
        if (!globalThis.CSS?.highlights || typeof Highlight === "undefined") {
            return;
        }
        setHoveredAnnotation(null);
        const ranges = data.annotations
            .filter(hasOpenComment)
            .map((annotation) => rangeForTarget(annotation.target))
            .filter(Boolean);
        CSS.highlights.set("obs-comments", new Highlight(...ranges));
    };

    const reviewedFilename = () => {
        const stem = document.title.trim().replace(/[<>:"/\\|?*]+/g, "-") || "document";
        return `${stem}-reviewed.html`;
    };

    const captureReviewedCopy = () => {
        // Restored obs-asset: references are fetched in a live-document clone, so clone into an inert one.
        const inert = document.implementation?.createHTMLDocument?.("");
        const clone = inert ? inert.importNode(document.documentElement, true)
            : document.documentElement.cloneNode(true);
        globalThis.obsPayload?.restore(clone);
        globalThis.obsAssets?.restore(clone);
        clone.querySelectorAll("[data-transient-view]").forEach((view) => view.remove());
        clone.querySelectorAll("dialog.figure-overlay").forEach((view) => view.remove());
        clone.classList.remove("paged-mode", "preparing-print");
        const active = clone.querySelector("[data-active-chapter]");
        if (active) active.hidden = false;
        const clonedIsland = clone.querySelector("[data-comment-island]");
        const reviewedData = {...data, reviewers: [...new Set([...data.reviewers, currentAuthor()])]};
        clonedIsland.textContent = escapeJson(reviewedData);
        const artifactIsland = clone.querySelector("[data-artifact-data]");
        const model = globalThis.obsArtifact?.serializeModel?.() || artifactIsland.textContent;
        globalThis.obsRunningHeader.snapshot(clone, JSON.parse(model).document.metadata);
        clone.querySelectorAll("[data-review-gutter]").forEach((gutter) => gutter.remove());
        clone.querySelectorAll("[data-review-item]").forEach((item) => {
            item.removeAttribute("data-review-item");
            item.removeAttribute("data-review-state");
            item.style.removeProperty("--review-rail-offset");
        });
        clone.querySelector("[data-chapter-body]")?.classList.remove("review-mode");
        clone.querySelectorAll("[data-transient-content]").forEach((view) => view.replaceChildren());
        clone.querySelectorAll("[data-bar]").forEach((bar) => {
            bar.hidden = true;
            delete bar.dataset.dock;
            clone.querySelector("[data-bar-parking]")?.append(bar);
        });
        clone.querySelectorAll("[data-dock-bar]").forEach((button) =>
            button.setAttribute("aria-pressed", "false"));
        clone.querySelectorAll("[data-bar-resize]").forEach((separator) => separator.remove());
        globalThis.obsArtifactTransport.restoreScripts(clone);
        delete clone.dataset.artifactStatus;
        return {
            clone, model, savedState: currentSnapshot(),
            savedArtifactState: currentArtifactSnapshot(),
            contentBaseline: globalThis.obsArtifact.contentBaseline?.(),
        };
    };

    const reviewedHtml = async (snapshot) => {
        await globalThis.obsHtmlReady;
        await globalThis.obsArtifact.whenChapterReady?.();
        snapshot ||= captureReviewedCopy();
        await globalThis.obsArtifactTransport.writeIsland(
            snapshot.clone.querySelector("[data-artifact-data]"), snapshot.model,
        );
        return `<!doctype html>\n${snapshot.clone.outerHTML}`;
    };

    const saveReviewedCopy = async () => {
        try {
            // Invoke the picker before cloning/compression can consume activation.
            const picker = globalThis.showSaveFilePicker
                ? globalThis.showSaveFilePicker({
                    suggestedName: reviewedFilename(),
                    types: [{description: "HTML file", accept: {"text/html": [".html"]}}],
                }).then(handle => ({handle}), error => ({error}))
                : null;
            await globalThis.obsHtmlReady;
            await globalThis.obsArtifact.whenChapterReady?.();
            const snapshot = captureReviewedCopy();
            const picked = picker ? await picker : null;
            let fileError = picked?.error;
            if (fileError?.name === "AbortError") throw fileError;
            const contents = await reviewedHtml(snapshot);
            if (picked?.handle) {
                try {
                    const writable = await picked.handle.createWritable();
                    await writable.write(contents);
                    await writable.close();
                    savedSnapshot = snapshot.savedState;
                    savedArtifactSnapshot = snapshot.savedArtifactState;
                    globalThis.obsArtifact.adoptContentBaseline?.(snapshot.contentBaseline);
                    updateSaveGuidance();
                    announcer.textContent = "HTML saved.";
                    return;
                } catch (error) {
                    if (error?.name === "AbortError") throw error;
                    fileError = error;
                }
            }
            const link = document.createElement("a");
            link.href = URL.createObjectURL(new Blob([contents], {type: "text/html"}));
            link.download = reviewedFilename();
            link.click();
            URL.revokeObjectURL(link.href);
            announcer.textContent = (fileError ? `File save failed: ${fileError.message}. ` : "") +
                "Download started. The browser cannot confirm it was saved; unsaved changes remain." +
                (globalThis.obsCapabilities?.limit("downloads")
                    ? ` ${globalThis.obsCapabilities.explain("downloads")}` : "");
        } catch (error) {
            if (error?.name === "AbortError") return;
            announcer.textContent = `HTML could not be saved: ${error.message}`;
        }
    };

    const signatureNode = (node) => ({
        author: node.author,
        text: node.text,
        status: node.status,
        replies: node.replies.map(signatureNode),
    });

    const signature = (annotation) => {
        const target = {...annotation.target};
        delete target.item;
        delete target.section;
        delete target.wholeItem;
        return JSON.stringify({
            target,
            ...(annotation.batch ? {batch: annotation.batch} : {}),
            ...signatureNode(annotation),
        });
    };

    const importFiles = async (files) => {
        const signatures = new Set(data.annotations.map(signature));
        let added = 0;
        let rejected = 0;
        for (const file of files) {
            try {
                const documentCopy = new DOMParser().parseFromString(await file.text(), "text/html");
                const islands = documentCopy.querySelectorAll("#obs-comments[data-comment-island]");
                if (islands.length !== 1) {
                    throw new Error("Expected one comment island.");
                }
                const imported = parseData(JSON.parse(islands[0].textContent || "{}"));
                imported.reviewers.forEach((reviewer) => {
                    if (!data.reviewers.includes(reviewer)) data.reviewers.push(reviewer);
                });
                imported.reviews.forEach((review) => {
                    if (!data.reviewers.includes(review.reviewer)) {
                        data.reviewers.push(review.reviewer);
                    }
                    const index = data.reviews.findIndex((candidate) =>
                        candidate.chapter === review.chapter &&
                        candidate.item === review.item &&
                        candidate.reviewer === review.reviewer
                    );
                    if (index < 0) data.reviews.push(review);
                    else data.reviews[index] = review;
                });
                imported.annotations.forEach((annotation) => {
                    const key = signature(annotation);
                    if (!signatures.has(key)) {
                        signatures.add(key);
                        data.annotations.push(annotation);
                        added += 1;
                    }
                });
            } catch (_error) {
                rejected += 1;
            }
        }
        persist();
        renderComments();
        syncReviewFields();
        updateReviewSummary();
        updateReviewMode();
        repaintHighlights();
        globalThis.obsFilter?.refresh();
        announcer.textContent = `${added} comments loaded${rejected ? `; ${rejected} files rejected` : ""}.`;
    };

    saveButton.addEventListener("click", saveReviewedCopy);
    artifactDownload.addEventListener("click", saveReviewedCopy);
    loadButton.addEventListener("click", () => fileInput.click());
    copyButton.addEventListener("click", copyComments);
    fileInput.addEventListener("change", async () => {
        await importFiles([...fileInput.files]);
        fileInput.value = "";
    });

    chapterBody.addEventListener("mousemove", (event) => {
        setHoveredAnnotation(annotationAtPoint(event));
    });

    chapterBody.addEventListener("mouseleave", () => setHoveredAnnotation(null));

    document.addEventListener("obs-bar-change", (event) => {
        if (event.detail?.bar === "comments") updateReviewMode();
        requestAnimationFrame(positionReviewRails);
    });
    const reviewLayout = new ResizeObserver(() => requestAnimationFrame(positionReviewRails));
    reviewLayout.observe(chapterBody);
    window.addEventListener("resize", positionReviewRails);

    document.addEventListener("obs-chapter-change", () => {
        updateReviewMode();
        repaintHighlights();
    });
    document.addEventListener("obs-chapter-content-ready", () => {
        updateReviewMode();
        repaintHighlights();
    });
    document.addEventListener("obs-table-definition-change", (event) => {
        globalThis.obsArtifact.records.forEach((record) => {
            if (record.tables?.some((table) => table.key === event.detail?.key)) {
                reviewItemsCache.delete(record.slug);
            }
        });
        syncReviewFields();
        updateReviewSummary();
        updateReviewMode();
        globalThis.obsFilter?.refresh();
    });
    document.addEventListener("obs-pages-layout", (event) => {
        if (["table-change", "row-details"].includes(event.detail?.reason)) return;
        updateReviewMode();
        repaintHighlights();
        updateSelectedTarget();
    });
    document.addEventListener("obs-table-change", (event) => {
        if (!chapterBody.contains(event.target)) return;
        if (["detail-selection", "row-details"].includes(event.detail?.reason)) {
            requestAnimationFrame(positionReviewRails);
        } else updateReviewMode();
        repaintHighlights();
        updateSelectedTarget();
    });

    document.addEventListener("obs-filter-change", (event) => {
        activeReviewFilter = event.detail?.query || globalThis.obsQuery.compile("");
        updateReviewMode();
    });

    document.addEventListener("obs-canonical-property-change", () => {
        const slugs = new Set(globalThis.obsArtifact.records.map((record) => record.slug));
        reviewItemsCache.forEach((_, slug) => {
            if (!slugs.has(slug)) reviewItemsCache.delete(slug);
        });
        // A Base may select rows from any canonical note, including a newly matching one.
        globalThis.obsArtifact.records.forEach((record) => {
            if (record.tables?.length) reviewItemsCache.delete(record.slug);
        });
        syncReviewFields();
        updateReviewSummary();
        updateReviewMode();
        updateSaveGuidance();
    });

    reviewSummary.addEventListener("click", (event) => {
        const button = event.target.closest("[data-review-summary-state]");
        if (!button) return;
        syncReviewFields();
        globalThis.obsArtifact.openBar("filter", "right");
        globalThis.obsFilter?.setExpression(`review: /^${button.dataset.reviewSummaryState}$/`);
    });

    chapterBody.addEventListener("click", (event) => {
        const annotation = annotationAtPoint(event);
        if (!annotation) return;
        globalThis.obsArtifact?.openBar?.("comments", "right");
        filterInput.value = "";
        activeFilter = globalThis.obsQuery.compile("");
        renderComments();
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                list.querySelector(`[data-comment-id="${CSS.escape(annotation.id)}"]`)
                    ?.scrollIntoView({block: "center"});
            });
        });
    });

    persist();
    savedSnapshot = currentSnapshot();
    savedArtifactSnapshot = currentArtifactSnapshot();
    updateSaveGuidance();
    renderComments();
    const prepareReview = async () => {
        for (const record of globalThis.obsArtifact.records) {
            if (globalThis.obsArtifact.isDocument(record) && record.html.trim()) {
                if (globalThis.obsStartup) await globalThis.obsStartup.yield();
                reviewItemsForRecord(record);
            }
        }
        syncReviewFields();
        updateReviewSummary();
        // Review fields change only what a filter matches; an empty filter matches all.
        if (globalThis.obsArtifact.filterSummary().expression) globalThis.obsFilter?.refresh();
    };
    if (globalThis.obsStartup) {
        reviewSummary.setAttribute("aria-busy", "true");
        globalThis.obsStartup.defer("Review index", async () => {
            await prepareReview();
            reviewSummary.removeAttribute("aria-busy");
        });
    } else {
        syncReviewFields();
        updateReviewSummary();
    }
    updateReviewMode();
    repaintHighlights();

    globalThis.obsComments = {
        data,
        importFiles,
        repaintHighlights,
        reviewedHtml,
        saveReviewedCopy,
    };
})();
