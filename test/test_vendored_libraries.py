"""Each vendored library the adapter tracks is the release vendor.json pins.

Reader: whoever updates a vendored library or its pin.

spec/architecture.md, Packaged browser assets, owns the design: a vendored library is its release's
file, unchanged, and vendor.json names that release and its integrity. obs's repository allows
these files over its size bound only because they are pinned here (obs's architecture.md,
Repository layout), so a changed copy fails.
"""
from __future__ import annotations

import base64
import hashlib
import json
import shutil
from pathlib import Path

PART = Path(__file__).parents[1]
MANIFEST = "vendor.json"
CFG = PART / "src" / "obs_html" / "cfg.json"


def pins(part: Path) -> dict[str, dict[str, str]]:
    return json.loads((part / MANIFEST).read_text(encoding="utf-8"))["libraries"]


def integrity(path: Path) -> str:
    """The file's integrity in the form vendor.json and a script's `integrity` write it."""
    return "sha384-" + base64.b64encode(hashlib.sha384(path.read_bytes()).digest()).decode()


def vendored_findings(part: Path) -> list[str]:
    """Each file vendor.json pins that is missing, not its pinned release, or whose source names
    another version."""
    found = []
    for name, pin in pins(part).items():
        where = f"{MANIFEST}: libraries.{name}"
        release = f"{pin['package']} {pin['version']}"
        if pin["version"] not in pin["source"]:
            found.append(f"{where}.source: names no version {pin['version']}; name the release's source")
        if not (part / name).is_file():
            found.append(f"{where}: no such file; copy {release} from {pin['source']}, or remove the pin")
        elif (actual := integrity(part / name)) != pin["integrity"]:
            found.append(f"{where}.integrity: the file is {actual}, not {release}; copy the release "
                         f"unchanged from {pin['source']}, or pin the release it is")
    return found


def test_each_vendored_library_is_its_pinned_release() -> None:
    assert pins(PART), f"{MANIFEST} pins no library"
    assert vendored_findings(PART) == []


def test_a_changed_copy_of_a_library_fails(tmp_path: Path) -> None:
    name = "src/obs_html/vendor/pdf-lib.min.js"
    shutil.copy(PART / MANIFEST, tmp_path / MANIFEST)
    for pinned in pins(PART):
        (tmp_path / pinned).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(PART / pinned, tmp_path / pinned)
    with (tmp_path / name).open("ab") as copy:
        copy.write(b"\n")

    findings = vendored_findings(tmp_path)

    assert len(findings) == 1
    assert findings[0].startswith(f"{MANIFEST}: libraries.{name}.integrity: ")


def test_the_cdn_delivery_is_the_vendored_plotting_release() -> None:
    """artifact.figures' CDN pin and the embedded copy are the same Plotly release."""
    figures = json.loads(CFG.read_text(encoding="utf-8"))["artifact"]["figures"]
    plotly = pins(PART)["src/obs_html/vendor/plotly-basic.min.js"]

    assert (figures["plotlyCdnUrl"], figures["plotlyCdnIntegrity"]) == (plotly["source"], plotly["integrity"])
