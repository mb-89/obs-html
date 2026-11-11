"""The browser libraries the artifact embeds, each behind one door (architecture.md, Library doors).

Reader: whoever changes how a library is packaged, delivered or reached.

This is the one module that reads a library's packaged files: the plotting library (Plotly,
``vendor/plotly-basic.min.js``), the maths library (math.js, packaged from its npm lockfile
``maths/package-lock.json`` by hatch_build.py into ``vendor/maths``) and the PDF library
(pdf-lib, ``vendor/pdf-lib.min.js``). ``element`` writes what embeds one: the library with its
licence, then its door, the one script that calls it (``plotly-door.js``, ``maths-door.js``,
``pdf-door.js``). The renderer asks it for each library its included features need (features.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files


@dataclass(frozen=True)
class Library:
    """A browser library: ``element`` is the id of the script that embeds it, ``door`` the script
    that calls it, ``code`` and ``licences`` its packaged files below ``obs_html``."""

    key: str
    element: str
    door: str
    code: tuple[str, ...]
    licences: tuple[tuple[str, ...], ...]


LIBRARIES = {library.key: library for library in (
    Library("plotting", "plotly-script", "plotly-door.js", ("vendor", "plotly-basic.min.js"),
            (("vendor", "plotly.LICENSE"), ("vendor", "plotly-basic.min.js.LICENSE.txt"))),
    Library("maths", "maths-script", "maths-door.js", ("vendor", "maths", "math.js"),
            (("vendor", "maths", "LICENSE"), ("vendor", "maths", "math.js.LICENSE.txt"))),
    Library("pdf", "pdf-library-script", "pdf-door.js", ("vendor", "pdf-lib.min.js"),
            (("vendor", "pdf-lib.LICENSE"),)),
)}


def _read(*parts: str) -> str:
    return files("obs_html").joinpath(*parts).read_text(encoding="utf-8")


def _script(source: str) -> str:
    """``source`` as a script element's content: a ``</script`` in it cannot end the element."""
    return source.replace("</script", "<\\/script")


def code(key: str) -> str:
    """The library's code as the package ships it."""
    return _read(*LIBRARIES[key].code)


def licence(key: str) -> str:
    """The library's licences, which ship with it, as one comment's text."""
    return "\n".join(_read(*parts) for parts in LIBRARIES[key].licences).replace("*/", "* /")


def door(key: str) -> str:
    """The element of the library's door, which follows the library."""
    library = LIBRARIES[key]
    return f'<script id="{library.door.removesuffix(".js")}-script">{_script(_read(library.door))}</script>'


def element(key: str) -> str:
    """What embeds the library: the library with its licence, then its door."""
    library = LIBRARIES[key]
    return (f'<script id="{library.element}">/* {licence(key)} */\n{_script(code(key))}</script>'
            + door(key))


def cdn_element(url: str, integrity: str) -> str:
    """The plotting library from its CDN (artifact.figures.plotlyDelivery "cdn"), then its door:
    an optional runtime, which degrades to the figures' own notice where it does not load."""
    return (f'<script id="{LIBRARIES["plotting"].element}" src="{url}" integrity="{integrity}" '
            'crossorigin="anonymous" data-optional-runtime></script>' + door("plotting"))
