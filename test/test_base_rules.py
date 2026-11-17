"""The build refuses what base.js refuses in a table beyond the schema (input-model.md, Compact
declarative table presentation; obs_html.base_rules).

``fixtures/base-rules.json`` is the one list of Base definitions; base-rules.test.js runs it through
base.js, these tests through the build: a refused case fails at its note and field, an accepted one
builds. The guard holds the list to base.js: a ``throw`` in ``validate`` or ``supportedProperty``
that no rule of the list names fails it.
"""
import copy
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from conftest import ROOT
from documents import chapter, document, node
from obs_html.base_rules import RULES, first_breach
from obs_html.config import load_config
from obs_html.errors import InputError
from obs_html.render import base_definition_error, render

CONFIG = load_config()
FIXTURE = json.loads((ROOT / "test" / "fixtures" / "base-rules.json").read_text(encoding="utf-8"))
BASE_JS = ROOT / "src" / "obs_html" / "base.js"
REGISTERS = json.loads((ROOT / "test" / "fixtures" / "documents" / "registers.json").read_text(encoding="utf-8"))
GUARDED = ("validate", "supportedProperty")
"""The base.js functions whose every throw a rule of the list names; project's other throws need
another note's values and stay in the page."""


def _fence(definition: dict, home: bool) -> dict:
    fence = node("bases", source="", spec=copy.deepcopy(definition))
    return document("Rules", abstract=(fence,)) if home else document("Rules", chapter("one", "One", fence))


@pytest.mark.parametrize("home", [False, True], ids=["chapter", "home"])
@pytest.mark.parametrize("case", FIXTURE["refused"], ids=lambda case: case["name"])
def test_a_refused_case_fails_the_build_at_its_note_and_field(case: dict, home: bool) -> None:
    with pytest.raises(InputError) as failure:
        render(_fence(case["definition"], home), CONFIG)
    assert (failure.value.source, failure.value.field) == ("manifest.md" if home else "chapter one", case["field"])


@pytest.mark.parametrize("home", [False, True], ids=["chapter", "home"])
@pytest.mark.parametrize("case", FIXTURE["accepted"], ids=lambda case: case["name"])
def test_an_accepted_case_builds(case: dict, home: bool) -> None:
    render(_fence(case["definition"], home), CONFIG)


@pytest.mark.parametrize("case", FIXTURE["refused"], ids=lambda case: case["name"])
def test_a_base_file_names_the_field_without_base_and_a_one_view_table_by_its_index_in_the_file(case: dict) -> None:
    """A .base file's fields sit at the top; a one-view table's view is named by its index in the file."""
    field = case["field"].removeprefix("base.")
    error = base_definition_error(copy.deepcopy(case["definition"]), "rules.base")
    assert (error.source, error.field) == ("rules.base", field)
    if len(case["definition"]["views"]) == 1:
        error = base_definition_error(copy.deepcopy(case["definition"]), "rules.base", views=[3])
        assert (error.source, error.field) == ("rules.base", re.sub(r"^views\[0\]", "views[3]", field))
    for accepted in FIXTURE["accepted"]:
        assert base_definition_error(copy.deepcopy(accepted["definition"]), "rules.base") is None, accepted["name"]


def test_the_build_breaks_each_refused_case_by_its_rule_and_names_the_rules_the_list_names() -> None:
    """base_rules.py's rules are the list's, and each refused case breaks the rule it names."""
    assert RULES == FIXTURE["rules"]
    assert {case["name"]: first_breach(case["definition"]).rule for case in FIXTURE["refused"]} == \
        {case["name"]: case["rule"] for case in FIXTURE["refused"]}


def _second(document_: dict) -> dict:
    """The register that embeds points.base by its second view's heading."""
    stack = list(next(item for item in document_["chapters"] if item["id"] == "second")["content"])
    while stack[0]["type"] != "registers":
        stack[:1] = stack[0]["children"]
    assert stack[0]["attrs"]["view"] == 1
    return stack[0]


def test_a_register_embedded_by_one_view_is_checked_as_that_one_view() -> None:
    """The rules run on the table the page gets: the file's other views neither break the name rule
    nor show an expanded column for the embedded one."""
    repeated = copy.deepcopy(REGISTERS)
    base = _second(repeated)["attrs"]["base"]
    base["views"][0]["name"] = base["views"][1]["name"]
    render(repeated, CONFIG)
    unshown = copy.deepcopy(REGISTERS)
    register = _second(unshown)["attrs"]
    register["base"]["views"][0]["order"].append("phase")
    register["base"]["obsHtml"] = {"expandProperties": {"phase": {
        "sourceNote": "columns", "property": "phases", "keyProperty": "key"}}}
    with pytest.raises(InputError) as failure:
        render(unshown, CONFIG)
    assert (failure.value.source, failure.value.field) == (register["target"], "obsHtml.expandProperties.phase")


PROPERTY_FIELDS = {
    "base.properties.<key>": r"base\.properties\.[^.]+\.[^.]+$",
    "base.views[i].order[j]": r"base\.views\[\d+\]\.order\[\d+\]$",
    "base.views[i].columnSize.<key>": r"base\.views\[\d+\]\.columnSize\..+$",
    "base.views[i].groupBy.property": r"base\.views\[\d+\]\.groupBy\.property$",
    "base.views[i].sort[k].property": r"base\.views\[\d+\]\.sort\[\d+\]\.property$",
    "base.views[i].sort.property": r"base\.views\[\d+\]\.sort\.property$",
    "base.properties.<p>.obsHtml.leadingLines[j]": r"base\.properties\.[^.]+\.obsHtml\.leadingLines\[\d+\]$",
}


def test_the_cases_cover_every_rule_every_property_field_and_the_edge_cases() -> None:
    refused, accepted = FIXTURE["refused"], FIXTURE["accepted"]
    assert {case["rule"] for case in refused} == set(FIXTURE["rules"])
    fields = [case["field"] for case in refused if case["rule"] == "unsupported-property"]
    assert {name for name, pattern in PROPERTY_FIELDS.items() if any(re.match(pattern, field) for field in fields)} \
        == set(PROPERTY_FIELDS)
    conflicts = {case["field"].rsplit(".", 1)[1] for case in refused if case["rule"] == "leading-lines-with-presentation"}
    assert conflicts == {"icon", "icons", "reference", "editable"}
    views = lambda case: case["definition"]["views"]  # noqa: E731
    assert any(view.get("columnSize") == {} for case in refused for view in views(case))
    assert any("file.name\n" in view["order"] for case in refused for view in views(case))
    assert any([view.get("name") for view in views(case)] == ["A", "﻿"] for case in refused)
    assert any(view.get("obsHtml") == {"showEmptyGroups": False} for case in accepted for view in views(case))
    assert any(len(views(case)) == 1 and "name" not in views(case)[0] for case in accepted)
    assert any([view.get("name") for view in views(case)] == ["A", "\u001f"] for case in accepted)
    assert any("file.name" in view["order"] for case in accepted for view in views(case))
    assert any(case["definition"].get("filters") == "note.formula.x == 1" for case in accepted)


def test_a_formula_property_filter_still_fails_at_base_filters() -> None:
    """The filter note.formula.x reads a note property, as the core does; formula.x stays refused."""
    with pytest.raises(InputError) as failure:
        render(_fence({"filters": "formula.x == 1", "views": [{"type": "table", "order": ["file.name"]}]}, False), CONFIG)
    assert (failure.value.source, failure.value.field) == ("chapter one", "base.filters")


def _function(script: str, name: str) -> str:
    """The source of base.js's arrow function ``name``, to the next declaration at its indentation."""
    match = re.search(rf"^( *)const {name} = .*?(?=^\1const )", script, re.MULTILINE | re.DOTALL)
    assert match, f"base.js has no function {name}"
    return match[0]


def _unnamed_throws(path: Path) -> dict[str, tuple[int, int]]:
    """Per guarded function whose throws and fixture rules differ in number: (throws, rules)."""
    script = path.read_text(encoding="utf-8")
    rules = Counter(FIXTURE["rules"].values())
    counts = {name: (len(re.findall(r"\bthrow\b", _function(script, name))), rules[name]) for name in GUARDED}
    return {name: count for name, count in counts.items() if count[0] != count[1]}


def test_every_throw_of_base_js_validate_has_a_rule_with_an_example(tmp_path: Path) -> None:
    """A rule base.js's check gains fails here until base-rules.json names it, with an example, and
    base_rules.py repeats it."""
    assert _unnamed_throws(BASE_JS) == {}
    script = BASE_JS.read_text(encoding="utf-8")
    anchor = "        compileFilter(definition.filters, () => undefined);\n"
    assert anchor in script
    grown = tmp_path / "base.js"
    grown.write_text(script.replace(anchor, anchor + '        if (definition.x) throw new TypeError("x");\n'),
                     encoding="utf-8")
    assert _unnamed_throws(grown) == {"validate": (6, 5)}
