((root, factory) => {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    root.ObsHtmlAttachmentReplacement = api;
    (root.obsHtmlTrustedExtensions ||= []).push(api);
})(typeof globalThis === "undefined" ? this : globalThis, () => {
    "use strict";

    // The trusted extension obsHtml.attachments: replace one archive-backed attachment and every
    // canonical record that references it, in one revision-checked canonical transaction.
    // spec/capabilities/attachment-replacement.md owns its contract.
    const namespace = "obsHtml.attachments";
    const KEY = /^[a-f0-9]{64}$/;
    const failure = (message, cause) =>
        new Error(`Trusted extension ${namespace}: ${message}`, cause ? {cause} : undefined);

    const replaceReferences = (value, from, to) => {
        if (typeof value === "string") return value.split(from).join(to);
        if (Array.isArray(value)) return value.map(item => replaceReferences(item, from, to));
        if (value && typeof value === "object") {
            return Object.fromEntries(Object.entries(value)
                .map(([field, item]) => [field, replaceReferences(item, from, to)]));
        }
        return value;
    };

    const noteId = note => typeof note.sourcePath === "string" ? note.sourcePath.replace(/\.md$/, "") : note.slug;

    const create = ({artifact, payload, trusted}) => {
        if (!artifact || typeof artifact.stageCanonicalTransaction !== "function" ||
                !payload || typeof payload.describeAsset !== "function" || typeof trusted !== "function") {
            throw new TypeError(`Trusted extension ${namespace} needs the artifact, payload, and trust owners.`);
        }
        if (!trusted()) {
            throw failure("this HTML has no registered trusted runtime bundle; build it with " +
                "--trusted-runtime-bundle ID=PATH and call the extension from that bundle.");
        }

        const replace = async ({expectedRevision, key, bytes, mime, signal} = {}) => {
            if (!Number.isSafeInteger(expectedRevision) || expectedRevision < 0) {
                throw failure("expectedRevision must be the artifact.revision the replacement was prepared against.");
            }
            if (typeof key !== "string" || !KEY.test(key)) {
                throw failure("key must be the 64-hex key of the attachment's obs-asset: reference.");
            }
            if (!(bytes instanceof Uint8Array)) throw failure("bytes must be a Uint8Array.");
            if (signal?.aborted) throw failure("cancelled before staging; nothing was applied.");
            if (artifact.revision !== expectedRevision) {
                throw failure(`revision ${expectedRevision} is stale (current ${artifact.revision}); ` +
                    "re-read artifact.revision and prepare the replacement again.");
            }
            const current = artifact.embeddedAssets()[key];
            if (current === undefined) throw failure(`no embedded attachment has key ${key}.`);
            if (typeof current !== "object" || typeof current.archivePath !== "string" ||
                    !current.archivePath.startsWith("vault/")) {
                throw failure(`attachment ${key} is not a vault member of the source archive; ` +
                    "only archive-backed attachments can be replaced.");
            }
            const reference = `obs-asset:${key}`;
            const model = JSON.parse(artifact.serializeModel());
            delete model.notes;
            delete model.embeddedAssets;
            if (JSON.stringify(model).includes(reference)) {
                throw failure(`attachment ${key} is referenced outside the canonical notes; ` +
                    "only attachments that canonical records own can be replaced.");
            }
            let descriptor;
            try {
                descriptor = await payload.describeAsset(
                    current.archivePath.slice("vault/".length), bytes, mime ?? current.mime);
            } catch (error) {
                throw failure(`the replacement is invalid: ${error.message}`, error);
            }
            if (descriptor.key === key) {
                throw failure(`the replacement bytes equal attachment ${key}; nothing to replace.`);
            }
            const dependents = [];
            const notes = artifact.canonicalNotes().map(note => {
                if (!JSON.stringify(note).includes(reference)) return note;
                dependents.push(noteId(note));
                return replaceReferences(note, reference, `obs-asset:${descriptor.key}`);
            });
            if (!dependents.length) throw failure(`no canonical record references attachment ${key}.`);
            let staged;
            try {
                staged = await artifact.stageCanonicalTransaction({
                    expectedRevision,
                    notes,
                    assetChanges: [{...descriptor, bytes}],
                    sourceChanges: [],
                });
            } catch (error) {
                throw failure(`staging failed, nothing was applied: ${error.message}`, error);
            }
            if (signal?.aborted) throw failure("cancelled after staging; nothing was applied.");
            try {
                staged.commit();
            } catch (error) {
                throw failure(`commit failed: ${error.message}`, error);
            }
            return Object.freeze({previousKey: key, key: descriptor.key, dependents,
                revision: artifact.revision});
        };

        return Object.freeze({namespace, replace});
    };

    return Object.freeze({namespace, create});
});
