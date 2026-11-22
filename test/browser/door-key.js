// An element's key in the browser door (test/browser/browser-door.md, Recording and replay): the
// id of its nearest ancestor that has one, then its tag and position among its siblings of that tag
// below it, as `#<id> > div:2 > span:1` (positions count from 1). An element outside the document
// starts at its topmost ancestor's tag instead of an id. The fake browser keys its default answers
// by it; the recorder and the fake's replay load the same function.
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

if (typeof module === "object" && module.exports) module.exports = {doorKey};
else globalThis.obsDoorKey = doorKey;
