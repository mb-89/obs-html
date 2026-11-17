"""Portable PDF links: a printed PDF's links to files of the builder's machine, made relative.

Pure: bytes in, bytes out; it reads no file and starts no browser (spec/artifact-ui.md, Pages and
PDF, owns what the links name)."""
from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Iterator
from urllib.parse import quote, urlsplit
from urllib.request import url2pathname

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject


def portable(pdf: bytes, printed: Path, companion: str) -> bytes:
    """``pdf`` with each link to a ``file:`` URI made relative: one to ``printed``, the absolute path of
    the HTML the browser printed, names ``./`` and ``companion`` with the URI's fragment; one to another
    file names its path from ``printed``'s folder, and one with no such path loses its link. A PDF with
    no ``file:`` link is returned as given."""
    reader = PdfReader(BytesIO(pdf))
    if next(_file_links(reader.pages), None) is None:
        return pdf
    writer = PdfWriter(clone_from=reader)
    for page in writer.pages:
        dropped = []
        for annotation, action in _file_links([page]):
            uri = _relative(str(action["/URI"]), printed, companion)
            if uri is None:
                dropped.append(annotation)
            else:
                action[NameObject("/URI")] = TextStringObject(uri)
        if dropped:
            annotations = page["/Annots"].get_object()
            page[NameObject("/Annots")] = ArrayObject(
                entry for entry in annotations if not any(entry.get_object() is gone for gone in dropped))
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _relative(uri: str, printed: Path, companion: str) -> str | None:
    """The relative URI the ``file:`` URI ``uri`` becomes in a PDF printed from ``printed`` (see
    portable), or None where its file has no path relative to ``printed``'s folder."""
    parts = urlsplit(uri)
    location = f"//{parts.netloc}{parts.path}" if parts.netloc not in ("", "localhost") else parts.path
    target = Path(url2pathname(location))
    if target == printed:
        return f"./{quote(companion, safe='')}" + (f"#{parts.fragment}" if parts.fragment else "")
    try:
        path = Path(os.path.relpath(target, printed.parent)).as_posix()
    except ValueError:  # Another Windows drive: no relative path.
        return None
    query = f"?{parts.query}" if "?" in uri.split("#", 1)[0] else ""
    fragment = f"#{parts.fragment}" if "#" in uri else ""
    return ("" if path.startswith("../") else "./") + quote(path, safe="/") + query + fragment


def _file_links(pages) -> Iterator[tuple[DictionaryObject, DictionaryObject]]:
    """Each link annotation of ``pages`` whose action opens a ``file:`` URI, with that action."""
    for page in pages:
        for entry in page.get("/Annots") or []:
            annotation = entry.get_object()
            action = annotation.get("/A")
            action = action.get_object() if action is not None else None
            if (annotation.get("/Subtype") == "/Link" and isinstance(action, DictionaryObject)
                    and action.get("/S") == "/URI"
                    and urlsplit(str(action.get("/URI", ""))).scheme.lower() == "file"):
                yield annotation, action
