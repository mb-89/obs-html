((root, factory) => {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    root.ObsHtmlGuidedCard = api;
})(globalThis, () => {
    "use strict";

    const focusable = "a[href], button:not(:disabled), input:not(:disabled):not([hidden]), textarea:not(:disabled)";

    // Overlay tier 2 (artifact-ui.md "Floating window"): one window per artifact, shared by all its uses.
    // Each shown content is a history entry; Back/Forward move through them; closing discards them all.
    // The window is Document Picture-in-Picture when permitted, else an owned helper, else inline.
    const createHost = ({window, size, applyLinkPolicy}) => {
        const document = window.document;
        const element = (tag, className, text) => {
            const node = document.createElement(tag);
            if (className) node.className = className;
            if (text) node.textContent = text;
            return node;
        };
        const button = (text, label, attribute) => {
            const node = element("button", "", text);
            node.type = "button";
            node.dataset[attribute] = "";
            node.setAttribute("aria-label", label);
            return node;
        };
        const card = element("section", "guided-card");
        card.dataset.guidedCard = "";
        card.dataset.transientView = "";
        const header = element("div", "guided-card-header");
        const back = button("←", "Back", "guidedCardBack");
        const forward = button("→", "Forward", "guidedCardForward");
        const use = element("span", "guided-card-use");
        use.dataset.guidedCardUse = "";
        const close = button("Close", "Close window", "guidedCardClose");
        header.append(back, forward, use, close);
        const heading = element("h2", "guided-card-title");
        const message = element("p", "guided-card-message");
        message.dataset.guidedCardMessage = "";
        message.setAttribute("role", "status");
        const retry = element("button", "", "Open floating window");
        retry.type = "button";
        retry.dataset.guidedCardRetry = "";
        retry.hidden = true;
        const slot = element("div", "guided-card-slot");
        const frame = [header, heading, message, retry, slot];

        const entries = [];
        let index = -1;
        let owned = null;
        let mode = "inline";
        let windowCleanups = [];
        let requesting = false;
        const isOpen = () => requesting || card.isConnected || Boolean(owned && !owned.closed);
        const focusFirst = root => root.querySelector(focusable)?.focus({preventScroll: true});
        const render = () => {
            const entry = entries[index];
            use.textContent = entry.use;
            heading.textContent = entry.title;
            card.setAttribute("aria-label", `${entry.use}: ${entry.title}`);
            back.disabled = index <= 0;
            forward.disabled = index >= entries.length - 1;
            slot.replaceChildren(entry.content);
            if (owned && !owned.closed) owned.document.title = entry.title;
        };
        const closeWindow = () => {
            const last = entries[index];
            requesting = false;
            entries.splice(0).forEach(entry => entry.dispose());
            index = -1;
            windowCleanups.splice(0).forEach(cleanup => cleanup());
            card.remove();
            card.append(...frame);
            slot.replaceChildren();
            message.textContent = "";
            retry.hidden = true;
            if (owned && !owned.closed) owned.close();
            owned = null;
            mode = "inline";
            // A committed action may re-render its trigger; return focus to its replacement.
            globalThis.requestAnimationFrame(() => {
                const target = last?.trigger?.isConnected ? last.trigger : last?.returnFocus?.();
                if (document.hasFocus?.() && target?.isConnected &&
                        (!document.activeElement || document.activeElement === document.body)) {
                    target.focus({preventScroll: true});
                }
            });
        };
        // A finished entry leaves the history; the window closes when nothing is left to show.
        const finish = (entry) => {
            const position = entries.indexOf(entry);
            if (position < 0) return entry.dispose();
            if (entries.length === 1) return closeWindow();
            entries.splice(position, 1);
            entry.dispose();
            if (index > position || (index === position && position > 0)) index -= 1;
            render();
            focusFirst(entries[index].content);
        };
        const step = (delta) => {
            if (!entries[index + delta]) return;
            index += delta;
            render();
            focusFirst(entries[index].content);
        };
        back.addEventListener("click", () => step(-1));
        forward.addEventListener("click", () => step(1));
        close.addEventListener("click", closeWindow);
        window.addEventListener("pagehide", () => { if (isOpen()) closeWindow(); });

        const showInline = reason => {
            requesting = false;
            mode = "inline";
            card.append(...frame);
            if (!card.isConnected) document.body.append(card);
            message.textContent = reason;
            retry.hidden = false;
        };
        const attach = (child, kind) => {
            requesting = false;
            if (!entries.length) {
                child.close();
                return;
            }
            owned = child;
            mode = kind;
            const childDocument = child.document;
            childDocument.title = entries[index].title;
            document.querySelectorAll("head style").forEach(style =>
                childDocument.head.append(childDocument.importNode(style, true)));
            const syncTheme = () => {
                childDocument.documentElement.dataset.theme = document.documentElement.dataset.theme;
            };
            syncTheme();
            const theme = new MutationObserver(syncTheme);
            theme.observe(document.documentElement, {attributes: true, attributeFilter: ["data-theme"]});
            windowCleanups.push(() => theme.disconnect());
            childDocument.body.className = "guided-card-window";
            message.textContent = "";
            retry.hidden = true;
            childDocument.body.replaceChildren(header, heading, slot);
            // Dropping a file outside the drop target must not navigate our helper away.
            ["dragover", "drop"].forEach(type =>
                childDocument.addEventListener(type, event => event.preventDefault()));
            child.addEventListener("pagehide", () => { if (owned === child) closeWindow(); }, {once: true});
            // The window now holds the only card; an inline fallback shown before a retry goes away.
            card.remove();
            focusFirst(slot);
        };
        const openHelper = () => {
            if (!entries.length || (owned && !owned.closed)) return;
            let child = null;
            try {
                child = window.open("", "_blank",
                    `popup,width=${size.widthPixels},height=${size.heightPixels}`);
            } catch {
                child = null;
            }
            if (child) {
                try {
                    attach(child, "helper");
                    return;
                } catch {
                    child.close();
                    owned = null;
                }
            }
            // Where the canary could not decide, a window that did not open is the observed refusal.
            const reason = globalThis.obsCapabilities?.fail("popups", "window.open returned no window");
            showInline("A separate window could not be opened here, so the card is shown in this page." +
                (reason ? ` ${reason}` : ""));
            focusFirst(slot);
        };
        // Must run synchronously inside the reader's activation: both PiP and popups require it.
        const openWindow = () => {
            const pip = window.documentPictureInPicture;
            if (window !== window.top || typeof pip?.requestWindow !== "function") {
                openHelper();
                return;
            }
            let request;
            requesting = true;
            try {
                request = Promise.resolve(pip.requestWindow({
                    width: size.widthPixels, height: size.heightPixels,
                }));
            } catch (error) {
                request = Promise.reject(error);
            }
            request.then(child => {
                try {
                    attach(child, "pip");
                } catch {
                    child.close();
                    owned = null;
                    openHelper();
                }
            }, () => {
                requesting = false;
                openHelper();
            });
        };
        retry.addEventListener("click", openWindow);

        // New content replaces the shown content in place; an open window is never closed and reopened.
        const open = ({use: purpose, title, mount, returnFocus}) => {
            if (typeof purpose !== "string" || !purpose.trim() || typeof title !== "string" || !title.trim() ||
                    typeof mount !== "function") {
                throw new TypeError("The floating window requires a use, a title and a trusted mount function.");
            }
            const controller = new AbortController();
            const content = element("div", "guided-card-content");
            content.dataset.guidedCardContent = "";
            let disposed = false;
            const entry = {
                use: purpose, title, content, returnFocus, trigger: document.activeElement,
                dispose() {
                    if (disposed) return;
                    disposed = true;
                    controller.abort();
                    content.remove();
                },
            };
            const session = Object.freeze({
                get active() { return !disposed; },
                get mode() { return mode; },
                get window() { return owned; },
                signal: controller.signal,
                close: () => finish(entry),
            });
            entry.session = session;
            try {
                mount(content, session);
                applyLinkPolicy(content);
            } catch (error) {
                entry.dispose();
                throw error;
            }
            // Like browser history, showing new content after going back drops the forward entries.
            entries.splice(index + 1).forEach(dropped => dropped.dispose());
            entries.push(entry);
            index = entries.length - 1;
            const shown = isOpen();
            render();
            if (shown) focusFirst(content);
            else openWindow();
            return session;
        };
        return Object.freeze({
            open, close: () => { if (isOpen()) closeWindow(); },
            get current() { return entries[index]?.session ?? null; },
        });
    };

    // Generic declared card body: source link, subject, rich guidance, staged file, required text, submit.
    const mountForm = (root, session, {card, accept, render, value, submit}) => {
        const document = root.ownerDocument;
        const element = (tag, className, text) => {
            const node = document.createElement(tag);
            if (className) node.className = className;
            if (text) node.textContent = text;
            return node;
        };
        // The source link comes first: the reader opens it before following the instructions.
        if (card.link) {
            const source = element("p", "guided-card-source");
            source.dataset.guidedCardSource = "";
            render(source, card.link);
            const links = [...source.querySelectorAll("a[href]")];
            links.forEach(link => {
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                const hint = element("span", "guided-card-hint", " (opens in a new tab)");
                link.append(hint);
            });
            if (links.length) root.append(source);
        }
        if (card.subject) {
            const subject = element("p", "guided-card-subject");
            subject.dataset.guidedCardSubject = "";
            render(subject, card.subject);
            if (subject.textContent.trim()) root.append(subject);
        }
        for (const field of card.content || []) {
            const block = element("div", "guided-card-instructions rich-metadata");
            block.dataset.guidedCardInstructions = field;
            render(block, field);
            if (block.textContent.trim()) root.append(block);
        }
        const form = element("form", "guided-card-form");
        form.noValidate = true;
        const idBase = `guided-card-${Math.random().toString(36).slice(2)}`;
        const picker = element("input");
        picker.type = "file";
        picker.accept = accept;
        picker.hidden = true;
        picker.dataset.guidedCardFile = "";
        const drop = element("div", "guided-card-drop");
        drop.dataset.guidedCardDrop = "";
        const dropText = element("p", "", "Drop the file here, or");
        const choose = element("button", "", "Choose file…");
        choose.type = "button";
        choose.dataset.guidedCardChoose = "";
        choose.addEventListener("click", () => picker.click());
        const staged = element("p", "guided-card-staged", "No file chosen yet.");
        staged.id = `${idBase}-staged`;
        staged.dataset.guidedCardStaged = "";
        staged.setAttribute("aria-live", "polite");
        choose.setAttribute("aria-describedby", staged.id);
        drop.append(dropText, choose, staged, picker);
        form.append(drop);
        let text = null;
        if (card.input) {
            const label = element("label", "", card.input.label);
            label.htmlFor = `${idBase}-text`;
            text = element("textarea");
            text.id = label.htmlFor;
            text.rows = 3;
            text.required = true;
            text.setAttribute("aria-required", "true");
            text.dataset.guidedCardText = card.input.property;
            const prefill = value(card.input.property);
            text.value = typeof prefill === "string" ? prefill : "";
            form.append(label, text);
        }
        const error = element("p", "guided-card-error");
        error.dataset.guidedCardError = "";
        error.setAttribute("role", "alert");
        const actions = element("div", "guided-card-actions");
        const apply = element("button", "guided-card-submit", card.submit);
        apply.type = "submit";
        apply.dataset.guidedCardSubmit = "";
        const cancel = element("button", "", "Cancel");
        cancel.type = "button";
        cancel.dataset.guidedCardCancel = "";
        cancel.addEventListener("click", session.close);
        actions.append(apply, cancel);
        form.append(error, actions);
        root.append(form);

        let file = null;
        let busy = false;
        const stage = candidate => {
            if (busy || !candidate) return;
            file = candidate;
            staged.textContent = `Staged: ${candidate.name} (${candidate.size.toLocaleString()} bytes). It is applied only with ${card.submit}.`;
            drop.dataset.staged = "";
            error.textContent = "";
        };
        picker.addEventListener("change", () => stage(picker.files?.[0]));
        root.addEventListener("dragover", event => {
            if (![...(event.dataTransfer?.types || [])].includes("Files")) return;
            event.preventDefault();
            drop.dataset.dragging = "";
        });
        root.addEventListener("dragleave", event => {
            if (!root.contains(event.relatedTarget)) delete drop.dataset.dragging;
        });
        root.addEventListener("drop", event => {
            event.preventDefault();
            delete drop.dataset.dragging;
            stage(event.dataTransfer?.files?.[0]);
        });
        form.addEventListener("submit", async event => {
            event.preventDefault();
            if (busy || !session.active) return;
            const entered = text ? text.value.trim() : "";
            if (!file) {
                error.textContent = "Choose or drop a file first.";
                choose.focus();
                return;
            }
            if (text && !entered) {
                error.textContent = `${card.input.label} is required.`;
                text.focus();
                return;
            }
            busy = true;
            form.setAttribute("aria-busy", "true");
            [choose, apply, ...(text ? [text] : [])].forEach(control => { control.disabled = true; });
            error.textContent = "";
            try {
                await submit({file, values: text ? {[card.input.property]: entered} : {}, signal: session.signal});
                session.close();
            } catch (failure) {
                if (!session.active) return;
                error.textContent = `Not applied; the previous state is unchanged. ${failure?.message || failure}`;
                busy = false;
                form.removeAttribute("aria-busy");
                [choose, apply, ...(text ? [text] : [])].forEach(control => { control.disabled = false; });
                apply.focus();
            }
        });
    };

    return Object.freeze({createHost, mountForm});
});
