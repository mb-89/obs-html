"""Parity gate: features.md lists what the interim adapter offers and whether this adapter does.

Reader: whoever changes either adapter, and obs#3, which deletes the interim adapter
(src/obs_html_interim) once this table holds no "missing" row.

features.md has one row per interim feature: every CLI option, every settings key, every
capability, reader control and output form. Each row's status is one of:

- "same", and its evidence names at least one test as `path::test_name`, a path from the
  repository root to a test file that defines that test;
- "known difference", and its evidence names the issue (#n) or the design note (a path to a .md
  file with its #anchor) that decided it;
- "missing", and its evidence names the issue (#n) that tracks the gap.

A row "same (untested)" is refused: it marks parity nobody shows. The table is checked against the
interim itself: its argparse parser (built, not run) and its settings schema name every option and
key the table must list. A settings row that says "same" names this adapter's key, or the core's,
in the first code span of its Integrated cell (`obs-html <key>` or `obs-document <key>`), and
test_a_shared_setting_keeps_the_interim_default_limits_and_reader holds that key to the interim's.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

TABLE = Path(__file__).with_name("features.md")
ADAPTER = Path(__file__).parents[2]
ROOT = ADAPTER.parents[1]
INTERIM = ROOT / "src" / "obs_html_interim"
OWNER = "adapters/html/test/parity/test_parity_table.py"
STATUSES = {"same", "known difference", "missing"}
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
    if row.status == "same":
        references = TEST_REFERENCE.findall(row.evidence)
        if not references:
            return ["says same but names no test. Name the test that shows it as `path::test_name`, "
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


def interim_options() -> set[str]:
    from obs_html_interim.cli import build_parser
    return {option for action in build_parser()._actions for option in action.option_strings
            if option.startswith("--")}


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


def interim_settings() -> set[str]:
    return setting_keys(json.loads((INTERIM / "cfg.schema.json").read_text(encoding="utf-8")))


def compare(listed: list[str], offered: set[str], section: str, source: str) -> None:
    unlisted = sorted(offered - set(listed))
    unknown = sorted(set(listed) - offered)
    assert not unlisted and not unknown, (
        f"{TABLE.relative_to(ROOT).as_posix()}: {section}: "
        + (f"the interim offers {', '.join(unlisted)} ({source}), which no row lists. Add a row each. "
           if unlisted else "")
        + (f"rows list {', '.join(unknown)}, which {source} does not offer. Correct or remove them. "
           if unknown else "")
        + f"See {OWNER}")


def test_every_interim_cli_option_has_a_row() -> None:
    compare(keys("CLI options"), interim_options(), "CLI options",
            "src/obs_html_interim/cli.py build_parser")


def test_every_interim_settings_key_has_a_row() -> None:
    compare(keys("Settings"), interim_settings(), "Settings", "src/obs_html_interim/cfg.schema.json")


def test_every_capability_has_a_row() -> None:
    ids = {re.search(r"^  id: (\S+)$", note.read_text(encoding="utf-8"), re.MULTILINE)[1]
           for note in (ROOT / "spec" / "capabilities").glob("*.md")}
    compare(keys("Capabilities"), ids, "Capabilities", "spec/capabilities")


# The shared settings: each "same" settings row and the key its Integrated cell names.
def shared_settings() -> list[tuple[Row, str, str]]:
    shared = []
    for row in rows():
        if row.section != "Settings" or row.status != "same":
            continue
        match = CODE.search(row.integrated)
        owner, _, key = (match[1] if match else "").partition(" ")
        if owner not in {"obs-html", "obs-document"} or not key:
            raise AssertionError(
                f"{row.where()} says same but its Integrated cell does not start with the key that "
                f"holds it, `obs-html <key>` or `obs-document <key>`. Name it; see {OWNER}")
        shared.append((row, owner, key))
    return shared


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
def test_a_shared_setting_keeps_the_interim_default_limits_and_reader(row, owner, key) -> None:
    """The key that holds an interim setting here has the interim's default and, where this
    adapter holds it, the interim's limits; and code outside the settings files reads it."""
    interim_schema = load(INTERIM / "cfg.schema.json")
    default = lookup(load(INTERIM / "cfg.json"), row.key)
    if owner == "obs-html":
        package = ADAPTER / "src" / "obs_html"
        schema = load(package / "cfg.schema.json")
        assert lookup(load(package / "cfg.json"), key) == default, (
            f"{row.where()}: adapters/html/src/obs_html/cfg.json {key} is not the interim's default "
            f"{default!r}. Restore it, or say known difference with its decision; see {OWNER}")
        assert constraints(schema, schema_node(schema, key)) == \
            constraints(interim_schema, schema_node(interim_schema, row.key)), (
            f"{row.where()}: adapters/html/src/obs_html/cfg.schema.json {key} accepts other values "
            f"than the interim's {row.key}. Restore the limits, or say known difference; see {OWNER}")
        sources = [path for path in package.rglob("*") if path.suffix in {".py", ".js"}]
    else:
        package = ROOT / "src" / "obs"
        node = schema_node(load(package / "config.schema.json"), key)
        assert node.get("default") == default, (
            f"{row.where()}: src/obs/config.schema.json {key} defaults to {node.get('default')!r}, "
            f"not the interim's {default!r}. Restore it, or say known difference; see {OWNER}")
        sources = list(package.glob("*.py"))
    name = key.rsplit(".", 1)[-1]
    readers = [path for path in sources if name in path.read_text(encoding="utf-8")]
    assert readers or name in {"$schema", "schemaVersion"}, (
        f"{row.where()}: no code of {package.relative_to(ROOT).as_posix()} reads {key}: the setting "
        f"is accepted but changes nothing. Read it, or say missing; see {OWNER}")


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
