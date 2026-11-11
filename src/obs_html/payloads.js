(() => {
    let archive;
    let members;
    const pending = new Set();
    const decoded = new Map();
    const urls = new Map();
    const resolved = new Map();
    // Each blob URL's Blob, so a file offer can save the bytes without fetching the URL (file-offers.js).
    const blobs = new Map();
    const artifactDataIsland = document.querySelector("[data-artifact-data]");
    const artifactData = JSON.parse(artifactDataIsland.textContent);
    let assets = artifactData.embeddedAssets || {};
    const failures = [];
    const fail = (error) => {
        failures.push(error);
        let notice = document.querySelector("[data-payload-error]");
        if (!notice) {
            notice = document.createElement("p");
            notice.dataset.payloadError = "";
            notice.dataset.transientView = "";
            notice.setAttribute("role", "alert");
            document.querySelector(".reader-shell").prepend(notice);
        }
        notice.textContent = `Embedded asset error: ${error.message}`;
        console.error(notice.textContent);
    };
    const index = () => {
        if (members) return;
        const island = document.getElementById("obs-source-archive");
        if (!island) {
            members = new Map();
            return;
        }
        const encoded = island.textContent.replace(/\s/g, "");
        if (encoded.length % 4 || !/^[A-Za-z0-9+/]*={0,2}$/.test(encoded)) {
            throw new Error("Invalid embedded source archive encoding.");
        }
        archive = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
        const view = new DataView(archive.buffer);
        const bound = (offset, length) => {
            if (!Number.isSafeInteger(offset) || offset < 0 || offset + length > archive.length) {
                throw new Error("Truncated embedded ZIP metadata.");
            }
        };
        if (archive.length < 22) throw new Error("Truncated embedded ZIP archive.");
        let end = archive.length - 22;
        for (; end >= Math.max(0, archive.length - 65557); end--) {
            if (view.getUint32(end, true) === 0x06054b50 &&
                    end + 22 + view.getUint16(end + 20, true) === archive.length) break;
        }
        if (end < Math.max(0, archive.length - 65557)) throw new Error("Invalid embedded ZIP directory.");
        if (view.getUint32(end + 4, true) !== 0 ||
                view.getUint16(end + 8, true) !== view.getUint16(end + 10, true)) {
            throw new Error("Multipart embedded ZIP archives are unsupported.");
        }
        const count = view.getUint16(end + 10, true);
        const length = view.getUint32(end + 12, true);
        const start = view.getUint32(end + 16, true);
        if (count === 65535 || start === 0xffffffff || length === 0xffffffff) {
            throw new Error("ZIP64 embedded archives are unsupported.");
        }
        bound(start, length);
        if (start + length !== end) throw new Error("Invalid embedded ZIP directory bounds.");
        const entries = new Map();
        let position = start;
        const text = new TextDecoder("utf-8", {fatal: true});
        for (let entry = 0; entry < count; entry++) {
            bound(position, 46);
            if (view.getUint32(position, true) !== 0x02014b50) throw new Error("Invalid embedded ZIP member.");
            const flags = view.getUint16(position + 8, true);
            const method = view.getUint16(position + 10, true);
            const crc = view.getUint32(position + 16, true);
            const compressed = view.getUint32(position + 20, true);
            const size = view.getUint32(position + 24, true);
            const nameLength = view.getUint16(position + 28, true);
            const extraLength = view.getUint16(position + 30, true);
            const commentLength = view.getUint16(position + 32, true);
            const local = view.getUint32(position + 42, true);
            bound(position + 46, nameLength + extraLength + commentLength);
            const name = text.decode(archive.subarray(position + 46, position + 46 + nameLength));
            if (entries.has(name) || /(^[/\\]|(^|[/\\])\.\.([/\\]|$))/.test(name)) {
                throw new Error(`Invalid or duplicate embedded ZIP path: ${name}`);
            }
            if (flags & 1 || ![0, 8].includes(method)) throw new Error(`Unsupported embedded ZIP compression: ${name}`);
            bound(local, 30);
            if (view.getUint32(local, true) !== 0x04034b50 ||
                    view.getUint16(local + 6, true) !== flags ||
                    view.getUint16(local + 8, true) !== method) throw new Error(`Invalid ZIP header: ${name}`);
            const localNameLength = view.getUint16(local + 26, true);
            const offset = local + 30 + localNameLength + view.getUint16(local + 28, true);
            bound(local + 30, localNameLength);
            if (text.decode(archive.subarray(local + 30, local + 30 + localNameLength)) !== name ||
                    offset + compressed > start) throw new Error(`Invalid ZIP member bounds: ${name}`);
            bound(offset, compressed);
            entries.set(name, {method, crc, size, offset, compressed});
            position += 46 + nameLength + extraLength + commentLength;
        }
        if (position !== end) throw new Error("Invalid embedded ZIP directory length.");
        members = entries;
    };
    const crc32 = (bytes) => {
        let crc = 0xffffffff;
        for (const byte of bytes) {
            crc ^= byte;
            for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
        }
        return (crc ^ 0xffffffff) >>> 0;
    };
    const read = (name) => {
        if (!decoded.has(name)) decoded.set(name, (async () => {
            index();
            const entry = members.get(name);
            if (!entry) throw new Error(`Missing embedded ZIP member: ${name}`);
            const compressed = archive.subarray(entry.offset, entry.offset + entry.compressed);
            const bytes = entry.method === 0 ? compressed : new Uint8Array(await new Response(
                new Blob([compressed]).stream().pipeThrough(new DecompressionStream("deflate-raw")),
            ).arrayBuffer());
            if (bytes.length !== entry.size || crc32(bytes) !== entry.crc) {
                throw new Error(`Corrupt embedded ZIP member: ${name}`);
            }
            return bytes;
        })());
        return decoded.get(name);
    };
    const assetUrl = (key, asset) => {
        if (!urls.has(key)) urls.set(key, (async () => {
            if (!asset || typeof asset.archivePath !== "string" ||
                    !/^(?:image\/[a-z0-9.+-]+|application\/(?:pdf|octet-stream|json)|text\/plain)$/.test(asset.mime || "") ||
                    !/^[a-f0-9]{64}$/.test(asset.sha256 || "")) {
                throw new Error(`Invalid embedded asset descriptor: ${key}`);
            }
            const bytes = await read(asset.archivePath);
            const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
                .map(byte => byte.toString(16).padStart(2, "0")).join("");
            if (digest !== asset.sha256) throw new Error(`Embedded asset digest mismatch: ${asset.archivePath}`);
            const blob = new Blob([bytes], {type: asset.mime});
            const url = URL.createObjectURL(blob);
            blobs.set(url, blob);
            resolved.set(key, url);
            return url;
        })());
        return urls.get(key);
    };
    // A src that still names obs-asset: makes the browser try to fetch it once the element is connected,
    // so the reference waits in data-obs-asset-src until the blob URL exists.
    const PENDING_SOURCE = "data-obs-asset-src";
    const activate = (element, attribute, key, asset) => {
        if (resolved.has(key)) {
            element.setAttribute(attribute, resolved.get(key));
            if (attribute === "src") element.removeAttribute(PENDING_SOURCE);
            return;
        }
        if (attribute === "src") {
            element.setAttribute(PENDING_SOURCE, key);
            element.removeAttribute("src");
        }
        const operation = assetUrl(key, asset).then(url => {
            if (attribute !== "src") {
                element.setAttribute(attribute, url);
            } else if (element.getAttribute(PENDING_SOURCE) === key) {
                element.setAttribute("src", url);
                element.removeAttribute(PENDING_SOURCE);
            }
        });
        pending.add(operation);
        operation.catch(fail).finally(() => pending.delete(operation));
    };
    const ready = async () => {
        while (pending.size) await Promise.all([...pending]);
        if (failures.length) throw failures[0];
    };
    const hydrate = (root) => {
        const selector = `[src], [href], [${PENDING_SOURCE}]`;
        const elements = [...root.querySelectorAll(selector)];
        if (root.matches?.(selector)) elements.unshift(root);
        elements.forEach(element => {
            const references = [["src", element.getAttribute("src") || ""],
                ["href", element.getAttribute("href") || ""]];
            if (element.hasAttribute(PENDING_SOURCE) && !element.hasAttribute("src")) {
                references[0][1] = `obs-asset:${element.getAttribute(PENDING_SOURCE)}`;
            }
            references.forEach(([attribute, reference]) => {
                const match = /^obs-asset:([a-f0-9]{64})$/.exec(reference);
                if (!match) return;
                const asset = assets[match[1]];
                if (typeof asset === "string") {
                    element.setAttribute(attribute, asset);
                    if (attribute === "src") element.removeAttribute(PENDING_SOURCE);
                } else activate(element, attribute, match[1], asset);
            });
        });
    };
    const restore = (root) => {
        const references = new Map([...resolved].map(([key, url]) => [url, `obs-asset:${key}`]));
        root.querySelectorAll("[src], [href]").forEach(element => ["src", "href"].forEach(attribute => {
            const reference = references.get(element.getAttribute(attribute));
            if (reference) element.setAttribute(attribute, reference);
        }));
        root.querySelectorAll(`[${PENDING_SOURCE}]`).forEach(element => {
            if (!element.hasAttribute("src")) {
                element.setAttribute("src", `obs-asset:${element.getAttribute(PENDING_SOURCE)}`);
            }
            element.removeAttribute(PENDING_SOURCE);
        });
    };
    const bytes = async () => {
        index();
        if (!archive) throw new Error("Missing embedded source archive.");
        await ready();
        await Promise.all(Object.entries(assets).map(([key, asset]) =>
            typeof asset === "string" ? null : assetUrl(key, asset)));
        await Promise.all([...members.keys()].map(read));
        return archive;
    };
    const digest = async bytes => [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
        .map(byte => byte.toString(16).padStart(2, "0")).join("");
    const describeAsset = async (archivePath, bytes, mime) => {
        if (typeof archivePath !== "string" || archivePath.startsWith("/") ||
                archivePath.includes("\\") || archivePath.split("/").some(part => !part || part === "..") ||
                !(bytes instanceof Uint8Array) ||
                !/^(?:application\/(?:pdf|octet-stream|json)|image\/[a-z0-9.+-]+|text\/plain)$/.test(mime || "")) {
            throw new Error("Invalid replacement asset.");
        }
        const sha256 = await digest(bytes);
        const key = await digest(new TextEncoder().encode(`${archivePath}\0${sha256}`));
        return {key, archivePath, mime, sha256};
    };
    const stageRewrite = async (changes, nextModel, sourceChanges = []) => {
        if (!Array.isArray(changes) || !Array.isArray(sourceChanges) ||
                !nextModel || typeof nextModel !== "object") {
            throw new Error("Invalid archive transaction.");
        }
        await ready();
        index();
        const complete = Boolean(archive) && artifactData.sourceArchiveComplete !== false;
        const replacements = [];
        const removeKeys = new Set();
        const removePaths = new Set();
        const nextAssets = structuredClone(nextModel.embeddedAssets || {});
        for (const change of changes) {
            if (!change || (change.removePaths !== undefined && !Array.isArray(change.removePaths)) ||
                    (change.removeKeys !== undefined && !Array.isArray(change.removeKeys))) {
                throw new Error("Invalid archive transaction change.");
            }
            const descriptor = await describeAsset(change.archivePath, change.bytes, change.mime);
            if (change.key !== descriptor.key || change.sha256 !== descriptor.sha256) {
                throw new Error(`Replacement asset digest mismatch: ${change.archivePath}`);
            }
            replacements.push({path: `vault/${descriptor.archivePath}`, bytes: change.bytes});
            nextAssets[descriptor.key] = {
                archivePath: `vault/${descriptor.archivePath}`,
                mime: descriptor.mime,
                sha256: descriptor.sha256,
            };
            (change.removeKeys || []).forEach(key => {
                if (!/^[a-f0-9]{64}$/.test(key)) throw new Error("Invalid obsolete asset key.");
                removeKeys.add(key);
            });
            (change.removePaths || []).forEach(path => {
                if (typeof path !== "string" || !path.startsWith("vault/assets/evidence/") ||
                        path.split("/").some(part => part === ".." || part === "")) {
                    throw new Error(`Invalid obsolete evidence member: ${path}`);
                }
                removePaths.add(path);
            });
        }
        removeKeys.forEach(key => delete nextAssets[key]);
        const referencedKeys = new Set();
        const referencedPaths = new Set();
        const collect = value => {
            if (typeof value === "string") {
                for (const match of value.matchAll(/obs-asset:([a-f0-9]{64})/g)) referencedKeys.add(match[1]);
                for (const match of value.matchAll(/(?:^|[^A-Za-z0-9])assets\/evidence\/[A-Za-z0-9._-]+/g)) {
                    referencedPaths.add(`vault/${match[0].replace(/^[^A-Za-z0-9]*/, "")}`);
                }
                return;
            }
            if (Array.isArray(value)) value.forEach(collect);
            else if (value && typeof value === "object") Object.values(value).forEach(collect);
        };
        collect({...nextModel, embeddedAssets: undefined});
        for (const key of Object.keys(nextAssets)) {
            if (!referencedKeys.has(key)) delete nextAssets[key];
        }
        for (const key of referencedKeys) {
            if (!nextAssets[key]) throw new Error(`Missing replacement asset descriptor: ${key}`);
        }
        for (const [key, asset] of Object.entries(nextAssets)) {
            if (typeof asset === "string") continue;
            if (!asset || typeof asset.archivePath !== "string" ||
                    !/^[a-f0-9]{64}$/.test(asset.sha256 || "") ||
                    !/^(?:application\/(?:pdf|octet-stream|json)|image\/[a-z0-9.+-]+|text\/plain)$/.test(asset.mime || "")) {
                throw new Error(`Invalid embedded asset descriptor: ${key}`);
            }
            if (removePaths.has(asset.archivePath)) {
                throw new Error(`Cannot remove referenced evidence member: ${asset.archivePath}`);
            }
        }
        for (const archivePath of removePaths) {
            if (referencedPaths.has(archivePath)) {
                throw new Error(`Cannot remove referenced evidence member: ${archivePath}`);
            }
            replacements.push({path: archivePath, remove: true});
        }
        if (complete && sourceChanges.length) {
            const seen = new Set(replacements.map(change => change.path));
            for (const change of sourceChanges) {
                if (!change || typeof change.path !== "string" ||
                        !change.path.startsWith("vault/") || change.path.includes("\\") ||
                        change.path.split("/").some(part => !part || part === "." || part === "..") ||
                        change.path.startsWith("vault/assets/evidence/") || seen.has(change.path) ||
                        (change.remove !== true && !(change.bytes instanceof Uint8Array))) {
                    throw new Error("Invalid source projection archive change.");
                }
                seen.add(change.path);
                replacements.push(change);
            }
        }
        if (complete && (sourceChanges.length || replacements.length)) {
            const inventory = JSON.parse(new TextDecoder("utf-8", {fatal: true}).decode(
                await read("source-inventory.json")));
            if (!Array.isArray(inventory.vault) || !Array.isArray(inventory.generator) ||
                    inventory.vault.some(path => typeof path !== "string")) {
                throw new Error("Invalid source projection inventory.");
            }
            const paths = new Set(inventory.vault);
            for (const change of replacements) {
                const path = change.path.slice("vault/".length);
                if (change.remove) paths.delete(path);
                else paths.add(path);
            }
            replacements.push({path: "source-inventory.json",
                bytes: new TextEncoder().encode(JSON.stringify({...inventory, vault: [...paths].sort()}))});
        }
        const nextArchive = globalThis.ObsHtmlZipRewrite.rewrite(
            archive || globalThis.ObsHtmlZipRewrite.empty(), replacements,
        );
        const names = new Set(globalThis.ObsHtmlZipRewrite.inspect(nextArchive).entries.map(entry => entry.name));
        for (const asset of Object.values(nextAssets)) {
            if (typeof asset === "object" && !names.has(asset.archivePath)) {
                throw new Error(`Missing embedded ZIP member: ${asset.archivePath}`);
            }
        }
        for (const archivePath of removePaths) {
            if (names.has(archivePath)) throw new Error(`Obsolete evidence member remains: ${archivePath}`);
        }
        for (const change of changes) {
            const descriptor = nextAssets[change.key];
            const stored = globalThis.ObsHtmlZipRewrite.readStoredMember(nextArchive, descriptor.archivePath);
            if (await digest(stored) !== descriptor.sha256 || stored.length !== change.bytes.length ||
                    stored.some((byte, index) => byte !== change.bytes[index])) {
                throw new Error(`Replacement ZIP member validation failed: ${descriptor.archivePath}`);
            }
        }
        let encoded = "";
        for (let offset = 0; offset < nextArchive.length; offset += 32768) {
            encoded += String.fromCharCode(...nextArchive.subarray(offset, offset + 32768));
        }
        return {archive: nextArchive, archiveBase64: btoa(encoded), assets: nextAssets, complete};
    };
    const commitRewrite = staged => {
        const nextKeys = new Set(Object.keys(staged.assets));
        for (const [key, url] of resolved) {
            if (nextKeys.has(key)) continue;
            URL.revokeObjectURL(url);
            resolved.delete(key);
            urls.delete(key);
            decoded.delete(key);
        }
        archive = staged.archive;
        members = undefined;
        decoded.clear();
        assets = staged.assets;
        artifactData.embeddedAssets = staged.assets;
        artifactData.sourceArchiveComplete = staged.complete;
        let island = document.getElementById("obs-source-archive");
        if (!island) {
            island = document.createElement("script");
            island.id = "obs-source-archive";
            island.type = "application/octet-stream";
            document.body.append(island);
            const exports = document.querySelector("[data-source-exports]");
            if (exports) {
                exports.hidden = false;
                const attach = exports.querySelector("[data-source-attach]");
                if (attach) attach.hidden = true;
            }
        }
        island.textContent = staged.archiveBase64;
    };
    document.addEventListener("click", async event => {
        const link = event.target.closest?.('a[href^="obs-asset:"]');
        if (!link) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        try {
            await ready();
            if (link.href.startsWith("blob:")) link.click();
        } catch (error) {
            fail(error);
        }
    }, true);
    new MutationObserver(changes => changes.forEach(change => {
        if (change.type === "attributes") hydrate(change.target);
        else change.addedNodes.forEach(node => {
            if (node.nodeType === 1) hydrate(node);
        });
    })).observe(document.body, {subtree: true, childList: true, attributes: true,
        attributeFilter: ["src", "href"]});
    globalThis.obsPayload = {
        activate, hydrate, restore, ready, bytes, fail, describeAsset, stageRewrite, commitRewrite,
        blobFor: url => blobs.get(url) || null,
        readMember: async path => {
            await ready();
            index();
            return (await read(path)).slice();
        },
    };
})();
