"""The limited-host banner's markup (spec/architecture.md, Limited-host banner).

Reader: whoever changes when the banner ships or what it says.

Pure: the needs a page declares (``artifact.limitedHostNeeds``) in, the banner's elements out, or
nothing where it declares none, so a page without the option is byte for byte what it was. What each
need stops and where to open the page instead is limited-host.json's; limited-host.js probes the host
and words the line.
"""
from __future__ import annotations

from html import escape
from importlib.resources import files
import json


def limited_host_markup(needs: list[str]) -> str:
    """The banner, the table of each declared need it words, its style and its script; "" without needs."""
    if not needs:
        return ""
    package = files("obs_html")
    table = json.loads(package.joinpath("limited-host.json").read_text(encoding="utf-8"))
    declared = {need: table["needs"][need] for need in needs if need in table["needs"]}
    island = json.dumps(declared, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return (f'<style id="limited-host-styles">\n{package.joinpath("limited-host.css").read_text(encoding="utf-8")}'
            f'  </style>\n  <div id="limited-host" class="limited-host" role="alert">{escape(table["noScripts"])}</div>\n'
            f'  <script id="limited-host-needs" type="application/json">{island}</script>\n'
            f'  <script id="limited-host-script">\n{package.joinpath("limited-host.js").read_text(encoding="utf-8")}'
            f'  </script>\n  ')
