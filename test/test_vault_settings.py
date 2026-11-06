"""A vault's settings reach the artifact: the core carries the vault's cfg.json keys it does not own
in the Document's projectConfig, and obs-html merges them over its settings, after --config.

Owner: adapters/html/spec/configuration.md ("Vault settings"). Errors are matched by their source
and field path (AGENTS.md), never by wording.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from conftest import FIXTURE
from obs_html import cli
from obs_html.artifact_data import decode_artifact_data


PRESETS = [{"label": "Chapters only", "expression": "depth: /^1$/"}]


def test_a_vault_cfg_json_sets_the_filter_presets_of_a_one_call_build(tmp_path, core_root) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "manifest.md").write_text("---\ntitle: Presets\n---\n- [[chapter]]\n", encoding="utf-8")
    (vault / "chapter.md").write_text("# Chapter\n\nText.\n", encoding="utf-8")
    (vault / "cfg.json").write_text(json.dumps({"schemaVersion": 1, "artifact": {"filterPresets": PRESETS}}),
                                    encoding="utf-8")
    destination = tmp_path / "a.html"

    completed = subprocess.run(
        [sys.executable, "-m", "obs.document", "--source", str(vault), "--adapter", "html",
         "--adapter-config", str(core_root / "adapters.json"), "--destination", str(destination)],
        capture_output=True, text=True, env={**os.environ, "UV_OFFLINE": "1"}, check=False)

    assert completed.returncode == 0, completed.stderr
    assert decode_artifact_data(destination.read_text(encoding="utf-8"))["filterPresets"] == PRESETS


def _document(tmp_path, settings: object) -> object:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["projectConfig"] = {"path": "cfg.json", "settings": settings}
    path = tmp_path / "document.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_the_vault_s_settings_merge_over_the_config_file_key_by_key(tmp_path) -> None:
    config = tmp_path / "settings.json"
    config.write_text(json.dumps({"artifact": {"tablePageSize": 7, "filterPresets": [
        {"label": "From --config", "expression": "depth: /^0$/"}]}}), encoding="utf-8")
    destination = tmp_path / "artifact.html"

    cli.main([str(_document(tmp_path, {"artifact": {"filterPresets": PRESETS}})), str(destination),
              "--config", str(config)])

    model = decode_artifact_data(destination.read_text(encoding="utf-8"))
    assert model["filterPresets"] == PRESETS
    assert model["tablePageSize"] == 7


@pytest.mark.parametrize(("settings", "field"), [
    ({"artifact": {"filterPreset": []}}, "artifact.filterPreset"),
    ({"artefact": {}}, "artefact"),
    ({"artifact": {"tablePageSize": 0}}, "artifact.tablePageSize"),
    ({"report": {}}, "report"),
])
def test_a_vault_setting_the_adapter_does_not_know_names_the_vault_file_and_the_field(
        tmp_path, settings, field, capsys) -> None:
    destination = tmp_path / "artifact.html"

    with pytest.raises(SystemExit) as refused:
        cli.main([str(_document(tmp_path, settings)), str(destination), "--vault-root", "vault"])

    assert refused.value.code == 2
    error = capsys.readouterr().err
    assert f"\n{os.path.join('vault', 'cfg.json')}: {field}: " in f"\n{error}", error
    assert not destination.exists()

