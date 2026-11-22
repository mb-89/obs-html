"""The browser door's classification names every browser test file once, as logic or hot, with its reason.

Reader: whoever adds, moves or removes a browser test, or works a package of the browser door
(test/browser/browser-door.md).

The design note's table "Classification" holds one row per browser test file: its name, its class
(`logic`, which runs on the fake browser, or `hot`, which runs in the one real Chromium and records
its answers), the package that moves it and the reason. A browser test file is a test module of
this repository with a test that takes a browser fixture (structure/test_quality.py's
BROWSER_FIXTURES, or the PDF path's ``pdf_browser``), directly or through a fixture of its own
module, or that carries the ``browser`` mark.
"""
import ast
import re
from pathlib import Path

from structure.test_quality import BROWSER_FIXTURES, fixture_names, is_fixture

ROOT = Path(__file__).parents[2]
TESTS = ROOT / "test"
NOTE = TESTS / "browser" / "browser-door.md"
# The fixtures that open a real browser for a test: the pages' pools, and the PDF path's browser.
REAL_BROWSER = BROWSER_FIXTURES | {"pdf_browser"}
CLASSES = {"logic", "hot"}
ROW = re.compile(r"^\| `(?P<file>[^`]+)` \| (?P<cls>[^|]*?) \| (?P<package>[^|]*?) \| (?P<reason>[^|]*?) \|$")


def marked_browser(node: ast.AST) -> bool:
    """Whether a decorator list or a ``pytestmark`` value names ``pytest.mark.browser``."""
    return any(isinstance(each, ast.Attribute) and each.attr == "browser"
               and isinstance(each.value, ast.Attribute) and each.value.attr == "mark" for each in ast.walk(node))


def is_browser_test_file(path: Path) -> bool:
    """Whether a test module has a test that takes a real browser or carries the browser mark."""
    module = ast.parse(path.read_text(encoding="utf-8"))
    if any(isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "pytestmark"
                                                 for target in node.targets) and marked_browser(node.value)
           for node in module.body):
        return True
    functions = [node for node in ast.walk(module) if isinstance(node, ast.FunctionDef)]
    browser = set(REAL_BROWSER)
    while True:  # A fixture of the module that takes a browser fixture is one too, at any depth.
        more = {function.name for function in functions
                if is_fixture(function) and fixture_names(function) & browser} - browser
        if not more:
            break
        browser |= more
    return any(function.name.startswith("test_")
               and (fixture_names(function) & browser or marked_browser(ast.Module(function.decorator_list, [])))
               for function in functions)


def browser_test_files() -> set[str]:
    return {path.name for path in TESTS.rglob("test_*.py")
            if "node_modules" not in path.parts and is_browser_test_file(path)}


def classification() -> list[dict[str, str]]:
    """The rows of the note's table under its heading "Classification", in order."""
    text = NOTE.read_text(encoding="utf-8")
    section = text.split("\n## Classification\n", 1)
    assert len(section) == 2, f"{NOTE.relative_to(ROOT).as_posix()}: no section headed '## Classification'"
    body = section[1].split("\n## ", 1)[0]
    return [match.groupdict() for match in map(ROW.match, body.splitlines()) if match]


def test_every_browser_test_file_is_classified_once() -> None:
    rows = classification()
    named = [row["file"] for row in rows]
    repeated = sorted({name for name in named if named.count(name) > 1})
    missing = sorted(browser_test_files() - set(named))
    extra = sorted(set(named) - browser_test_files())
    assert not (repeated or missing or extra), (
        f"{NOTE.relative_to(ROOT).as_posix()}, Classification: named twice {repeated}; browser test files it does "
        f"not classify {missing}; rows that name no browser test file {extra}. Remedy: give each browser test file "
        "one row, and remove the row of a file that no longer drives a browser.")


def test_each_row_has_a_class_a_package_and_a_reason() -> None:
    packages = set(re.findall(r"^\d+\. \*\*`([a-z0-9-]+)`\*\*", NOTE.read_text(encoding="utf-8"), re.MULTILINE))
    wrong = [f"{row['file']}: class {row['cls']!r}" for row in classification() if row["cls"] not in CLASSES]
    wrong += [f"{row['file']}: package {row['package']!r}" for row in classification()
              if row["package"].strip("`") not in packages]
    wrong += [f"{row['file']}: no reason" for row in classification() if not row["reason"].strip()]
    assert not wrong, (f"{NOTE.relative_to(ROOT).as_posix()}, Classification: {wrong}. Remedy: the class is one of "
                       f"{sorted(CLASSES)}, the package one the section Packages lists, and the reason says what "
                       "the file checks.")


def test_the_check_finds_a_browser_test_through_a_module_fixture_and_the_mark(tmp_path: Path) -> None:
    (tmp_path / "test_through_fixture.py").write_text('''
import pytest

@pytest.fixture
def page(reader_browser):
    return reader_browser.new_page()

@pytest.fixture
def opened(page):
    return page

def test_reads(opened):
    pass
''', encoding="utf-8")
    (tmp_path / "test_marked.py").write_text('''
import pytest

@pytest.mark.browser
def test_sweeps():
    pass
''', encoding="utf-8")
    (tmp_path / "test_plain.py").write_text("def test_adds():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    assert [is_browser_test_file(tmp_path / name) for name in
            ("test_through_fixture.py", "test_marked.py", "test_plain.py")] == [True, True, False]
