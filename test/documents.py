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


def frontmatter(metadata: dict, fields: dict[str, list[str | dict]] | None = None) -> dict:
    """A ``markdown-frontmatter`` node; ``fields`` maps a dotted field path to the inline nodes the
    core parsed its string into (a string is a text node), as one ``field`` node each."""
    result = node("markdown-frontmatter", metadata=metadata)
    result["children"] = [{"type": "field", "attrs": {"name": name},
                           "children": [text(item) if isinstance(item, str) else item for item in items]}
                          for name, items in (fields or {}).items()]
    return result


def field_nodes(fields: dict) -> list[dict]:
    """A note record's ``fieldNodes`` for values that are plain text: one text field node per
    nonempty string, by dotted path, as the core parses a string without inline Markdown."""
    def walk(value: object, name: str):
        items = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else ()
        for key, item in items:
            yield from walk(item, f"{name}.{key}" if name else str(key))
        if isinstance(value, str) and value:
            yield {"type": "field", "attrs": {"name": name}, "children": [text(value)]}
    return list(walk(fields, ""))


def chapter(identifier: str, title: str, *content: dict, metadata: dict | None = None,
            fields: dict[str, list[str | dict]] | None = None, children: tuple[dict, ...] = ()) -> dict:
    nodes = list(content)
    if metadata is not None:
        nodes.insert(0, frontmatter(metadata, fields))
    result = {"id": identifier, "title": title, "content": nodes, "children": list(children)}
    if metadata is not None:
        result["metadata"] = metadata
    return result


def document(title: str, *chapters: dict, metadata: dict | None = None,
             fields: dict[str, list[str | dict]] | None = None,
             abstract: tuple[dict, ...] = (), records: tuple[dict, ...] = ()) -> dict:
    """``fields`` are the manifest frontmatter's field nodes (see frontmatter)."""
    metadata = {"title": title, **(metadata or {})}
    manifest_frontmatter = [frontmatter(metadata, fields)] if fields else []
    result = {
        "schemaVersion": 1,
        "manifest": {"title": title, "metadata": metadata,
                     "abstract": [node("manifest"), node("markdown"), *manifest_frontmatter, *abstract]},
        "chapters": list(chapters), "links": [], "assets": [],
        "records": [{**record, "fieldNodes": field_nodes(record["fields"])}
                    if record["type"] == "note" and "fieldNodes" not in record else record for record in records],
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
