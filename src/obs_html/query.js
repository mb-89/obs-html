(() => {
    const INCOMPLETE = "still typing";

    const incomplete = () => new Error(INCOMPLETE);

    const lex = (source) => {
        const tokens = [];
        const characters = Array.from(source);
        let index = 0;
        while (index < characters.length) {
            const character = characters[index];
            if (character === " " || character === "\t") {
                index += 1;
            } else if (character === "(" || character === ")") {
                tokens.push({ kind: character, text: character });
                index += 1;
            } else if (character === ":") {
                tokens.push({ kind: "colon", text: character });
                index += 1;
            } else if (character === '"') {
                let end = index + 1;
                let text = "";
                while (end < characters.length && characters[end] !== '"') {
                    if (characters[end] === "\\" && ["\\", '"'].includes(characters[end + 1])) {
                        text += characters[end + 1];
                        end += 2;
                    } else {
                        text += characters[end];
                        end += 1;
                    }
                }
                if (end >= characters.length) throw incomplete();
                tokens.push({ kind: "quoted", text });
                index = end + 1;
            } else if (character === "/") {
                let end = index + 1;
                while (end < characters.length && characters[end] !== "/") {
                    if (characters[end] === "\\") end += 1;
                    end += 1;
                }
                if (end >= characters.length) throw incomplete();
                // The c flag matches case, like a query condition's matchCase (capabilities/queries#Conditions).
                const matchCase = characters[end + 1] === "c" && (end + 2 >= characters.length ||
                    " \t()".includes(characters[end + 2]));
                tokens.push({ kind: "regex", text: characters.slice(index + 1, end).join(""), matchCase });
                index = end + (matchCase ? 2 : 1);
            } else {
                let end = index;
                while (end < characters.length && !" \t():\"".includes(characters[end])) end += 1;
                const text = characters.slice(index, end).join("");
                const operator = text.toLocaleLowerCase();
                tokens.push({
                    kind: ["and", "or", "not"].includes(operator) ? operator : "word",
                    text,
                });
                index = end;
            }
        }
        return tokens;
    };

    // Every selection compares text by capabilities/queries#Conditions, as the core's
    // conditions_select does: a property resolves like a Bases property, and a missing
    // property or null has no text.
    const conditionTexts = (value) => {
        if (Array.isArray(value)) return value.flatMap(conditionTexts);
        if (value === undefined || value === null || typeof value === "object") return [];
        return [typeof value === "boolean" ? (value ? "true" : "false") : String(value)];
    };
    // mark and mark.<category> name a note's marks when its frontmatter has no such property.
    const markValue = (record, field) => {
        const name = field.replace(/^note\./, "").toLowerCase();
        const marks = record.marks || [];
        if (name === "mark") return marks.length ? [...new Set(marks.map((mark) => mark.kind))] : undefined;
        if (!name.startsWith("mark.")) return undefined;
        const selected = marks.filter((mark) => mark.kind.toLowerCase() === name.slice(5)).map((mark) => mark.label);
        return selected.length ? selected : undefined;
    };
    // A condition sees note properties and marks only: no other derived field is a property.
    const propertyValue = (record, field) => {
        const value = record.frontmatter ? globalThis.obsBases.recordValue(record, field) : undefined;
        return value === undefined ? markValue(record, field) : value;
    };
    const propertyTexts = (record, field) => conditionTexts(propertyValue(record, field));
    // The reader's own fields (title, text, query aliases) answer only names that are no
    // note property; a note. prefix asks for the property alone, as drill-downs do.
    const readerValue = (record, field) => {
        const value = record.frontmatter || record.marks ? propertyValue(record, field) : undefined;
        return value !== undefined || /^note\./.test(field) ? value : record.fields?.[field.toLocaleLowerCase()];
    };

    const quotePattern = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

    class Clause {
        constructor(field, value) {
            this.name = field;
            this.field = field.toLocaleLowerCase();
            this.needle = null;
            this.pattern = null;
            this.flags = value.matchCase ? "" : "i";
            if (value.kind === "regex") {
                this.pattern = value.text;
            } else if (value.text.includes("*")) {
                this.pattern = value.text.split("*").map(quotePattern).join(".*");
            } else {
                this.needle = value.text.toLocaleLowerCase();
            }
            this.expression = this.pattern === null ? null : new RegExp(this.pattern, this.flags);
        }

        value(record) {
            if (!this.field) return record.haystack;
            if (this.field === "detail" || this.field === "details") return record.detail;
            return readerValue(record, this.name);
        }

        hit(value) {
            return conditionTexts(value).some((text) => this.expression !== null
                ? this.expression.test(text) : text.toLocaleLowerCase().includes(this.needle));
        }

        match(record) {
            return this.hit(this.value(record));
        }

        appliesTo(field) {
            if (!this.field) return true;
            if (field === "text") {
                return ["text", "content", "body", "detail", "details"].includes(this.field);
            }
            return this.field.replace(/^note\./, "") === field;
        }

        ranges(value, field) {
            if (!this.appliesTo(field)) return [];
            if (this.pattern !== null) {
                const ranges = [];
                const expression = new RegExp(this.pattern, `g${this.flags}`);
                for (const match of value.matchAll(expression)) {
                    if (match[0].length) ranges.push([match.index, match.index + match[0].length]);
                }
                return ranges;
            }
            const ranges = [];
            const lower = value.toLocaleLowerCase();
            let start = lower.indexOf(this.needle);
            while (this.needle && start >= 0) {
                ranges.push([start, start + this.needle.length]);
                start = lower.indexOf(this.needle, start + this.needle.length);
            }
            return ranges;
        }
    }

    class Parser {
        constructor(tokens) {
            this.tokens = tokens;
            this.index = 0;
        }

        peek() {
            return this.tokens[this.index]?.kind || "";
        }

        parseOr() {
            let left = this.parseAnd();
            while (this.peek() === "or") {
                this.index += 1;
                left = { kind: "or", left, right: this.parseAnd() };
            }
            return left;
        }

        parseAnd() {
            let left = this.parseUnary();
            while (true) {
                if (this.peek() === "and") {
                    this.index += 1;
                } else if (!["word", "quoted", "regex", "(", "not"].includes(this.peek())) {
                    return left;
                }
                left = { kind: "and", left, right: this.parseUnary() };
            }
        }

        parseUnary() {
            if (this.peek() === "not") {
                this.index += 1;
                return { kind: "not", child: this.parseUnary() };
            }
            return this.parsePrimary();
        }

        parsePrimary() {
            if (this.peek() === "(") {
                this.index += 1;
                const node = this.parseOr();
                if (this.peek() !== ")") throw incomplete();
                this.index += 1;
                return node;
            }
            if (["word", "quoted", "regex"].includes(this.peek())) return this.parseClause();
            if (!this.peek()) throw incomplete();
            throw new Error(`cannot read "${this.tokens[this.index].text}"`);
        }

        parseClause() {
            const first = this.tokens[this.index];
            this.index += 1;
            if (["word", "quoted"].includes(first.kind) && this.peek() === "colon") {
                const negated = first.kind === "word" && first.text.startsWith("-");
                const field = negated ? first.text.slice(1) : first.text;
                this.index += 1;
                const clause = new Clause(field, this.value());
                return negated ? { kind: "not", child: clause } : clause;
            }
            if (first.kind === "word" && first.text.startsWith("-") && first.text.length > 1) {
                return { kind: "not", child: new Clause("", { kind: "word", text: first.text.slice(1) }) };
            }
            return new Clause("", first);
        }

        value() {
            if (!["word", "quoted", "regex"].includes(this.peek())) throw incomplete();
            const value = this.tokens[this.index];
            this.index += 1;
            return value;
        }
    }

    const matchNode = (node, record) => {
        if (node instanceof Clause) return node.match(record);
        if (node.kind === "and") return matchNode(node.left, record) && matchNode(node.right, record);
        if (node.kind === "or") return matchNode(node.left, record) || matchNode(node.right, record);
        return !matchNode(node.child, record);
    };

    const positiveClauses = (node, positive = true) => {
        if (node instanceof Clause) return positive ? [node] : [];
        if (node.kind === "not") return positiveClauses(node.child, !positive);
        return [
            ...positiveClauses(node.left, positive),
            ...positiveClauses(node.right, positive),
        ];
    };

    const clauseFields = (node) => {
        if (node instanceof Clause) return node.field ? [node.field] : [];
        if (node.kind === "not") return clauseFields(node.child);
        return [...clauseFields(node.left), ...clauseFields(node.right)];
    };

    const mergeRanges = (ranges) => {
        const sorted = ranges.sort((left, right) => left[0] - right[0] || left[1] - right[1]);
        const merged = [];
        sorted.forEach((range) => {
            const previous = merged.at(-1);
            if (previous && range[0] <= previous[1]) previous[1] = Math.max(previous[1], range[1]);
            else merged.push([...range]);
        });
        return merged;
    };

    const compile = (source) => {
        const tokens = lex(source);
        if (!tokens.length) {
            return { source, empty: true, fields: [], match: () => true, ranges: () => [] };
        }
        tokens.filter((token) => token.kind === "regex").forEach((token) => new RegExp(token.text));
        const parser = new Parser(tokens);
        const root = parser.parseOr();
        if (parser.index !== tokens.length) throw new Error(`cannot read "${tokens[parser.index].text}"`);
        const clauses = positiveClauses(root);
        return {
            source,
            empty: false,
            fields: [...new Set(clauseFields(root))],
            match: (record) => matchNode(root, record),
            ranges: (value, field = "") => {
                const fields = Array.isArray(field) ? field : [field];
                return mergeRanges(fields.flatMap((candidate) =>
                    clauses.flatMap((clause) => clause.ranges(value, candidate)),
                ));
            },
        };
    };

    // An exact clause is the reader-language form of an equals condition: the same pattern
    // obsBases.textMatcher compares with, so a drill-down retains exactly what its count counted.
    const exactClause = (field, value, matchCase = false) => {
        const pattern = globalThis.obsBases.escapePattern(String(value));
        const name = /^[A-Za-z][\w.-]*$/.test(field) ? field : JSON.stringify(field);
        return `${name}: /^${pattern}$/${matchCase ? "c" : ""}`;
    };
    const conditionsExpression = (conditions = []) => conditions.map((condition) =>
        "equals" in condition ? exactClause(`note.${condition.field}`, condition.equals, condition.matchCase === true)
            : `${JSON.stringify(`note.${condition.field}`)}: /\\S/`,
    ).join(" AND ");
    const compileConditions = (conditions) => {
        const tests = (conditions || []).map((condition) => {
            const same = "equals" in condition
                ? globalThis.obsBases.textMatcher(String(condition.equals), condition.matchCase === true) : null;
            return (record) => {
                const texts = propertyTexts(record, condition.field);
                return same ? texts.some(same) : texts.some((text) => text.trim() !== "");
            };
        });
        return {match: (record) => tests.every((test) => test(record))};
    };
    const compiledConditions = new WeakMap();
    const conditionsMatch = (record, conditions = []) => {
        if (!compiledConditions.has(conditions)) compiledConditions.set(conditions, compileConditions(conditions));
        return compiledConditions.get(conditions).match(record);
    };

    globalThis.obsQuery = {compile, exactClause, conditionsExpression, conditionsMatch, compileConditions, propertyTexts,
        incomplete: INCOMPLETE};
})();