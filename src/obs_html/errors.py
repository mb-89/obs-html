"""The one message form of every error obs-html raises: its settings file, the notes and keys a
Document carries, the Document itself, a style module, a returned artifact, and the arguments of
its commands. test_errors.py fails on a raise that does not go through it.

``<source>: <field path>: <what is wrong>. <remedy>.``, the form of the core's contract failures
(obs input-model, Chapter content), written here again because the adapter does not import the
core. The source is a file or note (its vault-relative path), ``Document of <manifest>`` for a
Document the current core does not write, or a command for its arguments. A test matches an
error by its ``source`` and ``field``, never by its wording.
"""
from __future__ import annotations

import argparse
import json
import sys

from jsonschema.exceptions import ValidationError, best_match


class InputError(ValueError):
    """Something obs-html reads is invalid; ``source`` and ``field`` say where, ``remedy`` how to fix it."""

    def __init__(self, source: object, field: str, problem: str, remedy: str) -> None:
        self.source, self.field, self.problem, self.remedy = str(source), field or "top level", problem, remedy
        super().__init__(f"{self.source}: {self.field}: {problem}. {remedy}.")


class Parser(argparse.ArgumentParser):
    """A command's argument parser whose own refusals (an unknown, missing or malformed argument)
    take the one form, naming the command (``obs-html``, ``obs-html-inspect render``)."""

    def error(self, message: str):
        self.print_usage(sys.stderr)
        self.exit(2, f"{InputError(self.prog, 'arguments', message, f'Run {self.prog} --help for the accepted arguments')}\n")


def field_path(parts: list[object] | tuple[object, ...], prefix: str = "") -> str:
    """A field path as the messages write it: ``obsHtml.pages[0].page``."""
    path = prefix
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else f".{part}" if path else str(part)
    return path


def schema_error(errors: list[ValidationError], source: object, reference: str,
                 prefix: str = "") -> InputError | None:
    """The most relevant schema failure in the one form, or None without failures. ``prefix``
    is the field the validated value sits at; ``reference`` names the schema that owns it."""
    if not errors:
        return None
    error = best_match(errors)
    parts, problem, remedy = _describe(error)
    if "propertyNames" in error.absolute_schema_path:
        parts = [error.instance, *parts]  # The refused key is the value checked; it sits at its own path.
    return InputError(source, field_path([*error.absolute_path, *parts], prefix), problem,
                      f"{remedy}; see {reference}")


_KINDS = {"array": "a list", "object": "a mapping", "string": "text", "boolean": "true or false",
          "integer": "a whole number", "number": "a number", "null": "empty"}


def _shown(value: object) -> str:
    text = json.dumps(value, default=str, ensure_ascii=False)
    return text if len(text) <= 60 else text[:57] + "..."


def _describe(error: ValidationError) -> tuple[list[object], str, str]:
    """The extra path parts, the problem and the remedy of one schema failure, in plain words."""
    keyword, expected, value = error.validator, error.validator_value, error.instance
    if keyword == "type":
        kinds = expected if isinstance(expected, list) else [expected]
        wanted = " or ".join(_KINDS.get(kind, kind) for kind in kinds)
        return [], f"must be {wanted}, not {_shown(value)}", f"Write {wanted}"
    if keyword in {"enum", "const"}:
        allowed = ", ".join(_shown(item) for item in (expected if keyword == "enum" else [expected]))
        return [], f"is {_shown(value)}, not one of {allowed}", f"Write one of {allowed}"
    if keyword == "required":
        missing = next(name for name in expected if name not in value)
        return [missing], "is missing", f"Add {missing}"
    if keyword == "additionalProperties":
        known = set(error.schema.get("properties", {}))
        extra = sorted(name for name in value if name not in known)[0]
        return [extra], "is not a known key", f"Remove it or write one of {', '.join(sorted(known))}"
    if keyword in {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}:
        bound = {"minimum": "at least", "maximum": "at most", "exclusiveMinimum": "above",
                 "exclusiveMaximum": "below"}[keyword]
        return [], f"is {_shown(value)}, not {bound} {expected}", f"Write a number {bound} {expected}"
    if keyword in {"minItems", "maxItems", "minLength", "maxLength", "minProperties", "maxProperties"}:
        bound = "at least" if keyword.startswith("min") else "at most"
        unit = "items" if "Items" in keyword else "characters" if "Length" in keyword else "keys"
        return [], f"has {len(value)} {unit}, not {bound} {expected}", f"Give it {bound} {expected} {unit}"
    if keyword == "pattern":
        return [], f"is {_shown(value)}, which does not match {expected}", f"Write text that matches {expected}"
    return [], f"is {_shown(value)}, which the schema does not allow ({keyword})", "Write an allowed value"
