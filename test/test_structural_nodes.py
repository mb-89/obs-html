"""Structural nodes: every type the core's Document schema lists renders, and no node is dropped.

The structural types are the core's (``$defs/structuralType`` of ``src/obs/document.schema.json``);
the core-built Document ``fixtures/documents/structural.json`` holds each Markdown construct as the
core emits it (its vault is ``structural`` in ``fixtures/build_documents.py``).
"""
import json
import re
from pathlib import Path

import pytest

from conftest import CORE_ROOT, ROOT
from documents import chapter, document as build, node, paragraph, text
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.render import RenderError, render


CONFIG = load_config()
SCHEMA = json.loads((CORE_ROOT / "src" / "obs" / "document.schema.json").read_text(encoding="utf-8"))
STRUCTURAL_TYPES = SCHEMA["$defs"]["structuralType"]["enum"]
STRUCTURAL = json.loads((ROOT / "test" / "fixtures" / "documents" / "structural.json").read_text(encoding="utf-8"))


def test_the_adapter_reads_the_structural_types_from_the_core_schema() -> None:
    from obs_html.render import STRUCTURAL as adapter_types

    assert sorted(adapter_types) == sorted(STRUCTURAL_TYPES)
