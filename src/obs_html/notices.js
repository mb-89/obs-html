// Notice center: every notice the artifact raises is one entry here, and no notice draws its own banner.
// The top of the page shows at most one icon per severity, with a count pill; an icon opens its list,
// an entry expands its details. Adding a kind of notice is one post() call from its owner.
(() => {
    const severities = [
        {key: "error", label: "Errors", icon: "notice.error"},
        {key: "warning", label: "Warnings", icon: "notice.warning"},
        {key: "information", label: "Information", icon: "notice.information"},
    ];
    const entries = new Map();
    const area = document.createElement("div");
    area.className = "header-notices";
    area.dataset.headerNotices = "";
    area.dataset.transientView = "";
    area.setAttribute("role", "region");
    area.setAttribute("aria-label", "Notices");
    const groups = new Map(severities.map((severity) => {
        const group = document.createElement("div");
        group.className = "notice-group";
        group.dataset.noticeGroup = severity.key;
        group.hidden = true;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "notice-icon";
        button.dataset.noticeIcon = severity.key;
        button.setAttribute("aria-expanded", "false");
        button.setAttribute("aria-controls", `obs-notice-list-${severity.key}`);
        const pill = document.createElement("span");
        pill.className = "notice-pill";
        pill.dataset.noticeCount = "";
        pill.setAttribute("aria-hidden", "true");
        button.append(globalThis.obsAssets.create(severity.icon), pill);
        const list = document.createElement("ul");
        list.className = "notice-list";
        list.id = `obs-notice-list-${severity.key}`;
        list.dataset.noticeList = severity.key;
        list.setAttribute("aria-label", severity.label);
        list.hidden = true;
        button.addEventListener("click", () => toggle(severity.key));
        group.append(button, list);
        area.append(group);
        return [severity.key, {severity, group, button, pill, list}];
    }));

    const changed = () => {
        groups.forEach(({severity, group, button, pill, list}) => {
            const count = list.children.length;
            group.hidden = count === 0;
            if (!count) close(severity.key);
            pill.textContent = String(count);
            button.setAttribute("aria-label", `${severity.label}: ${count} ${count === 1 ? "notice" : "notices"}`);
            button.title = button.getAttribute("aria-label");
        });
        document.dispatchEvent(new CustomEvent("obs-notices-change"));
    };
    const open = (key) => {
        groups.forEach((_, other) => { if (other !== key) close(other); });
        const {button, list} = groups.get(key);
        list.hidden = false;
        button.setAttribute("aria-expanded", "true");
    };
    const close = (key) => {
        const {button, list} = groups.get(key);
        list.hidden = true;
        button.setAttribute("aria-expanded", "false");
    };
    const toggle = (key) => (groups.get(key).list.hidden ? open(key) : close(key));
    const expand = (item, expanded) => {
        item.querySelector("[data-notice-title]").setAttribute("aria-expanded", String(expanded));
        item.querySelector("[data-notice-details]").hidden = !expanded;
    };

    // Shows or updates one entry: details is text, a node, or a list of either.
    const post = ({id, severity, title, details = []}) => {
        if (!groups.has(severity)) {
            throw new Error(`obsNotices.post(${id}): unknown severity "${severity}"; ` +
                `use one of ${severities.map(({key}) => key).join(", ")}.`);
        }
        let item = entries.get(id);
        if (item && item.dataset.noticeSeverity !== severity) {
            item.remove();
            item = undefined;
        }
        if (!item) {
            item = document.createElement("li");
            item.className = "notice-entry";
            item.dataset.notice = id;
            const heading = document.createElement("button");
            heading.type = "button";
            heading.className = "notice-entry-title";
            heading.dataset.noticeTitle = "";
            heading.setAttribute("aria-controls", `obs-notice-${id}`);
            const body = document.createElement("div");
            body.className = "notice-details";
            body.id = `obs-notice-${id}`;
            body.dataset.noticeDetails = "";
            heading.addEventListener("click", () => expand(item, body.hidden));
            item.append(heading, body);
            expand(item, false);
            entries.set(id, item);
        }
        item.dataset.noticeSeverity = severity;
        item.querySelector("[data-notice-title]").textContent = title;
        item.querySelector("[data-notice-details]").replaceChildren(
            ...[details].flat().map((part) => typeof part === "string" ? paragraph(part) : part));
        const list = groups.get(severity).list;
        if (item.parentElement !== list) list.append(item);
        changed();
    };
    const paragraph = (text) => {
        const element = document.createElement("p");
        element.textContent = text;
        return element;
    };
    const remove = (id) => {
        const item = entries.get(id);
        if (!item) return;
        entries.delete(id);
        item.remove();
        changed();
    };
    // Opens the entry's list and expands it, for a control whose reason the entry carries.
    const reveal = (id) => {
        const item = entries.get(id);
        if (!item) return;
        open(item.dataset.noticeSeverity);
        expand(item, true);
    };

    area.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        const openGroup = [...groups.values()].find(({list}) => !list.hidden);
        if (!openGroup) return;
        event.preventDefault();
        close(openGroup.severity.key);
        openGroup.button.focus();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape" || area.contains(event.target)) return;
        groups.forEach((_, key) => close(key));
    });

    // The icons sit in the top band, directly left of the menu; a figure overlay takes them along.
    const band = document.querySelector("[data-top-band-end]");
    const dock = () => band.prepend(area);
    document.addEventListener("obs-figure-overlay", ({detail}) => {
        if (detail.open) detail.dialog.append(area);
        else dock();
    });
    dock();

    globalThis.obsNotices = Object.freeze({
        post,
        remove,
        reveal,
        has: (id) => entries.has(id),
        severities: Object.freeze(severities.map(({key}) => key)),
    });
})();
