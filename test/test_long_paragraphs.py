"""The core's long-paragraph lint through the one-call build (input-model, Long paragraphs): the
core prints the warning once, and the artifact never carries it."""
from __future__ import annotations

import os
import subprocess
import sys


def test_a_one_call_build_warns_once_per_long_paragraph_and_keeps_it_out_of_the_html(tmp_path, core_root) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "manifest.md").write_text("---\ntitle: Long\n---\n- [[chapter]]\n", encoding="utf-8")
    (vault / "chapter.md").write_text("# Chapter\n\n" + "word " * 81 + "\n\nShort.\n\n" + "word " * 90 + "\n",
                                      encoding="utf-8")
    destination = tmp_path / "long.html"

    completed = subprocess.run(
        [sys.executable, "-m", "obs.document", "--source", str(vault / "manifest.md"), "--adapter", "html",
         "--adapter-config", str(core_root / "adapters.json"), "--destination", str(destination)],
        capture_output=True, text=True, env={**os.environ, "UV_OFFLINE": "1"}, check=False)

    assert completed.returncode == 0, completed.stderr
    printed = [line.split(": ")[:3] for line in completed.stderr.splitlines() if "long paragraph" in line]
    assert printed == [["obs-document", "warning", "chapter.md:3"], ["obs-document", "warning", "chapter.md:7"]]
    assert "long paragraph" not in destination.read_text(encoding="utf-8")
