((root, factory) => {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    root.ObsHtmlHoverCard = api;
})(globalThis, () => {
    "use strict";

    // Overlay tier 1 (artifact-ui.md "Overlays"): the one in-page card every hover in the artifact uses.
    // Features register a trigger selector and a resolver; this owner places, fits, renders and dismisses.
    const create = ({window, delayMilliseconds}) => {
        const document = window.document;
        const card = document.createElement("aside");
        card.id = "hover-card";
        card.className = "hover-card";
        card.dataset.transientView = "";
        card.setAttribute("role", "region");
        card.setAttribute("aria-label", "Hover card");
        card.setAttribute("popover", "manual");
        card.hidden = true;
        document.body.append(card);
        const registrations = [];
        let trigger = null;
        let pending = null;
        let timer;

        const register = (selector, resolve) => registrations.push({selector, resolve});
        const resolveAt = (target) => {
            for (let node = target?.nodeType === 1 ? target : target?.parentElement; node; node = node.parentElement) {
                if (card.contains(node)) return null;
                for (const {selector, resolve} of registrations) {
                    if (!node.matches(selector)) continue;
                    const content = resolve(node);
                    if (content) return {trigger: node, content};
                }
            }
            return null;
        };
        // While a card waits for its delay the card carries data-pending, so a reader of the page
        // can tell a hover that will show a card from one that shows none without waiting.
        const cancel = () => {
            clearTimeout(timer);
            pending = null;
            delete card.dataset.pending;
        };
        const describe = (element, on) => {
            const ids = (element.getAttribute("aria-describedby") || "").split(/\s+/)
                .filter(id => id && id !== card.id);
            if (on) ids.push(card.id);
            if (ids.length) element.setAttribute("aria-describedby", ids.join(" "));
            else element.removeAttribute("aria-describedby");
        };
        const hide = () => {
            cancel();
            if (trigger) describe(trigger, false);
            trigger = null;
            if (!card.hidden && card.hidePopover) card.hidePopover();
            card.hidden = true;
            card.replaceChildren();
        };
        const visibleArea = (element) => {
            let area = {top: 0, left: 0, bottom: window.innerHeight, right: window.innerWidth};
            for (let node = element.parentElement; node && node !== document.body; node = node.parentElement) {
                const style = getComputedStyle(node);
                if (!/(auto|scroll|hidden)/.test(`${style.overflowX} ${style.overflowY}`)) continue;
                const box = node.getBoundingClientRect();
                area = {top: Math.max(area.top, box.top), left: Math.max(area.left, box.left),
                    bottom: Math.min(area.bottom, box.bottom), right: Math.min(area.right, box.right)};
            }
            return area;
        };
        const inView = (element) => {
            const box = element.getBoundingClientRect();
            const area = visibleArea(element);
            return box.bottom > area.top && box.top < area.bottom && box.right > area.left && box.left < area.right;
        };
        const place = () => {
            const anchor = trigger.getBoundingClientRect();
            const box = card.getBoundingClientRect();
            const gap = parseFloat(getComputedStyle(card).getPropertyValue("--hover-card-gap")) || 0;
            const left = Math.max(gap, Math.min(anchor.left, window.innerWidth - box.width - gap));
            const below = anchor.bottom + gap;
            const top = below + box.height <= window.innerHeight - gap
                ? below : Math.max(gap, anchor.top - box.height - gap);
            card.style.left = `${left}px`;
            card.style.top = `${top}px`;
        };
        const show = (element) => {
            cancel();
            const resolved = element?.isConnected ? resolveAt(element) : null;
            if (!resolved || resolved.trigger !== element) return false;
            if (trigger && trigger !== element) describe(trigger, false);
            trigger = element;
            card.replaceChildren();
            card.setAttribute("aria-label", resolved.content.label || "Hover card");
            resolved.content.render(card);
            if (card.hidden) {
                card.hidden = false;
                if (card.showPopover) card.showPopover();
            }
            place();
            describe(trigger, true);
            return true;
        };
        const schedule = (event) => {
            if (event.pointerType === "touch" || card.contains(event.target)) {
                if (card.contains(event.target)) cancel();
                return;
            }
            const resolved = resolveAt(event.target);
            if (!resolved) {
                cancel();
                return;
            }
            if (resolved.trigger === trigger || resolved.trigger === pending) return;
            cancel();
            pending = resolved.trigger;
            card.dataset.pending = "";
            timer = setTimeout(() => show(resolved.trigger), delayMilliseconds);
        };
        document.addEventListener("pointerover", schedule);
        document.addEventListener("focusin", schedule);
        // Passing over a trigger without resting on it shows nothing; a shown card stays.
        document.addEventListener("pointerout", (event) => {
            if (pending && !pending.contains(event.relatedTarget)) cancel();
        });
        document.addEventListener("click", (event) => {
            if (card.contains(event.target)) return;
            const resolved = resolveAt(event.target);
            if (resolved?.content.showOnClick) show(resolved.trigger);
            else hide();
        }, true);
        document.addEventListener("keydown", (event) => {
            if (event.defaultPrevented) return;
            if (event.key === "ArrowDown" && !card.hidden && document.activeElement === trigger) {
                const link = card.querySelector("a[href]");
                if (link) {
                    event.preventDefault();
                    link.focus();
                }
            }
            if (event.key === "Escape" && (!card.hidden || pending)) {
                const returnFocus = card.contains(document.activeElement) ? trigger : null;
                hide();
                returnFocus?.focus();
            }
        });
        document.addEventListener("scroll", (event) => {
            if (card.hidden || card.contains(event.target)) return;
            if (!trigger.isConnected || !inView(trigger)) hide();
            else place();
        }, true);
        window.addEventListener("resize", hide);
        window.addEventListener("beforeprint", hide);
        new MutationObserver(() => {
            if (trigger && !trigger.isConnected) hide();
        }).observe(document.body, {childList: true, subtree: true});

        // Declarative explanations: any element may carry its hover text instead of a native tooltip.
        register("[data-hover-help]", (element) => {
            const text = element.dataset.hoverHelp.trim();
            return text && {
                label: element.getAttribute("aria-label") || "Help",
                render: (target) => {
                    const paragraph = document.createElement("p");
                    paragraph.textContent = text;
                    target.append(paragraph);
                },
            };
        });

        return Object.freeze({
            element: card, register, show, hide,
            get trigger() { return trigger; },
        });
    };

    return Object.freeze({create});
});
