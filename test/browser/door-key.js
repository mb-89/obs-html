// An element's key in the browser door (test/browser/browser-door.md, Recording and replay): the
// id of its nearest ancestor that has one, then its tag and position among its siblings of that tag
// below it, as `#<id> > div:2 > span:1` (positions count from 1). An element outside the document
// starts at its topmost ancestor's tag instead of an id. The fake browser keys its default answers
// and its replayed answers by it; the recorder (test/browser/door.py) loads the same file into the
// one Chromium, and finds the element a key names with doorElement.
"use strict";

function doorKey(element) {
    const parts = [];
    let current = element;
    while (current && current.nodeType === 1) {
        if (current.id) {
            parts.unshift(`#${current.id}`);
            return parts.join(" > ");
        }
        const tag = current.localName;
        const parent = current.parentElement;
        let position = 1;
        if (parent) {
            for (const sibling of parent.children) {
                if (sibling === current) break;
                if (sibling.localName === tag) position += 1;
            }
        }
        parts.unshift(`${tag}:${position}`);
        current = parent;
    }
    return parts.join(" > ");
}

// The element of `document` a key names, or null where none has it: the inverse of doorKey for an
// element in the document.
function doorElement(key, document) {
    const parts = String(key).split(" > ");
    let current = null;
    let index = 0;
    if (parts[0].startsWith("#")) {
        current = document.getElementById(parts[0].slice(1));
        if (!current) return null;
        index = 1;
    }
    for (; index < parts.length; index += 1) {
        const separator = parts[index].lastIndexOf(":");
        const tag = parts[index].slice(0, separator);
        const position = Number(parts[index].slice(separator + 1));
        const children = current ? [...current.children] : [document.documentElement];
        current = children.filter((child) => child.localName === tag)[position - 1] || null;
        if (!current) return null;
    }
    return current;
}

if (typeof module === "object" && module.exports) module.exports = {doorKey, doorElement};
