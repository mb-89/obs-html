"""The source archive: the ZIP obs-html packages from a Document's ``sourceArchive``.

Reader: whoever changes what the archive holds, how the artifact embeds it or how it reaches a
PDF; input-model.md, "Optional reproduction archive", owns the behaviour.

The core carries the vault's source files only when the build asks for them (obs-document
--embed-source; obs architecture, Source archive). This module packages them as the interim
adapter does, each file at ``vault/<path>``, and makes the ZIP the one owner of every asset's
bytes it holds: a reader image or download whose bytes are a member becomes an ``obs-asset:``
reference to a descriptor naming the member (payloads.js resolves it). The reader downloads the
ZIP as ``ARCHIVE_NAME`` through the downloads feature (features.py); ``attach`` puts it into a
saved PDF.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from io import BytesIO
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import NameObject, create_string_object

from obs_html.errors import DOCUMENT_OF, InputError

ARCHIVE_NAME = "obs-html-source.zip"
"""The download's and the PDF attachment's file name, the interim adapter's."""
_TIME = (1980, 1, 1, 0, 0, 0)
"""Every member's timestamp, so the same files give the same ZIP."""
_ISLAND = re.compile(r'<script id="obs-source-archive" type="application/octet-stream">([A-Za-z0-9+/=\s]*)</script>')
_URI = re.compile(r"""(?P<prefix>\b(?:src|href)\s*=\s*)(?P<quote>["'])"""
                  r"""(?P<uri>data:[^"'\s<>]+;base64,[A-Za-z0-9+/=]+)(?P=quote)""", re.IGNORECASE)
_SHARED_MIME = re.compile(r"image/[a-z0-9.+-]+|application/(?:pdf|octet-stream|json)|text/plain")
"""The media types payloads.js serves from a ZIP member; other bytes keep their data URI."""


def package(document: dict, embed_attachments: bool = False) -> bytes | None:
    """The ZIP of the Document's source files, or None for a Document built without them: each file
    at ``vault/<path>``, the interim's ``source-inventory.json`` (which the reader's archive
    transactions update; this archive has no generator) and ``REPRODUCE.txt``, the rebuild command
    with the build's ``embed_attachments`` choice."""
    archive = document.get("sourceArchive")
    if archive is None:
        return None
    source = f"{DOCUMENT_OF}{document['manifest']['path']}"
    assets = {item["id"]: item for item in document["assets"]}
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zipped:
        for index, item in enumerate(archive["files"]):
            if "asset" in item:
                asset = assets.get(item["asset"])
                if asset is None or "data" not in asset:
                    problem = "names no asset of the Document" if asset is None else "names an asset without bytes"
                    raise InputError(source, f"sourceArchive.files[{index}].asset",
                                     f"is {item['asset']!r}, which {problem}",
                                     "Rebuild the Document with the current obs core (obs-document --embed-source)")
                data = asset["data"]
            else:
                data = item["data"]
            zipped.writestr(_member(f"vault/{item['path']}"), base64.b64decode(data))
        paths = sorted(item["path"] for item in archive["files"])
        zipped.writestr(_member("source-inventory.json"), json.dumps({"vault": paths, "generator": []},
                                                                       separators=(",", ":")))
        option = " --adapter-option embed-attachments=true" if embed_attachments else ""
        zipped.writestr(_member("REPRODUCE.txt"), (
            "Source archive\n\n"
            "vault/ holds the vault's source files as the build disclosed them (obs-document\n"
            "--embed-source); it does not hold obs or obs-html. With both installed, rebuild from this\n"
            "extracted directory with:\n"
            f"  obs-document --source vault/{document['manifest']['path']} --adapter html "
            f"--destination document.html --embed-source{option}\n"
            "Append --execute-commands where the vault's command fences should run again.\n"
            "Documents include build timestamps; byte-identical output is not promised.\n"))
    return buffer.getvalue()


def _member(name: str) -> ZipInfo:
    member = ZipInfo(name, _TIME)
    member.compress_type = ZIP_DEFLATED
    return member


def share(model: dict, archive: bytes) -> dict:
    """``model`` with every data URI whose bytes are a ZIP member replaced by an ``obs-asset:``
    reference, its descriptor in ``embeddedAssets``: the ZIP alone holds those bytes."""
    with ZipFile(BytesIO(archive)) as zipped:
        members = {hashlib.sha256(zipped.read(info)).hexdigest(): info.filename
                   for info in zipped.infolist() if not info.is_dir()}
    assets = dict(model.get("embeddedAssets", {}))

    def descriptor(uri: str) -> dict | None:
        header, encoded = uri.split(",", 1)
        mime = header[5:].split(";", 1)[0]
        digest = hashlib.sha256(base64.b64decode(encoded)).hexdigest()
        if digest not in members or not _SHARED_MIME.fullmatch(mime):
            return None
        return {"archivePath": members[digest], "mime": mime, "sha256": digest}

    for key, uri in list(assets.items()):
        if isinstance(uri, str):
            assets[key] = descriptor(uri) or uri

    def replace(match: re.Match[str]) -> str:
        shared = descriptor(match["uri"])
        if shared is None:
            return match[0]
        key = hashlib.sha256(match["uri"].encode("ascii")).hexdigest()
        assets[key] = shared
        return f'{match["prefix"]}{match["quote"]}obs-asset:{key}{match["quote"]}'

    def transform(value: object) -> object:
        if isinstance(value, str):
            return _URI.sub(replace, value)
        if isinstance(value, list):
            return [transform(item) for item in value]
        if isinstance(value, dict):
            return {key: transform(item) for key, item in value.items()}
        return value

    shared = transform(model)
    shared["embeddedAssets"] = assets
    shared["sourceArchiveComplete"] = True
    return shared


def island(archive: bytes) -> str:
    """The artifact's archive island, which the reader downloads and resolves assets from."""
    return (f'<script id="obs-source-archive" type="application/octet-stream">'
            f'{base64.b64encode(archive).decode("ascii")}</script>')


def embedded(artifact: str, source: object) -> bytes | None:
    """The ZIP an artifact embeds, or None without one; ``source`` names the artifact in errors."""
    match = _ISLAND.search(artifact)
    if match is None:
        if 'id="obs-source-archive"' in artifact:
            raise InputError(source, "obs-source-archive", "is no base64 island", "Rebuild the artifact "
                             "with obs-document --embed-source")
        return None
    try:
        content = base64.b64decode(re.sub(r"\s", "", match[1]), validate=True)
        with ZipFile(BytesIO(content)) as zipped:
            corrupt = zipped.testzip()
    except (binascii.Error, BadZipFile, OSError, EOFError) as error:
        raise InputError(source, "obs-source-archive", f"is no readable ZIP ({error})",
                         "Rebuild the artifact with obs-document --embed-source") from error
    if corrupt is not None:
        raise InputError(source, "obs-source-archive", f"has the corrupt member {corrupt}",
                         "Rebuild the artifact with obs-document --embed-source")
    return content


def attach(pdf: bytes, archive: bytes, source: object) -> bytes:
    """``pdf`` with ``archive`` attached as ``ARCHIVE_NAME``, as the interim adapter attaches it."""
    operation = "--attach-source-to-pdf"
    try:
        reader = PdfReader(BytesIO(pdf), strict=True)
        if reader.is_encrypted:
            raise InputError(source, operation, "is encrypted", "Attach the ZIP to an unencrypted PDF")
        if reader.trailer["/Root"].get("/Perms") or any(
                field.get("/FT") == "/Sig" for field in (reader.get_fields() or {}).values()):
            raise InputError(source, operation, "is signed, so attaching would break its signature",
                             "Attach the ZIP before signing the PDF")
        if ARCHIVE_NAME in reader.attachments:
            raise InputError(source, operation, f"already holds {ARCHIVE_NAME}",
                             "Attach to the PDF as printed, without a source ZIP")
        writer = PdfWriter(clone_from=reader)
        attachment = writer.add_attachment(ARCHIVE_NAME, archive)
        attachment.subtype = NameObject("/application/zip")
        attachment.description = create_string_object("The vault's source files")
        output = BytesIO()
        writer.write(output)
        return output.getvalue()
    except PdfReadError as error:
        raise InputError(source, operation, f"is no readable PDF ({error})",
                         "Name a PDF saved from the artifact") from error
