"""Browser tests open what the shared fixtures give them; they build no artifact and start no browser.

Reader: whoever writes or changes a browser test of this adapter.

The owner is obs quality.md (Testing boundaries): each test process starts one browser and leases
every test a page from its pool, and an artifact a browser test opens is built once, by a
shared fixture. A browser test is a test function that requests a browser fixture
(BROWSER_FIXTURES) or a fixture of its own module that does. Neither it nor a function of its
module that it calls may start Playwright (``sync_playwright``), launch or connect a browser,
open a browser context, or build an artifact with this adapter (``render`` or the CLI's
``main``). An artifact is built by a shared fixture (SHARED_FIXTURES, or a module fixture
that builds inside ``built_once``) or by ``artifacts.artifact_html``.
"""
import ast
from pathlib import Path

TESTS = Path(__file__).parents[1]
# The fixtures that hand a test a browser page; test/conftest.py owns them. A test of the PDF
# path (``pdf_browser``) runs the CLI, whose build is what it tests.
BROWSER_FIXTURES = {"reader_browser", "shared_reader_browser", "overlay_scrollbar_browser", "page_pool",
                    "overlay_scrollbar_pool", "worker_browser", "worker_playwright"}
# The fixtures that build an artifact once per run, wherever they are defined; a browser test
# reads what they built, and the check does not look into them.
SHARED_FIXTURES = {"fixture_artifact", "parity_artifacts", "spec_artifact"}
# What only test/conftest.py may call: starting Playwright, launching or connecting a browser,
# and opening a browser context.
BROWSER_CALLS = {"sync_playwright", "launch", "launch_persistent_context", "connect", "connect_over_cdp",
                 "new_context"}
# This adapter's builders, (module, name) as a test module imports them, and the modules whose
# ``main`` builds, as ``cli.main(...)`` calls it.
BUILDERS = {("obs_html.render", "render"), ("obs_html.cli", "main")}
BUILDER_MODULES = {("obs_html", "cli")}


def fixture_names(function: ast.FunctionDef) -> set[str]:
    return {argument.arg for argument in function.args.args}


def is_fixture(function: ast.FunctionDef) -> bool:
    return any("fixture" in ast.unparse(decorator) for decorator in function.decorator_list)


def builder_names(module: ast.Module) -> set[str]:
    """The names a module calls this adapter's builders by: ``render``, or ``cli.main``."""
    names = set()
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if (node.module, alias.name) in BUILDERS:
                    names.add(alias.asname or alias.name)
                if (node.module, alias.name) in BUILDER_MODULES:
                    names.add(f"{alias.asname or alias.name}.main")
    return names


def called(node: ast.AST) -> list[tuple[str, ast.Call]]:
    """Each call under the node, by the name it calls: ``f()`` and ``x.f()`` are ``f``, and
    ``module.f()`` is also ``module.f``."""
    found = []
    for call in ast.walk(node):
        if isinstance(call, ast.Call):
            target = call.func
            if isinstance(target, ast.Name):
                found.append((target.id, call))
            elif isinstance(target, ast.Attribute):
                found.append((target.attr, call))
                if isinstance(target.value, ast.Name):
                    found.append((f"{target.value.id}.{target.attr}", call))
    return found


def built_once_builds(module: ast.Module, functions: dict[str, ast.FunctionDef]) -> set[str]:
    """The functions a module passes to ``built_once`` as its build: they build once per run."""
    builds = set()
    for name, call in called(module):
        if name == "built_once" and len(call.args) >= 3 and isinstance(call.args[2], ast.Name):
            builds.add(call.args[2].id)
    return builds & functions.keys()


def violations(path: Path) -> list[str]:
    """Each browser test of the module that reaches a browser call or a builder, and where."""
    module = ast.parse(path.read_text(encoding="utf-8"))
    # The module's functions and classes: a call to a class reaches every method it has.
    functions = {node.name: node for node in module.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    builders = builder_names(module)
    exempt = built_once_builds(module, functions) | SHARED_FIXTURES
    browser_fixtures = {name for name, function in functions.items() if isinstance(function, ast.FunctionDef)
                        and is_fixture(function) and fixture_names(function) & BROWSER_FIXTURES}
    found = []
    for name, test in functions.items():
        if (not name.startswith("test_") or not isinstance(test, ast.FunctionDef)
                or not fixture_names(test) & (BROWSER_FIXTURES | browser_fixtures)):
            continue
        reached, pending = set(), [name, *(fixture_names(test) & browser_fixtures)]
        while pending:
            current = pending.pop()
            if current in reached or current in exempt:
                continue
            reached.add(current)
            for called_name, call in called(functions[current]):
                where = f"{path.name}:{call.lineno} ({current})"
                if called_name in BROWSER_CALLS:
                    found.append(f"{name}: {where} calls {called_name}; lease a page from reader_browser")
                elif called_name in builders:
                    found.append(f"{name}: {where} builds an artifact with {called_name}; use "
                                 "artifacts.artifact_html or a fixture that builds inside built_once")
                elif called_name in functions and called_name not in exempt:
                    pending.append(called_name)
    return found


def test_no_browser_test_builds_an_artifact_or_starts_a_browser() -> None:
    found = [violation for path in sorted(TESTS.glob("test_*.py")) for violation in violations(path)]
    assert found == [], "test/structure/test_quality.py: " + "\n".join(found)


def test_the_check_names_a_test_that_launches_a_browser_or_renders(tmp_path: Path) -> None:
    """The check is not vacuous: each kind of call it refuses is named, with its test and line."""
    (tmp_path / "test_new_browser.py").write_text('''
from playwright.sync_api import sync_playwright
from obs_html.render import render
from obs_html import cli


def helper(document):
    return render(document, {})


def test_own_browser(reader_browser):
    with sync_playwright() as playwright:
        playwright.chromium.launch()


def test_own_artifact(reader_browser, tmp_path):
    helper({})
    cli.main(["document.json", str(tmp_path / "artifact.html")])


def test_own_context(reader_browser):
    reader_browser.new_context()


def test_without_a_browser():
    render({}, {})


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    def build(folder):
        cli.main(["document.json", str(folder / "artifact.html")])
    return built_once(tmp_path_factory, "built", build)


@pytest.fixture(scope="session")
def parity_artifacts():
    return render({}, {})


def test_shared_artifacts(reader_browser, built, parity_artifacts, fixture_artifact):
    reader_browser.new_page()


class Reader:
    def __init__(self, reader_browser):
        self.page = reader_browser.new_context().new_page()


def test_own_context_in_a_class(reader_browser):
    Reader(reader_browser)''', encoding="utf-8")
    found = violations(tmp_path / "test_new_browser.py")
    assert [line.split(":")[0] for line in found] == [
        "test_own_browser", "test_own_browser", "test_own_artifact", "test_own_artifact", "test_own_context",
        "test_own_context_in_a_class"]
    assert any("(helper) builds an artifact with render" in line for line in found)
    assert any("calls sync_playwright" in line for line in found)
    assert any("calls launch" in line for line in found)
    assert any("calls new_context" in line for line in found)
