import json
from pathlib import Path

import pytest

from conftest import FIXTURE
from obs_html import cli, timings


def test_nested_stages_record_exclusive_durations(monkeypatch) -> None:
    clock = iter([0.0, 1.0, 3.0, 6.0])
    monkeypatch.setattr(timings, "perf_counter", lambda: next(clock))
    with timings.recording() as recorded:
        with timings.stage("outer"):
            with timings.stage("inner"):
                pass
    assert recorded.durations == {"outer": 4.0, "inner": 2.0}


def test_stages_outside_a_recording_are_free(monkeypatch) -> None:
    monkeypatch.setattr(timings, "perf_counter", lambda: (_ for _ in ()).throw(AssertionError("timed")))
    with timings.stage("free"):
        pass


# The baseline warning, at the command: an injected clock steps one second per reading, so the
# write stage (one reading on entry, one on exit, nothing nested) always takes 1.000 s.
def _stepping_clock(monkeypatch) -> None:
    readings = iter(range(1_000_000))
    clock = lambda: float(next(readings))
    monkeypatch.setattr(timings, "perf_counter", clock)
    monkeypatch.setattr(cli, "perf_counter", clock)


def _baselines(tmp_path, monkeypatch, stages: dict | str) -> Path:
    path = tmp_path / "timing-baselines.json"
    text = stages if isinstance(stages, str) else json.dumps({"schemaVersion": 1, "stages": stages})
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(timings, "BASELINES", path)
    return path


@pytest.mark.parametrize("baseline, thresholds, warns", [
    (0.5, {}, True),  # 0.5 s and 100 % over: both packaged thresholds (0.25 s, 50 %).
    (0.7, {}, False),  # 0.3 s but 43 % over: only the absolute threshold.
    (0.5, {"absoluteThresholdSeconds": 0.6}, False),  # 100 % but 0.5 s over: only the relative one.
])
def test_timings_warn_about_a_stage_over_both_thresholds_of_its_baseline(
        tmp_path, monkeypatch, capsys, baseline, thresholds, warns) -> None:
    _stepping_clock(monkeypatch)
    path = _baselines(tmp_path, monkeypatch, {"write": baseline})
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"timings": thresholds}), encoding="utf-8")
    cli.main([str(FIXTURE), str(tmp_path / "artifact.html"), "--timings", "--config", str(settings)])
    output = capsys.readouterr()
    assert "Timing: write 1.000 s" in output.out
    warnings = [line for line in output.err.splitlines() if line.startswith(f"Warning: {path}: ")]
    assert [line.split(": ")[2] for line in warnings] == (["stages.write"] if warns else []), output.err


def test_without_timings_no_baseline_is_read(tmp_path, monkeypatch, capsys) -> None:
    _stepping_clock(monkeypatch)
    path = _baselines(tmp_path, monkeypatch, "not JSON")
    cli.main([str(FIXTURE), str(tmp_path / "artifact.html")])
    assert str(path) not in capsys.readouterr().err


def test_packaged_baselines_name_only_registered_stages() -> None:
    baselines = timings.load_baselines()
    assert baselines and set(baselines) <= set(timings.STAGES)
    assert all(seconds > 0 for seconds in baselines.values())


def test_every_stage_a_build_records_is_registered(tmp_path, capsys) -> None:
    cli.main([str(FIXTURE), str(tmp_path / "artifact.html"), "--timings"])
    recorded = {line.split()[1] for line in capsys.readouterr().out.splitlines() if line.startswith("Timing:")}
    assert recorded - {"total"} <= set(timings.STAGES), recorded


@pytest.mark.parametrize("stages, field", [
    ({"write": 0}, "stages.write"),
    ({"unknown": 1.0}, "stages.unknown"),
    ("not JSON", "top level"),
])
def test_invalid_baselines_name_the_baselines_file_and_the_field(tmp_path, monkeypatch, capsys, stages, field) -> None:
    path = _baselines(tmp_path, monkeypatch, stages)
    with pytest.raises(SystemExit) as exit_info:
        cli.main([str(FIXTURE), str(tmp_path / "artifact.html"), "--timings"])
    assert exit_info.value.code == 2
    assert f"\n{path}: {field}: " in f"\n{capsys.readouterr().err}"
