"""Which canaries an artifact runs, and which of them cannot decide, as their owners declare it.

Reader: a test that expects the canaries' results of an artifact it opens.

The feature registry (obs_html.features, FEATURES) owns which features an artifact carries, in
registry order, and so which canaries it runs. Each canary, canaries/<key>.js, owns how it
decides: one that asks capabilities.js's ``sandboxAllows`` cannot decide where an enclosing frame
hides its sandbox flags, and one that reads the parameter obs-html serve adds to the page's URL
(obs_html.serve.PARAMETER) cannot decide on a page obs-html serve did not serve. A test derives its
lists from here, so a feature added to the registry is expected without a literal edit.
"""
from importlib.resources import files

from obs_html import features
from obs_html.artifact_data import decode_artifact_data
from obs_html.serve import PARAMETER

# The capabilities.js helper a canary asks for a sandbox token of its frame.
SANDBOX_FLAGS = "sandboxAllows("


def canary_source(feature: features.Feature) -> str:
    """The feature's canary script, as the package ships it."""
    return files("obs_html").joinpath(feature.canary).read_text(encoding="utf-8")


def canaries(html: str) -> list[str]:
    """The key of each canary an artifact without a trusted runtime runs, in registry order."""
    return [feature.key for feature in features.included(decode_artifact_data(html), False)]


def undecided_where_flags_hidden(html: str) -> list[str]:
    """The canaries of ``canaries(html)`` that cannot decide in a frame that hides its sandbox flags,
    on a page obs-html serve did not serve, in registry order."""
    undecided = []
    for feature in features.included(decode_artifact_data(html), False):
        source = canary_source(feature)
        if SANDBOX_FLAGS in source or PARAMETER in source:
            undecided.append(feature.key)
    return undecided
