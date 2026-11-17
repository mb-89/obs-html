"""The build's instant: what time a build writes into a page or a PDF (architecture.md, Build time).

``SOURCE_DATE_EPOCH``, where the build's environment sets it, names the instant; the clock does
otherwise. The one module of obs-html that reads the wall clock for what a build writes; the
structure test test/structure/test_architecture.py keeps every other one from it.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping

from obs_html.errors import InputError

VARIABLE = "SOURCE_DATE_EPOCH"
"""The standard variable that fixes a build's time, in whole seconds since 1970-01-01T00:00:00Z."""

LATEST = 253402300799
"""The last second the variable may name, 9999-12-31T23:59:59Z, the last a datetime holds."""

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_DIGITS = re.compile(r"[0-9]+")


def _clock() -> datetime:
    return datetime.now(timezone.utc)


def fixed(environment: Mapping[str, str]) -> datetime | None:
    """The instant ``environment``'s ``SOURCE_DATE_EPOCH`` names, or None where it is unset.

    Computed from the epoch, not with ``datetime.fromtimestamp``, which on Windows refuses years after
    3000."""
    value = environment.get(VARIABLE)
    if value is None:
        return None
    if not _DIGITS.fullmatch(value) or int(value) > LATEST:
        raise InputError("obs-html", VARIABLE, f"is {value!r}, not a whole number of seconds since "
                         f"1970 of at most {LATEST} (9999-12-31T23:59:59Z)",
                         "Set it to digits only, such as 1700000000, or unset it")
    return _EPOCH + timedelta(seconds=int(value))


def instant(environment: Mapping[str, str], clock: Callable[[], datetime] = _clock) -> datetime:
    """The build's instant, an aware UTC datetime: what ``environment``'s ``SOURCE_DATE_EPOCH`` names,
    else the reading of ``clock``."""
    moment = fixed(environment)
    return clock() if moment is None else moment


def iso(moment: datetime) -> str:
    """The form a page records its build time in, ``2023-11-14T22:13:20+00:00``."""
    return moment.isoformat()


def pdf_date(moment: datetime) -> str:
    """The form a PDF's document information dates take, ``D:20231114221320+00'00'``, as Chromium
    writes them."""
    utc = moment.astimezone(timezone.utc)
    return (f"D:{utc.year:04}{utc.month:02}{utc.day:02}{utc.hour:02}{utc.minute:02}{utc.second:02}"
            "+00'00'")
