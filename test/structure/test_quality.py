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

No test of this adapter builds obs's spec itself: it reads the run's one shared build, which obs
test/spec_build.py owns, with what counts as building it (``own_builds``); a test that needs
another build copies the vault, builds only that variant, and is named in SPEC_BUILD_EXCEPTIONS.

A test states the browser engine it needs by the fixture it takes. The bulk runs on Playwright's
headless shell (``reader_browser`` and the other BROWSER_FIXTURES); full Chromium
(FULL_CHROMIUM_FIXTURES) serves only the named set FULL_CHROMIUM_TESTS, the checks whose
behaviour can differ in the shell. A test outside the set that takes full Chromium, and a named
test that does not, both fail.
"""
import re
import ast
from pathlib import Path

from conftest import spec_build

TESTS = Path(__file__).parents[1]
# The fixtures that hand a test a browser page; test/conftest.py owns them. A test of the PDF
# path (``pdf_browser``) runs the CLI, whose build is what it tests.
BROWSER_FIXTURES = {"reader_browser", "shared_reader_browser", "overlay_scrollbar_browser", "page_pool",
                    "overlay_scrollbar_pool", "worker_playwright", "full_chromium_browser",
                    "shared_full_chromium_browser", "full_page_pool", "phone_browser", "phone_pool"}
# The fixtures that run a test on full Chromium instead of the headless shell; test/conftest.py
# owns them. The PDF path's browser (``pdf_browser``) is full Chromium too.
FULL_CHROMIUM_FIXTURES = {"full_chromium_browser", "shared_full_chromium_browser", "full_page_pool", "pdf_browser"}
# Every test of the module.
EVERY_TEST = "every test"
# The named set that runs on full Chromium, by module: the checks whose behaviour can differ in the
# headless shell (obs quality.md, Testing boundaries). Every other browser test runs on the shell.
FULL_CHROMIUM_TESTS = {
    # Print and PDF export: the PDF path prints with the browser it finds, and print media.
    "test_pdf.py": EVERY_TEST,
    "test_pdf_inspect.py": EVERY_TEST,
    "test_notice_center_browser.py": {"test_icon_opens_its_list_an_entry_expands_and_escape_closes"},
    # The viewer fixture's sandboxed frame: what a scripts-only, out-of-process frame limits, when a
    # stand-in in it runs, and its print.
    "test_features_browser.py": {"test_a_host_stand_in_is_in_place_before_the_artifacts_first_script"},
    "test_sandboxed_preview_browser.py": {
        "test_artifact_runs_as_srcdoc_of_a_scripts_only_sandbox", "test_canaries_find_what_a_scripts_only_sandbox_limits",
        "test_each_canary_says_what_it_observed", "test_a_sandboxed_frame_lists_its_limits_as_warning_notices",
        "test_print_to_pdf_in_a_sandboxed_frame_ends_in_an_inline_message"},
    # The startup marks: the first chapter's paint in the browser a reader opens.
    "test_startup_browser.py": {"test_the_spec_artifact_shows_its_first_chapter_within_a_second"},
}
# The fixtures that build an artifact once per run, wherever they are defined; a browser test
# reads what they built, and the check does not look into them.
SHARED_FIXTURES = {"fixture_artifact", "feature_artifact", "spec_html", "spec_artifact"}
# What denotes obs's checkout in a test of this adapter (test/conftest.py owns CORE_ROOT).
CORE_ROOTS = r"CORE_ROOT|core_root"
# The tests that build obs's spec themselves, by module: test -> why it is a variant of its own.
SPEC_BUILD_EXCEPTIONS = {
    "test_spec_archive_rebuild.py": {
        "test_reproduce_rebuilds_obs_spec_from_its_archive_with_the_references_entry":
            "builds a copy of the vault with --embed-source and rebuilds it from the archive it embeds"},
}
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


def engine_violations(path: Path, named=None) -> list[str]:
    """Each test of the module on full Chromium outside the named set, and each named test that is not.

    ``named`` is the module's entry in FULL_CHROMIUM_TESTS: a set of test names, EVERY_TEST or None."""
    module = ast.parse(path.read_text(encoding="utf-8"))
    functions = {node.name: node for node in module.body if isinstance(node, ast.FunctionDef)}
    full = set(FULL_CHROMIUM_FIXTURES)
    fixtures = {name: function for name, function in functions.items() if is_fixture(function)}
    while True:  # a module fixture that takes full Chromium hands it on
        more = {name for name, function in fixtures.items() if fixture_names(function) & full} - full
        if not more:
            break
        full |= more
    tests = {name: function for name, function in functions.items() if name.startswith("test_")}
    found = []
    for name, test in tests.items():
        engine = sorted(fixture_names(test) & full)
        listed = named == EVERY_TEST or name in (named or set())
        if engine and not listed:
            found.append(f"{name}: {path.name}:{test.lineno} runs on full Chromium ({', '.join(engine)}) outside "
                         "FULL_CHROMIUM_TESTS; take reader_browser (the headless shell), or name the test there "
                         "with why the shell differs")
        elif listed and not engine and named != EVERY_TEST:
            found.append(f"{name}: {path.name}:{test.lineno} is named in FULL_CHROMIUM_TESTS but runs on the "
                         "headless shell; take full_chromium_browser, or remove it from the set")
    if isinstance(named, set):
        found += [f"{name}: {path.name} has no such test, which FULL_CHROMIUM_TESTS names; remove it from the set"
                  for name in sorted(named - tests.keys())]
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
def spec_html():
    return render({}, {})


def test_shared_artifacts(reader_browser, built, spec_html, fixture_artifact):
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


def test_only_the_named_set_runs_on_full_chromium() -> None:
    found = [violation for path in sorted(TESTS.glob("test_*.py"))
             for violation in engine_violations(path, FULL_CHROMIUM_TESTS.get(path.name))]
    missing = sorted(name for name in FULL_CHROMIUM_TESTS if not (TESTS / name).is_file())
    found += [f"{name}: FULL_CHROMIUM_TESTS names a module the tests do not have; remove it" for name in missing]
    assert found == [], "test/structure/test_quality.py: " + "\n".join(found)


def test_the_engine_check_names_a_full_chromium_test_outside_the_set(tmp_path: Path) -> None:
    """The check is not vacuous: a test on full Chromium outside the set, directly or through a
    module fixture, a named test on the shell and a named test the module lacks are each named."""
    (tmp_path / "test_engines.py").write_text('''
@pytest.fixture(scope="module")
def printed(pdf_browser):
    return None


def test_on_the_shell(reader_browser):
    reader_browser.new_page()


def test_on_full_chromium(full_chromium_browser):
    full_chromium_browser.new_page()


def test_through_a_fixture(printed):
    assert printed is None


def test_named(full_chromium_browser):
    full_chromium_browser.new_page()


def test_named_on_the_shell(reader_browser):
    reader_browser.new_page()
''', encoding="utf-8")
    found = engine_violations(tmp_path / "test_engines.py", {"test_named", "test_named_on_the_shell", "test_gone"})
    assert [line.split(":")[0] for line in found] == [
        "test_on_full_chromium", "test_through_a_fixture", "test_named_on_the_shell", "test_gone"]
    assert "(full_chromium_browser) outside FULL_CHROMIUM_TESTS" in found[0]
    assert "(printed) outside FULL_CHROMIUM_TESTS" in found[1]
    assert engine_violations(tmp_path / "test_engines.py", EVERY_TEST) == []


def test_no_test_builds_obs_spec_itself() -> None:
    found = [violation for path in sorted(TESTS.glob("*.py"))
             for violation in spec_build.own_builds(path, CORE_ROOTS, set(SPEC_BUILD_EXCEPTIONS.get(path.name, {})))]
    missing = sorted(name for name in SPEC_BUILD_EXCEPTIONS if not (TESTS / name).is_file())
    found += [f"{name}: SPEC_BUILD_EXCEPTIONS names a module the tests do not have; remove it" for name in missing]
    assert found == [], "test/structure/test_quality.py: " + "\n".join(found)


def test_the_spec_check_names_a_test_that_builds_obs_spec_through_the_core_root(tmp_path: Path) -> None:
    """The check is not vacuous in this adapter: a build of obs's spec through CORE_ROOT is named, and
    a build of this adapter's own spec, or the shared spec artifact, is not."""
    (tmp_path / "test_own_spec.py").write_text('''
from pathlib import Path

from conftest import CORE_ROOT
from spec_artifact import run, spec_artifact, uv

ROOT = Path(__file__).parents[1]


def test_core_spec(tmp_path):
    core = CORE_ROOT
    run([uv(), "run", "obs-document", "--source", str(core / "spec"), "--document", str(tmp_path / "r.json")],
        core, "building obs's spec")


def test_own_spec(tmp_path):
    run([uv(), "run", "obs-document", "--source", str(ROOT / "spec" / "manifest.md")], ROOT, "own spec")


def test_shared(tmp_path_factory):
    assert spec_artifact(tmp_path_factory).is_file()
''', encoding="utf-8")
    found = spec_build.own_builds(tmp_path / "test_own_spec.py", CORE_ROOTS, set())
    assert [line.split(":")[0] for line in found] == ["test_core_spec"]
    assert "test_own_spec.py:12" in found[0] and "test/spec_build.py" in found[0]
