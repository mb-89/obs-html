(() => {
    // The Bases schema (#base-schema) ships only with the tables feature (features.py), so it is
    // read on first use: a page without a Base table never asks for it.
    let schemaCache;
    const schema = () => schemaCache ??= JSON.parse(document.querySelector("#base-schema").textContent);
    const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
    const supportedProperty = field => {
        if (/^note(?:\.file\.|\["file\.)/.test(field) || /^(?:formula|this)\./.test(field) || field.startsWith("file.") &&
                !["file.name", "file.path", "file.folder", "file.ext"].includes(field)) {
            throw new TypeError(`Unsupported Bases property: ${field}`);
        }
    };

    // This validator implements only the JSON Schema keywords used by the shared Bases schema.
    const validateNode = (value, rule, path = "root", owner = schema()) => {
        if (rule.$ref) {
            const [file, fragment] = rule.$ref.split("#");
            if (file) {
                const source = document.querySelector(`[data-json-schema="${file}"]`);
                if (!source) throw new TypeError(`${path}: unavailable schema ${file}.`);
                owner = JSON.parse(source.textContent);
            }
            const target = fragment.slice(1).split("/").reduce(
                (node, key) => node[key.replaceAll("~1", "/").replaceAll("~0", "~")], owner);
            return validateNode(value, target, path, owner);
        }
        if (rule.oneOf) {
            const matches = rule.oneOf.filter((choice) => {
                try {
                    validateNode(value, choice, path, owner);
                    return true;
                } catch (error) {
                    if (!(error instanceof TypeError)) throw error;
                    return false;
                }
            });
            if (matches.length !== 1) throw new TypeError(`${path}: unsupported definition value.`);
        }
        if (rule.not) {
            let matches = true;
            try {
                validateNode(value, rule.not, path, owner);
            } catch (error) {
                if (!(error instanceof TypeError)) throw error;
                matches = false;
            }
            if (matches) throw new TypeError(`${path}: unsupported combination of properties.`);
        }
        if (rule.type) {
            const valid = rule.type === "object" ? isObject(value)
                : rule.type === "array" ? Array.isArray(value)
                    : rule.type === "integer" ? Number.isInteger(value)
                        : typeof value === rule.type;
            if (!valid) throw new TypeError(`${path}: expected ${rule.type}.`);
        }
        if (typeof value === "number" &&
            ((rule.minimum !== undefined && value < rule.minimum) ||
                (rule.maximum !== undefined && value > rule.maximum))) {
            throw new TypeError(`${path}: number is outside the supported range.`);
        }
        if (rule.enum && !rule.enum.includes(value)) {
            throw new TypeError(`${path}: expected ${rule.enum.join(" or ")}.`);
        }
        if (Object.hasOwn(rule, "const") && value !== rule.const) {
            throw new TypeError(`${path}: expected ${JSON.stringify(rule.const)}.`);
        }
        if (typeof value === "string" && (
            (rule.minLength && value.length < rule.minLength) ||
            (rule.maxLength !== undefined && value.length > rule.maxLength) ||
            (rule.pattern && !new RegExp(rule.pattern).test(value))
        )) throw new TypeError(`${path}: unsupported or empty text.`);
        if (Array.isArray(value)) {
            if ((rule.minItems && value.length < rule.minItems) ||
                (rule.maxItems && value.length > rule.maxItems) ||
                (rule.uniqueItems && new Set(value.map((item) => JSON.stringify(item))).size !== value.length)) {
                throw new TypeError(`${path}: invalid number of items or duplicate items.`);
            }
            if (rule.items) value.forEach((item, index) => validateNode(item, rule.items, `${path}.${index}`, owner));
        }
        if (isObject(value)) {
            if ((rule.minProperties && Object.keys(value).length < rule.minProperties) ||
                    (rule.maxProperties && Object.keys(value).length > rule.maxProperties)) {
                throw new TypeError(`${path}: invalid number of properties.`);
            }
            Object.entries(rule.dependentRequired || {}).forEach(([key, dependencies]) => {
                if (!Object.hasOwn(value, key)) return;
                dependencies.forEach(dependency => {
                    if (!Object.hasOwn(value, dependency)) {
                        throw new TypeError(`${path}: ${key} requires ${dependency}.`);
                    }
                });
            });
            (rule.required || []).forEach((key) => {
                if (!Object.hasOwn(value, key)) throw new TypeError(`${path}: missing ${key}.`);
            });
            Object.entries(value).forEach(([key, item]) => {
                const property = rule.properties && Object.hasOwn(rule.properties, key)
                    ? rule.properties[key] : undefined;
                if (property) validateNode(item, property, `${path}.${key}`, owner);
                else if (rule.additionalProperties === false) {
                    throw new TypeError(`${path}: unsupported property ${key}.`);
                } else if (isObject(rule.additionalProperties)) {
                    validateNode(item, rule.additionalProperties, `${path}.${key}`, owner);
                }
            });
        }
    };

    const validate = (definition) => {
        validateNode(definition, schema());
        Object.keys(definition.properties || {}).forEach(supportedProperty);
        compileFilter(definition.filters, () => undefined);
        definition.views.forEach(view => {
            view.order.forEach(supportedProperty);
            compileFilter(view.filters, () => undefined);
            if (view.obsHtml?.groupOrder && !view.groupBy) {
                throw new TypeError("obsHtml.groupOrder requires groupBy.");
            }
            Object.keys(view.columnSize || {}).forEach(supportedProperty);
            if (view.columnSize && view.obsHtml?.columnSizing === "equal") {
                throw new TypeError("columnSize cannot be combined with columnSizing: equal.");
            }
            for (const key of ["groupBy", "sort"]) {
                const directives = view[key] || [];
                for (const directive of Array.isArray(directives) ? directives : [directives]) {
                    supportedProperty(directive.property);
                }
            }
        });
        Object.values(definition.properties || {}).forEach(property => {
            const options = property.obsHtml || {};
            if (options.leadingLines) {
                options.leadingLines.forEach(supportedProperty);
                const conflict = ["icon", "icons", "reference", "editable"].find(key => Object.hasOwn(options, key));
                if (conflict) throw new TypeError(`leadingLines cannot be combined with ${conflict}.`);
            }
            for (const icon of (options.icon ? [options.icon] : options.icons || [])) {
                if (globalThis.obsAssets) {
                    for (const state of ["active", "inactive"]) globalThis.obsAssets.icon(icon.name, state);
                }
                if (icon.linkProperty && icon.download === undefined) {
                    icon.download = icon.name === "snapshot";
                }
            }
        });
        const names = definition.views.map(view => String(view.name ?? "").trim());
        if (names.length > 1 && (names.some(name => !name) || new Set(names).size !== names.length)) {
            throw new TypeError("Several views of one base need unique nonempty names.");
        }
        return definition;
    };
    const parse = (source) => validate(JSON.parse(JSON.stringify(globalThis.jsyaml.load(source, {
        schema: globalThis.jsyaml.JSON_SCHEMA,
    }))));
    const dump = (definition) => globalThis.jsyaml.dump(definition, {noRefs: true, lineWidth: -1});
    const quoteField = (field) => /^[A-Za-z][\w.]*$/.test(field) ? field : JSON.stringify(field);
    // The schema's comparison pattern owns the syntax of the Bases filter grammar (generic-tables).
    let comparisonPattern;
    const unsupportedFilter = (filter) => new TypeError(`Unsupported Bases filter: ${
        typeof filter === "string" ? filter : JSON.stringify(filter)}`);
    const comparison = (filter) => {
        comparisonPattern ??= new RegExp(schema().$defs.comparison.pattern);
        const match = typeof filter === "string" ? filter.match(comparisonPattern) : null;
        if (!match) throw unsupportedFilter(filter);
        const [, simple, spaced, operator, literal] = match;
        if (simple === "recordType") {
            throw new TypeError(`Unsupported Bases filter: ${filter} (recordType filters were removed; ` +
                "select projected rows with obs.records; see obs capabilities/registers)");
        }
        try {
            supportedProperty(simple || `note["${spaced}"]`);
        } catch (error) {
            throw new TypeError(`Unsupported Bases filter: ${filter} (${error.message})`);
        }
        const expected = /^["']/.test(literal) ? literal.slice(1, -1) : JSON.parse(literal);
        return {field: spaced || simple.replace(/^note\./, ""), operator, literal, expected};
    };
    const logical = (filter) => {
        const entries = isObject(filter) ? Object.entries(filter) : [];
        const [operator, value] = entries[0] || [];
        const operands = Array.isArray(value) ? value : [value];
        if (entries.length !== 1 || !["and", "or", "not"].includes(operator) || !operands.length
            || operands.some(item => item === undefined || item === null)) {
            throw unsupportedFilter(filter);
        }
        return {operator, operands};
    };
    const filterExpression = (filter) => {
        if (filter === undefined || filter === null) return "";
        if (typeof filter === "string") {
            const {field: name, operator, literal} = comparison(filter);
            const field = quoteField(name);
            if (literal === "null") return operator === "!=" ? `${field}: *` : `NOT ${field}: *`;
            const value = escapePattern(fold(/^["']/.test(literal) ? literal.slice(1, -1) : literal));
            const expression = `${field}: /^${value}$/`;
            return operator === "==" ? expression : `NOT ${expression}`;
        }
        const {operator, operands} = logical(filter);
        const expressions = operands.map(filterExpression);
        if (operator === "not") return `NOT (${expressions.join(" OR ")})`;
        return `(${expressions.join(operator === "and" ? " AND " : " OR ")})`;
    };
    const assigned = (value) => {
        if (value === undefined || value === null) return false;
        if (typeof value === "string") return Boolean(value.trim());
        if (Array.isArray(value)) return value.some(assigned);
        if (typeof value === "object") return Object.values(value).some(assigned);
        return true;
    };
    // capabilities/bases#Comparisons owns the rule set: text ignores case unless a query
    // condition's flag asks for it, and property names ignore case. Ignoring case compares
    // case foldings by the core's one table (obs/case-folding.json, the page's #case-folding).
    let folds;
    const fold = text => {
        if (!folds) {
            const table = document.querySelector("#case-folding");
            if (!table) throw new Error("base.js: the page holds no #case-folding table; embed obs/case-folding.json as the renderer does.");
            folds = new Map(Object.entries(JSON.parse(table.textContent).folds)
                .map(([code, folded]) => [Number.parseInt(code, 16), folded]));
        }
        let folded = "";
        for (const character of text) folded += folds.get(character.codePointAt(0)) ?? character;
        return folded;
    };
    const escapePattern = text => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replaceAll("/", "\\/");
    const textMatcher = (expected, matchCase = false) => {
        if (matchCase) return actual => actual === expected;
        const folded = fold(expected);
        return actual => fold(actual) === folded;
    };
    const propertyKey = (mapping, name) => {
        if (Object.hasOwn(mapping, name)) return name;
        const folded = fold(name);
        return Object.keys(mapping).find(key => fold(key) === folded);
    };
    const compileFilter = (filter, valueFor) => {
        if (filter === undefined || filter === null) return {empty: true, match: () => true};
        if (typeof filter === "string") {
            const {field, operator, expected} = comparison(filter);
            const sameText = typeof expected === "string" ? textMatcher(expected) : null;
            return {empty: false, match: row => {
                const actual = valueFor(row, field) ?? null;
                const equal = sameText && typeof actual === "string" ? sameText(actual) : actual === expected;
                return operator === "==" ? equal : !equal;
            }};
        }
        const {operator, operands} = logical(filter);
        const children = operands.map(item => compileFilter(item, valueFor));
        return {empty: false, match: row => operator === "or"
            ? children.some(child => child.match(row))
            : operator === "not" ? !children.some(child => child.match(row))
                : children.every(child => child.match(row))};
    };
    const recordValue = (record, field) => {
        field = field.replace(/^note\./, "");
        const fileName = record.sourcePath?.split("/").at(-1) || "";
        const dot = fileName.lastIndexOf(".");
        const extension = dot > 0 && dot < fileName.length - 1 ? dot : -1;
        if (field === "file.name") return extension < 0 ? fileName : fileName.slice(0, extension);
        if (field === "file.path") return record.sourcePath || "";
        if (field === "file.ext") return extension < 0 ? "" : fileName.slice(extension + 1);
        if (field === "file.folder") return record.sourcePath?.split("/").slice(0, -1).join("/") || "";
        const whole = propertyKey(record.frontmatter || {}, field);
        if (whole !== undefined) return record.frontmatter[whole];
        const traverse = (value, parts) => {
            if (!parts.length) return value;
            if (Array.isArray(value) && !/^(?:0|[1-9][0-9]*)$/.test(parts[0])) {
                return value.flatMap(item => traverse(item, parts)).filter(item => item !== undefined);
            }
            const [part, ...remaining] = parts;
            if (Array.isArray(value)) return Object.hasOwn(value, part) ? traverse(value[part], remaining) : undefined;
            const key = isObject(value) ? propertyKey(value, part) : undefined;
            return key === undefined ? undefined : traverse(value[key], remaining);
        };
        return traverse(record.frontmatter, field.split("."));
    };
    const expandMetadata = (record, paths) => paths.flatMap(path => {
        const expand = (value, parts, prefix = []) => {
            if (!parts.length) return [prefix.join(".")];
            const [part, ...rest] = parts;
            if (part === "*") {
                if (!Array.isArray(value)) return [];
                return value.flatMap((item, index) => expand(item, rest, [...prefix, String(index)]));
            }
            return expand(value?.[part], rest, [...prefix, part]);
        };
        return expand(record.frontmatter, path.split("."));
    });
    const project = (authored, records) => {
        const definition = structuredClone(validate(authored));
        for (const [field, expansion] of Object.entries(definition.obsHtml?.expandProperties || {})) {
            const source = records.find(record => record.sourcePath === `${expansion.sourceNote}.md`);
            if (!source) throw new TypeError(`Missing column source note: ${expansion.sourceNote}`);
            const entries = recordValue(source, expansion.property);
            if (!Array.isArray(entries)) throw new TypeError(`Column source must be a list: ${expansion.property}`);
            const views = definition.views.filter(view => view.order.includes(field));
            if (!views.length) throw new TypeError(`Expanded property is not ordered: ${field}`);
            const keys = new Set();
            const columns = entries.map(entry => {
                const key = recordValue({frontmatter: entry}, expansion.keyProperty);
                if (typeof key !== "string" || !key.trim() || keys.has(key) || key.includes(".")) {
                    throw new TypeError(`Invalid or duplicate column key in ${expansion.property}`);
                }
                keys.add(key);
                const column = `${field}.${key}`;
                if (definition.views.some(view => view.order.includes(column)) ||
                        Object.hasOwn(definition.properties || {}, column)) {
                    throw new TypeError(`Expanded column collides with authored property: ${column}`);
                }
                const labels = (expansion.labelProperties || [expansion.keyProperty])
                    .map(path => recordValue({frontmatter: entry}, path)).filter(value => value !== "" && value != null);
                definition.properties ||= {};
                definition.properties[column] = {
                    ...structuredClone(definition.properties[field] || {}),
                    displayName: labels.join(expansion.separator ?? " "),
                };
                return column;
            });
            for (const view of views) {
                view.order = view.order.flatMap(key => key === field ? columns : [key]);
                if (!view.order.length) throw new TypeError(`Column expansion is empty: ${field}`);
            }
        }
        return definition;
    };
    const referenceRecords = (record, field, recordsBySlug) => {
        const template = document.createElement("template");
        template.innerHTML = record.frontmatterHtml?.[field] || "";
        const seen = new Set();
        return [...template.content.querySelectorAll('a[href^="#"]')].flatMap(link => {
            const href = link.getAttribute("href");
            const slug = decodeURIComponent(href.slice(1)).split("?", 1)[0].split("/", 1)[0];
            const target = recordsBySlug.get(slug);
            if (!target || seen.has(slug)) return [];
            seen.add(slug);
            return [{record: target, href}];
        });
    };
    globalThis.obsBases = {
        validate, parse, dump, filterExpression, compileFilter, assigned, recordValue, referenceRecords,
        project, expandMetadata, textMatcher, escapePattern, fold,
    };
})();
