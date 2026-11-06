(() => {
    const input = document.querySelector("[data-filter-input]");
    const status = document.querySelector("[data-filter-status]");
    const presetSection = document.querySelector("[data-filter-presets-section]");
    const presetList = document.querySelector("[data-filter-presets]");
    const selectionSection = document.querySelector("[data-filter-selections-section]");
    const selectionList = document.querySelector("[data-filter-selections]");
    const fieldList = document.querySelector("[data-filter-fields]");
    const { filterPresets, facetDistinctRatio, queryProfile } = globalThis.obsArtifact;
    let selectionBase = "";
    const selections = new Map();

    const syncPresets = () => {
        presetList.querySelectorAll("[data-filter-preset]").forEach((button) => {
            button.setAttribute("aria-pressed", String(button.dataset.expression === input.value.trim()));
        });
    };

    const syncStatus = () => {
        if (input.getAttribute("aria-invalid") === "true") return;
        const summary = globalThis.obsArtifact.filterSummary();
        status.textContent = summary.empty
            ? queryProfile.scope === "records" ? "All records." : "All chapters."
            : queryProfile.scope === "records"
                ? `${summary.records}/${summary.totalRecords} records.`
                : `${summary.chapters} chapter${summary.chapters === 1 ? "" : "s"}.`;
    };

    const apply = () => {
        let query;
        try {
            query = globalThis.obsQuery.compile(input.value);
        } catch (error) {
            input.setAttribute("aria-invalid", "true");
            status.textContent = error.message;
            return;
        }
        input.removeAttribute("aria-invalid");
        globalThis.obsArtifact.setFilter(query);
        syncStatus();
        syncPresets();
        document.dispatchEvent(new CustomEvent("obs-filter-change", {detail: {query}}));
    };

    const setExpression = (expression) => {
        input.value = expression;
        selectionBase = "";
        selections.clear();
        fieldList.querySelectorAll(".filter-value").forEach((button) => {
            button.setAttribute("aria-checked", "false");
        });
        selectionList.replaceChildren();
        selectionSection.hidden = true;
        apply();
    };

    const selectExpression = (expression) => {
        setExpression(expression);
        globalThis.obsArtifact.openBar("filter");
    };
    const exactClause = globalThis.obsQuery.exactClause;

    const syncSelections = () => {
        fieldList.querySelectorAll(".filter-value").forEach((candidate) => {
            const candidateField = candidate.closest(".filter-field").dataset.field;
            candidate.setAttribute(
                "aria-checked",
                String((selections.get(candidateField) || []).includes(candidate.dataset.filterValue)),
            );
        });
        selectionList.replaceChildren();
        selections.forEach((values, field) => {
            values.forEach((value) => {
                const button = document.createElement("button");
                button.className = "filter-pill filter-selected";
                button.type = "button";
                button.title = `Remove ${field}: ${value}`;
                button.setAttribute("aria-label", button.title);
                button.textContent = `${field}: ${value}`;
                globalThis.obsAssets.append(button, "close");
                button.addEventListener("click", () => toggleSelection(field, value));
                selectionList.append(button);
            });
        });
        selectionSection.hidden = !selections.size;
    };

    const toggleSelection = (field, value) => {
        if (!selections.size) selectionBase = globalThis.obsArtifact.filterSummary().expression.trim();
        const selectedValues = selections.get(field) || [];
        const index = selectedValues.indexOf(value);
        if (index >= 0) selectedValues.splice(index, 1);
        else selectedValues.push(value);
        if (selectedValues.length) selections.set(field, selectedValues);
        else selections.delete(field);
        syncSelections();
        const selected = [...selections].map(([selectedField, items]) => {
            // A pill counts one exact spelling, so its clause matches case (obs artifact-ui, Filter attributes).
            const clauses = items.map((item) => exactClause(selectedField, item, true));
            return clauses.length > 1 ? `(${clauses.join(" OR ")})` : clauses[0];
        });
        input.value = [selectionBase, ...selected].filter(Boolean).join(" AND ");
        apply();
    };

    const presets = filterPresets;
    presetList.replaceChildren();
    presetSection.hidden = !presets.length;
    if (presets.length) {
        presets.forEach((preset) => {
            const button = document.createElement("button");
            button.className = "filter-pill filter-preset";
            button.type = "button";
            button.dataset.filterPreset = "";
            button.dataset.expression = preset.expression;
            button.setAttribute("aria-pressed", "false");
            button.title = preset.expression;
            button.textContent = preset.label;
            button.addEventListener("click", () => setExpression(preset.expression));
            presetList.append(button);
        });
    }

    const renderFields = () => {
        globalThis.obsFilterFields.render({
            container: fieldList,
            facets: globalThis.obsArtifact.facetFields(
                globalThis.obsArtifact.filterRecords(), queryProfile.fields),
            onSelect: toggleSelection,
            isSelected: (field, value) => (selections.get(field) || []).includes(value),
        });
        syncSelections();
    };
    renderFields();
    document.addEventListener("obs-canonical-property-change", renderFields);
    document.addEventListener("obs-artifact-filter", syncStatus);

    input.addEventListener("input", () => {
        selectionBase = "";
        selections.clear();
        fieldList.querySelectorAll(".filter-value").forEach((button) => {
            button.setAttribute("aria-checked", "false");
        });
        selectionList.replaceChildren();
        selectionSection.hidden = true;
        apply();
    });

    document.addEventListener("obs-bar-change", (event) => {
        if (event.detail?.bar === "filter" && !event.detail.open && input.value) {
            setExpression("");
        }
    });

    globalThis.obsFilter = {setExpression, selectExpression, refresh: apply};
    const expression = globalThis.obsArtifact.initialFilterExpression;
    if (expression.trim()) {
        setExpression(expression);
        globalThis.obsArtifact.openBar("filter");
    }
})();
