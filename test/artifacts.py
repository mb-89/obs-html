"""The artifacts browser tests open, each rendered once per test process from its Document.

Reader: a browser test that opens an artifact of a Document it writes itself.

A browser test never renders on its own: it asks
``artifact_html`` for the artifact of its Document and render options, and every later ask for
the same Document and options, in any test of the process, reads the same artifact. The module's
tests share one worker of the complete suite, so a Document is rendered once per run. An input
of many modules, or one built from a vault by the core, is built once per run by a fixture
through ``built_once`` (test/conftest.py) instead.
"""
import json

from obs_html.config import load_config
from obs_html.render import render

_RENDERED: dict[str, str] = {}


def artifact_html(document: dict, **options) -> str:
    """The artifact this adapter renders from the Document with the packaged configuration and ``options``."""
    key = json.dumps([document, sorted(options.items())], sort_keys=True, default=repr)
    if key not in _RENDERED:
        _RENDERED[key] = render(document, load_config(), **options)
    return _RENDERED[key]
