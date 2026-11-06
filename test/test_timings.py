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


def test_packaged_baselines_name_only_registered_stages() -> None:
    baselines = timings.load_baselines()
    assert baselines and set(baselines) <= set(timings.STAGES)
    assert all(seconds > 0 for seconds in baselines.values())


def test_every_stage_a_build_records_is_registered(tmp_path, capsys) -> None:
    cli.main([str(FIXTURE), str(tmp_path / "artifact.html"), "--timings"])
    recorded = {line.split()[1] for line in capsys.readouterr().out.splitlines() if line.startswith("Timing:")}
    assert recorded - {"total"} <= set(timings.STAGES), recorded
