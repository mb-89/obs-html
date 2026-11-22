"""test/first_chapter.py, CI's median judgment of the spec artifact's first chapter, on fake runs.

Reader: whoever changes how CI judges the first chapter's second (test/first_chapter.py).
"""
import ast
from pathlib import Path

import pytest

import first_chapter

STARTUP_TEST = Path(__file__).with_name("test_startup_browser.py")


def runs(*painted: float | None, budget: float = 1000, failure: str = "") -> list:
    return [(time, budget, failure) for time in painted]


def test_the_median_is_the_middle_of_five_runs_whatever_their_order() -> None:
    assert first_chapter.median([1800, 400, 900, 950, 420]) == 900
    assert first_chapter.RUNS == 5


@pytest.mark.parametrize(("median", "blocking", "expected"), [
    (999, False, "pass"), (1000, False, "pass"), (1000, True, "pass"),
    (1001, False, "warn"), (1001, True, "fail")])
def test_a_median_over_the_budget_warns_until_it_blocks(median, blocking, expected) -> None:
    assert first_chapter.verdict(median, 1000, blocking) == expected


def test_the_step_prints_every_time_the_median_and_its_own_time() -> None:
    lines, code = first_chapter.judge(runs(300, 1200, 500, 450, 2000), False, 61.4, actions=True)

    assert code == 0
    assert [line for line in lines if " run " in line] == [
        f"first chapter: run {index} painted {time} ms" for index, time in
        enumerate((300, 1200, 500, 450, 2000), 1)]
    assert "median 500 ms of 5 runs" in lines[-2] and "within its 1000 ms budget" in lines[-2]
    assert "the step took 61 s" in lines[-2]
    assert lines[-1] == f"::notice title={first_chapter.TITLE}::{lines[-2]}"


def test_a_slow_median_warns_and_stays_green_while_not_blocking() -> None:
    lines, code = first_chapter.judge(runs(1100, 1200, 900, 1300, 1050), False, 50, actions=True)

    assert code == 0
    assert lines[-1].startswith(f"::warning title={first_chapter.TITLE}::")
    assert "median 1100 ms" in lines[-1] and "warn-only" in lines[-1]


def test_a_slow_median_fails_once_blocking() -> None:
    lines, code = first_chapter.judge(runs(1100, 1200, 900, 1300, 1050), True, 50, actions=True)

    assert code == 1
    assert lines[-1].startswith(f"::error title={first_chapter.TITLE}::") and "blocking" in lines[-1]


@pytest.mark.parametrize("blocking", [False, True])
def test_a_failed_run_is_an_error_that_blocks_only_once_blocking(blocking) -> None:
    measured = [*runs(400, 500), (None, None, "AssertionError: order"), *runs(450, 420)]
    lines, code = first_chapter.judge(measured, blocking, 50, actions=True)

    assert code == (1 if blocking else 0)
    assert "first chapter: run 3 painted no time" in lines
    assert any(line.startswith("first chapter: run 3 failed: AssertionError: order") for line in lines)
    assert lines[-1].startswith("::error ") and "no median is judged" in lines[-1]


def test_annotations_are_written_only_on_github_actions() -> None:
    lines, _code = first_chapter.judge(runs(400, 400, 400, 400, 400), False, 5, actions=False)

    assert not any(line.startswith("::") for line in lines)


def test_main_runs_the_test_five_times_and_judges_their_median(capsys) -> None:
    times = iter([10.0, 52.0])
    called: list[int] = []

    def run(index, folder, environment):
        called.append(index)
        return 1500 if index in (1, 2, 3) else 200, 1000, ""

    code = first_chapter.main({"GITHUB_ACTIONS": "true"}, clock=lambda: next(times), run=run)

    printed = capsys.readouterr().out
    assert called == [1, 2, 3, 4, 5] and code == 0
    assert "median 1500 ms" in printed and "the step took 42 s" in printed and "::warning " in printed


def test_the_median_variable_is_the_startup_tests() -> None:
    constants = {target.id: node.value.value for node in ast.parse(STARTUP_TEST.read_text(encoding="utf-8")).body
                 if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name)
                 and isinstance(node.value, ast.Constant)}
    assert constants["MEDIAN_VARIABLE"] == first_chapter.MEDIAN_VARIABLE
