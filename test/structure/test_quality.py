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

Nor may a browser test add an init script (``add_init_script``): in the preview's srcdoc frames
one can run after the artifact's own scripts (#233, #298); a stand-in goes into the artifact's
head instead (test/browser/viewer.py, ``with_stand_in``). And it reads the artifact's timings
from the artifact's own performance marks: it reads no clock of its own in Python, sets no
performance mark, and takes no time in a listener of its own in the page.
"""
import re
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
# A setting only the artifact itself can make reliable in the preview's srcdoc frames.
INIT_SCRIPTS = {"add_init_script"}
# Python's clocks, as the time module's functions.
CLOCKS = {"time", "time_ns", "monotonic", "monotonic_ns", "perf_counter", "perf_counter_ns", "process_time"}
# A page script that sets a mark of its own, or takes a time in a listener of its own.
OWN_MARK = re.compile(r"performance\.mark\(")
OWN_TIME = re.compile(r"performance\.now\(|Date\.now\(")
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


def clock_names(module: ast.Module) -> set[str]:
    """The names a module calls Python's clocks by: ``time.perf_counter`` or an imported ``perf_counter``."""
    names = {f"{alias.asname or alias.name}.{clock}" for node in ast.walk(module) if isinstance(node, ast.Import)
             for alias in node.names if alias.name == "time" for clock in CLOCKS}
    return names | {alias.asname or alias.name for node in ast.walk(module)
                    if isinstance(node, ast.ImportFrom) and node.module == "time"
                    for alias in node.names if alias.name in CLOCKS}


def own_timings(module: ast.Module) -> list[str]:
    """Each page script of the module that sets its own performance mark or takes a time in its own listener."""
    found = []
    for node in ast.walk(module):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if OWN_MARK.search(node.value):
                found.append(f"{node.lineno} sets a performance mark of its own")
            elif "addEventListener" in node.value and OWN_TIME.search(node.value):
                found.append(f"{node.lineno} takes a time in a listener of its own")
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
    clocks = clock_names(module)
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
                elif called_name in INIT_SCRIPTS:
                    found.append(f"{name}: {where} calls {called_name}; write a stand-in into the artifact's "
                                 "head (browser/viewer.py, with_stand_in)")
                elif called_name in clocks:
                    found.append(f"{name}: {where} reads the clock {called_name}; read the artifact's own "
                                 "performance marks")
                elif called_name in builders:
                    found.append(f"{name}: {where} builds an artifact with {called_name}; use "
                                 "artifacts.artifact_html or a fixture that builds inside built_once")
                elif called_name in functions and called_name not in exempt:
                    pending.append(called_name)
    if any(line.split(":")[0].startswith("test_") for line in found) or any(
            name.startswith("test_") and isinstance(test, ast.FunctionDef)
            and fixture_names(test) & (BROWSER_FIXTURES | browser_fixtures) for name, test in functions.items()):
        found += [f"{path.name}:{timing}; read the artifact's own performance marks" for timing in own_timings(module)]
    return found


def test_no_browser_test_builds_an_artifact_or_starts_a_browser() -> None:
    found = [violation for path in sorted(TESTS.glob("test_*.py")) for violation in violations(path)]
    assert found == [], "test/structure/test_quality.py: " + "\n".join(found)


def test_the_check_names_a_test_that_launches_a_browser_or_renders(tmp_path: Path) -> None:
    """The check is not vacuous: each kind of call it refuses is named, with its test and line."""
    (tmp_path / "test_new_browser.py").write_text('''
import time
from time import perf_counter

from playwright.sync_api import sync_playwright
from obs_html.render import render
from obs_html import cli

TIMES = "document.addEventListener('obs-html-ready', () => { globalThis.ready = performance.now(); })"
MARK = "performance.mark('mine')"


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
    Reader(reader_browser)


def test_own_init_script_and_clocks(reader_browser):
    page = reader_browser.new_page()
    page.add_init_script(TIMES)
    started = time.monotonic()
    return perf_counter() - started
''', encoding="utf-8")
    found = violations(tmp_path / "test_new_browser.py")
    assert [line.split(":")[0] for line in found] == [
        "test_own_browser", "test_own_browser", "test_own_artifact", "test_own_artifact", "test_own_context",
        "test_own_context_in_a_class", "test_own_init_script_and_clocks", "test_own_init_script_and_clocks",
        "test_own_init_script_and_clocks", "test_new_browser.py", "test_new_browser.py"]
    assert any("(helper) builds an artifact with render" in line for line in found)
    assert any("calls sync_playwright" in line for line in found)
    assert any("calls launch" in line for line in found)
    assert any("calls new_context" in line for line in found)
    assert any("calls add_init_script; write a stand-in" in line for line in found)
    assert any("reads the clock time.monotonic" in line for line in found)
    assert any("reads the clock perf_counter" in line for line in found)
    assert any("takes a time in a listener of its own" in line for line in found)
    assert any("sets a performance mark of its own" in line for line in found)
