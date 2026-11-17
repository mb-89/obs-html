"""The build reads a Base definition's patterns as the page's JavaScript reads them (input-model.md,
Compact declarative table presentation; obs_html.page_pattern).

``fixtures/pattern-conformance.json`` holds the page's answers; pattern-conformance.test.js runs it
through base.js's ``patternMatches``, these tests through ``page_pattern.matches`` and the build's
Base check. The table must hold every pattern base.js reaches, so a new one cannot go unchecked.
"""
import copy
import json

import pytest

from conftest import ROOT
from obs_html.errors import InputError
from obs_html.page_pattern import matches
from obs_html.render import base_definition_error

SCHEMAS = ROOT / "src" / "obs_html"
FIXTURE = json.loads((ROOT / "test" / "fixtures" / "pattern-conformance.json").read_text(encoding="utf-8"))
TABLE = {"type": "table", "name": "T", "order": ["file.name"]}
PAGE_PATTERN = "obs-html (src/obs_html/page_pattern.py)"


def _reached_patterns() -> set[str]:
    """Every ``pattern`` base.js's validateNode reaches from base.schema.json's root, following its
    ``$ref``s into assets.schema.json, and the ``unsupportedProperty`` pattern its supportedProperty reads."""
    owners = {name: json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
              for name in ("base.schema.json", "assets.schema.json")}
    found: set[str] = {owners["base.schema.json"]["$defs"]["unsupportedProperty"]["pattern"]}
    seen: set[tuple[str, str]] = set()

    def walk(rule: dict, owner: str) -> None:
        if "$ref" in rule:
            file, fragment = rule["$ref"].split("#")
            owner = file or owner
            if (owner, fragment) in seen:
                return
            seen.add((owner, fragment))
            target = owners[owner]
            for key in fragment.lstrip("/").split("/"):
                target = target[key.replace("~1", "/").replace("~0", "~")]
            walk(target, owner)
            return
        if isinstance(rule.get("pattern"), str):
            found.add(rule["pattern"])
        for keyword in ("items", "additionalProperties", "not"):
            if isinstance(rule.get(keyword), dict):
                walk(rule[keyword], owner)
        for choice in rule.get("oneOf", []):
            walk(choice, owner)
        for item in rule.get("properties", {}).values():
            walk(item, owner)

    walk(owners["base.schema.json"], "base.schema.json")
    return found


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: f"{case['pattern']!r} {case['text']!r}")
def test_each_case_gives_the_pages_answer(case: dict) -> None:
    assert matches(case["pattern"], case["text"]) is case["matches"]


def test_the_table_holds_every_pattern_base_js_reaches_with_a_matching_and_a_refused_text() -> None:
    answers: dict[str, set[bool]] = {}
    for case in FIXTURE["cases"]:
        answers.setdefault(case["pattern"], set()).add(case["matches"])
    reached = _reached_patterns()
    assert reached <= set(answers)
    assert {pattern: answer for pattern, answer in answers.items() if pattern in reached and answer != {True, False}} == {}


@pytest.mark.parametrize("pattern", [".", "\\d", "\\Z"])
def test_a_sign_outside_the_subset_is_an_input_error_at_pattern(pattern: str) -> None:
    with pytest.raises(InputError) as failure:
        matches(pattern, "text")
    assert (failure.value.source, failure.value.field) == (PAGE_PATTERN, "pattern")


def test_a_view_projection_that_ends_in_a_line_break_fails_at_its_field() -> None:
    error = base_definition_error({"obsHtml": {"viewProjection": "mapping\n"}, "views": [dict(TABLE)]}, "t.base")
    assert error is not None and (error.source, error.field) == ("t.base", "obsHtml.viewProjection")


def _passing(label: str) -> dict:
    view = copy.deepcopy(TABLE)
    view["obsHtml"] = {"passing": {"filters": 'kind == "Item"', "label": label}}
    return {"views": [view]}


def test_a_passing_label_of_only_a_byte_order_mark_fails_at_its_field() -> None:
    error = base_definition_error(_passing("﻿"), "t.base")
    assert error is not None and (error.source, error.field) == ("t.base", "views[0].obsHtml.passing.label")


def test_a_passing_label_of_one_invisible_control_character_passes() -> None:
    assert base_definition_error(_passing("\u001f"), "t.base") is None
