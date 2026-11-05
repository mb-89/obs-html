"""Build small contract-valid Documents for runtime tests, as the core would emit them."""
from __future__ import annotations

from obs_html.render import STRUCTURAL


def text(value: str) -> dict:
    return {"type": "text", "attrs": {}, "children": [], "text": value}


def paragraph(*children: str | dict) -> dict:
    return {"type": "paragraph", "attrs": {},
            "children": [text(child) if isinstance(child, str) else child for child in children]}


def heading(level: int, title: str) -> dict:
    return {"type": "section", "attrs": {"level": level}, "children": [text(title)]}


def node(kind: str, **attrs: object) -> dict:
    return {"type": kind, "attrs": attrs, "children": []}


def chapter(identifier: str, title: str, *content: dict, metadata: dict | None = None,
            children: tuple[dict, ...] = ()) -> dict:
    nodes = list(content)
    if metadata is not None:
        nodes.insert(0, node("markdown-frontmatter", metadata=metadata))
    result = {"id": identifier, "title": title, "content": nodes, "children": list(children)}
    if metadata is not None:
        result["metadata"] = metadata
    return result


def document(title: str, *chapters: dict, metadata: dict | None = None,
             abstract: tuple[dict, ...] = (), records: tuple[dict, ...] = ()) -> dict:
    metadata = {"title": title, **(metadata or {})}
    result = {
        "schemaVersion": 1,
        "manifest": {"title": title, "metadata": metadata,
                     "abstract": [node("manifest"), node("markdown"), *abstract]},
        "chapters": list(chapters), "links": [], "assets": [], "records": list(records),
        "semanticResources": [], "diagnostics": [], "capabilities": [],
    }
    used: set[str] = set()

    def collect(nodes: list[dict]) -> None:
        for item in nodes:
            if item["type"] not in STRUCTURAL:
                used.add(item["type"])
            collect(item["children"])

    collect(result["manifest"]["abstract"])
    stack = list(chapters)
    while stack:
        current = stack.pop()
        collect(current["content"])
        stack.extend(current["children"])
    result["capabilities"] = sorted(used)
    return result
