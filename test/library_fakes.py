"""The switch between the browser libraries and their doors' fakes for every artifact a test builds.

Reader: a test that builds an artifact, and whoever changes a library door or its fake.

The artifact reaches each browser library through its door (architecture.md, Library doors;
obs_html/libraries.py). ``install``, which test/conftest.py calls as the test process starts, makes
every in-process build embed each door's fake (test/fakes/<door>.js) in place of the library and
its door: a page then evaluates a few kilobytes instead of Plotly, math.js and pdf-lib (obs
quality.md, Testing boundaries). A build inside ``real()`` embeds the real libraries; only the
tests test/structure/test_quality.py names (REAL_LIBRARY_TESTS) enter it. The plotting library's
CDN delivery is no embedded library and is built as it is.

``mode`` names the libraries a build embeds now; the shared builds (test/artifacts.py and
test/conftest.py, built_once) keep the builds of each mode apart.
"""
from __future__ import annotations

import contextlib
from pathlib import Path

from obs_html import libraries

FAKES = Path(__file__).parent / "fakes"
FAKE = "fake-libraries"
REAL = "real-libraries"
_real_element = libraries.element
_mode = [REAL]


def fake(key: str) -> str:
    """The door's fake, where the artifact would embed the library ``key`` and its door: in the
    library's element, marked as a fake."""
    library = libraries.LIBRARIES[key]
    source = (FAKES / library.door).read_text(encoding="utf-8").replace("</script", "<\\/script")
    return f'<script id="{library.element}" data-library-fake>{source}</script>'


def _element(key: str) -> str:
    return _real_element(key) if _mode[-1] == REAL else fake(key)


def install() -> None:
    """Make every later build of this process embed the doors' fakes."""
    libraries.element = _element
    _mode[:] = [FAKE]


@contextlib.contextmanager
def real():
    """Builds inside embed the real libraries."""
    _mode.append(REAL)
    try:
        yield
    finally:
        _mode.pop()


def mode() -> str:
    """The libraries a build embeds now: FAKE or REAL."""
    return _mode[-1]
