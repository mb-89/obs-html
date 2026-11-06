"""Exclusive per-stage wall-clock durations for ``--timings``, and the warning about a slow stage.

``STAGES`` is the one list of stages; help and baselines read it. Owners mark their work with ``stage(name)``; it costs nothing unless a ``recording()``
is active. A nested stage pauses its enclosing stage, so durations never overlap.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from importlib.resources import files
from time import perf_counter
from typing import Iterator

from jsonschema import Draft202012Validator

from obs_html.errors import InputError, schema_error, warn

BASELINES = files("obs_html") / "timing-baselines.json"
"""Each stage's baseline seconds; adapters/html/spec/architecture.md#build-stage-timings owns how they are measured."""
BASELINES_SCHEMA = files("obs_html") / "timing-baselines.schema.json"
OWNER = "adapters/html/spec/architecture.md#build-stage-timings"

STAGES: dict[str, str] = {
    "render": "HTML projection",
    "figures": "figure fences",
    "open": "loading the HTML in the browser",
    "print": "PDF printing",
    "write": "output file",
}


def load_baselines() -> dict[str, float]:
    """Each registered stage's baseline seconds from the packaged baselines."""
    try:
        value = json.loads(BASELINES.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InputError(BASELINES, "", f"is not JSON ({error.msg} at line {error.lineno}, column {error.colno})",
                         f"Correct the JSON there; see {OWNER}") from error
    schema = json.loads(BASELINES_SCHEMA.read_text(encoding="utf-8"))
    error = schema_error(list(Draft202012Validator(schema).iter_errors(value)), BASELINES,
                         "timing-baselines.schema.json")
    if error:
        raise error
    for name in value["stages"]:
        if name not in STAGES:
            raise InputError(BASELINES, f"stages.{name}", "names no build stage",
                             f"Name one of {', '.join(STAGES)} (obs_html.timings.STAGES), or remove it")
    return value["stages"]


def warn_slower_stages(durations: dict[str, float], baselines: dict[str, float], relative: float,
                       absolute_seconds: float) -> None:
    """Warn about each stage that exceeds its baseline by both thresholds."""
    for name, seconds in durations.items():
        baseline = baselines.get(name)
        if baseline is None:
            continue
        increase = seconds - baseline
        if increase > absolute_seconds and increase > relative * baseline:
            warn(InputError(
                BASELINES, f"stages.{name}", f"took {seconds:.3f} s, {increase / baseline:.0%} and "
                f"{increase:.3f} s over its baseline of {baseline:.3f} s",
                f"Find what made it slower; if the new time is intended, measure the stage again and "
                f"record it there, as {OWNER} says"))


class Timings:
    def __init__(self) -> None:
        self.durations: dict[str, float] = {}
        self._open: list[list] = []

    def add(self, name: str, seconds: float) -> None:
        self.durations[name] = self.durations.get(name, 0.0) + seconds

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        now = perf_counter()
        if self._open:
            enclosing = self._open[-1]
            self.add(enclosing[0], now - enclosing[1])
        self._open.append([name, now])
        try:
            yield
        finally:
            now = perf_counter()
            self.add(name, now - self._open.pop()[1])
            if self._open:
                self._open[-1][1] = now


_active: ContextVar[Timings | None] = ContextVar("obs_html_timings", default=None)


@contextmanager
def recording() -> Iterator[Timings]:
    timings = Timings()
    token = _active.set(timings)
    try:
        yield timings
    finally:
        _active.reset(token)


@contextmanager
def stage(name: str) -> Iterator[None]:
    timings = _active.get()
    if timings is None:
        yield
        return
    with timings.stage(name):
        yield
