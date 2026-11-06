"""A trusted runtime bundle through the core: obs-document --adapter html --adapter-option
trusted-runtime-bundle=ID=PATH embeds it, and the source archive's rebuild embeds it again.

Reader: whoever changes how a one-call build trusts a runtime bundle; obs cli.md, "Adapter
options", owns the vault-file option, and cli.md, "Trusted runtime", the bundle. The bundle is a
file of the vault, named only by the explicit option, as the interim's --trusted-runtime-bundle
was. The rebuild runs the step reproduce.py composes, offline, with this checkout standing in for
the clone, as test_spec_archive_rebuild.py does.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import CORE_ROOT

RUNTIME = "globalThis.trustedFixture = '</script>';\n"
OPTION = "trusted-runtime-bundle=app-v1=apps/runtime.js"


def _vault(folder: Path) -> Path:
    vault = folder / "vault"
    (vault / "apps").mkdir(parents=True)
    (vault / "apps" / "runtime.js").write_text(RUNTIME, encoding="utf-8")
    (vault / "notes.txt").write_text("not code\n", encoding="utf-8")
    (vault / "manifest.md").write_text("---\ntitle: Trusted\n---\n- [[chapter]]\n", encoding="utf-8")
    (vault / "chapter.md").write_text("# Chapter\n\nText.\n", encoding="utf-8")
    return vault


def _one_call(vault: Path, destination: Path, *options: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "obs.document", "--source", str(vault / "manifest.md"), "--adapter", "html",
         "--adapter-config", str(CORE_ROOT / "adapters.json"), "--destination", str(destination), *options],
        capture_output=True, text=True, env={**os.environ, "UV_OFFLINE": "1"}, check=False)


def _embeds_the_bundle(html: str) -> None:
    assert '<meta name="obs-trusted-runtime" content="app-v1">' in html
    assert 'id="trusted-application-runtime"' in html
    assert "globalThis.trustedFixture = '<\\/script>';" in html


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    """The artifact of a one-call build that names the bundle, with its source archive."""
    folder = tmp_path_factory.mktemp("trusted")
    destination = folder / "out" / "trusted.html"
    completed = _one_call(_vault(folder), destination, "--adapter-option", OPTION, "--embed-source")
    assert completed.returncode == 0, completed.stderr
    return destination


def test_a_one_call_build_embeds_the_named_trusted_bundle(built) -> None:
    _embeds_the_bundle(built.read_text(encoding="utf-8"))


def test_without_the_option_no_vault_file_becomes_a_runtime(tmp_path) -> None:
    destination = tmp_path / "plain.html"

    assert _one_call(_vault(tmp_path), destination).returncode == 0

    assert "trusted-application-runtime" not in destination.read_text(encoding="utf-8")


def test_a_bundle_that_is_no_js_file_fails_naming_the_option(tmp_path) -> None:
    completed = _one_call(_vault(tmp_path), tmp_path / "out.html", "--adapter-option",
                          "trusted-runtime-bundle=app-v1=notes.txt")

    assert completed.returncode != 0 and "--trusted-runtime-bundle" in completed.stderr
    assert not (tmp_path / "out.html").exists()
