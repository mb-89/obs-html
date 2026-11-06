(() => {
    const applyLinkPolicy = (root = document) => {
        const links = [...(root.matches?.("a[href]") ? [root] : []),
            ...root.querySelectorAll("a[href]")];
        links.forEach(link => {
            const external = /^(?:https?:)?\/\//i.test(link.getAttribute("href")) &&
                !link.hasAttribute("download") && !link.hasAttribute("data-source-download");
            if (external) {
                link.setAttribute("target", "_blank");
                link.setAttribute("rel", "noopener noreferrer");
                link.dataset.externalWebLink = "";
            } else if (link.hasAttribute("data-external-web-link")) {
                link.removeAttribute("target");
                link.removeAttribute("rel");
                delete link.dataset.externalWebLink;
            }
        });
    };
    new MutationObserver(mutations => mutations.forEach(mutation => {
        if (mutation.type === "attributes") applyLinkPolicy(mutation.target);
        else [...mutation.addedNodes].filter(node => node.nodeType === 1).forEach(applyLinkPolicy);
    })).observe(document.body, {subtree: true, childList: true, attributes: true,
        attributeFilter: ["href", "download", "data-source-download"]});
    document.addEventListener("click", event => {
        const link = event.target.closest?.("a[href]");
        if (link) applyLinkPolicy(link);
    }, true);
    applyLinkPolicy();
    const artifactData = JSON.parse(document.querySelector("[data-artifact-data]").textContent);
    let embeddedAssets = artifactData.embeddedAssets || {};
    const notes = artifactData.notes;
    const notesBySlug = new Map(notes.map((note) => [note.slug, note]));
    const chapters = artifactData.toc.map((slug) => notesBySlug.get(slug));
    const tocSlugs = new Set(artifactData.toc);
    const queryProfile = artifactData.query || {scope: "chapters"};
    const contentTemplate = document.createElement("template");
    const formatMetadataValue = (value) => {
        if (value === null) return "null";
        if (typeof value === "boolean") return value ? "true" : "false";
        return String(value);
    };
    const isScalarList = (value) => Array.isArray(value)
        && value.every((item) => item === null || typeof item !== "object");
    // The single frontmatter walk: [path, display text, filter atoms]; empty mappings have no atoms.
    const flattenFrontmatter = (value, prefix = "", entries = []) => {
        if (isScalarList(value)) {
            const atoms = value.map(formatMetadataValue);
            entries.push([prefix, atoms.length ? atoms.join(", ") : "[]", atoms]);
        } else if (Array.isArray(value)) {
            value.forEach((item, index) => flattenFrontmatter(item, `${prefix}.${index}`, entries));
        } else if (value && typeof value === "object") {
            const fields = Object.entries(value);
            if (!fields.length && prefix) entries.push([prefix, "{}", null]);
            fields.forEach(([key, item]) => {
                flattenFrontmatter(item, prefix ? `${prefix}.${key}` : key, entries);
            });
        } else if (prefix) {
            const text = formatMetadataValue(value);
            entries.push([prefix, text, [text]]);
        }
        return entries;
    };
    const formatStructuredValue = (value) => {
        if (value === null || typeof value !== "object") return formatMetadataValue(value);
        if (isScalarList(value)) return value.length ? value.map(formatMetadataValue).join(", ") : "[]";
        const entries = flattenFrontmatter({...value});
        if (!entries.length) return Array.isArray(value) ? "[]" : "{}";
        const width = Math.max(...entries.map(([key]) => key.length + 1));
        return entries.map(([key, item]) => `${`${key}:`.padEnd(width)} ${item}`).join("\n");
    };
    const makeRecord = (chapter) => {
        contentTemplate.innerHTML = chapter.html;
        const text = contentTemplate.content.textContent.replace(/\s+/g, " ").trim();
        const metadata = chapter.generated === "home" ? artifactData.document.metadata : chapter.frontmatter;
        const metadataEntries = flattenFrontmatter(metadata);
        const frontmatterAttributes = Object.fromEntries(metadataEntries
            .filter(([, , atoms]) => atoms).map(([name, , atoms]) => [name, atoms]));
        const filterAttributes = {
            title: [chapter.title],
            slug: [chapter.slug],
            depth: [String(chapter.depth)],
            mark: [...new Set(chapter.marks.map((mark) => mark.kind))],
            ...frontmatterAttributes,
        };
        chapter.marks.forEach((mark) => {
            const field = `mark.${mark.kind}`;
            if (!filterAttributes[field]) filterAttributes[field] = [];
            filterAttributes[field].push(mark.label);
        });
        const fields = {
            title: chapter.title,
            text,
            content: text,
            body: text,
            slug: chapter.slug,
            depth: String(chapter.depth),
        };
        Object.entries(filterAttributes)
            .filter(([name]) => name === "mark" || name.startsWith("mark."))
            .forEach(([name, values]) => {
                fields[name] = values;
            });
        Object.entries(frontmatterAttributes).forEach(([name, values]) => {
            const key = name.toLocaleLowerCase();
            fields[key] = fields[key] ? [fields[key], ...values] : values;
            fields[`frontmatter.${key}`] = values;
        });
        const metadataText = metadataEntries.flatMap(([name, value]) => [name, value]).join(" ");
        if (metadataText) fields.frontmatter = metadataText;
        return {
            ...chapter,
            paragraphCount: contentTemplate.content.querySelectorAll("p").length,
            text,
            metadataEntries,
            filterAttributes,
            haystack: `${chapter.title} ${text} ${metadataText}`,
            detail: text,
            fields,
        };
    };
    const records = notes.map(makeRecord);
    const recordsBySlug = new Map(records.map((record) => [record.slug, record]));
    const isDocument = (record) => record?.frontmatter?.obs?.document !== false;
    // An ignored note (obs markdown-frontmatter, Ignored notes) is never selected or counted
    // automatically; explicit links still reach it.
    const selectable = (record) => record?.ignored !== true;
    const queryPopulation = globalThis.obsQuery.compileConditions(queryProfile.where);
    const scalarValues = (value) => (Array.isArray(value) ? value.flat(Infinity) : [value])
        .filter((item) => item !== undefined && item !== null && typeof item !== "object")
        .map(formatMetadataValue);
    const recordValues = (record, path) => {
        const value = globalThis.obsBases.recordValue
            ? globalThis.obsBases.recordValue(record, path)
            : record.fields[`frontmatter.${path.toLocaleLowerCase()}`] ?? record.fields[path.toLocaleLowerCase()];
        const direct = scalarValues(value);
        if (direct.length) return direct;
        const parts = path.split(".");
        for (let split = parts.length - 1; split > 0; split -= 1) {
            const references = globalThis.obsBases.referenceRecords?.(
                record, parts.slice(0, split).join("."), recordsBySlug,
            ) || [];
            if (references.length) return references.flatMap(({record: target}) =>
                recordValues(target, parts.slice(split).join(".")),
            );
        }
        return [];
    };
    const refreshQueryFields = () => records.forEach((record) => {
        if (queryProfile.scope === "records" && !queryPopulation.match(record)) return;
        const searchable = [];
        (queryProfile.fields || []).forEach(({field, source = field}) => {
            const values = [...new Set((Array.isArray(source) ? source : [source])
                .flatMap((path) => recordValues(record, path)))];
            record.fields[field.toLocaleLowerCase()] = values;
            record.filterAttributes[field] = values;
            searchable.push(field, ...values);
        });
        if (queryProfile.fields) record.haystack = [
            record.title, record.text,
            ...record.metadataEntries.flatMap(([field, value]) => [field, value]),
            ...searchable,
        ].join(" ");
    });
    refreshQueryFields();
    const filterRecords = () => queryProfile.scope === "records"
        ? records.filter((record) => !record.generated && selectable(record) && queryPopulation.match(record))
        : records.filter(selectable);
    const facetFields = (population, catalog) => {
        const selected = catalog && new Map(catalog.map(entry => [entry.field.toLocaleLowerCase(), entry]));
        const values = new Map();
        const populated = new Map();
        population.forEach(record => {
            const attributes = record.filterAttributes || record.fields || record.values || {};
            Object.entries(attributes).forEach(([field, entries]) => {
                const declaration = selected?.get(field.toLocaleLowerCase());
                if (selected && !declaration) return;
                field = declaration?.field || field;
                const atoms = scalarValues(entries).filter(value => value.trim());
                if (!atoms.length) return;
                if (!values.has(field)) values.set(field, new Map());
                populated.set(field, (populated.get(field) || 0) + 1);
                new Set(atoms).forEach(value => {
                    const counts = values.get(field);
                    counts.set(value, (counts.get(value) || 0) + 1);
                });
            });
        });
        return [...values].filter(([field, available]) => available.size > 1 &&
            available.size <= Math.floor(populated.get(field) * artifactData.facetDistinctRatio))
            .sort(([left], [right]) => left.localeCompare(right))
            .map(([field, available]) => ({
                field, label: selected?.get(field.toLocaleLowerCase())?.label || field,
                counts: Object.fromEntries(available),
                values: [...available.keys()].sort((left, right) =>
                    left.localeCompare(right, undefined, {numeric: true})),
            }));
    };
    const previewConfig = artifactData.hoverCard;
    const hoverCard = globalThis.ObsHtmlHoverCard.create({
        window, delayMilliseconds: previewConfig.showDelayMilliseconds,
    });
    const tableIconHelp = new WeakMap();
    const tableIconCards = new WeakMap();
    const element = (tag, className, text) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text) node.textContent = text;
        return node;
    };
    const shortenPreview = (text, limit) => {
        const normalized = text.replace(/\s+/g, " ").trim();
        if (normalized.length <= limit) return normalized;
        const clipped = normalized.slice(0, limit - 3);
        const boundary = clipped.lastIndexOf(" ");
        return `${boundary > 0 ? clipped.slice(0, boundary) : clipped}...`;
    };
    const previewText = (record) => {
        const template = document.createElement("template");
        template.innerHTML = record.html;
        template.content.querySelectorAll("table, pre, script, style, [data-data-table]").forEach(
            (node) => node.remove(),
        );
        const paragraphs = [...template.content.querySelectorAll("p")].map(
            (node) => node.textContent.trim(),
        ).filter(Boolean);
        const summary = document.createElement("template");
        summary.innerHTML = record.definitionHtml || "";
        const lead = summary.content.textContent.trim();
        return shortenPreview(
            [lead, ...paragraphs.filter((text) => text !== lead)].filter(Boolean).join(" "),
            previewConfig.excerptCharacters,
        );
    };
    const externalUrl = (value) => typeof value === "string" && /^https?:\/\//i.test(value.trim())
        ? value.trim() : null;
    const cardTitle = (text, href) => {
        const title = element(href ? "a" : "div", "hover-card-title", text);
        if (href) title.href = href;
        return title;
    };
    const cardHtml = (tag, markup, className = "") => {
        const node = element(tag, className);
        appendTrustedHtml(node, markup);
        return node;
    };
    const fieldHtml = (record, field) => record.frontmatterHtml?.[field] ||
        (record.frontmatter?.[field] == null ? "" : null);
    const appendField = (card, record, field, className) => {
        const html = fieldHtml(record, field);
        if (html) card.append(cardHtml("p", html, className));
        else if (html === null) card.append(element("p", className, formatStructuredValue(record.frontmatter[field])));
    };
    // Artifact-ui.md "Link hover card": the content shown depends on the kind of the linked target.
    const renderReferenceCard = (card, record, href, url) => {
        card.append(cardTitle(record.title, href));
        const link = element("a", "hover-card-external", url);
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.append(element("span", "hover-card-hint", " (opens in a new tab)"));
        const line = element("p");
        line.append(link);
        card.append(line);
        appendField(card, record, "description", "hover-card-description");
        if (record.frontmatter.accessed != null) {
            card.append(element("p", "hover-card-note", `Accessed ${formatStructuredValue(record.frontmatter.accessed)}`));
        }
    };
    const renderQuantityCard = (card, record, href) => {
        const {frontmatter} = record;
        card.append(cardTitle(record.title, href));
        const value = element("p", "hover-card-value");
        if (frontmatter.query) {
            const calculated = element("span", "", "Calculating…");
            calculated.dataset.quantityReference = record.sourcePath;
            calculated.setAttribute("aria-busy", "true");
            value.append(calculated);
        } else {
            value.textContent = record.valueLabel;
        }
        card.append(value);
        if (frontmatter.query) {
            const query = element("p", "hover-card-note", "Counted by the query ");
            query.append(element("code", "", formatStructuredValue(frontmatter.query.where)));
            card.append(query);
        }
        if (frontmatter.command) {
            const command = element("p", "hover-card-note", "Computed by the command ");
            command.append(element("code", "", formatStructuredValue(frontmatter.command)));
            card.append(command);
        }
        const derivation = previewText(record);
        if (derivation) card.append(element("p", "", derivation));
        if (frontmatter.source != null) {
            const source = element("p", "hover-card-note", "Source: ");
            const html = fieldHtml(record, "source");
            if (html) appendTrustedHtml(source, html);
            else source.append(formatStructuredValue(frontmatter.source));
            card.append(source);
        }
    };
    const renderGlossaryCard = (card, record, href) => {
        card.append(cardTitle(record.title, href));
        if (record.definitionHtml) card.append(cardHtml("p", record.definitionHtml));
    };
    const renderNoteCard = (card, record, href) => {
        card.append(cardTitle(record.title, href));
        const metadata = document.createElement("dl");
        record.metadataEntries.filter(([key]) =>
            !["title", "term", "aliases", "definition"].includes(key.toLocaleLowerCase()),
        ).slice(0, previewConfig.metadataEntries).forEach(([key, value]) => {
            const detail = document.createElement("dd");
            const rendered = record.frontmatterHtml?.[key];
            const template = document.createElement("template");
            template.innerHTML = rendered || "";
            if (rendered && template.content.textContent.trim().length <= previewConfig.metadataValueCharacters) {
                appendTrustedHtml(detail, rendered);
            } else {
                detail.textContent = shortenPreview(value, previewConfig.metadataValueCharacters);
            }
            metadata.append(element("dt", "", key), detail);
        });
        if (metadata.children.length) card.append(metadata);
        const excerpt = previewText(record);
        if (excerpt) card.append(element("p", "", excerpt));
    };
    // The mark card reads the shared tag record projection (the register's rows), so it follows
    // that projection when its source changes (input-model.md "Callouts").
    const renderMarkCard = (card, row) => {
        card.append(cardTitle(`${String(row.values.type).replace(/_/g, " ")}: ${row.values.label}`));
        const text = element("p");
        appendTableCell(text, row.cells.text, row.values.text);
        card.append(text);
        const source = element("p", "hover-card-note");
        appendTableCell(source, row.cells.source, row.values.source);
        card.append(source);
    };
    const linkTarget = (link) => {
        const href = link.getAttribute("href");
        if (!href?.startsWith("#")) return null;
        // Resolve through the same canonical slug used by click navigation.
        const target = decodeURIComponent(href.slice(1));
        const record = recordsBySlug.get(target.split("?", 1)[0].split("/", 1)[0]);
        return record ? {record, href} : null;
    };
    const markTarget = (link) => tagTableRows().find((row) =>
        row.values.type === link.dataset.tagKind && row.values.label === link.dataset.tagLabel);
    hoverCard.register("a[href]", (link) => {
        if (link.dataset.tagKind) {
            const target = markTarget(link);
            return target && {label: "Mark", render: (card) => renderMarkCard(card, target)};
        }
        const destination = linkTarget(link);
        if (!destination) return null;
        const {record, href} = destination;
        const url = externalUrl(record.frontmatter?.url);
        const kind = record.frontmatter?.kind;
        return {label: `Link: ${record.title}`, render: (card) => {
            if (url) renderReferenceCard(card, record, href, url);
            else if (kind === "quantity") renderQuantityCard(card, record, href);
            else if (kind === "glossary") renderGlossaryCard(card, record, href);
            else renderNoteCard(card, record, href);
        }};
    });
    hoverCard.register(".data-table-icon-action", (control) => {
        const help = tableIconHelp.get(control);
        if (!help) return null;
        const {icon, row} = help;
        return {
            label: icon.label,
            showOnClick: !icon.action && !icon.linkProperty,
            render: (card) => {
                card.append(cardTitle(icon.label));
                if (icon.helpProperty) {
                    const content = document.createElement("div");
                    appendTableCell(content, row.cells[icon.helpProperty], row.values[icon.helpProperty]);
                    if (content.textContent.trim()) card.append(content);
                }
                if (icon.help) card.append(element("p", "", icon.help));
            },
        };
    });
    document.addEventListener("obs-chapter-change", hoverCard.hide);
    const chapterRecords = chapters.map((chapter) => recordsBySlug.get(chapter.slug));
    const activeChapter = document.querySelector("[data-active-chapter]");
    const chapterBody = document.querySelector("[data-chapter-body]");
    const chapterScroll = document.querySelector("[data-chapter-scroll]");
    const frontmatterToggle = document.querySelector("[data-frontmatter-toggle]");
    const bandPath = document.querySelector("[data-top-band-path]");
    const frontmatterPanel = document.querySelector("[data-frontmatter-panel]");
    const frontmatterBody = document.querySelector("[data-frontmatter-body]");
    const tocTree = document.querySelector("[data-toc-tree]");
    const stepButtons = [...document.querySelectorAll("[data-step]")];
    const rootStyle = document.documentElement.style;
    rootStyle.setProperty("--inactive-icon-opacity", String(artifactData.inactiveIconOpacity));
    rootStyle.setProperty("--attention-period", `${artifactData.reading.pingPeriodMilliseconds}ms`);
    rootStyle.setProperty("--attention-count", String(artifactData.reading.pingCount));
    rootStyle.setProperty("--attention-scale", String(artifactData.reading.pingScale));
    const stopPing = (target) => target?.classList.remove("attention-ping");
    const ping = (target) => {
        if (target.classList.contains("attention-ping")) return;
        target.classList.add("attention-ping");
    };
    document.addEventListener("animationend", (event) => {
        if (event.animationName === "attention-radar") stopPing(event.target);
    });
    stepButtons.forEach((button) => {
        const icon = document.createElement("span");
        icon.className = "chapter-nav-icon";
        icon.setAttribute("aria-hidden", "true");
        globalThis.obsAssets.append(icon, button.dataset.step === "-1" ? "left" : "right");
        button.append(icon);
    });
    const menuButton = document.querySelector("[data-menu-button]");
    const menu = document.querySelector("[data-bars-menu]");
    const parking = document.querySelector("[data-bar-parking]");
    const bars = new Map(
        [...document.querySelectorAll("[data-bar]")].map((bar) => [bar.dataset.bar, bar]),
    );
    const dockButtons = [...document.querySelectorAll("[data-dock-bar]")];
    const resizeHandles = [...document.querySelectorAll("[data-dock-resize]")];
    let tocLinks = [];
    let activeIndex = 0;
    let visibleIndices = chapters.map((_chapter, index) => index);
    let activeFilter = globalThis.obsQuery.compile("");
    let filterRevision = 0;

    const headingToc = (chapter) => {
        const source = document.createElement("template");
        source.innerHTML = recordsBySlug.get(chapter.slug).html;
        const headings = [];
        const stack = [{level: 1, children: headings}];
        source.content.querySelectorAll("h2[id], h3[id], h4[id], h5[id], h6[id]").forEach((heading) => {
            const level = Number(heading.tagName.slice(1));
            while (stack.length > 1 && stack.at(-1).level >= level) stack.pop();
            const node = {
                title: heading.textContent.trim(),
                href: `#${chapter.slug}/${heading.id.startsWith(`${chapter.slug}--`)
                    ? heading.id.slice(chapter.slug.length + 2) : `@${heading.id}`}`,
                children: [],
            };
            stack.at(-1).children.push(node);
            stack.push({...node, level});
        });
        return headings;
    };

    const tocItem = (title, href, children, chapterIndex) => {
        const item = document.createElement("li");
        const entry = document.createElement("div");
        entry.className = "toc-entry";
        if (children.length) {
            const button = document.createElement("button");
            button.className = "disclosure-toggle toc-toggle";
            button.type = "button";
            button.dataset.tocToggle = "";
            button.dataset.label = title;
            button.setAttribute("aria-expanded", "false");
            button.setAttribute("aria-label", `Expand ${title}`);
            button.title = `Expand ${title}`;
            const icon = document.createElement("span");
            icon.setAttribute("aria-hidden", "true");
            globalThis.obsAssets.set(icon, "collapsed");
            button.append(icon);
            entry.append(button);
        } else {
            const spacer = document.createElement("span");
            spacer.className = "toc-toggle-spacer";
            spacer.setAttribute("aria-hidden", "true");
            entry.append(spacer);
        }
        const link = document.createElement("a");
        link.href = href;
        if (chapterIndex !== undefined) {
            link.dataset.tocLink = chapters[chapterIndex].slug;
            link.dataset.chapterIndex = String(chapterIndex);
        }
        link.textContent = title;
        entry.append(link);
        item.append(entry);
        if (children.length) {
            const nested = document.createElement("ol");
            nested.append(...children);
            const container = document.createElement("div");
            container.dataset.tocChildren = "";
            container.hidden = true;
            container.append(nested);
            item.append(container);
        }
        return item;
    };

    const headingTocItems = (nodes) => nodes.map((node) =>
        tocItem(node.title, node.href, headingTocItems(node.children)));

    const createTocLevel = (startIndex, depth) => {
        const list = document.createElement("ol");
        let index = startIndex;
        while (index < chapters.length) {
            const chapter = chapters[index];
            if (chapter.generated === "home") {
                index += 1;
                continue;
            }
            if (chapter.depth < depth) break;
            if (chapter.depth > depth) throw new Error("Artifact data skips a TOC nesting level.");

            const hasChildren = index + 1 < chapters.length && chapters[index + 1].depth > depth;
            const chapterIndex = index;
            const children = headingTocItems(headingToc(chapter));
            index += 1;

            if (hasChildren) {
                const nested = createTocLevel(index, depth + 1);
                children.push(...nested.list.children);
                index = nested.index;
            }
            list.append(tocItem(chapter.title, `#${chapter.slug}`, children, chapterIndex));
        }
        return { list, index };
    };

    const buildToc = () => {
        const tree = createTocLevel(0, 0);
        if (tree.index !== chapters.length) throw new Error("Artifact data could not build a TOC.");
        tocTree.replaceChildren(tree.list);
        tocLinks = [...tocTree.querySelectorAll("[data-toc-link]")];
    };

    const setTocExpanded = (button, expanded) => {
        const children = button.closest("li")?.querySelector(":scope > [data-toc-children]");
        if (!children) return;
        button.setAttribute("aria-expanded", String(expanded));
        button.setAttribute("aria-label", `${expanded ? "Collapse" : "Expand"} ${button.dataset.label}`);
        button.title = `${expanded ? "Collapse" : "Expand"} ${button.dataset.label}`;
        globalThis.obsAssets.set(button.querySelector("[data-icon]"), expanded ? "expanded" : "collapsed");
        children.hidden = !expanded;
    };

    const expandTocAncestors = (link) => {
        let children = link?.closest("[data-toc-children]");
        while (children) {
            const parentItem = children.parentElement;
            const button = parentItem?.querySelector(":scope > .toc-entry [data-toc-toggle]");
            if (button) setTocExpanded(button, true);
            children = parentItem?.parentElement.closest("[data-toc-children]");
        }
    };

    const initializeHeadingSections = () => {
        const headings = [...chapterBody.querySelectorAll("h2, h3, h4, h5, h6")];
        [...headings].reverse().forEach((heading) => {
            const level = Number(heading.tagName.slice(1));
            const section = document.createElement("div");
            section.className = "heading-section-body";
            section.dataset.headingSection = heading.id || `section-${headings.indexOf(heading)}`;
            while (heading.nextSibling) {
                const next = heading.nextSibling;
                const nextHeading = next.matches?.(".collapsible-heading")
                    ? next.querySelector("h2, h3, h4, h5, h6") : next;
                if (/^H[2-6]$/.test(nextHeading.tagName || "") &&
                        Number(nextHeading.tagName.slice(1)) <= level) {
                    break;
                }
                section.append(next);
            }
            heading.after(section);

            const label = heading.textContent.trim();
            const wrapper = document.createElement("div");
            wrapper.className = "collapsible-heading";
            const button = document.createElement("button");
            button.className = "disclosure-toggle heading-toggle";
            button.type = "button";
            button.dataset.headingToggle = "";
            button.dataset.headingSectionTarget = section.dataset.headingSection;
            button.dataset.label = label;
            button.setAttribute("aria-expanded", "true");
            button.setAttribute("aria-label", `Collapse ${label}`);
            button.title = `Collapse ${label}`;
            const icon = document.createElement("span");
            icon.setAttribute("aria-hidden", "true");
            globalThis.obsAssets.set(icon, "expanded");
            button.append(icon);
            heading.before(wrapper);
            wrapper.append(button, heading);
        });
    };

    const setMenuOpen = (open) => {
        menu.hidden = !open;
        menuButton.setAttribute("aria-expanded", String(open));
    };

    const stepTarget = (step) => {
        if (activeIndex < 0) return undefined;
        const targets = [
            ...visibleIndices.map((index) => ({type: "chapter", index})),
        ];
        let position = targets.findIndex(
            (target) => target.type === "chapter" && target.index === activeIndex,
        );
        if (position < 0) {
            position = step < 0
                ? targets.findLastIndex((target) => target.type === "chapter" && target.index < activeIndex)
                : targets.findIndex((target) => target.type === "chapter" && target.index > activeIndex) - 1;
        }
        return targets[position + step];
    };

    const updateStepButtons = () => {
        stepButtons.forEach((button) => {
            button.disabled = stepTarget(Number(button.dataset.step)) === undefined;
            if (button.disabled) {
                delete button.dataset.scrollBoundary;
                stopPing(button.querySelector(".chapter-nav-icon"));
            }
        });
    };

    const clearScrollCues = (except) => stepButtons.forEach((button) => {
        if (button === except) return;
        delete button.dataset.scrollBoundary;
        stopPing(button.querySelector(".chapter-nav-icon"));
    });
    let scrollIntent = 0;
    const cueScrollBoundary = (direction) => {
        const atBoundary = direction < 0 ? chapterScroll.scrollTop <= 0
            : Math.ceil(chapterScroll.scrollTop + chapterScroll.clientHeight) >= chapterScroll.scrollHeight;
        const button = stepButtons.find((button) => Number(button.dataset.step) === direction);
        const available = atBoundary && button && !button.disabled;
        clearScrollCues(available ? button : null);
        if (available) {
            button.dataset.scrollBoundary = "true";
            ping(button.querySelector(".chapter-nav-icon"));
        }
    };
    const readerScrollIntent = (target) => {
        if (target.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])")) {
            return false;
        }
        for (let node = target; node && node !== chapterScroll; node = node.parentElement) {
            if (node.scrollHeight > node.clientHeight &&
                /auto|scroll/.test(getComputedStyle(node).overflowY)) return false;
        }
        return true;
    };
    chapterScroll.addEventListener("wheel", (event) => {
        if (event.deltaY && !event.ctrlKey && readerScrollIntent(event.target)) {
            scrollIntent = Math.sign(event.deltaY);
            cueScrollBoundary(scrollIntent);
        }
    }, {passive: true});
    chapterScroll.addEventListener("keydown", (event) => {
        if (event.defaultPrevented || !readerScrollIntent(event.target)) return;
        const direction = ["ArrowUp", "PageUp", "Home"].includes(event.key) ? -1
            : ["ArrowDown", "PageDown", "End"].includes(event.key) ? 1
            : event.key === " " ? (event.shiftKey ? -1 : 1) : 0;
        if (direction) {
            scrollIntent = direction;
            cueScrollBoundary(direction);
        }
    });
    let touchY;
    chapterScroll.addEventListener("touchstart", (event) => {
        touchY = event.touches.length === 1 ? event.touches[0].clientY : undefined;
    }, {passive: true});
    chapterScroll.addEventListener("touchmove", (event) => {
        if (event.touches.length !== 1) {
            touchY = undefined;
            return;
        }
        const nextY = event.touches[0].clientY;
        if (touchY !== undefined && touchY !== nextY && readerScrollIntent(event.target)) {
            scrollIntent = Math.sign(touchY - nextY);
            cueScrollBoundary(scrollIntent);
        }
        touchY = nextY;
    }, {passive: true});
    let previousScrollTop = chapterScroll.scrollTop;
    chapterScroll.addEventListener("pointerdown", (event) => {
        if (event.target === chapterScroll) scrollIntent = null;
    });
    chapterScroll.addEventListener("scroll", () => {
        const direction = Math.sign(chapterScroll.scrollTop - previousScrollTop);
        previousScrollTop = chapterScroll.scrollTop;
        if (!direction) return;
        if (scrollIntent === null || scrollIntent === direction) cueScrollBoundary(direction);
        else clearScrollCues();
    }, {passive: true});

    const setFrontmatterExpanded = (expanded) => {
        frontmatterPanel.hidden = !expanded;
        frontmatterToggle.setAttribute("aria-expanded", String(expanded));
        frontmatterToggle.setAttribute("aria-label", `${expanded ? "Hide" : "Show"} frontmatter`);
        frontmatterToggle.title = `${expanded ? "Hide" : "Show"} frontmatter`;
    };

    const metadataRows = (record) => record.metadataEntries.map(([field, value]) => {
        const row = document.createElement("tr");
        row.dataset.frontmatterField = field.toLocaleLowerCase();
        const heading = document.createElement("th");
        heading.scope = "row";
        heading.textContent = field;
        const cell = document.createElement("td");
        appendTableCell(cell, record.frontmatterHtml?.[field]
            ? {type: "html", html: record.frontmatterHtml[field]} : null, value);
        row.append(heading, cell);
        return row;
    });
    const renderFrontmatter = (record) => {
        frontmatterBody.replaceChildren(...metadataRows(record));
        frontmatterToggle.hidden = !record.metadataEntries.length;
        setFrontmatterExpanded(!record.html.trim() && record.metadataEntries.length > 0);
    };

    const trustedFragment = (markup) => {
        const template = document.createElement("template");
        template.innerHTML = markup;
        globalThis.obsAssets.hydrate(template.content);
        activateEmbeddedAssets(template.content);
        return template.content;
    };

    const appendTrustedHtml = (parent, markup) => {
        parent.append(trustedFragment(markup));
    };

    const replaceTrustedHtml = (parent, markup) => {
        parent.replaceChildren(trustedFragment(markup));
    };

    const activateEmbeddedAssets = (root) => {
        if (!Object.keys(embeddedAssets).length) return;
        root.querySelectorAll("[src], [href]").forEach((element) => {
            ["src", "href"].forEach((attribute) => {
                const reference = element.getAttribute(attribute);
                const match = /^obs-asset:([a-f0-9]{64})$/i.exec(reference || "");
                if (!match) return;
                const asset = embeddedAssets[match[1]];
                if (asset && typeof asset === "object" && globalThis.obsPayload) {
                    globalThis.obsPayload.activate(element, attribute, match[1], asset);
                    return;
                }
                if (typeof asset !== "string") {
                    throw new Error(`Missing embedded asset: ${match[1]}`);
                }
                element.setAttribute(attribute, asset);
            });
        });
    };

    // `ownFields` are the row's own filter fields (generic-tables, Bases filter grammar);
    // `values` are the displayed cells and may add flattened frontmatter text. `recordType`
    // only partitions rows for obs.records and is never a filter field.
    const tableRecord = (key, values, options = {}) => {
        const text = Object.values(values).join(" ");
        return {
            key,
            values,
            ownFields: options.ownFields ||
                Object.fromEntries(Object.entries(values).filter(([field]) => field !== "recordType")),
            fields: Object.fromEntries(
                Object.entries(values).map(([field, value]) => [field.toLocaleLowerCase(), value]),
            ),
            haystack: text,
            detail: text,
            depth: options.depth || 0,
            parentKey: options.parentKey || "",
            cells: options.cells || {},
            source: options.source,
            noteId: options.noteId || "",
            canonicalId: options.canonicalId || "",
        };
    };
    const queryProjection = (record) => Object.fromEntries((queryProfile.fields || [])
        .map(({field}) => [field, record.fields[field.toLocaleLowerCase()] || []]));

    const noteLabelCell = (record, label) => ({
        type: tocSlugs.has(record.slug) ? "link" : "detail",
        href: `#${record.slug}`,
        label,
    });

    // Own fields resolve before the owner note's properties in projected-row filters (generic-tables).
    const noteOwnFields = (record) => ({
        chapter: record.title,
        title: record.title,
        depth: String(record.depth),
        slug: record.slug,
        sourcePath: record.sourcePath,
    });

    const noteTableRows = () => records.filter((record) => !record.generated && selectable(record)).map((record) => {
        const ownFields = noteOwnFields(record);
        return tableRecord(`note:${record.slug}`, {
            ...Object.fromEntries(record.metadataEntries),
            ...queryProjection(record),
            recordType: "note",
            ...ownFields,
            "file.name": globalThis.obsBases.recordValue(record, "file.name"),
            "file.path": record.sourcePath,
            "file.folder": globalThis.obsBases.recordValue(record, "file.folder"),
            "file.ext": globalThis.obsBases.recordValue(record, "file.ext"),
        }, {
            ownFields,
            noteId: record.slug,
            canonicalId: record.sourcePath.replace(/\.md$/i, ""),
            cells: {
                ...Object.fromEntries(Object.entries(record.frontmatterHtml || {}).map(
                    ([field, html]) => [field, {type: "html", html}],
                )),
                chapter: noteLabelCell(record, record.title),
                title: noteLabelCell(record, record.title),
            },
        });
    });

    const chapterTableRows = () => {
        const ancestors = [];
        return chapterRecords.filter((record) => !record.generated).flatMap((record) => {
            ancestors.length = record.depth;
            const parentKey = record.depth ? ancestors[record.depth - 1] || "" : "";
            ancestors[record.depth] = selectable(record) ? record.slug : parentKey;
            if (!selectable(record)) return [];
            const ownFields = noteOwnFields(record);
            const row = tableRecord(record.slug, {
                ...Object.fromEntries(record.metadataEntries),
                ...queryProjection(record),
                recordType: "chapter",
                chapter: record.title,
                title: record.title,
                sourcePath: record.sourcePath,
                depth: String(record.depth),
                slug: record.slug,
            }, {
                ownFields,
                noteId: record.slug,
                depth: record.depth,
                parentKey,
                cells: {
                    ...Object.fromEntries(Object.entries(record.frontmatterHtml || {}).map(
                        ([field, html]) => [field, {type: "html", html}],
                    )),
                    chapter: {type: "link", href: `#${record.slug}`, label: record.title},
                },
            });
            row.haystack = record.title;
            return row;
        });
    };

    const tagTableRows = () => records.flatMap((record) => record.marks.map((mark) => {
        const ownFields = {
            sourcePath: record.sourcePath,
            type: mark.kind,
            label: mark.label,
            text: mark.text,
            source: record.title,
        };
        return tableRecord(`${record.slug}:${mark.kind}:${mark.label}`, {
            recordType: "tag",
            ...ownFields,
            backlinks: mark.backlinks.map((location) => location.label),
        }, {
            ownFields,
            cells: {
                text: {type: "html", html: mark.html},
                source: {
                    type: "source",
                    href: `#${mark.anchor}`,
                    chapter: record.slug,
                    label: record.title,
                },
                backlinks: {type: "links", links: mark.backlinks},
            },
        });
    }));

    const glossaryTableRows = () => records.filter(
        (record) => record.frontmatter.kind === "glossary" && selectable(record),
    ).map((record) => {
        const ownFields = {
            sourcePath: record.sourcePath,
            term: record.frontmatter.term,
            definition: record.frontmatter.definition,
            aliases: record.frontmatter.aliases || [],
        };
        return tableRecord(`glossary:${record.slug}`, {
            ...Object.fromEntries(record.metadataEntries),
            recordType: "glossary",
            ...ownFields,
        }, {
            ownFields,
            noteId: record.slug,
            cells: {
                ...Object.fromEntries(Object.entries(record.frontmatterHtml || {}).map(
                    ([field, html]) => [field, {type: "html", html}],
                )),
                term: noteLabelCell(record, record.frontmatter.term),
                definition: {type: "html", html: record.definitionHtml},
            },
        });
    });

    const sourceArchiveInfo = () => {
        const available = Boolean(document.getElementById("obs-source-archive"));
        const complete = available && artifactData.sourceArchiveComplete !== false;
        return {available, complete, label: !available ? "Source archive unavailable"
            : complete ? "Download source ZIP" : "Download partial evidence ZIP"};
    };
    const refreshSourceControls = () => {
        const info = sourceArchiveInfo();
        const exports = document.querySelector("[data-source-exports]");
        if (exports) exports.hidden = !info.available;
        const attach = exports?.querySelector("[data-source-attach]");
        if (attach) attach.hidden = !info.complete;
        const heading = chapterBody.querySelector(".document-heading");
        if (info.available && heading && !heading.querySelector("[data-source-download]")) {
            const card = document.createElement("aside");
            card.className = "content-card source-archive-bar";
            card.dataset.transientView = "";
            const link = document.createElement("a");
            link.href = "obs-source:archive";
            link.dataset.sourceDownload = "";
            card.append(link);
            heading.prepend(card);
        }
        document.querySelectorAll('[data-source-download], a[href="obs-source:archive"]').forEach(control => {
            control.dataset.sourceDownload = "";
            control.setAttribute("aria-disabled", String(!info.available));
            control.title = info.label;
            if (!info.complete || !control.textContent.trim()) control.textContent = info.label;
            if (control.tagName === "BUTTON") control.disabled = !info.available;
        });
    };
    const downloadSourceArchive = async () => {
        const info = sourceArchiveInfo();
        if (!info.available) throw new Error("The source archive is missing from this HTML.");
        const bytes = globalThis.obsPayload ? await globalThis.obsPayload.bytes() :
            Uint8Array.from(atob(document.getElementById("obs-source-archive").textContent.trim()),
                char => char.charCodeAt(0));
        const url = URL.createObjectURL(new Blob([bytes], {type: "application/zip"}));
        const download = document.createElement("a");
        download.href = url;
        download.download = info.complete ? "obs-html-source.zip" : "obs-html-partial-evidence.zip";
        document.body.append(download);
        download.click();
        download.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
    };
    document.addEventListener("click", async (event) => {
        const link = event.target.closest?.('[data-source-download], a[href="obs-source:archive"]');
        if (!link) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (!sourceArchiveInfo().available) return;
        try {
            await downloadSourceArchive();
            const limited = globalThis.obsCapabilities?.explain("downloads");
            if (limited) globalThis.obsCapabilities.note(link, limited);
        } catch (error) {
            if (globalThis.obsPayload) globalThis.obsPayload.fail(error);
            else showApplicationError(error);
        }
    }, true);
    const baseFilterExpression = globalThis.obsBases.filterExpression;
    let cachedContentTableRows;
    const contentTableRows = () => {
        if (!cachedContentTableRows) {
            cachedContentTableRows = [
                ...chapterTableRows(), ...noteTableRows(), ...tagTableRows(), ...glossaryTableRows(),
            ];
        }
        return cachedContentTableRows;
    };

    let cachedDocumentMetadataRows;
    const documentMetadataRows = () => {
        if (!cachedDocumentMetadataRows) {
            cachedDocumentMetadataRows = [
                ...Object.entries(artifactData.document.metadata).filter(([key]) => key !== "history")
                    .map(([key, value]) => [key, value, "metadata"]),
                ...Object.entries(artifactData.document.generation).map(
                    ([key, value]) => [key, value, "generation"],
                ),
            ].map(([key, value, owner]) => {
                const text = formatStructuredValue(value);
                return tableRecord(`${owner}:${key}`, {recordType: "documentMetadata", key, value: text},
                    value !== null && typeof value === "object" && !isScalarList(value)
                        ? {cells: {value: {type: "preformatted", label: text}}} : {});
            });
        }
        return cachedDocumentMetadataRows;
    };

    let cachedDocumentHistoryRows;
    const documentHistoryRows = () => {
        if (!cachedDocumentHistoryRows) {
            cachedDocumentHistoryRows = (artifactData.document.metadata.history || []).map((entry, index) =>
                tableRecord(`history:${index}`, {
                    recordType: "documentHistory", ...entry, date: entry.date || "",
                })
            );
        }
        return cachedDocumentHistoryRows;
    };

    let cachedArtifactTableRows;
    const artifactTableRows = () => {
        if (!cachedArtifactTableRows) {
            cachedArtifactTableRows = [
                ...contentTableRows(), ...documentMetadataRows(), ...documentHistoryRows(),
            ];
        }
        return cachedArtifactTableRows;
    };

    const appendTableCell = (cell, descriptor, fallback) => {
        if (!descriptor) {
            cell.append(String(fallback ?? ""));
            return;
        }
        if (descriptor.type === "links") {
            const list = document.createElement("ul");
            descriptor.links.forEach((location) => {
                const item = document.createElement("li");
                appendTableCell(item, {type: "link", ...location});
                list.append(item);
            });
            cell.append(list);
            return;
        }
        if (descriptor.type === "html") {
            appendTrustedHtml(cell, descriptor.html || "");
            return;
        }
        if (descriptor.type === "preformatted") {
            const text = document.createElement("span");
            text.className = "data-table-preformatted";
            text.textContent = descriptor.label;
            cell.append(text);
            return;
        }
        if (descriptor.type === "detail") {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "data-table-detail-label";
            button.dataset.tableDetailToggle = "";
            button.textContent = descriptor.label;
            cell.append(button);
            return;
        }
        const link = document.createElement("a");
        link.href = descriptor.href;
        link.textContent = descriptor.label;
        if (descriptor.type === "source") {
            link.className = "mark-source-link";
            link.prepend(globalThis.obsAssets.create("right"));
            link.dataset.sourceChapter = descriptor.chapter;
            link.dataset.sourceTarget = descriptor.href.slice(1);
        }
        cell.append(link);
        return link;
    };

    const rendersLink = (row, field) => {
        const content = document.createElement("div");
        appendTableCell(content, row.cells[field], row.values[field]);
        return Boolean(content.querySelector("a[href]"));
    };

    const appendIconCell = (cell, icon, row) => {
        // A card that declares a source link is only offered on rows that have one.
        const cardUnavailable = Boolean(icon.card?.link) && !rendersLink(row, icon.card.link);
        const hasHelp = !cardUnavailable && Boolean(icon.help || (icon.helpProperty &&
            (row.cells[icon.helpProperty] || meaningfulMetadata(row.values[icon.helpProperty]))));
        let link;
        if (icon.linkProperty) {
            const content = document.createElement("div");
            appendTableCell(content, row.cells[icon.linkProperty], "");
            link = content.querySelector("a[href]");
        } else if (icon.action === "sourceArchive" && document.getElementById("obs-source-archive")) {
            link = document.createElement("a");
            link.href = "#";
            link.dataset.sourceDownload = "";
        }
        const control = link || document.createElement("button");
        control.className = "data-table-icon-action";
        control.setAttribute("aria-label", icon.label);
        control.title = icon.label;
        if (hasHelp) tableIconHelp.set(control, {icon, row});
        if (link && icon.linkProperty) {
            if (icon.download) {
                link.download = "";
                link.removeAttribute("target");
            } else link.removeAttribute("download");
        }
        if (!link && icon.action && icon.action !== "sourceArchive" && !cardUnavailable) {
            control.dataset.artifactAction = icon.action;
            control.dataset.actionNoteId = row.canonicalId;
            if (icon.card) tableIconCards.set(control, {card: icon.card, row});
        }
        if (!link) {
            control.type = "button";
            if (cardUnavailable ||
                    (!hasHelp && (!icon.action || icon.action === "sourceArchive"))) {
                const reason = icon.unavailable || (icon.action === "sourceArchive"
                    ? "Original source archive unavailable" : "No help available");
                control.disabled = true;
                control.setAttribute("aria-label", `${icon.label}: ${reason}`);
                control.title = `${icon.label}: ${reason}`;
                control.dataset.unavailable = "";
            }
        }
        globalThis.obsAssets.replace(control, icon.name, control.disabled ? "inactive" : "active");
        cell.append(control);
    };

    const meaningfulMetadata = globalThis.obsBases.assigned;
    let subjectContentCache = new WeakMap();
    const subjectContentState = record => {
        if (!subjectContentCache.has(record)) subjectContentCache.set(record, {profiles: new Map()});
        return subjectContentCache.get(record);
    };
    const permittedMetadata = (record, allowlist) => {
        const state = subjectContentState(record);
        const entries = state.metadata ||= record.metadataEntries.filter(([field]) =>
            meaningfulMetadata(globalThis.obsBases.recordValue(record, field)));
        if (!Array.isArray(allowlist)) return entries;
        const selected = new Set();
        return globalThis.obsBases.expandMetadata(record, allowlist).flatMap(prefix => entries.filter(([field]) =>
            (field === prefix || field.startsWith(`${prefix}.`)) && !selected.has(field) &&
            selected.add(field),
        ));
    };
    const hasSubjectContent = (record, allowlist) => {
        const state = subjectContentState(record);
        const signature = JSON.stringify(allowlist || null);
        if (state.profiles.has(signature)) return state.profiles.get(signature);
        const template = document.createElement("template");
        template.innerHTML = record.html || "";
        const available = Boolean(template.content.textContent.trim()) ||
            Boolean(template.content.querySelector("img:not(.resource-icon *), svg:not(.resource-icon *), math, [data-base-table]")) ||
            permittedMetadata(record, allowlist).some(([, value]) => String(value).trim());
        state.profiles.set(signature, available);
        return available;
    };
    const sourceHref = (record, field) => {
        if (!field) return undefined;
        const value = globalThis.obsBases.recordValue(record, field);
        if (typeof value === "string" && URL.canParse(value) &&
                ["http:", "https:"].includes(new URL(value).protocol)) return new URL(value).href;
        const template = document.createElement("template");
        template.innerHTML = record.frontmatterHtml?.[field] || "";
        const href = template.content.querySelector("a[href]")?.getAttribute("href");
        return href && URL.canParse(href) && ["http:", "https:"].includes(new URL(href).protocol)
            ? new URL(href).href : undefined;
    };
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
    const propertyEditor = (owner, field, presentation = {}) => {
        const definition = owner?.editableProperties?.[field];
        if (!definition) return null;
        const singleLine = presentation.editor === "singleLine";
        const editor = document.createElement(singleLine ? "input" : "textarea");
        if (singleLine) {
            editor.type = "text";
            editor.dataset.propertySingleLine = "";
        }
        editor.dataset.propertyEditor = "";
        editor.dataset.propertyNote = owner.slug;
        editor.dataset.propertyField = field;
        editor.maxLength = definition.maxLength;
        if (!singleLine) editor.rows = 2;
        editor.value = owner.frontmatter[field];
        editor.setAttribute("aria-label", definition.label);
        editor.dataset.hoverHelp = "Enter or leave the field to apply. Save reviewed HTML explicitly to retain changes.";
        return editor;
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
            return !note || !queryPopulation.match(note) || activeFilter.match(note);
        });
    // Search and table filters read every row's reader-visible text from the model,
    // independent of which page, group or detail panel is currently rendered.
    let rowTextCache = new Map();
    let searchIndex = null;
    ["obs-canonical-property-change", "obs-table-definition-change"].forEach(type =>
        document.addEventListener(type, () => {
            rowTextCache = new Map();
            searchIndex = null;
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
    const searchHits = () => {
        searchIndex ||= records.filter(isDocument).flatMap(record => [
            {kind: "chapter", slug: record.slug, chapter: record, target: record},
            ...(record.tables || []).flatMap(table => tableSearchHits(record, table)),
        ]);
        return searchIndex.filter(hit => hit.kind !== "row" || filterTableRows([hit.row]).length);
    };
    const viewSelections = new Map(Object.entries(artifactData.readerState?.views || {}));
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
                    document.dispatchEvent(new CustomEvent("obs-reader-state-change"));
                },
                columns: definition.columns,
                availableColumns: definition.availableColumns,
                fieldCatalog: definition.fieldCatalog,
                initialGroup: definition.initialGroup,
                initialSort: definition.initialSort,
                initialPageSize: staticView ? Number.MAX_SAFE_INTEGER : definition.pageSize,
                initialExpression: table.key === record.tables[0].key ? firstTableFilter : "",
                initialPresentation: state.presentation,
                onPresentationChange: staticView ? undefined : (presentation, defaults) => {
                    state.presentation = savedPresentations?.[table.key] === undefined &&
                        JSON.stringify(presentation) === JSON.stringify(defaults) ? undefined : presentation;
                    document.dispatchEvent(new CustomEvent("obs-reader-state-change"));
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
                    visibleIndices.some((index) => chapters[index].slug === row.key),
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
                if (staticView) {
                    const plainTable = rendered.element.querySelector("table");
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

    const chapterParentIndex = (index) => {
        const depth = chapters[index].depth;
        if (!depth) return -1;
        for (let candidate = index - 1; candidate >= 0; candidate -= 1) {
            if (chapters[candidate].depth === depth - 1) return candidate;
        }
        return -1;
    };

    const chapterChildren = (parentIndex) => {
        if (parentIndex >= 0 && chapters[parentIndex].generated === "home") parentIndex = -1;
        const depth = parentIndex < 0 ? 0 : chapters[parentIndex].depth + 1;
        const start = parentIndex < 0 ? 0 : parentIndex + 1;
        const result = [];
        for (let index = start; index < chapters.length; index += 1) {
            if (parentIndex >= 0 && chapters[index].depth <= chapters[parentIndex].depth) break;
            if (!chapters[index].generated && chapters[index].depth === depth) {
                result.push({chapter: chapters[index], index});
            }
        }
        return result;
    };

    const syncBreadcrumbs = () => {
        bandPath.querySelectorAll(".chapter-breadcrumb-chooser").forEach((chooser) => {
            const links = [...chooser.querySelectorAll(".chapter-breadcrumb-menu a")];
            links.forEach((link) => {
                link.hidden = !visibleIndices.includes(Number(link.dataset.chapterIndex));
            });
            chooser.hidden = links.every((link) => link.hidden);
            if (chooser.hidden) chooser.removeAttribute("open");
        });
    };
    const renderBreadcrumbs = (index, record) => {
        const path = [];
        let current = index;
        while (current >= 0) {
            path.unshift(current);
            current = chapterParentIndex(current);
        }
        const navigation = document.createElement("nav");
        navigation.className = "chapter-breadcrumbs";
        navigation.setAttribute("aria-label", "Chapter path");
        const home = document.createElement("a");
        home.href = "#home";
        home.className = "chapter-home-link";
        home.setAttribute("aria-label", "Home");
        home.title = artifactData.document.title;
        globalThis.obsAssets.replace(home, "home");
        if (record.generated === "home") home.setAttribute("aria-current", "page");
        navigation.append(home);
        let currentCrumb = home;
        const appendChooser = (parentIndex, label, selectedIndex = -1) => {
            const chooser = document.createElement("details");
            chooser.className = "chapter-breadcrumb-chooser";
            const summary = document.createElement("summary");
            summary.className = "disclosure-toggle chapter-breadcrumb-toggle";
            summary.setAttribute("aria-label", label);
            summary.title = summary.getAttribute("aria-label");
            const menu = document.createElement("span");
            menu.className = "chapter-breadcrumb-menu";
            chapterChildren(parentIndex).forEach(({chapter, index: choiceIndex}) => {
                const link = document.createElement("a");
                link.href = `#${chapter.slug}`;
                link.dataset.chapterIndex = String(choiceIndex);
                link.textContent = chapter.title;
                if (choiceIndex === selectedIndex) link.setAttribute("aria-current", "page");
                menu.append(link);
            });
            chooser.append(summary, menu);
            navigation.append(chooser);
            return chooser;
        };
        path.forEach((chapterIndex, level) => {
            if (chapters[chapterIndex].generated === "home") return;
            appendChooser(
                level ? path[level - 1] : -1,
                `Choose ${level ? "subchapter" : "chapter"}`,
                chapterIndex,
            );
            const link = document.createElement("a");
            link.href = `#${chapters[chapterIndex].slug}`;
            link.textContent = chapters[chapterIndex].title;
            link.title = link.textContent;
            if (chapterIndex === index) {
                link.setAttribute("aria-current", "page");
                currentCrumb = link;
            }
            navigation.append(link);
        });
        if (index < 0) {
            const label = document.createElement("a");
            label.href = `#${record.slug}`;
            label.textContent = record.title;
            label.title = label.textContent;
            label.setAttribute("aria-current", "page");
            navigation.append(label);
            currentCrumb = label;
        }
        currentCrumb.dataset.breadcrumbCurrent = "";
        if (index >= 0 && chapterChildren(index).length) {
            const chooser = appendChooser(index, `Show children of ${chapters[index].title}`);
            chooser.id = `breadcrumb-children-${chapters[index].slug}`;
            currentCrumb.setAttribute("aria-controls", chooser.id);
            currentCrumb.setAttribute("aria-expanded", "false");
            currentCrumb.title = chooser.querySelector("summary").title;
            chooser.addEventListener("toggle", () => {
                currentCrumb.setAttribute("aria-expanded", String(chooser.hasAttribute("open")));
            });
        }
        bandPath.replaceChildren(navigation);
        syncBreadcrumbs();
    };

    const revealSource = (element, block = "center") => {
        let section = element?.closest("[data-heading-section]");
        while (section) {
            const button = chapterBody.querySelector(
                `[data-heading-section-target="${section.dataset.headingSection}"]`,
            );
            if (button?.getAttribute("aria-expanded") === "false") button.click();
            section = section.parentElement.closest("[data-heading-section]");
        }
        element?.scrollIntoView({block});
    };

    let navigationGeneration = 0;
    let pendingNavigation = null;
    let pendingStep = 0;
    let navigationReady = Promise.resolve();
    const activateChapter = (slug, historyMode = "push") => {
        if (pendingNavigation === slug) return navigationReady;
        const [path, parameters = ""] = slug.split("?", 2);
        const [noteSlug, heading] = decodeURIComponent(path).split("/", 2);
        const tableFilter = new URLSearchParams(parameters).get("tableFilter");
        if (tableFilter !== null) globalThis.obsQuery.compile(tableFilter);
        const record = recordsBySlug.get(noteSlug);
        if (!record) return;
        if (!isDocument(record)) {
            activateChapter("home", historyMode);
            return;
        }
        const requestedIndex = chapters.findIndex((chapter) => chapter.slug === noteSlug);
        if (requestedIndex >= 0 && !visibleIndices.includes(requestedIndex)) {
            activateChapter("home", historyMode);
            return;
        }
        const groupTarget = heading?.startsWith("@table-group--");
        const groupTable = groupTarget && (record.tables || []).find(({key}) =>
            heading.startsWith(`@table-group--${key}--`),
        );
        if (groupTarget && !groupTable) {
            throw new Error("The linked table group does not belong to this chapter.");
        }
        const generation = ++navigationGeneration;
        pendingNavigation = null;
        pendingStep = 0;
        document.dispatchEvent(new CustomEvent("obs-chapter-changing", {
            detail: {slug: record.slug},
        }));
        const nextIndex = chapters.findIndex((chapter) => chapter.slug === noteSlug);

        activeIndex = nextIndex;
        scrollIntent = 0;
        clearScrollCues();
        activeChapter.id = record.slug;
        activeChapter.dataset.chapter = record.slug;
        activeChapter.dataset.tableFilter = tableFilter || "";
        activeChapter.className = ["chapter", ...record.cssClasses].join(" ");
        replaceTrustedHtml(chapterBody, record.html);
        const deferred = [];
        if (globalThis.obsStartup && globalThis.obsArtifact) {
            chapterBody.querySelectorAll("[data-base-table], [data-artifact-figure]").forEach(node => {
                if (node.parentElement.closest("[data-artifact-figure]")) return;
                const placeholder = document.createElement("div");
                placeholder.className = "reader-pending";
                placeholder.setAttribute("role", "status");
                placeholder.setAttribute("aria-busy", "true");
                placeholder.textContent = node.matches("[data-base-table]")
                    ? "Loading table…" : "Loading overview…";
                node.replaceWith(placeholder);
                deferred.push({node, placeholder});
            });
        }
        refreshSourceControls();
        renderBreadcrumbs(activeIndex, record);
        const completeTables = () => {
            renderChapterTables(record);
            if (tableFilter !== null) {
                const table = groupTable
                    ? [...chapterBody.querySelectorAll("[data-data-table]")].find(
                        (element) => element.dataset.dataTable === groupTable.key,
                    )
                    : chapterBody.querySelector("[data-data-table]");
                if (!table) throw new Error("The linked note has no table to filter.");
                table.dispatchEvent(new CustomEvent("obs-table-set-filter", {
                    detail: {expression: tableFilter},
                }));
            }
        };
        if (!deferred.length) completeTables();
        renderFrontmatter(record);
        initializeHeadingSections();
        document.dispatchEvent(new CustomEvent("obs-chapter-change", {
            detail: {slug: record.slug},
        }));
        tocLinks.forEach((link) => {
            if (link.dataset.tocLink === noteSlug) {
                link.setAttribute("aria-current", "page");
                if (historyMode !== "replace") expandTocAncestors(link);
            } else {
                link.removeAttribute("aria-current");
            }
        });
        updateStepButtons();
        chapterScroll.scrollTop = 0;
        previousScrollTop = 0;
        chapterScroll.focus({ preventScroll: true });
        const revealHeading = () => {
            if (!heading) return;
            const target = heading.startsWith("@") ? heading.slice(1)
                : heading.startsWith("mark-") && document.getElementById(heading) ? heading
                    : `${noteSlug}--${heading}`;
            const element = document.getElementById(target) || (groupTable
                ? [...chapterBody.querySelectorAll("[data-data-table]")].find(
                    (item) => item.dataset.dataTable === groupTable.key,
                )
                : null);
            revealSource(element, "start");
        };
        revealHeading();
        const sourceLine = new URLSearchParams(parameters).get("sourceLine");
        const sourceCell = new URLSearchParams(parameters).get("sourceCell");
        const sourceField = new URLSearchParams(parameters).get("sourceField");
        if (sourceLine !== null) {
            revealSource([...chapterBody.querySelectorAll("[data-source-line]")].find(
                (element) => element.dataset.sourceLine === sourceLine &&
                    (sourceCell === null || element.dataset.sourceCell === sourceCell),
            ));
        }
        if (sourceField !== null) {
            setFrontmatterExpanded(true);
            revealSource([...frontmatterBody.querySelectorAll("[data-frontmatter-field]")].find(
                (element) => element.dataset.frontmatterField === sourceField.toLocaleLowerCase(),
            ));
        }

        const hash = `#${slug}`;
        // A sandboxed or srcdoc frame (Claude's preview) cannot change its URL; navigation
        // still works there, only the address and browser Back do not follow it.
        try {
            if (historyMode === "push" && window.location.hash !== hash) {
                window.history.pushState({ slug }, "", hash);
            } else if (historyMode === "replace") {
                window.history.replaceState({ slug }, "", hash);
            }
        } catch {
            // Fail open: the chapter is shown without a history entry.
        }
        if (deferred.length) {
            pendingNavigation = slug;
            navigationReady = (async () => {
                await globalThis.obsStartup.paint();
                if (generation !== navigationGeneration) return false;
                document.dispatchEvent(new CustomEvent("obs-chapter-content-changing"));
                deferred.forEach(({node, placeholder}) => placeholder.replaceWith(node));
                completeTables();
                if (generation !== navigationGeneration) return false;
                pendingNavigation = null;
                pendingStep = 0;
                document.dispatchEvent(new CustomEvent("obs-chapter-content-ready", {
                    detail: {slug: record.slug},
                }));
                revealHeading();
                return true;
            })().catch(error => {
                if (generation !== navigationGeneration) return false;
                pendingNavigation = null;
                pendingStep = 0;
                deferred.forEach(({placeholder}) => {
                    placeholder.removeAttribute("aria-busy");
                    placeholder.setAttribute("role", "alert");
                    placeholder.textContent = `Content could not load: ${error.message}`;
                });
                showApplicationError(error);
                return false;
            });
        } else navigationReady = Promise.resolve(true);
        return navigationReady;
    };

    const dockBars = (region) => [...region.querySelectorAll(":scope > .dock-bar")];
    const dockAnchors = new WeakMap();
    const horizontalDock = region => ["top", "bottom"].includes(region.dataset.dockRegion);
    const dockSpan = region => horizontalDock(region) ? region.clientWidth : region.clientHeight;
    const dockStart = region => {
        const bounds = region.getBoundingClientRect();
        return horizontalDock(region) ? bounds.left + region.clientLeft : bounds.top + region.clientTop;
    };
    const separatorPosition = separator => {
        const region = separator.closest("[data-dock-region]");
        const bounds = separator.getBoundingClientRect();
        return (horizontalDock(region) ? bounds.left : bounds.top) - dockStart(region);
    };
    const layoutDockBars = region => {
        const panes = dockBars(region);
        const separators = [...region.querySelectorAll(":scope > [data-bar-resize]")];
        if (!panes.length || !dockSpan(region)) return;
        const bounds = separators[0]?.getBoundingClientRect();
        const gap = bounds ? horizontalDock(region) ? bounds.width : bounds.height : 0;
        const span = dockSpan(region);
        const minimum = Math.min(artifactData.dockPaneMinimumPixels,
            Math.max(0, (span - separators.length * gap) / panes.length));
        const anchors = dockAnchors.get(region) || new Map();
        const fixed = [{index: 0, position: -gap}];
        separators.forEach((separator, offset) => {
            const anchor = anchors.get(panes[offset]);
            if (!anchor || anchor.next !== panes[offset + 1]) return;
            const index = offset + 1;
            const prior = fixed.at(-1);
            anchor.position = Math.max(prior.position + (index - prior.index) * (minimum + gap),
                Math.min(anchor.position, span - (panes.length - index) * (minimum + gap)));
            fixed.push({index, position: anchor.position});
            separator.dataset.anchored = "";
        });
        fixed.push({index: panes.length, position: span});
        for (let index = 1; index < fixed.length; index++) {
            const left = fixed[index - 1], right = fixed[index];
            const size = (right.position - left.position) / (right.index - left.index) - gap;
            panes.slice(left.index, right.index).forEach(pane =>
                pane.style.setProperty("--bar-size", `${size}px`));
        }
        separators.forEach(updateBarSeparatorValue);
    };

    const updateBarSeparatorValue = (separator) => {
        const previous = separator.previousElementSibling;
        const next = separator.nextElementSibling;
        if (!previous?.classList.contains("dock-bar") || !next?.classList.contains("dock-bar")) return;
        const direction = separator.closest("[data-dock-region]").dataset.dockRegion;
        const horizontal = direction === "top" || direction === "bottom";
        const previousSize = horizontal ? previous.getBoundingClientRect().width : previous.getBoundingClientRect().height;
        const nextSize = horizontal ? next.getBoundingClientRect().width : next.getBoundingClientRect().height;
        const percent = Math.round(previousSize / (previousSize + nextSize) * 100);
        separator.setAttribute("aria-valuenow", String(percent));
        separator.setAttribute("aria-valuetext", `${percent}% before separator`);
    };

    const resizeAdjacentBars = (separator, delta) => {
        const region = separator.closest("[data-dock-region]");
        const barsInRegion = dockBars(region);
        const previous = separator.previousElementSibling;
        const next = separator.nextElementSibling;
        const direction = region.dataset.dockRegion;
        const horizontal = direction === "top" || direction === "bottom";
        const sizeOf = (bar) => horizontal ? bar.getBoundingClientRect().width : bar.getBoundingClientRect().height;
        const previousSize = sizeOf(previous);
        const nextSize = sizeOf(next);
        const minimum = Math.min(artifactData.dockPaneMinimumPixels, (previousSize + nextSize) / 2);
        const constrained = Math.min(Math.max(delta, minimum - previousSize), nextSize - minimum);
        barsInRegion.forEach((bar) => bar.style.setProperty("--bar-size", `${sizeOf(bar)}px`));
        previous.style.setProperty("--bar-size", `${previousSize + constrained}px`);
        next.style.setProperty("--bar-size", `${nextSize - constrained}px`);
        const anchors = dockAnchors.get(region) || new Map();
        anchors.set(previous, {next, position: separatorPosition(separator)});
        dockAnchors.set(region, anchors);
        separator.dataset.anchored = "";
        updateBarSeparatorValue(separator);
    };

    const initializeBarSeparator = (separator) => {
        const region = separator.closest("[data-dock-region]");
        const direction = region.dataset.dockRegion;
        const horizontal = direction === "top" || direction === "bottom";
        const coordinate = (event) => horizontal ? event.clientX : event.clientY;
        let previousCoordinate = 0;

        separator.addEventListener("pointerdown", (event) => {
            event.preventDefault();
            previousCoordinate = coordinate(event);
            separator.setPointerCapture(event.pointerId);
            separator.dataset.resizing = "";
        });
        separator.addEventListener("pointermove", (event) => {
            if (!separator.hasPointerCapture(event.pointerId)) return;
            const current = coordinate(event);
            resizeAdjacentBars(separator, current - previousCoordinate);
            previousCoordinate = current;
        });
        const finish = (event) => {
            if (separator.hasPointerCapture(event.pointerId)) separator.releasePointerCapture(event.pointerId);
            delete separator.dataset.resizing;
        };
        separator.addEventListener("pointerup", finish);
        separator.addEventListener("pointercancel", finish);
        separator.addEventListener("dblclick", () => {
            dockAnchors.get(region)?.delete(separator.previousElementSibling);
            delete separator.dataset.anchored;
            layoutDockBars(region);
        });
        separator.addEventListener("keydown", (event) => {
            const changes = horizontal
                ? { ArrowLeft: -16, ArrowRight: 16 }
                : { ArrowUp: -16, ArrowDown: 16 };
            const change = changes[event.key];
            if (!change) return;
            event.preventDefault();
            resizeAdjacentBars(separator, change);
        });
        requestAnimationFrame(() => updateBarSeparatorValue(separator));
    };

    const refreshBarSeparators = (region) => {
        if (!region) return;
        region.querySelectorAll(":scope > [data-bar-resize]").forEach((separator) => separator.remove());
        const barsInRegion = dockBars(region);
        if (barsInRegion.length < 2) {
            dockAnchors.delete(region);
            barsInRegion.forEach((bar) => bar.style.removeProperty("--bar-size"));
            return;
        }
        const direction = region.dataset.dockRegion;
        const orientation = direction === "top" || direction === "bottom" ? "vertical" : "horizontal";
        barsInRegion.slice(1).forEach((bar, index) => {
            const previous = barsInRegion[index];
            const separator = document.createElement("div");
            separator.className = "bar-resize-handle";
            separator.dataset.barResize = "";
            separator.tabIndex = 0;
            separator.setAttribute("role", "separator");
            separator.setAttribute("aria-orientation", orientation);
            separator.setAttribute(
                "aria-label",
                `Resize ${previous.getAttribute("aria-label")} and ${bar.getAttribute("aria-label")}`,
            );
            separator.dataset.hoverHelp = "Drag to resize adjacent bars; double-click to reset";
            region.insertBefore(separator, bar);
            initializeBarSeparator(separator);
        });
        layoutDockBars(region);
    };
    const dockObserver = new ResizeObserver(entries => {
        entries.forEach(({target}) => layoutDockBars(target));
    });
    document.querySelectorAll("[data-dock-region]").forEach(region => dockObserver.observe(region));

    const filterInput = document.querySelector("[data-filter-input]");
    // The applied filter is an information entry of the notice center; its details can clear it.
    const clearFilter = document.createElement("button");
    clearFilter.type = "button";
    clearFilter.dataset.filterClear = "";
    globalThis.obsAssets.replace(clearFilter, "close");
    clearFilter.append(" Clear filter");
    clearFilter.addEventListener("click", () => globalThis.obsFilter.setExpression(""));
    const filterSummary = () => {
        const authored = chapterRecords.filter((record) => !record.generated);
        const retained = visibleIndices.map((index) => chapterRecords[index])
            .filter((record) => !record.generated);
        const population = filterRecords();
        return {
            expression: activeFilter.empty ? "" : activeFilter.source,
            empty: activeFilter.empty,
            chapters: retained.length,
            totalChapters: authored.length,
            paragraphs: retained.reduce((sum, record) => sum + record.paragraphCount, 0),
            totalParagraphs: authored.reduce((sum, record) => sum + record.paragraphCount, 0),
            records: population.filter((record) => activeFilter.match(record)).length,
            totalRecords: population.length,
        };
    };
    const setFilter = (query) => {
        filterRevision++;
        // Reapplications preserve drafts; new programmatic queries use the editable owner.
        if (globalThis.obsFilter && activeFilter.source !== query.source && filterInput.value !== query.source) {
            globalThis.obsFilter.selectExpression(query.source);
            return filterSummary().chapters;
        }
        activeFilter = query;
        menuButton.setAttribute("aria-label", "Open bars menu");
        menuButton.title = "Bars";
        visibleIndices = chapterRecords
            .map((record, index) => record.generated === "home" ||
                queryProfile.scope === "records" || query.match(record) ? index : -1)
            .filter((index) => index >= 0);
        const visibleTocIndices = new Set(visibleIndices);
        visibleIndices.forEach((index) => {
            let depth = chapters[index].depth;
            for (let candidate = index - 1; candidate >= 0 && depth > 0; candidate -= 1) {
                if (chapters[candidate].depth < depth) {
                    visibleTocIndices.add(candidate);
                    depth = chapters[candidate].depth;
                }
            }
        });
        visibleIndices = [...visibleTocIndices].sort((left, right) => left - right);
        tocLinks.forEach((link) => {
            link.closest("li").hidden = !visibleTocIndices.has(Number(link.dataset.chapterIndex));
        });
        if (activeIndex >= 0 && !visibleTocIndices.has(activeIndex)) activateChapter("home", "replace");
        syncBreadcrumbs();
        const summary = filterSummary();
        if (query.empty) globalThis.obsNotices.remove("applied-filter");
        else {
            globalThis.obsNotices.post({
                id: "applied-filter", severity: "information",
                title: `Filtered view \u00b7 ${summary.chapters}/${summary.totalChapters} chapters`,
                details: [
                    `Filter: ${summary.expression}`,
                    `${summary.chapters}/${summary.totalChapters} chapters \u00b7 ` +
                        `${summary.paragraphs}/${summary.totalParagraphs} paragraphs` +
                        (queryProfile.scope === "records"
                            ? ` \u00b7 ${summary.records}/${summary.totalRecords} records` : ""),
                    clearFilter,
                ],
            });
        }
        updateStepButtons();
        document.dispatchEvent(new CustomEvent("obs-artifact-filter"));
        return summary.chapters;
    };

    const markMatches = (root, fieldForNode, query) => {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
            acceptNode: (node) => node.parentElement.closest("button, mark")
                ? NodeFilter.FILTER_REJECT
                : NodeFilter.FILTER_ACCEPT,
        });
        const textNodes = [];
        while (walker.nextNode()) textNodes.push(walker.currentNode);
        // Code-span break opportunities (<wbr>) split one word into several text nodes;
        // match across them so `content.py` stays findable.
        const runs = [];
        textNodes.forEach((node) => {
            const run = runs[runs.length - 1];
            const previous = node.previousSibling;
            if (run && previous?.nodeName === "WBR" && previous.previousSibling === run[run.length - 1]) {
                run.push(node);
            } else runs.push([node]);
        });
        runs.forEach((run) => {
            const field = fieldForNode(run[0]);
            const ranges = query.ranges(run.map((node) => node.data).join(""), field);
            if (!ranges.length) return;
            let base = 0;
            run.forEach((node) => {
                const end = base + node.data.length;
                const local = ranges
                    .map(([start, stop]) => [Math.max(start, base) - base, Math.min(stop, end) - base])
                    .filter(([start, stop]) => start < stop);
                base = end;
                if (!local.length) return;
                const fragment = document.createDocumentFragment();
                let offset = 0;
                local.forEach(([start, stop]) => {
                    fragment.append(node.data.slice(offset, start));
                    const mark = document.createElement("mark");
                    mark.className = "search-highlight";
                    mark.textContent = node.data.slice(start, stop);
                    fragment.append(mark);
                    offset = stop;
                });
                fragment.append(node.data.slice(offset));
                node.replaceWith(fragment);
            });
        });
    };

    const clearSearchHighlights = () => {
        document.querySelectorAll("mark.search-highlight").forEach(mark => {
            const parent = mark.parentNode;
            mark.replaceWith(document.createTextNode(mark.textContent));
            parent?.normalize();
        });
    };

    // Paged layout can re-flow after a reveal (deferred page numbering, images); keep the
    // hit in view until the reader interacts.
    let anchoredHit = null;
    const reanchor = () => {
        if (!anchoredHit) return;
        const target = anchoredHit.isConnected && chapterBody.contains(anchoredHit) ? anchoredHit
            : chapterBody.querySelector(".search-highlight");
        if (target) {
            anchoredHit = target;
            target.scrollIntoView({block: "center"});
        } else anchoredHit = null;
    };
    const anchorObserver = typeof ResizeObserver === "function" ? new ResizeObserver(reanchor) : null;
    const scrollToHit = target => {
        anchoredHit = target;
        target.scrollIntoView({block: "center"});
        anchorObserver?.disconnect();
        [chapterBody, target.closest(".paper-sheet, [data-data-table]")].filter(Boolean)
            .forEach(node => anchorObserver?.observe(node));
    };
    document.addEventListener("obs-pages-layout", reanchor);
    const releaseAnchor = () => {
        anchoredHit = null;
        anchorObserver?.disconnect();
    };
    ["pointerdown", "wheel", "keydown", "touchstart"].forEach(type =>
        document.addEventListener(type, releaseAnchor, {capture: true, passive: true}));
    document.addEventListener("obs-chapter-change", releaseAnchor);

    const highlight = (query) => {
        clearSearchHighlights();
        markMatches(chapterBody, (node) => node.parentElement.closest("h1") ? "title" : "text", query);
        markMatches(frontmatterBody, (node) => {
            const row = node.parentElement.closest("[data-frontmatter-field]");
            return node.parentElement.matches("th")
                ? ""
                : [row.dataset.frontmatterField, `frontmatter.${row.dataset.frontmatterField}`];
        }, query);
        const metadataMark = frontmatterBody.querySelector(".search-highlight");
        if (metadataMark) setFrontmatterExpanded(true);
        const firstMark = chapterBody.querySelector(".search-highlight") || metadataMark;
        if (firstMark) scrollToHit(firstMark);
        return Boolean(firstMark);
    };

    const liveTable = key => [...chapterBody.querySelectorAll("[data-data-table]:not([data-page-continuation])")]
        .find(shell => shell.dataset.dataTable === key);
    const tableRowElements = (key, rowKey) => [...chapterBody.querySelectorAll("tr[data-row-key], tr[data-detail-owner]")]
        .filter(row => (row.dataset.rowKey || row.dataset.detailOwner) === rowKey &&
            row.closest("[data-data-table]")?.dataset.dataTable === key);
    const revealTableHit = (hit, query) => {
        const shell = liveTable(hit.table);
        if (!shell) return false;
        const matching = items => items.find(item => query.ranges(item.text, "text").length);
        const cellHit = matching(hit.text.cells);
        const detailHit = cellHit ? undefined : matching(hit.text.details);
        const reveal = () => shell.dispatchEvent(new CustomEvent("obs-table-reveal-row", {detail: {
            key: hit.row.key, details: Boolean(detailHit), column: detailHit?.column,
        }}));
        reveal();
        if (!tableRowElements(hit.table, hit.row.key).length && shell.dataset.filterActive === "true") {
            shell.dispatchEvent(new CustomEvent("obs-table-set-filter", {detail: {expression: ""}}));
            reveal();
        }
        const rows = tableRowElements(hit.table, hit.row.key);
        if (!rows.length) return false;
        clearSearchHighlights();
        rows.forEach(row => markMatches(row, () => "text", query));
        const target = rows.map(row => row.querySelector(".search-highlight")).find(Boolean) || rows[0];
        scrollToHit(target);
        return true;
    };

    const activateSearchResult = async (slug, query, hit) => {
        const pending = activeChapter.dataset.chapter !== slug || pendingNavigation;
        if (!hit || hit.kind !== "row" || pending) await activateChapter(slug);
        if (activeChapter.dataset.chapter !== slug) return false;
        if (hit?.kind === "row") return revealTableHit(hit, query);
        return highlight(query);
    };

    const setBarDock = (barName, direction) => {
        const bar = bars.get(barName);
        if (!bar) return;
        const isClosing = bar.dataset.dock === direction;
        const previousRegion = bar.closest("[data-dock-region]");
        let nextRegion = null;

        if (isClosing) {
            delete bar.dataset.dock;
            bar.hidden = true;
            parking.append(bar);
        } else {
            const region = document.querySelector(`[data-dock-region="${direction}"]`);
            nextRegion = region;
            bar.dataset.dock = direction;
            bar.hidden = false;
            region.append(bar);
            requestAnimationFrame(() => {
                updateDockValue(region);
                bar.querySelector("[data-bar-autofocus]")?.focus();
            });
        }

        refreshBarSeparators(previousRegion);
        if (nextRegion !== previousRegion) refreshBarSeparators(nextRegion, true);

        dockButtons
            .filter((button) => button.dataset.dockBar === barName)
            .forEach((button) => {
                button.setAttribute(
                    "aria-pressed",
                    String(!isClosing && button.dataset.dockDirection === direction),
                );
            });
        document.dispatchEvent(new CustomEvent("obs-bar-change", {
            detail: {bar: barName, open: !bar.hidden, direction: bar.dataset.dock || null},
        }));
    };

    const openBar = (barName, direction = "right") => {
        const bar = bars.get(barName);
        if (!bar || (!bar.hidden && bar.dataset.dock)) return;
        setBarDock(barName, direction);
    };
    const closeBar = barName => {
        const bar = bars.get(barName);
        if (bar && !bar.hidden && bar.dataset.dock) setBarDock(barName, bar.dataset.dock);
    };
    const isBarOpen = barName => {
        const bar = bars.get(barName);
        return Boolean(bar && !bar.hidden && bar.dataset.dock);
    };
    document.addEventListener("click", event => {
        const close = event.target.closest("[data-bar-close]");
        if (!close) return;
        const bar = bars.get(close.dataset.barClose);
        if (!bar?.dataset.dock) return;
        const direction = bar.dataset.dock;
        setBarDock(close.dataset.barClose, direction);
        const trigger = menu.hidden ? menuButton : dockButtons.find(button =>
            button.dataset.dockBar === close.dataset.barClose && button.dataset.dockDirection === direction);
        trigger?.focus({preventScroll: true});
    });

    const updateDockValue = (region) => {
        const direction = region.dataset.dockRegion;
        const bounds = region.getBoundingClientRect();
        const size = direction === "left" || direction === "right" ? bounds.width : bounds.height;
        const handle = region.querySelector("[data-dock-resize]");
        handle.setAttribute("aria-valuenow", String(Math.round(size)));
    };

    const setDockSize = (region, size) => {
        region.style.setProperty("--dock-size", `${Math.round(size)}px`);
        updateDockValue(region);
    };

    // Measured from the region's outer edge, which is not the window's where a narrow screen
    // insets an overlaid bar beside the chapter arrows or the filter header sits above it.
    const sizeFromPointer = (region, direction, event) => {
        const bounds = region.getBoundingClientRect();
        if (direction === "left") return event.clientX - bounds.left;
        if (direction === "right") return bounds.right - event.clientX;
        if (direction === "top") return event.clientY - bounds.top;
        return bounds.bottom - event.clientY;
    };

    resizeHandles.forEach((handle) => {
        const direction = handle.dataset.dockResize;
        const region = handle.closest("[data-dock-region]");
        handle.addEventListener("pointerdown", (event) => {
            event.preventDefault();
            handle.setPointerCapture(event.pointerId);
            region.dataset.resizing = "";
        });
        handle.addEventListener("pointermove", (event) => {
            if (!handle.hasPointerCapture(event.pointerId)) return;
            setDockSize(region, sizeFromPointer(region, direction, event));
        });
        const finishResize = (event) => {
            if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
            delete region.dataset.resizing;
        };
        handle.addEventListener("pointerup", finishResize);
        handle.addEventListener("pointercancel", finishResize);
        handle.addEventListener("dblclick", () => {
            region.style.removeProperty("--dock-size");
            updateDockValue(region);
        });
        handle.addEventListener("keydown", (event) => {
            const changes = {
                left: { ArrowLeft: -16, ArrowRight: 16 },
                right: { ArrowLeft: 16, ArrowRight: -16 },
                top: { ArrowUp: -16, ArrowDown: 16 },
                bottom: { ArrowUp: 16, ArrowDown: -16 },
            };
            const change = changes[direction][event.key];
            if (!change) return;
            event.preventDefault();
            const bounds = region.getBoundingClientRect();
            const current = direction === "left" || direction === "right" ? bounds.width : bounds.height;
            setDockSize(region, current + change);
        });
    });

    frontmatterToggle.addEventListener("click", () => {
        setFrontmatterExpanded(frontmatterToggle.getAttribute("aria-expanded") !== "true");
    });

    stepButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const step = Number(button.dataset.step);
            if (pendingNavigation && pendingStep === step) return;
            const target = stepTarget(step);
            if (target?.type === "chapter") {
                activateChapter(chapters[target.index].slug);
                if (pendingNavigation) pendingStep = step;
            }
        });
    });

    // Artifact-ui.md "Floating window": a note without a place in the contents shows here as context;
    // the page stays put. Links inside the window follow the same rule.
    const floatingWindow = globalThis.ObsHtmlGuidedCard.createHost({
        window, size: artifactData.guidedCard, applyLinkPolicy,
    });
    const contextSources = "[data-chapter-body], [data-frontmatter-panel], #hover-card";
    const noteTarget = (href) => {
        const slug = href.slice(1);
        const noteSlug = decodeURIComponent(slug.split("?", 1)[0]).split("/", 1)[0];
        const record = recordsBySlug.get(noteSlug);
        return record ? {slug, noteSlug, record} : null;
    };
    const showContext = (record) => floatingWindow.open({
        use: "Context",
        title: record.title,
        mount: (root) => {
            const rows = metadataRows(record);
            if (rows.length) {
                const table = element("table", "guided-card-metadata");
                const tableBody = document.createElement("tbody");
                tableBody.append(...rows);
                table.append(tableBody);
                root.append(table);
            }
            const content = element("div", "guided-card-note");
            content.append(trustedFragment(record.html));
            const omitted = content.querySelectorAll("[data-base-table], [data-artifact-figure]");
            omitted.forEach((node) => node.remove());
            if (omitted.length) {
                content.append(element("p", "guided-card-hint", "Tables and figures of this note are not shown here."));
            }
            root.append(content);
            root.addEventListener("click", (event) => {
                const link = event.target.closest?.('a[href^="#"]');
                const target = link && noteTarget(link.getAttribute("href"));
                if (!target) return;
                event.preventDefault();
                event.stopPropagation();
                followNoteLink(target, true);
            });
        },
    });
    // Only a link to a whole note is context; a link to a place inside it (heading, source line or
    // field, table filter) navigates so that place can be revealed.
    const followNoteLink = ({slug, noteSlug, record}, context) => {
        if (context && decodeURIComponent(slug) === noteSlug && !(tocSlugs.has(noteSlug) && isDocument(record))) {
            showContext(record);
        } else {
            activateChapter(slug, "push");
        }
    };

    document.addEventListener("click", (event) => {
        const headingButton = event.target.closest("[data-heading-toggle]");
        if (headingButton) {
            const button = headingButton;
            const expanded = button.getAttribute("aria-expanded") !== "true";
            button.setAttribute("aria-expanded", String(expanded));
            button.setAttribute("aria-label", `${expanded ? "Collapse" : "Expand"} ${button.dataset.label}`);
            button.title = `${expanded ? "Collapse" : "Expand"} ${button.dataset.label}`;
            globalThis.obsAssets.set(button.querySelector("[data-icon]"), expanded ? "expanded" : "collapsed");
            chapterBody.querySelectorAll("[data-heading-section]").forEach((section) => {
                if (section.dataset.headingSection === button.dataset.headingSectionTarget) {
                    section.hidden = !expanded;
                }
            });
            document.dispatchEvent(new CustomEvent("obs-section-toggle"));
            return;
        }

        const tocButton = event.target.closest("[data-toc-toggle]");
        if (tocButton) {
            setTocExpanded(tocButton, tocButton.getAttribute("aria-expanded") !== "true");
            return;
        }

        const tocAction = event.target.closest("[data-toc-action]");
        if (tocAction) {
            const expanded = tocAction.dataset.tocAction === "expand";
            document.querySelectorAll("[data-toc-toggle]").forEach((toggle) => {
                setTocExpanded(toggle, expanded);
            });
            return;
        }

        if (!event.target.closest(".chapter-breadcrumbs")) {
            document.querySelectorAll(".chapter-breadcrumb-chooser[open]").forEach(
                (item) => item.removeAttribute("open"),
            );
        }

        const link = event.target.closest('a[href^="#"]');
        if (!link) return;
        if (link.classList.contains("chapter-home-link") && activeChapter.dataset.chapter !== "home") {
            event.preventDefault();
            activateChapter("home", "push");
            return;
        }
        if (link.hasAttribute("data-breadcrumb-current") &&
            link.getAttribute("href") === `#${activeChapter.dataset.chapter}`) {
            event.preventDefault();
            const chooser = document.getElementById(link.getAttribute("aria-controls"));
            if (chooser) {
                const open = !chooser.hasAttribute("open");
                document.querySelectorAll(".chapter-breadcrumb-chooser[open]").forEach(
                    (item) => item.removeAttribute("open"),
                );
                chooser.toggleAttribute("open", open);
                link.setAttribute("aria-expanded", String(open));
            }
            return;
        }
        // Deferred chapter tables exist only once navigation is ready; otherwise reveal on the next frame.
        const revealAfterNavigation = (navigation, reveal) => pendingNavigation === null
            ? requestAnimationFrame(reveal)
            : Promise.resolve(navigation).then((ready) => ready !== false && requestAnimationFrame(reveal));
        if (link.dataset.tagKind) {
            event.preventDefault();
            const row = tagTableRows().find((item) =>
                item.values.type === link.dataset.tagKind &&
                item.values.label === link.dataset.tagLabel);
            const destination = row && records.flatMap((record) =>
                (record.tables || []).map((table) => ({record, table})),
            ).find(({table}) => {
                const shown = tableDefinition({
                    ...table, definition: tableStates.get(table.key)?.definition || table.definition,
                    view: tableStates.get(table.key)?.view,
                });
                return shown.rows.some((item) => item.key === row.key && shown.baseQuery.match(item));
            });
            if (destination) {
                revealAfterNavigation(activateChapter(destination.record.slug, "push"), () => {
                    const table = [...chapterBody.querySelectorAll("[data-data-table]")].find(
                        (element) => element.dataset.dataTable === destination.table.key,
                    );
                    table?.dispatchEvent(new CustomEvent("obs-table-reveal-row", {
                        detail: {key: row.key},
                    }));
                    const target = table && [...table.querySelectorAll("[data-row-key]")].find(
                        (element) => element.dataset.rowKey === row.key,
                    );
                    revealSource(target);
                    target?.classList.add("semantic-source-target");
                    globalThis.setTimeout(
                        () => target?.classList.remove("semantic-source-target"), 1800,
                    );
                });
            } else {
                const message = "No table here includes this tag.";
                if (globalThis.obsCapabilities?.limit("dialogs")) globalThis.obsCapabilities.note(link, message);
                else globalThis.alert(message);
            }
            return;
        }
        const sourceChapter = link.dataset.sourceChapter;
        const sourceTarget = link.dataset.sourceTarget;
        if (sourceChapter && sourceTarget) {
            event.preventDefault();
            revealAfterNavigation(activateChapter(`${sourceChapter}/@${sourceTarget}`, "push"), () => {
                const target = document.getElementById(sourceTarget);
                revealSource(target);
                target?.classList.add("semantic-source-target");
                globalThis.setTimeout(() => target?.classList.remove("semantic-source-target"), 1800);
            });
            return;
        }
        const target = noteTarget(link.getAttribute("href"));
        if (target) {
            event.preventDefault();
            followNoteLink(target, Boolean(link.closest(contextSources)) && !link.closest(".chapter-breadcrumbs"));
        }
    });

    menuButton.addEventListener("click", (event) => {
        event.stopPropagation();
        setMenuOpen(menu.hidden);
    });

    menu.addEventListener("click", (event) => {
        event.stopPropagation();
        const button = event.target.closest("[data-dock-bar]");
        if (button) setBarDock(button.dataset.dockBar, button.dataset.dockDirection);
    });

    document.addEventListener("keydown", (event) => {
        if (event.defaultPrevented) return;
        if (event.key === "Escape") {
            setMenuOpen(false);
            document.querySelectorAll(".chapter-breadcrumb-chooser[open]").forEach(
                (item) => item.removeAttribute("open"),
            );
        }
        if (event.key === "ArrowLeft" && !event.target.matches("input, textarea")) {
            stepButtons.find((button) => button.dataset.step === "-1")?.click();
        }
        if (event.key === "ArrowRight" && !event.target.matches("input, textarea")) {
            stepButtons.find((button) => button.dataset.step === "1")?.click();
        }
    });
    window.addEventListener("popstate", () => {
        const target = window.location.hash.slice(1);
        activateChapter(target, "none");
    });

    buildToc();
    const initialSlug = window.location.hash.slice(1);
    const knownInitial = recordsBySlug.has(decodeURIComponent(initialSlug.split("?", 1)[0]).split("/", 1)[0]);
    activateChapter(knownInitial ? initialSlug : chapters[0].slug, "replace");
    const protectedPropertyFields = new Set(JSON.parse(
        document.getElementById("property-editor-schema").textContent,
    ).$defs.editableField.not.enum);
    const projectionPrimitiveType = (value) => {
        if (value === null) return "null";
        if (typeof value === "number" && !Number.isFinite(value)) return null;
        return ["string", "number", "boolean"].includes(typeof value) ? typeof value : null;
    };
    const projectionValueIsValid = (previous, value) => {
        if (Array.isArray(value)) {
            if (!value.every((item) => projectionPrimitiveType(item))) return false;
            const nextTypes = new Set(value.map(projectionPrimitiveType));
            if (nextTypes.size > 1) return false;
            if (!Array.isArray(previous)) return false;
            const previousTypes = new Set(previous.map(projectionPrimitiveType));
            return previous.every((item) => projectionPrimitiveType(item)) &&
                previousTypes.size <= 1 &&
                (!value.length || !previous.length || nextTypes.has([...previousTypes][0]));
        }
        const type = projectionPrimitiveType(value);
        return type !== null && !Array.isArray(previous) && projectionPrimitiveType(previous) === type;
    };
    const projectionValuesEqual = (left, right) => Array.isArray(left) && Array.isArray(right)
        ? left.length === right.length && left.every((value, index) => Object.is(value, right[index]))
        : Object.is(left, right);
    // The artifact timestamp is the time of the last content change. Content equal to a
    // baseline (the opened artifact or a confirmed save) keeps that baseline's timestamp, so
    // reverting an edit is not a change.
    const contentBaselines = new Map();
    const contentSignature = () => JSON.stringify(notes.map(({frontmatterHtml, ...note}) => note));
    const contentBaseline = () => ({
        signature: contentSignature(), timestamp: artifactData.document.generation?.timestamp,
    });
    let openedContentRecorded = false;
    const beforeContentChange = () => {
        if (openedContentRecorded) return;
        openedContentRecorded = true;
        const opened = contentBaseline();
        contentBaselines.set(opened.signature, opened.timestamp);
    };
    const adoptContentBaseline = (baseline) => {
        beforeContentChange();
        if (baseline?.signature) contentBaselines.set(baseline.signature, baseline.timestamp);
    };
    const recordContentChange = () => {
        if (!artifactData.document.generation) return;
        const signature = contentSignature();
        artifactData.document.generation.timestamp = contentBaselines.has(signature)
            ? contentBaselines.get(signature) : new Date().toISOString().replace(/Z$/, "+00:00");
    };
    const commitCanonicalProjection = (projection) => {
        if (!Array.isArray(projection) || projection.length === 0) {
            throw new Error("A canonical projection must contain at least one note update.");
        }
        const seenSlugs = new Set();
        const prepared = projection.map((update) => {
            if (!update || typeof update !== "object" || Array.isArray(update) ||
                typeof update.slug !== "string" || seenSlugs.has(update.slug) ||
                !update.fields || typeof update.fields !== "object" || Array.isArray(update.fields)) {
                throw new Error("A canonical projection requires unique note slugs and field maps.");
            }
            seenSlugs.add(update.slug);
            const note = notesBySlug.get(update.slug);
            if (!note || note.generated || !note.frontmatter || typeof note.frontmatter !== "object" ||
                Array.isArray(note.frontmatter)) {
                throw new Error("A canonical projection may only update an existing note's frontmatter.");
            }
            const fieldEntries = Object.entries(update.fields);
            if (!fieldEntries.length) {
                throw new Error("A canonical projection requires at least one field per note.");
            }
            const nextNote = {
                ...note,
                frontmatter: {...note.frontmatter},
                frontmatterHtml: {...(note.frontmatterHtml || {})},
            };
            const fields = [];
            for (const [field, value] of fieldEntries) {
                if (protectedPropertyFields.has(field.toLowerCase()) ||
                    !Object.hasOwn(note.frontmatter, field) ||
                    !projectionValueIsValid(note.frontmatter[field], value)) {
                    throw new Error(`Invalid canonical projection field: ${field}`);
                }
                const copiedValue = Array.isArray(value) ? [...value] : value;
                if (projectionValuesEqual(note.frontmatter[field], copiedValue)) continue;
                nextNote.frontmatter[field] = copiedValue;
                delete nextNote.frontmatterHtml[field];
                fields.push(field);
            }
            if (!fields.length) return null;
            const record = recordsBySlug.get(update.slug);
            const nextRecord = makeRecord(nextNote);
            const review = record.fields.review;
            if (review !== undefined) {
                nextRecord.fields.review = review;
                nextRecord.filterAttributes.review = review;
            }
            return {note, nextNote, record, nextRecord, fields};
        }).filter(Boolean);
        if (!prepared.length) return false;
        beforeContentChange();
        prepared.forEach(({note, nextNote, record, nextRecord}) => {
            note.frontmatter = nextNote.frontmatter;
            note.frontmatterHtml = nextNote.frontmatterHtml;
            Object.assign(record, nextRecord);
        });
        recordContentChange();
        refreshQueryFields();
        canonicalRevision += 1;
        cachedContentTableRows = undefined;
        subjectContentCache = new WeakMap();
        cachedDocumentMetadataRows = undefined;
        cachedArtifactTableRows = undefined;
        const changes = prepared.map(({note, fields}) => ({slug: note.slug, fields}));
        const detail = {projection: true, changes};
        if (changes.length === 1) {
            detail.slug = changes[0].slug;
            if (changes[0].fields.length === 1) detail.field = changes[0].fields[0];
        }
        document.dispatchEvent(new CustomEvent("obs-canonical-property-change", {detail}));
        setFilter(activeFilter);
        return true;
    };
    let canonicalRevision = 0;
    let registeredApplication;
    const expectedRuntimeBundle =
        document.querySelector('meta[name="obs-trusted-runtime"]')?.content || "";
    const canonicalNoteId = note => {
        if (typeof note.sourcePath !== "string" || !note.sourcePath.endsWith(".md")) {
            throw new Error("Canonical notes need an extension-bearing source path.");
        }
        return note.sourcePath.slice(0, -3);
    };
    const renderSafeCanonicalContent = (nodes, {note, candidateNotes, assetKeys}) => {
        if (!Array.isArray(nodes)) throw new Error("Safe canonical content must be a node array.");
        const idsToSlugs = new Map(candidateNotes.map(candidate => [canonicalNoteId(candidate), candidate.slug]));
        const container = document.createElement("div");
        const append = (parent, node) => {
            if (!node || typeof node !== "object" || Array.isArray(node)) {
                throw new Error("Invalid safe canonical content node.");
            }
            if (node.type === "text") {
                if (typeof node.text !== "string") throw new Error("Safe text content must be a string.");
                parent.append(document.createTextNode(node.text));
                return;
            }
            if (node.type === "paragraph" || node.type === "label") {
                const element = document.createElement(node.type === "paragraph" ? "p" : "label");
                (node.children || []).forEach(child => append(element, child));
                parent.append(element);
                return;
            }
            if (node.type === "lineBreak") {
                parent.append(document.createElement("br"));
                return;
            }
            if (node.type === "link") {
                if (typeof node.label !== "string") throw new Error("Safe links require a text label.");
                const link = document.createElement("a");
                link.textContent = node.label;
                if (typeof node.target === "string") {
                    const targetSlug = idsToSlugs.get(node.target);
                    if (!targetSlug) throw new Error(`Safe link target is missing: ${node.target}`);
                    link.href = `#${encodeURIComponent(targetSlug)}`;
                } else if (typeof node.assetKey === "string" && assetKeys.has(node.assetKey)) {
                    link.href = `obs-asset:${node.assetKey}`;
                    if (node.downloadName !== undefined) {
                        if (typeof node.downloadName !== "string" ||
                                !/^[A-Za-z0-9._ -]{1,160}$/.test(node.downloadName) ||
                                node.downloadName === "." || node.downloadName === "..") {
                            throw new Error("Safe asset download names must be plain filenames.");
                        }
                        link.download = node.downloadName;
                    }
                } else if (typeof node.url === "string" && /^https?:\/\//i.test(node.url)) {
                    link.href = node.url;
                    link.rel = "noopener noreferrer";
                } else {
                    throw new Error("Safe links need a canonical target, staged asset, or HTTP(S) URL.");
                }
                parent.append(link);
                return;
            }
            if (node.type === "propertyEditor") {
                const definition = note.editableProperties?.[node.field];
                if (!definition || typeof note.frontmatter?.[node.field] !== "string") {
                    throw new Error(`Safe property editor is not declared: ${node.field}`);
                }
                const label = document.createElement("label");
                label.className = "property-editor";
                const text = document.createElement("span");
                text.textContent = definition.label;
                const editor = document.createElement("textarea");
                editor.dataset.propertyEditor = "";
                editor.dataset.propertyNote = note.slug;
                editor.dataset.propertyField = node.field;
                editor.maxLength = definition.maxLength;
                editor.setAttribute("aria-label", definition.label);
                editor.rows = 2;
                label.append(text, editor);
                parent.append(label);
                return;
            }
            throw new Error(`Unsupported safe canonical content node: ${node.type}`);
        };
        nodes.forEach(node => append(container, node));
        return container.innerHTML;
    };
    const prepareCanonicalModel = async ({notes: candidateNotes, assetChanges, sourceChanges = []}) => {
        if (!globalThis.obsPayload) {
            throw new Error("Canonical evidence update services are unavailable.");
        }
        if (!Array.isArray(candidateNotes) || !Array.isArray(assetChanges)) {
            throw new Error("Canonical transaction notes and asset changes must be arrays.");
        }
        const sourceNotes = structuredClone(candidateNotes);
        const usedSlugs = new Set();
        const currentById = new Map(notes.map(note => [canonicalNoteId(note), note]));
        const preparedNotes = sourceNotes.map(note => {
            if (!note || typeof note !== "object" || Array.isArray(note) ||
                    typeof note.sourcePath !== "string" || !note.sourcePath.endsWith(".md") ||
                    note.sourcePath.startsWith("/") || note.sourcePath.includes("\\") ||
                    note.sourcePath.split("/").some(part => part === ".." || part === "")) {
                throw new Error("Invalid canonical transaction note path.");
            }
            const id = canonicalNoteId(note);
            if (usedSlugs.has(note.slug) || typeof note.slug !== "string" ||
                    !note.frontmatter || typeof note.frontmatter !== "object" ||
                    Array.isArray(note.frontmatter) || typeof note.html !== "string") {
                throw new Error(`Invalid or duplicate canonical note: ${id}`);
            }
            usedSlugs.add(note.slug);
            if (Object.hasOwn(note, "safeContent")) {
                note.html = renderSafeCanonicalContent(note.safeContent, {
                    note, candidateNotes: sourceNotes,
                    assetKeys: new Set([
                        ...Object.keys(artifactData.embeddedAssets || {}),
                        ...assetChanges.map(change => change.key),
                    ]),
                });
                delete note.safeContent;
            }
            if (Object.hasOwn(note, "safeFrontmatterContent")) {
                const rendered = {};
                for (const [field, content] of Object.entries(note.safeFrontmatterContent)) {
                    rendered[field] = renderSafeCanonicalContent(content, {
                        note, candidateNotes: sourceNotes,
                        assetKeys: new Set([
                            ...Object.keys(artifactData.embeddedAssets || {}),
                            ...assetChanges.map(change => change.key),
                        ]),
                    });
                }
                note.frontmatterHtml = {...(note.frontmatterHtml || {}), ...rendered};
                delete note.safeFrontmatterContent;
            }
            const previous = currentById.get(id);
            if (previous && tocSlugs.has(previous.slug) &&
                    JSON.stringify(note) !== JSON.stringify(previous)) {
                throw new Error(`Canonical transaction cannot alter authored chapter ${id}.`);
            }
            return note;
        });
        if (new Set(preparedNotes.map(canonicalNoteId)).size !== preparedNotes.length) {
            throw new Error("Canonical transaction note identities must be unique.");
        }
        for (const slug of artifactData.toc) {
            if (!preparedNotes.some(note => note.slug === slug)) {
                throw new Error(`Canonical transaction removed authored chapter ${slug}.`);
            }
        }
        const nextRecords = preparedNotes.map(makeRecord);
        const nextRecordsBySlug = new Map(nextRecords.map(record => [record.slug, record]));
        if (nextRecordsBySlug.size !== nextRecords.length) throw new Error("Duplicate canonical record slug.");
        const nextChapterRecords = chapters.map(chapter => {
            const record = nextRecordsBySlug.get(chapter.slug);
            if (!record) throw new Error(`Canonical transaction removed navigation record ${chapter.slug}.`);
            return record;
        });
        const nextModel = {...artifactData, notes: preparedNotes};
        const stagedAssets = assetChanges.length || sourceChanges.length
            ? await globalThis.obsPayload.stageRewrite(assetChanges, nextModel, sourceChanges)
            : null;
        if (stagedAssets) {
            nextModel.embeddedAssets = stagedAssets.assets;
            nextModel.sourceArchiveComplete = stagedAssets.complete;
        }
        JSON.stringify(nextModel);
        return {notes: preparedNotes, records: nextRecords, recordsBySlug: nextRecordsBySlug,
            chapterRecords: nextChapterRecords, assets: stagedAssets, model: nextModel};
    };
    const commitCanonicalModel = staged => {
        if (staged.assets) globalThis.obsPayload.commitRewrite(staged.assets);
        beforeContentChange();
        notes.splice(0, notes.length, ...staged.notes);
        recordContentChange();
        artifactData.notes = notes;
        if (staged.assets) {
            artifactData.embeddedAssets = staged.assets.assets;
            artifactData.sourceArchiveComplete = staged.assets.complete;
            embeddedAssets = staged.assets.assets;
        }
        notesBySlug.clear();
        notes.forEach(note => notesBySlug.set(note.slug, note));
        records.splice(0, records.length, ...staged.records);
        recordsBySlug.clear();
        staged.recordsBySlug.forEach((record, slug) => recordsBySlug.set(slug, record));
        chapterRecords.splice(0, chapterRecords.length, ...staged.chapterRecords);
        cachedContentTableRows = undefined;
        subjectContentCache = new WeakMap();
        cachedDocumentMetadataRows = undefined;
        cachedArtifactTableRows = undefined;
        canonicalRevision += 1;
        refreshQueryFields();
        refreshSourceControls();
        document.dispatchEvent(new CustomEvent("obs-canonical-property-change", {
            detail: {transaction: true},
        }));
        setFilter(activeFilter);
    };
    const canonicalTransactions = globalThis.ObsHtmlCanonicalTransaction.createCanonicalTransaction({
        revision: () => canonicalRevision,
        stage: prepareCanonicalModel,
        commit: commitCanonicalModel,
    });
    const registerApplication = bundle => {
        if (!expectedRuntimeBundle) throw new Error("The HTML has no trusted runtime bundle selection.");
        if (registeredApplication) throw new Error("A trusted runtime bundle is already registered.");
        if (!bundle || typeof bundle !== "object" || Array.isArray(bundle) ||
                bundle.id !== expectedRuntimeBundle || !Array.isArray(bundle.actions) || !bundle.actions.length) {
            throw new Error("Trusted runtime registration does not match the selected bundle.");
        }
        const actions = new Map();
        for (const action of bundle.actions) {
            if (!action || typeof action !== "object" ||
                    !/^[a-z][A-Za-z0-9._-]{0,63}$/.test(action.id || "") ||
                    typeof action.accept !== "string" || !/^[A-Za-z0-9.,+*/ _-]{1,256}$/.test(action.accept) ||
                    typeof action.help !== "string" || !action.help.trim() || action.help.length > 2000 ||
                    typeof action.handle !== "function" || actions.has(action.id)) {
                throw new Error("Trusted runtime action registration is invalid or duplicated.");
            }
            actions.set(action.id, action);
        }
        registeredApplication = {id: bundle.id, actions};
    };
    const trustedExtensions = new Map([globalThis.ObsHtmlAttachmentReplacement]
        .filter(Boolean).map(extension => [extension.namespace, extension.create]));
    const trustedExtension = namespace => {
        const create = trustedExtensions.get(namespace);
        if (!create) {
            throw new Error(`Trusted extension is unknown: ${namespace}; known: ${[...trustedExtensions.keys()].join(", ")}.`);
        }
        return create({
            artifact: globalThis.obsArtifact,
            payload: globalThis.obsPayload,
            trusted: () => Boolean(expectedRuntimeBundle) && registeredApplication?.id === expectedRuntimeBundle,
        });
    };
    const validateApplicationRuntime = expected => {
        if (expected !== expectedRuntimeBundle) throw new Error("Trusted runtime selection changed during opening.");
        if (expectedRuntimeBundle && registeredApplication?.id !== expectedRuntimeBundle) {
            throw new Error(`Trusted runtime bundle did not register: ${expectedRuntimeBundle}`);
        }
        if (!expectedRuntimeBundle && registeredApplication) {
            throw new Error("HTML without an explicit runtime selection registered executable code.");
        }
    };
    const showApplicationError = error => {
        let notice = document.querySelector("[data-application-runtime-error]");
        if (!notice) {
            notice = document.createElement("p");
            notice.dataset.applicationRuntimeError = "";
            notice.dataset.transientView = "";
            notice.setAttribute("role", "alert");
            document.querySelector(".reader-shell").prepend(notice);
        }
        notice.textContent = `Evidence update failed: ${error.message}`;
        console.error(notice.textContent);
    };
    const openGuidedAction = (action, noteId, {card, row}) => floatingWindow.open({
        use: "Evidence collection",
        title: card.title,
        returnFocus: () => [...document.querySelectorAll("[data-artifact-action]")].find(control =>
            control.dataset.artifactAction === action.id && control.dataset.actionNoteId === noteId),
        mount: (root, session) => globalThis.ObsHtmlGuidedCard.mountForm(root, session, {
            card,
            accept: action.accept,
            render: (container, field) => appendTableCell(container, row.cells[field], row.values[field]),
            value: field => row.values[field],
            submit: async ({file, values, signal}) => {
                if (!records.some(record => canonicalNoteId(record) === noteId)) {
                    throw new Error(`Canonical action note no longer exists: ${noteId}`);
                }
                const applied = await action.handle({
                    noteId, file, values, signal, artifact: globalThis.obsArtifact,
                });
                if (applied === false) throw new Error("The action did not apply the file.");
            },
        }),
    });
    const dispatchApplicationAction = (actionId, noteId, guided) => {
        const action = registeredApplication?.actions.get(actionId);
        if (!action) throw new Error(`Trusted application action is not registered: ${actionId}`);
        if (!records.some(record => canonicalNoteId(record) === noteId)) {
            throw new Error(`Canonical action note no longer exists: ${noteId}`);
        }
        if (guided?.card) return openGuidedAction(action, noteId, guided);
        const picker = document.createElement("input");
        picker.type = "file";
        picker.accept = action.accept;
        picker.hidden = true;
        picker.dataset.transientView = "";
        document.body.append(picker);
        const cleanup = () => picker.remove();
        picker.addEventListener("cancel", cleanup, {once: true});
        picker.addEventListener("change", () => {
            const file = picker.files?.[0];
            cleanup();
            if (!file) return;
            const operation = Promise.resolve().then(() =>
                action.handle({noteId, file, artifact: globalThis.obsArtifact}));
            operation.catch(showApplicationError);
        }, {once: true});
        try {
            picker.click();
        } catch (error) {
            cleanup();
            throw error;
        }
    };
    document.addEventListener("click", event => {
        const control = event.target.closest?.("[data-artifact-action]");
        if (!control) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        try {
            dispatchApplicationAction(control.dataset.artifactAction, control.dataset.actionNoteId,
                tableIconCards.get(control));
        } catch (error) {
            showApplicationError(error);
        }
    }, true);
    const commitProperty = (slug, field, value) => {
        const note = notesBySlug.get(slug);
        const definition = note?.editableProperties?.[field];
        if (!definition || !Object.hasOwn(note.frontmatter, field) ||
            typeof note.frontmatter[field] !== "string" || typeof value !== "string" ||
            value.length > definition.maxLength) {
            throw new Error("This property is not an enabled text editor or its text exceeds the declared limit.");
        }
        const branch = value.trim() ? "nonblank" : "blank";
        return commitCanonicalProjection([{
            slug,
            fields: {...(definition.projection?.[branch] || {}), [field]: value},
        }]);
    };

    const readerState = () => ({
        views: Object.fromEntries(viewSelections),
        filterExpression: activeFilter.empty ? "" : activeFilter.source,
        tables: Object.fromEntries([...tableStates]
            .filter(([, state]) => state.presentation !== undefined || state.view)
            .map(([key, state]) => [key, state.view
                ? {...state.presentation, view: state.definition.views[state.view].name}
                : state.presentation])),
    });
    const staticViews = new Map();
    globalThis.obsArtifact = {
        applyLinkPolicy,
        whenChapterReady: () => navigationReady,
        viewSelection: key => structuredClone(viewSelections.get(key)),
        setViewSelection(key, selected, choices) {
            if (typeof key !== "string" || !key || !Array.isArray(selected) ||
                !Array.isArray(choices) || !choices.every(value => typeof value === "string") ||
                !selected.every(value => choices.includes(value)) ||
                new Set(selected).size !== selected.length) {
                throw new Error("View selections must be unique known choices.");
            }
            if (selected.length || Object.hasOwn(artifactData.readerState?.views || {}, key)) {
                viewSelections.set(key, structuredClone(selected));
            } else {
                viewSelections.delete(key);
            }
            document.dispatchEvent(new CustomEvent("obs-reader-state-change"));
        },
        ping,
        records,
        isDocument,
        selectable,
        documentRecords: () => records.filter(isDocument),
        searchHits,
        filterRecords,
        facetFields,
        queryProfile,
        filterSummary,
        recordValues,
        filterPresets: artifactData.filterPresets || [],
        facetDistinctRatio: artifactData.facetDistinctRatio ?? 0.5,
        initialFilterExpression: artifactData.readerState?.filterExpression ?? "",
        setFilter,
        commitProperty,
        commitCanonicalProjection,
        registerApplication,
        validateApplicationRuntime,
        dispatchApplicationAction,
        trustedExtension,
        openFloatingWindow: options => floatingWindow.open(options),
        showApplicationError,
        get revision() { return canonicalRevision; },
        canonicalNotes: () => structuredClone(notes),
        stageCanonicalTransaction: candidate => canonicalTransactions.stage(candidate),
        contentBaseline,
        adoptContentBaseline,
        renderSafeCanonicalContent,
        embeddedAssets: () => structuredClone(embeddedAssets),
        sourceArchiveInfo,
        downloadSourceArchive,
        readerState,
        serializeModel: () => JSON.stringify({
            ...artifactData,
            readerState: readerState(),
        }).replace(
            /[<>&\u2028\u2029]/g,
            character => `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`,
        ),
        matchesFilter: (record) => activeFilter.match(record),
        openBar,
        closeBar,
        isBarOpen,
        activateChapter,
        activateSearchResult,
        renderStatic: (slug, root, respectFilter = true, firstTableFilter = "") => {
            const record = recordsBySlug.get(slug);
            const signature = JSON.stringify([canonicalRevision, record.html,
                respectFilter ? [filterRevision, activeFilter.source] : "", firstTableFilter,
                [...viewSelections],
                (record.tables || []).map(table => tableStates.get(table.key)),
            ]);
            const cached = staticViews.get(slug);
            if (cached?.signature === signature) {
                root.replaceChildren(...[...cached.content.childNodes].map(node => node.cloneNode(true)));
                return;
            }
            replaceTrustedHtml(root, record.html);
            renderChapterTables(record, root, true, respectFilter, firstTableFilter);
            globalThis.obsFigures?.projectSankeys(root);
            staticViews.set(slug, {signature, content: root.cloneNode(true)});
        },
        exportChapters: () => visibleIndices.map((index) => chapterRecords[index])
            .filter((record) => !record.generated),
        navigationChapters: () => visibleIndices.map((index) => chapterRecords[index])
            .filter(record => record.generated !== "home"),
    };
})();
