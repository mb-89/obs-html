"""The one message form of obs-html's own input errors: its settings file, the obsHtml presentation
keys a Document carries, and its command-line arguments.

``<file or note>: <field path>: <what is wrong>. <remedy>.``, the form of the core's contract
failures (obs input-model, Chapter content), written here again because the adapter does not
import the core. A test matches an error by its ``source`` and ``field``, never by its wording.
"""
from __future__ import annotations

import json

from jsonschema.exceptions import ValidationError, best_match


class InputError(ValueError):
    """One of obs-html's own inputs is invalid; ``source`` and ``field`` say where."""

    def __init__(self, source: object, field: str, problem: str, remedy: str) -> None:
        self.source, self.field = str(source), field or "top level"
        super().__init__(f"{self.source}: {self.field}: {problem}. {remedy}.")


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
