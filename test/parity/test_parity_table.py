"""Parity gate: features.md records every feature of this adapter and how it differs from the
interim adapter obs#3 deleted.

Reader: whoever changes this adapter or the core in front of it, and the dispatcher reading the
record.

features.md has one row per feature: every CLI option and settings key of this adapter (and of
the interim, whose rows stay as the record), every capability, reader control and output form.
Each row's status is one of:

- "same", and its evidence names at least one test as `path::test_name`, a path from the
  repository root to a test file that defines that test;
- "added", a feature the interim did not have, with the same evidence as "same";
- "known difference", and its evidence names the issue (#n) or the design note (a path to a .md
  file with its #anchor) that decided it;
- "missing", and its evidence names the issue (#n) that tracks the gap.

A row "same (untested)" is refused: it marks parity nobody shows. The table is checked against
this adapter itself: its argparse parser (built, not run) and its settings schema name every
option and key the table must list, and every option and key a row names must exist there or in
the core's. A settings row that says "same" names this adapter's key, or the core's, in the first
code span of its Integrated cell (`obs-html <key>` or `obs-document <key>`), and
test_a_shared_setting_keeps_its_schema_default_limits_and_reader holds that key to its own
schema: the reference for defaults and limits, once the interim's, is now this adapter's
cfg.schema.json and the core's config.schema.json as they stand.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

TABLE = Path(__file__).with_name("features.md")
ADAPTER = Path(__file__).parents[2]
ROOT = ADAPTER.parents[1]
OWNER = "adapters/html/test/parity/test_parity_table.py"
STATUSES = {"same", "added", "known difference", "missing"}
SECTIONS = ("CLI options", "Settings", "Capabilities", "Reader controls", "Input and checks", "Output forms")
TEST_REFERENCE = re.compile(r"`([\w./-]+\.py)::(\w+)`")
ISSUE = re.compile(r"(?<![\w/])#\d+\b")
DECISION = re.compile(r"\]\(([\w./-]+\.md)#([\w-]+)\)")
CODE = re.compile(r"`([^`]+)`")
# Schema keywords that describe a value rather than constrain it.
PROSE = {"description", "default", "$comment", "title"}


class Row:
    def __init__(self, line: int, section: str, cells: list[str]) -> None:
        self.line, self.section = line, section
        self.feature, self.interim, self.integrated, self.status, self.evidence = cells

    @property
    def key(self) -> str:
        """The feature's identifier: its first code span, or its text."""
        match = CODE.search(self.feature)
        return match[1] if match else self.feature

    def where(self) -> str:
        return f"{TABLE.relative_to(ROOT).as_posix()}:{self.line}: {self.section}, {self.key!r}"


def rows() -> list[Row]:
    found, section = [], None
    for number, line in enumerate(TABLE.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if not line.startswith("|") or set(line) <= set("|-: ") or section not in SECTIONS:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] == "Feature":
            continue
        if len(cells) != 5:
            raise AssertionError(
                f"{TABLE.relative_to(ROOT).as_posix()}:{number}: has {len(cells)} cells, not 5 "
                "(Feature, Interim, Integrated, Status, Evidence). Write | inside a cell as \\| or "
                f"reword it; see {OWNER}")
        found.append(Row(number, section, cells))
    return found


def keys(section: str) -> list[str]:
    return [row.key for row in rows() if row.section == section]


def defines(path: Path, name: str) -> bool:
    return path.is_file() and re.search(rf"^\s*(?:async\s+)?def {name}\(",
                                         path.read_text(encoding="utf-8"), re.MULTILINE) is not None


def problems(row: Row) -> list[str]:
    """What is wrong with a row's status and evidence, each with its remedy."""
    if row.status in {"same", "added"}:
        references = TEST_REFERENCE.findall(row.evidence)
        if not references:
            return [f"says {row.status} but names no test. Name the test that shows it as `path::test_name`, "
                    "or add the smallest one"]
        return [f"names {path}::{name}, which is not a test there. Correct the name or the path"
                for path, name in references if not defines(ROOT / path, name)]
    if row.status == "known difference":
        if ISSUE.search(row.evidence):
            return []
        decisions = DECISION.findall(row.evidence)
        if not decisions:
            return ["says known difference but names no issue (#n) or design note (path.md#anchor) "
                    "that decided it. Name it, or the row is missing"]
        return [f"names the design note {path}, which does not exist. Correct the path"
                for path, _ in decisions if not (ROOT / path).is_file()]
    if row.status == "missing":
        return [] if ISSUE.search(row.evidence) else [
            "says missing but names no issue (#n). Name the issue that tracks the gap"]
    if row.status == "same (untested)":
        return ["says same (untested): parity nobody shows. Add the smallest test and say same"]
    return [f"has the status {row.status!r}, not one of {', '.join(sorted(STATUSES))}. Use one of them"]


def test_every_row_has_a_known_status_and_the_evidence_it_needs() -> None:
    table = rows()
    assert table, f"{TABLE}: holds no rows under {', '.join(SECTIONS)}; see {OWNER}"
    failures = [f"{row.where()} {problem}; see {OWNER}" for row in table for problem in problems(row)]
    assert not failures, "\n".join(failures)


def test_every_feature_has_one_row() -> None:
    seen: dict[tuple[str, str], int] = {}
    failures = []
    for row in rows():
        if (row.section, row.key) in seen:
            failures.append(f"{row.where()} repeats the row at line {seen[row.section, row.key]}. "
                            f"Merge them; see {OWNER}")
        seen.setdefault((row.section, row.key), row.line)
    assert not failures, "\n".join(failures)


def options(parser) -> set[str]:
    return {option for action in parser._actions for option in action.option_strings if option.startswith("--")}


def adapter_options() -> set[str]:
    """The options of obs-html and of its serve subcommand, each from its own parser."""
    from obs_html import serve
    from obs_html.cli import build_parser
    return options(build_parser()) | options(serve.build_parser())


def core_options() -> set[str]:
    """obs-document's options, read from its help: this adapter imports nothing of the core."""
    import subprocess
    import sys

    result = subprocess.run([sys.executable, "-m", "obs.document", "--help"], capture_output=True, text=True,
                            encoding="utf-8", check=True)
    return set(re.findall(r"(?<![\w-])(--[a-z][\w-]*)", result.stdout))


def setting_keys(schema: dict, node: dict | None = None, prefix: str = "") -> set[str]:
    """Every leaf key of a settings schema as a dotted path: a key whose value is an object with
    properties is a branch, any other key a leaf. ``$ref`` resolves within the schema."""
    node = schema if node is None else node
    found = set()
    for name, value in node.get("properties", {}).items():
        value = resolve(schema, value)
        path = f"{prefix}{name}"
        found |= setting_keys(schema, value, f"{path}.") if value.get("properties") else {path}
    return found


def resolve(schema: dict, node: dict) -> dict:
    if "$ref" not in node:
        return node
    target = schema
    for part in node["$ref"].removeprefix("#/").split("/"):
        target = target[part]
    return {**resolve(schema, target), **{key: value for key, value in node.items() if key != "$ref"}}


ADAPTER_SCHEMA = ADAPTER / "src" / "obs_html" / "cfg.schema.json"
CORE_SCHEMA = ROOT / "src" / "obs" / "config.schema.json"
# A code span of an Integrated cell that names an option or a key of the integrated CLIs.
NAMED = re.compile(r"^(obs-html|obs-document)\b(.*)$")


def setting_paths(schema: dict, node: dict | None = None, prefix: str = "") -> set[str]:
    """Every key of a settings schema as a dotted path, branches included."""
    node = schema if node is None else node
    found = set()
    for name, value in node.get("properties", {}).items():
        value = resolve(schema, value)
        found |= {f"{prefix}{name}"} | setting_paths(schema, value, f"{prefix}{name}.")
    return found


def named(section: str) -> list[tuple[Row, str, str]]:
    """Each (row, CLI, rest) for every code span of a row's Integrated cell that starts with a CLI."""
    found = []
    for row in rows():
        if row.section == section:
            for span in CODE.findall(row.integrated):
                match = NAMED.match(span)
                if match:
                    found.append((row, match[1], match[2].strip()))
    return found


def compare(listed: set[str], offered: set[str], section: str, source: str) -> None:
    unlisted = sorted(offered - listed)
    assert not unlisted, (
        f"{TABLE.relative_to(ROOT).as_posix()}: {section}: {source} offers {', '.join(unlisted)}, which no "
        f"row lists. Add a row each (status added for a feature the interim did not have); see {OWNER}")


def test_every_adapter_cli_option_has_a_row() -> None:
    listed = set(keys("CLI options")) | {option for _, cli, rest in named("CLI options") if cli == "obs-html"
                                          for option in re.findall(r"--[\w-]+", rest)}
    compare(listed, adapter_options(), "CLI options",
            "adapters/html/src/obs_html/cli.py build_parser or adapters/html/src/obs_html/serve.py build_parser")


def option_problems() -> list[str]:
    """Each CLI-options row that names an option neither CLI offers, or none at all where it must."""
    offered = {"obs-html": adapter_options(), "obs-document": core_options()}
    failures = [f"{row.where()} names `{cli} {option}`, which {cli} does not offer. Correct or remove it; "
                f"see {OWNER}"
                for row, cli, rest in named("CLI options") for option in re.findall(r"--[\w-]+", rest)
                if option not in offered[cli]]
    failures += [f"{row.where()} says {row.status} but neither its feature nor its Integrated cell names an "
                 f"option obs-html or obs-document offers. Name it; see {OWNER}"
                 for row in rows() if row.section == "CLI options" and row.status in {"same", "added"}
                 and row.key not in offered["obs-html"] | offered["obs-document"]
                 and not any(span_row.line == row.line for span_row, _, _ in named("CLI options"))]
    return failures


def test_every_option_a_row_names_is_one_the_integrated_cli_offers() -> None:
    failures = option_problems()
    assert not failures, "\n".join(failures)


def test_a_row_whose_integrated_cell_names_an_offered_option_needs_no_option_key(monkeypatch) -> None:
    """A row is the same row each time the table is read: its source line, not the object, is its identity."""
    option = sorted(adapter_options())[0]
    monkeypatch.setattr(sys.modules[__name__], "rows", lambda: [
        Row(7, "CLI options", ["Some feature", "", f"`obs-html {option}`", "same", ""])])
    assert option_problems() == []


def test_every_adapter_settings_key_has_a_row() -> None:
    listed = {rest for _, cli, rest in named("Settings") if cli == "obs-html"}
    compare(listed, setting_keys(load(ADAPTER_SCHEMA)), "Settings", "adapters/html/src/obs_html/cfg.schema.json")


def test_every_settings_key_a_row_names_is_one_the_integrated_schemas_hold() -> None:
    held = {"obs-html": setting_paths(load(ADAPTER_SCHEMA)), "obs-document": setting_paths(load(CORE_SCHEMA))}
    failures = [f"{row.where()} names `{cli} {rest}`, which {cli}'s settings schema does not hold. Correct or "
                f"remove it; see {OWNER}"
                for row, cli, rest in named("Settings") if rest and not rest.startswith("-")
                and rest.split(" ")[0].rstrip(":,") not in held[cli]]
    assert not failures, "\n".join(failures)


def test_every_capability_has_a_row() -> None:
    ids = {re.search(r"^  id: (\S+)$", note.read_text(encoding="utf-8"), re.MULTILINE)[1]
           for note in (ROOT / "spec" / "capabilities").glob("*.md")}
    compare(set(keys("Capabilities")), ids, "Capabilities", "spec/capabilities")
    unknown = sorted(set(keys("Capabilities")) - ids)
    assert not unknown, (f"{TABLE.relative_to(ROOT).as_posix()}: Capabilities: rows list {', '.join(unknown)}, "
                         f"which spec/capabilities does not hold. Correct or remove them; see {OWNER}")


# The shared settings: each "same" settings row and the key its Integrated cell names.
def shared_settings() -> list[tuple[Row, str, str]]:
    shared = []
    for row in rows():
        if row.section != "Settings" or row.status not in {"same", "added"}:
            continue
        match = CODE.search(row.integrated)
        owner, _, key = (match[1] if match else "").partition(" ")
        if owner not in {"obs-html", "obs-document"} or not key:
            raise AssertionError(
                f"{row.where()} says same but its Integrated cell does not start with the key that "
                f"holds it, `obs-html <key>` or `obs-document <key>`. Name it; see {OWNER}")
        shared.append((row, owner, key))
    return shared


MISSING = object()


def has(value: object, path: str) -> bool:
    """Whether the settings ``value`` holds the dotted ``path``."""
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return False
        value = value[part]
    return True


def lookup(value: object, path: str) -> object:
    for part in path.split("."):
        assert isinstance(value, dict) and part in value, part
        value = value[part]
    return value


def schema_node(schema: dict, path: str) -> dict:
    node = schema
    for part in path.split("."):
        node = resolve(schema, resolve(schema, node)["properties"][part])
    return node


def constraints(schema: dict, node: dict) -> object:
    """A schema node without its prose, with every reference resolved."""
    if isinstance(node, dict):
        node = resolve(schema, node)
        return {key: constraints(schema, value) for key, value in node.items() if key not in PROSE}
    if isinstance(node, list):
        return [constraints(schema, value) for value in node]
    return node


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("row, owner, key", shared_settings(), ids=lambda value: getattr(value, "key", value))
def test_a_shared_setting_keeps_its_schema_default_limits_and_reader(row, owner, key) -> None:
    """The key that holds a setting here is constrained by its own schema, its default satisfies
    those limits, and code outside the settings files reads it. The schema as it stands is the
    reference: this adapter's cfg.schema.json with its packaged cfg.json, or the core's
    config.schema.json with the default it declares. An adapter option whose absence keeps an
    artifact byte for byte what it was (architecture.md, Rendering and runtime) stays out of the
    packaged cfg.json, which every artifact carries, and declares its default in cfg.schema.json."""
    from jsonschema import Draft202012Validator

    if owner == "obs-html":
        package = ADAPTER / "src" / "obs_html"
        schema, where = load(ADAPTER_SCHEMA), "adapters/html/src/obs_html/cfg.schema.json"
        packaged = load(package / "cfg.json")
        default = (lookup(packaged, key) if has(packaged, key)
                   else schema_node(schema, key).get("default", MISSING))
        assert default is not MISSING, (f"{row.where()}: {key} has no default in the packaged cfg.json nor in "
                                        f"{where}. Declare one; see {OWNER}")
        sources = [path for path in package.rglob("*") if path.suffix in {".py", ".js"}]
    else:
        package = ROOT / "src" / "obs"
        schema, where = load(CORE_SCHEMA), "src/obs/config.schema.json"
        default = schema_node(schema, key).get("default")
        assert "default" in schema_node(schema, key), (
            f"{row.where()}: {where} {key} declares no default. Declare it; see {OWNER}")
        sources = list(package.glob("*.py"))
    limits = constraints(schema, schema_node(schema, key))
    assert {"type", "enum", "const", "pattern"} & set(limits) or name_only(key), (
        f"{row.where()}: {where} {key} accepts any value. Give it a type and its limits; see {OWNER}")
    errors = [error.message for error in Draft202012Validator({**limits, "$defs": schema.get("$defs", {})})
              .iter_errors(default)]
    assert not errors, (f"{row.where()}: the default of {key}, {default!r}, is outside {where}'s limits: "
                        f"{'; '.join(errors)}. Correct the default or the limits; see {OWNER}")
    name = key.rsplit(".", 1)[-1]
    readers = [path for path in sources if name in path.read_text(encoding="utf-8")]
    assert readers or name_only(key), (
        f"{row.where()}: no code of {package.relative_to(ROOT).as_posix()} reads {key}: the setting "
        f"is accepted but changes nothing. Read it, or say missing; see {OWNER}")


def name_only(key: str) -> bool:
    """The settings file's own bookkeeping keys, which no renderer reads."""
    return key in {"$schema", "schemaVersion"}


@pytest.mark.parametrize("status, evidence, refused", [
    ("same", "#12", "names no test"),
    ("same", "`adapters/html/test/test_cli.py::test_that_does_not_exist`", "which is not a test there"),
    ("same (untested)", "`adapters/html/test/test_cli.py::test_help_is_the_complete_cli_reference`", "nobody shows"),
    ("known difference", "decided long ago", "names no issue"),
    ("known difference", "[note](spec/nowhere.md#anchor)", "does not exist"),
    ("missing", "proposed: feature/x-20261106", "names no issue"),
    ("gone", "#3", "not one of"),
])
def test_the_gate_refuses_a_row_without_the_evidence_its_status_needs(status, evidence, refused) -> None:
    row = Row(1, "CLI options", ["`--example`", "", "", status, evidence])
    assert any(refused in problem for problem in problems(row)), problems(row)


@pytest.mark.parametrize("status, evidence", [
    ("same", "`adapters/html/test/test_cli.py::test_help_is_the_complete_cli_reference`"),
    ("known difference", "#331"),
    ("known difference", "[architecture](adapters/html/spec/architecture.md#known-differences-from-the-interim)"),
    ("missing", "#3 (proposed: feature/x-20261106)"),
])
def test_the_gate_accepts_a_row_with_the_evidence_its_status_needs(status, evidence) -> None:
    assert problems(Row(1, "CLI options", ["`--example`", "", "", status, evidence])) == []


def test_the_coverage_check_names_an_option_no_row_lists() -> None:
    """A new adapter option or key without a row fails, naming it and its source."""
    with pytest.raises(AssertionError) as refused:
        compare({"--listed"}, {"--listed", "--new-option"}, "CLI options", "cli.py build_parser")
    assert "cli.py build_parser offers --new-option, which no row lists" in str(refused.value)
    compare({"--listed", "--extra"}, {"--listed"}, "CLI options", "cli.py build_parser")
