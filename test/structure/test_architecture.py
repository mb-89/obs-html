"""What architecture.md owns: each browser library is reached through its one door.

Reader: whoever changes a script or module that draws, computes or writes a PDF with a library.

architecture.md, Library doors: the package's scripts reach Plotly, math.js and pdf-lib only
through their doors (``plotly-door.js``, ``maths-door.js``, ``pdf-door.js``), and only
``libraries.py`` reads a library's packaged files. The check reads every script and module of
the package, without its comments and the libraries' own vendored files, and names each direct
reach outside the door with its file and line.
"""
import re
from pathlib import Path

PACKAGE = Path(__file__).parents[2] / "src" / "obs_html"
# A script's reach into a library: its global, and the drawn markup or state only the library
# defines, by the door that owns it.
LIBRARY_REACH = {
    "plotly-door.js": re.compile(r"(?:globalThis|window|self|view)\??\.Plotly\b|\bPlotly\b(?=\s*[.?\[(])|"
                                 r"\b_fullLayout\b|\bg\.legend\b|\bplotly_\w+"),
    "maths-door.js": re.compile(r"(?:globalThis|window|view|self)\??\.math\b(?!\w)|\bmath\.(?:Complex|parse|evaluate)\b"),
    "pdf-door.js": re.compile(r"\bPDFLib\b"),
}
# A module's reach into a library's packaged files, which only the Python door reads.
LIBRARY_FILES = re.compile(r"plotly-basic\.min\.js|plotly\.LICENSE|pdf-lib\.(?:min\.js|LICENSE)|"
                           r"[\"']maths[\"']\s*,\s*[\"']math\.js")
PYTHON_DOOR = "libraries.py"
COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)


def without_comments(source: str) -> str:
    """The script without its comments, each comment's lines kept as empty lines."""
    return COMMENT.sub(lambda match: "\n" * match.group().count("\n"), source)


def door_violations(package: Path) -> list[str]:
    found = []
    for script in sorted(package.rglob("*.js")):
        if "vendor" in script.relative_to(package).parts:
            continue
        code = without_comments(script.read_text(encoding="utf-8"))
        for door, reach in LIBRARY_REACH.items():
            if script.name == door:
                continue
            for match in reach.finditer(code):
                line = code.count("\n", 0, match.start()) + 1
                found.append(f"{script.relative_to(package).as_posix()}:{line} reaches {match.group()!r}; "
                             f"call the library's door, {door}")
    for module in sorted(package.rglob("*.py")):
        if module.name == PYTHON_DOOR:
            continue
        for number, line in enumerate(module.read_text(encoding="utf-8").splitlines(), start=1):
            match = LIBRARY_FILES.search(line.split("#")[0])
            if match:
                found.append(f"{module.relative_to(package).as_posix()}:{number} names the library file "
                             f"{match.group()!r}; ask {PYTHON_DOOR} for it")
    return found


def test_each_library_is_reached_only_through_its_door() -> None:
    found = door_violations(PACKAGE)
    assert found == [], "test/structure/test_architecture.py (architecture.md, Library doors):\n" + "\n".join(found)


def test_the_check_names_each_direct_reach_with_its_file_and_line(tmp_path: Path) -> None:
    """The check is not vacuous: each kind of reach it refuses is named, and a comment or the door
    itself is no reach."""
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "plotly.js").write_text("Plotly.newPlot()", encoding="utf-8")
    (tmp_path / "plotly-door.js").write_text("Plotly.newPlot(chart); chart._fullLayout;", encoding="utf-8")
    (tmp_path / "figure.js").write_text(
        "// Plotly.newPlot is the door's.\n/* PDFLib too */\nPlotly.relayout(chart, {});\n"
        "if (window.Plotly) chart._fullLayout.width;\nchart.querySelector('g.legend');\n"
        "chart.on('plotly_afterplot');\nconst z = new globalThis.math.Complex(1, 0);\nmath.parse(text);\n"
        "const {PDFDocument} = globalThis.PDFLib;\nMath.abs(1);\n", encoding="utf-8")
    (tmp_path / "render.py").write_text('read("vendor", "pdf-lib.min.js")  # a call\n# "plotly-basic.min.js"\n'
                                        'files("obs_html").joinpath("vendor", "maths", "math.js")\n', encoding="utf-8")
    (tmp_path / PYTHON_DOOR).write_text('read("vendor", "plotly-basic.min.js")\n', encoding="utf-8")

    found = door_violations(tmp_path)

    assert [line.split(" reaches ")[0].split(" names ")[0] for line in found] == [
        "figure.js:3", "figure.js:4", "figure.js:4", "figure.js:5", "figure.js:6",
        "figure.js:7", "figure.js:8", "figure.js:9", "render.py:1", "render.py:3"], found
    assert "call the library's door, pdf-door.js" in found[7] and "ask libraries.py for it" in found[8]
