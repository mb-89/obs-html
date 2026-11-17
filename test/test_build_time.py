"""The build's instant: SOURCE_DATE_EPOCH, where set, fixes every build time obs-html writes
(spec/architecture.md, Build time)."""
import os
import subprocess
import sys
from datetime import datetime, timezone

import pytest

from conftest import FIXTURE
from obs_html import build_time, cli
from obs_html.artifact_data import decode_artifact_data, same_artifact_content
from obs_html.errors import InputError

VARIABLE = "SOURCE_DATE_EPOCH"
INSTANT = "2023-11-14T22:13:20+00:00"
INVALID = ["", " 1700000000", "+1", "-1", "12.5", "1e9", "abc", "253402300800"]


def _clock() -> datetime:
    return datetime(2026, 11, 17, 3, 0, 40, 123456, tzinfo=timezone.utc)


def test_unset_the_instant_is_the_clocks_reading() -> None:
    assert build_time.instant({}, _clock) == _clock()
    assert build_time.fixed({}) is None


@pytest.mark.parametrize(("value", "iso", "pdf"), [
    ("0", "1970-01-01T00:00:00+00:00", "D:19700101000000+00'00'"),
    ("1700000000", INSTANT, "D:20231114221320+00'00'"),
    ("253402300799", "9999-12-31T23:59:59+00:00", "D:99991231235959+00'00'"),
])
def test_a_set_value_names_its_instant_in_both_forms(value, iso, pdf) -> None:
    moment = build_time.instant({VARIABLE: value}, _clock)
    assert moment.tzinfo is timezone.utc and moment == build_time.fixed({VARIABLE: value})
    assert (build_time.iso(moment), build_time.pdf_date(moment)) == (iso, pdf)


@pytest.mark.parametrize("value", INVALID)
def test_a_set_value_that_is_not_digits_up_to_9999_is_an_input_error(value) -> None:
    with pytest.raises(InputError) as raised:
        build_time.instant({VARIABLE: value}, _clock)
    assert (raised.value.source, raised.value.field) == ("obs-html", VARIABLE)
    assert repr(value) in raised.value.problem


def _timestamp(path) -> str:
    return decode_artifact_data(path.read_text(encoding="utf-8"))["document"]["generation"]["timestamp"]


def test_two_builds_under_one_value_are_byte_for_byte_equal(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(VARIABLE, "1700000000")
    cli.main([str(FIXTURE), str(tmp_path / "a.html")])
    cli.main([str(FIXTURE), str(tmp_path / "b.html")])
    assert (tmp_path / "a.html").read_bytes() == (tmp_path / "b.html").read_bytes()
    assert _timestamp(tmp_path / "a.html") == INSTANT


def test_unset_a_build_records_the_clock_and_two_builds_differ_in_it_alone(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(VARIABLE, raising=False)
    before = datetime.now(timezone.utc)
    cli.main([str(FIXTURE), str(tmp_path / "a.html")])
    cli.main([str(FIXTURE), str(tmp_path / "b.html")])
    after = datetime.now(timezone.utc)
    first, second = (_timestamp(tmp_path / name) for name in ("a.html", "b.html"))
    assert before <= datetime.fromisoformat(first) <= datetime.fromisoformat(second) <= after
    a, b = ((tmp_path / name).read_text(encoding="utf-8") for name in ("a.html", "b.html"))
    assert a != b and same_artifact_content(a, b)


def test_set_a_rebuild_rewrites_a_page_built_without_it_and_keeps_an_identical_one(tmp_path, monkeypatch) -> None:
    page = tmp_path / "page.html"
    monkeypatch.delenv(VARIABLE, raising=False)
    cli.main([str(FIXTURE), str(page)])
    monkeypatch.setenv(VARIABLE, "1700000000")
    cli.main([str(FIXTURE), str(page)])
    assert _timestamp(page) == INSTANT
    os.utime(page, ns=(1_000_000_000, 1_000_000_000))
    cli.main([str(FIXTURE), str(page)])
    assert page.stat().st_mtime_ns == 1_000_000_000


@pytest.mark.parametrize("value", INVALID)
@pytest.mark.parametrize("call", ["render", "check", "export-pdf"])
def test_an_invalid_value_stops_the_build_and_writes_nothing(tmp_path, monkeypatch, capsys, value, call) -> None:
    html = tmp_path / "given.html"
    html.write_text("<!doctype html>", encoding="utf-8")
    arguments = {"render": [str(FIXTURE), str(tmp_path / "out.html")], "check": [str(FIXTURE), "--check"],
                 "export-pdf": ["--export-pdf", str(html), "--output", str(tmp_path / "out.pdf")]}[call]
    monkeypatch.setenv(VARIABLE, value)
    with pytest.raises(SystemExit) as exit_info:
        cli.main(arguments)
    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert f"\nobs-html: {VARIABLE}: " in f"\n{error}", error
    assert sorted(path.name for path in tmp_path.iterdir()) == ["given.html"]


def test_the_calls_that_write_no_build_time_ignore_an_invalid_value(tmp_path, monkeypatch, capsys) -> None:
    page = tmp_path / "page.html"
    monkeypatch.delenv(VARIABLE, raising=False)
    cli.main([str(FIXTURE), str(page)])
    monkeypatch.setenv(VARIABLE, "12.5")
    capsys.readouterr()
    cli.main(["--print-chapter", str(page), "home"])
    cli.main(["--extract-comments", str(page)])
    assert capsys.readouterr().out


def _one_call_build(tmp_path, core_root, value: str) -> subprocess.CompletedProcess:
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    (vault / "manifest.md").write_text("---\ntitle: Dated\n---\n- [[chapter]]\n", encoding="utf-8")
    (vault / "chapter.md").write_text("# Chapter\n\nText.\n", encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "obs.document", "--source", str(vault / "manifest.md"), "--adapter", "html",
         "--adapter-config", str(core_root / "adapters.json"), "--destination", str(tmp_path / "dated.html")],
        capture_output=True, text=True, env={**os.environ, "UV_OFFLINE": "1", VARIABLE: value}, check=False)


def test_through_the_core_the_adapter_reads_the_variable(tmp_path, core_root) -> None:
    built = _one_call_build(tmp_path, core_root, "1700000000")
    assert built.returncode == 0, built.stderr
    assert _timestamp(tmp_path / "dated.html") == INSTANT

    (tmp_path / "dated.html").unlink()
    refused = _one_call_build(tmp_path, core_root, "12.5")
    assert refused.returncode != 0
    assert f"obs-html: {VARIABLE}: " in refused.stderr, refused.stderr
    assert not (tmp_path / "dated.html").exists()
