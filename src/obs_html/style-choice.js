/* The Theme select (features.py, style-choice; artifact-ui.md, Styling): on a page that carries local
   themes, the Settings bar offers Default and each theme below Appearance. Choosing one sets the
   root's data-style at once, then lays out again what the page measures, as a resize does. The
   select is a transient view and nothing stores the choice, so every opening starts in the start
   theme (reading.style). */
globalThis.obsStyleChoice = (() => {
    /* The pure core: the page's themes (reading.styles, Default first) and the chosen one in, the
       root's attributes and the select's options out. */
    const choice = (styles, chosen) => {
        if (!styles.includes(chosen)) {
            throw new Error(`style-choice.js: the theme "${chosen}" is not one of the page's themes ` +
                `(${styles.join(", ")}); see artifact-ui.md, Styling`);
        }
        return {
            root: {"data-style": chosen},
            options: styles.map(value => ({value, label: value === "default" ? "Default" : value})),
        };
    };
    return {choice};
})();

(() => {
    if (typeof document === "undefined") return;  // Read without a page (test/style-choice.test.js): the core above only.
    const {styles, style} = JSON.parse(document.querySelector("[data-artifact-data]").textContent).reading;
    const root = document.documentElement;
    const label = document.createElement("label");
    label.className = "settings-appearance settings-style";
    label.dataset.transientView = "";
    const select = document.createElement("select");
    select.dataset.styleSelect = "";
    select.setAttribute("aria-label", "Theme");
    const apply = (chosen) => {
        const view = globalThis.obsStyleChoice.choice(styles, chosen);
        Object.entries(view.root).forEach(([name, value]) => root.setAttribute(name, value));
        select.value = chosen;
    };
    // The root already carries the start theme from the startup line (render.py, _shell).
    select.append(...globalThis.obsStyleChoice.choice(styles, style).options
        .map(({value, label: text}) => new Option(text, value)));
    select.value = style;
    // The control span of the Appearance select (bars/settings.py), so base.css lays both out alike.
    const control = document.createElement("span");
    control.className = "settings-appearance-control";
    control.append(select);
    label.append("Theme", control);
    document.querySelector("[data-theme-select]").closest("label").after(label);
    select.addEventListener("change", () => {
        apply(select.value);
        window.dispatchEvent(new Event("resize"));
    });
})();
