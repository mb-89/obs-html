(() => {
    // The filter fields of a filter bar or a data table's facet panel: one pill per field, whose
    // popover lists the field's values with their counts (artifact-ui.md, Filter bar).
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

    globalThis.obsFilterFields = {render: renderFilterFields};
})();
