"""The browser door's classification names every browser test file once, as logic or hot, with its reason.

Reader: whoever adds, moves or removes a browser test, or works a package of the browser door
(test/browser/browser-door.md).

The design note's table "Classification" holds one row per browser test file: its name, its class
(`logic`, which runs on the fake browser, or `hot`, which runs in the one real Chromium and records
its answers), the package that moves it and the reason. A browser test file is a test module of
this repository with a test that takes a browser fixture (structure/test_quality.py's
BROWSER_FIXTURES, the PDF path's ``pdf_browser``, or the fake browser's FAKE_BROWSER_FIXTURES),
directly or through a fixture of its own module, or that carries the ``browser`` mark.

A row's Package names the package that moves the file while it still drives a real browser, and
reads ``moved by `<package>` `` once the package has landed and every browser test of the file
takes the fake browser, but the named exceptions of a logic file, which carry the ``hot`` mark
(``added by `<package>` `` for a file a package wrote on it): a file that takes no real browser
any more, or only in its hot tests, has a moved row, and a moved row's file takes none outside them.
"""
import ast
import re
from pathlib import Path

from structure.test_quality import BROWSER_FIXTURES, FAKE_BROWSER_FIXTURES, fixture_names, is_fixture

ROOT = Path(__file__).parents[2]
TESTS = ROOT / "test"
NOTE = TESTS / "browser" / "browser-door.md"
# The fixtures that open a real browser for a test: the pages' pools, and the PDF path's browser.
REAL_BROWSER = BROWSER_FIXTURES | {"pdf_browser"}
CLASSES = {"logic", "hot"}
ROW = re.compile(r"^\| `(?P<file>[^`]+)` \| (?P<cls>[^|]*?) \| (?P<package>[^|]*?) \| (?P<reason>[^|]*?) \|$")
# The Package of a row whose file the package moved to the fake browser, or added there.
MOVED = re.compile(r"^(?:moved|added) by `(?P<package>[a-z0-9-]+)`$")


def marked(node: ast.AST, mark: str) -> bool:
    """Whether a decorator list or a ``pytestmark`` value names ``pytest.mark.<mark>``."""
    return any(isinstance(each, ast.Attribute) and each.attr == mark
               and isinstance(each.value, ast.Attribute) and each.value.attr == "mark" for each in ast.walk(node))


def marked_browser(node: ast.AST) -> bool:
    """Whether a decorator list or a ``pytestmark`` value names ``pytest.mark.browser``."""
    return marked(node, "browser")


def hot(function: ast.FunctionDef) -> bool:
    """Whether a test carries the ``hot`` mark: a named exception of a logic file, which stays in the
    real Chromium (browser-door.md, Classification)."""
    return marked(ast.Module(function.decorator_list, []), "hot")


def _takes(functions: list[ast.FunctionDef], fixtures: set[str], but_hot: bool = False) -> bool:
    """Whether a test of the module takes one of ``fixtures``, directly or through a fixture of the
    module that takes one, at any depth; with ``but_hot``, a test other than a hot one."""
    taken = set(fixtures)
    while True:
        more = {function.name for function in functions
                if is_fixture(function) and fixture_names(function) & taken} - taken
        if not more:
            break
        taken |= more
    return any(function.name.startswith("test_") and fixture_names(function) & taken
               and not (but_hot and hot(function)) for function in functions)


def _functions(path: Path) -> tuple[ast.Module, list[ast.FunctionDef]]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    return module, [node for node in ast.walk(module) if isinstance(node, ast.FunctionDef)]


def takes_a_real_browser(path: Path, but_hot: bool = False) -> bool:
    """Whether a test of the module takes a real browser (REAL_BROWSER) or carries the browser mark;
    with ``but_hot``, a test other than one with the hot mark."""
    module, functions = _functions(path)
    if any(isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "pytestmark"
                                                 for target in node.targets) and marked_browser(node.value)
           for node in module.body):
        return True
    return _takes(functions, REAL_BROWSER, but_hot) or any(
        function.name.startswith("test_") and marked_browser(ast.Module(function.decorator_list, []))
        and not (but_hot and hot(function)) for function in functions)


def takes_the_fake_browser(path: Path) -> bool:
    """Whether a test of the module takes the fake browser (FAKE_BROWSER_FIXTURES)."""
    return _takes(_functions(path)[1], FAKE_BROWSER_FIXTURES)


def is_browser_test_file(path: Path) -> bool:
    """Whether a test module has a test that takes a real or the fake browser, or carries the browser mark."""
    return takes_a_real_browser(path) or takes_the_fake_browser(path)


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


def package_of(row: dict[str, str]) -> str:
    """The package a row names, moved or not."""
    moved = MOVED.match(row["package"])
    return moved["package"] if moved else row["package"].strip("`")


def test_each_row_has_a_class_a_package_and_a_reason() -> None:
    packages = set(re.findall(r"^\d+\. \*\*`([a-z0-9-]+)`\*\*", NOTE.read_text(encoding="utf-8"), re.MULTILINE))
    wrong = [f"{row['file']}: class {row['cls']!r}" for row in classification() if row["cls"] not in CLASSES]
    wrong += [f"{row['file']}: package {row['package']!r}" for row in classification()
              if package_of(row) not in packages]
    wrong += [f"{row['file']}: no reason" for row in classification() if not row["reason"].strip()]
    assert not wrong, (f"{NOTE.relative_to(ROOT).as_posix()}, Classification: {wrong}. Remedy: the class is one of "
                       f"{sorted(CLASSES)}, the package one the section Packages lists, and the reason says what "
                       "the file checks.")


def moved_rows_wrong(rows: list[dict[str, str]], files: dict[str, Path]) -> list[str]:
    """Each row whose Package says moved while a test of its file other than a hot one takes a real
    browser, or does not while its file takes only the fake browser and the hot tests the reason
    names, or that moves a hot file."""
    wrong = []
    for row in rows:
        path = files.get(row["file"])
        if path is None:
            continue
        moved = bool(MOVED.match(row["package"]))
        if moved and takes_a_real_browser(path, but_hot=True):
            wrong.append(f"{row['file']}: its Package says {row['package']}, but a test of it without the hot mark "
                         "takes a real browser or carries the browser mark")
        elif (not moved and row["cls"] == "logic" and not takes_a_real_browser(path, but_hot=True)
              and takes_the_fake_browser(path)):
            wrong.append(f"{row['file']}: its logic tests run on the fake browser, but its Package {row['package']} "
                         "does not say moved by `<package>`")
        elif not moved and not takes_a_real_browser(path):
            wrong.append(f"{row['file']}: its tests run on the fake browser, but its Package {row['package']} does not "
                         "say moved by `<package>` or added by `<package>`")
        elif moved and row["cls"] != "logic":
            wrong.append(f"{row['file']}: a hot file is not moved to the fake browser")
    return wrong


def test_a_row_says_moved_exactly_where_its_file_takes_only_the_fake_browser() -> None:
    # By name, as the rows name them: test_browser_door.py is both this file and the conformance
    # check, and only the check is a browser test file.
    files = {path.name: path for path in TESTS.rglob("test_*.py")
             if "node_modules" not in path.parts and is_browser_test_file(path)}
    wrong = moved_rows_wrong(classification(), files)
    assert not wrong, (f"{NOTE.relative_to(ROOT).as_posix()}, Classification: {wrong}. Remedy: a package that moves "
                       "a file to fake_page writes its row's Package as moved by `<package>`; a file that still "
                       "takes a real browser keeps the package that will move it.")


def test_the_moved_check_names_a_row_that_disagrees_with_its_file(tmp_path: Path) -> None:
    (tmp_path / "test_on_fake.py").write_text("def test_reads(fake_page):\n    pass\n", encoding="utf-8")
    (tmp_path / "test_on_real.py").write_text("def test_reads(reader_browser):\n    pass\n", encoding="utf-8")
    files = {path.name: path for path in tmp_path.glob("test_*.py")}
    rows = [{"file": "test_on_fake.py", "cls": "logic", "package": "`fake-browser-door`"},
            {"file": "test_on_real.py", "cls": "logic", "package": "moved by `fake-browser-door`"}]
    assert [line.split(":")[0] for line in moved_rows_wrong(rows, files)] == ["test_on_fake.py", "test_on_real.py"]
    rows = [{"file": "test_on_fake.py", "cls": "logic", "package": "moved by `fake-browser-door`"},
            {"file": "test_on_real.py", "cls": "logic", "package": "`fake-browser-door`"}]
    assert moved_rows_wrong(rows, files) == []


def test_a_moved_row_may_keep_its_hot_exceptions_on_the_real_browser(tmp_path: Path) -> None:
    (tmp_path / "test_with_hot.py").write_text('''
import pytest

def test_reads(fake_page):
    pass

@pytest.mark.hot
@pytest.mark.browser
def test_measures(reader_browser):
    pass
''', encoding="utf-8")
    (tmp_path / "test_unmarked.py").write_text('''
import pytest

def test_reads(fake_page):
    pass

@pytest.mark.browser
def test_measures(reader_browser):
    pass
''', encoding="utf-8")
    files = {path.name: path for path in tmp_path.glob("test_*.py")}
    rows = [{"file": "test_with_hot.py", "cls": "logic", "package": "moved by `layout-logic-to-fake-browser`"},
            {"file": "test_unmarked.py", "cls": "logic", "package": "`layout-logic-to-fake-browser`"}]
    assert moved_rows_wrong(rows, files) == []
    rows = [{"file": "test_with_hot.py", "cls": "logic", "package": "`layout-logic-to-fake-browser`"},
            {"file": "test_unmarked.py", "cls": "logic", "package": "moved by `layout-logic-to-fake-browser`"}]
    assert [line.split(":")[0] for line in moved_rows_wrong(rows, files)] == ["test_with_hot.py", "test_unmarked.py"]


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
    (tmp_path / "test_on_fake.py").write_text('''
import pytest

@pytest.fixture
def opened(fake_page):
    return fake_page

def test_reads(opened):
    pass
''', encoding="utf-8")
    assert [is_browser_test_file(tmp_path / name) for name in ("test_through_fixture.py", "test_marked.py",
                                                               "test_plain.py", "test_on_fake.py")] == [
        True, True, False, True]
