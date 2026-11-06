/* The options menu of tables and figures: one component, so both have the same control,
   placement and behaviour (artifact-ui.md, One figure frame; generic-tables.md). Its toggle is the
   options icon button; its panel is a popover placed below the toggle, right-aligned within the
   viewport, and closes on a second click, Escape or a pointer outside both. What the panel's
   controls change is the caller's view state; the menu itself keeps nothing. */
globalThis.obsOptionsMenu = function optionsMenu({label, toggleClass, panelClass}) {
    const toggle = document.createElement("button");
    toggle.className = `icon-button options-menu-toggle ${toggleClass}`;
    toggle.type = "button";
    toggle.setAttribute("aria-label", label);
    toggle.setAttribute("aria-expanded", "false");
    toggle.title = label;
    globalThis.obsAssets.replace(toggle, "options");
    const panel = document.createElement("div");
    panel.className = `options-menu ${panelClass}`;
    panel.setAttribute("popover", "manual");
    panel.setAttribute("aria-label", label);
    panel.hidden = true;
    const close = () => {
        if (!panel.hidden) panel.hidePopover();
        panel.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
    };
    toggle.addEventListener("click", () => {
        if (!panel.hidden) {
            close();
            return;
        }
        panel.hidden = false;
        panel.showPopover();
        const anchor = toggle.getBoundingClientRect();
        const bounds = panel.getBoundingClientRect();
        panel.style.left = `${Math.max(8, Math.min(
            anchor.right - bounds.width, window.innerWidth - bounds.width - 8,
        ))}px`;
        panel.style.top = `${anchor.bottom + 4}px`;
        panel.style.setProperty(
            "--options-menu-available-height",
            `${Math.max(0, window.innerHeight - anchor.bottom - 12)}px`,
        );
        toggle.setAttribute("aria-expanded", "true");
    });
    const outside = (event) => {
        if (!toggle.isConnected && !panel.isConnected) {
            document.removeEventListener("pointerdown", outside);
            document.removeEventListener("keydown", escape);
            return;
        }
        if (!toggle.contains(event.target) && !panel.contains(event.target)) close();
    };
    const escape = (event) => {
        if (event.key === "Escape") close();
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return {toggle, panel, close};
};
