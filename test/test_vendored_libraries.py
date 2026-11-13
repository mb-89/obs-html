"""Each vendored library the adapter tracks is the release vendor.json pins.

Reader: whoever updates a vendored library or its pin.

spec/architecture.md, Packaged browser assets, owns the design: a vendored library is its release's
file, unchanged, and vendor.json names that release and its integrity. obs's repository allows
these files over its size bound only because they are pinned here (obs's architecture.md,
Repository layout), so a changed copy fails, and so does a vendored library vendor.json does not pin.
"""
from __future__ import annotations

import base64
import hashlib
import json
import shutil
from pathlib import Path

PART = Path(__file__).parents[1]
MANIFEST = "vendor.json"
# The vendored libraries: each minified release file directly in this folder, every one pinned.
VENDORED = "src/obs_html/vendor/*.min.js"
CFG = PART / "src" / "obs_html" / "cfg.json"


def pins(part: Path) -> dict[str, dict[str, str]]:
    return json.loads((part / MANIFEST).read_text(encoding="utf-8"))["libraries"]


def integrity(path: Path) -> str:
    """The file's integrity in the form vendor.json and a script's `integrity` write it."""
    return "sha384-" + base64.b64encode(hashlib.sha384(path.read_bytes()).digest()).decode()


def vendored_findings(part: Path) -> list[str]:
    """Each vendored library vendor.json does not pin, and each file it pins that is missing, not
    its pinned release, or whose source names another version."""
    found = []
    pinned = pins(part)
    for path in sorted(part.glob(VENDORED)):
        if (name := path.relative_to(part).as_posix()) not in pinned:
            found.append(f"{MANIFEST}: libraries.{name}: no entry for this vendored library; pin its "
                         "release by package, version, source and integrity, or remove the file")
    for name, pin in pinned.items():
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


def test_a_vendored_library_without_a_pin_fails(tmp_path: Path) -> None:
    name = "src/obs_html/vendor/unlisted.min.js"
    shutil.copy(PART / MANIFEST, tmp_path / MANIFEST)
    for pinned in pins(PART):
        (tmp_path / pinned).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(PART / pinned, tmp_path / pinned)
    (tmp_path / name).write_text("/*! unlisted 1.0.0 */\n", encoding="utf-8")

    findings = vendored_findings(tmp_path)

    assert len(findings) == 1
    assert findings[0].startswith(f"{MANIFEST}: libraries.{name}: ")


def test_the_cdn_delivery_is_the_vendored_plotting_release() -> None:
    """artifact.figures' CDN pin and the embedded copy are the same Plotly release."""
    figures = json.loads(CFG.read_text(encoding="utf-8"))["artifact"]["figures"]
    plotly = pins(PART)["src/obs_html/vendor/plotly-basic.min.js"]

    assert (figures["plotlyCdnUrl"], figures["plotlyCdnIntegrity"]) == (plotly["source"], plotly["integrity"])
