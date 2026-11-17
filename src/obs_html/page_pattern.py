"""A schema ``pattern`` answered as the page's JavaScript answers it.

JSON Schema's patterns are JavaScript patterns, and the page checks a table definition with
``new RegExp(pattern).test(text)`` (base.js, ``patternMatches``). Python's ``re`` reads some of the
same signs differently, so :func:`matches` translates a pattern into ``re`` first and answers what
the page answers (input-model.md, Compact declarative table presentation). These rules own the
translation:

- It searches the text as JavaScript does without flags, over UTF-16 code units: the pattern and
  the text are both read as code units, so a character above U+FFFF counts as two.
- ``$`` outside a class means the very end of the text (``\\Z``), never the place before a final
  line break; ``^`` means the very start.
- ``\\s`` is JavaScript's set of spaces, :data:`JS_SPACES`: U+0009 to U+000D, U+0020, U+00A0,
  U+1680, U+2000 to U+200A, U+2028, U+2029, U+202F, U+205F, U+3000 and U+FEFF. ``\\S`` is every
  other code unit, inside a class too.

It reads only this subset of signs, enough for every pattern the page checks:

- literal characters;
- the escapes ``\\\\ \\/ \\. \\- \\^ \\$ \\* \\+ \\? \\( \\) \\[ \\] \\{ \\} \\| \\"`` and
  ``\\t \\n \\r \\f \\v``;
- ``\\s`` and ``\\S``;
- classes and negated classes of literal characters, these escapes, ``\\s`` and ``\\S``, with ranges
  between two characters;
- ``^`` and ``$``;
- the groups ``( )``, ``(?: )``, ``(?= )`` and ``(?! )``, and ``|``;
- the quantifiers ``* + ? {n} {n,} {n,m}`` after a character, a class or a ``( )`` or ``(?: )``
  group, each greedy or lazy (a trailing ``?``).

Any other sign, such as ``.``, ``\\d``, ``\\w``, ``\\b``, ``\\Z``, a back reference, a lookbehind, an
inline flag, an empty class or a quantifier on nothing, raises an :class:`InputError` at field
``pattern`` that names the pattern and the sign, so a new pattern cannot read differently in the
build and the page without notice. Compiled patterns are cached.

Pure and standalone: it imports the standard library and only ``InputError`` from obs_html.
"""
from __future__ import annotations

import re
from array import array
from functools import lru_cache

from obs_html.errors import InputError

SOURCE = "obs-html (src/obs_html/page_pattern.py)"

JS_SPACES = (*range(0x09, 0x0E), 0x20, 0xA0, 0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F,
             0x205F, 0x3000, 0xFEFF)
"""The code units JavaScript's ``\\s`` matches: its WhiteSpace and LineTerminator code points."""

ESCAPED = frozenset('\\/.-^$*+?()[]{}|"')
"""The signs a backslash makes literal."""
CONTROLS = {"t": 0x09, "n": 0x0A, "r": 0x0D, "f": 0x0C, "v": 0x0B}
"""The control escapes and the code unit each stands for."""
QUANTIFIER = re.compile(r"\{([0-9]+)(,([0-9]*))?\}")
"""A bounded quantifier, ``{n}``, ``{n,}`` or ``{n,m}``, at the place it is read."""


def _unit(code: int) -> str:
    return f"\\u{code:04x}"


def _spans(codes: tuple[int, ...]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for code in sorted(codes):
        if spans and spans[-1][1] + 1 == code:
            spans[-1] = (spans[-1][0], code)
        else:
            spans.append((code, code))
    return spans


def _members(spans: list[tuple[int, int]]) -> str:
    return "".join(_unit(low) if low == high else f"{_unit(low)}-{_unit(high)}" for low, high in spans)


SPACE_SPANS = _spans(JS_SPACES)
NON_SPACE_SPANS = [(low, high) for low, high in zip(
    [0, *(high + 1 for _, high in SPACE_SPANS)], [*(low - 1 for low, _ in SPACE_SPANS), 0xFFFF]) if low <= high]
SPACE = _members(SPACE_SPANS)
"""``\\s`` as members of a Python class."""
NON_SPACE = _members(NON_SPACE_SPANS)
"""``\\S`` as members of a Python class: every code unit ``\\s`` does not hold."""


def _units(text: str) -> str:
    """``text`` as its UTF-16 code units, one character each: what JavaScript counts and searches."""
    if all(ord(character) <= 0xFFFF for character in text):
        return text
    return "".join(map(chr, array("H", text.encode("utf-16-le", "surrogatepass"))))


def _refuse(pattern: str, sign: str) -> InputError:
    return InputError(SOURCE, "pattern", f"is {pattern!r}, which holds {sign}, a sign outside the subset the "
                      "build reads as the page does", "Write the pattern with the signs page_pattern.py lists, "
                      "or teach page_pattern.py the sign with a case in test/fixtures/pattern-conformance.json")


def _translate(pattern: str) -> str:
    """``pattern``, a JavaScript pattern of the subset, as a Python pattern over code units."""
    source = _units(pattern)
    out: list[str] = []
    groups: list[bool] = []  # per open group: may a quantifier follow it once it closes
    quantifiable = False
    position = 0

    def escape(at: int, in_class: bool) -> tuple[str, int | None]:
        """The escape at ``at`` (its backslash) as Python text and, for a single character, its code."""
        if at + 1 >= len(source):
            raise _refuse(pattern, "a trailing backslash")
        sign = source[at + 1]
        if sign in ESCAPED:
            return _unit(ord(sign)), ord(sign)
        if sign in CONTROLS:
            return _unit(CONTROLS[sign]), CONTROLS[sign]
        if sign in "sS":
            members = SPACE if sign == "s" else NON_SPACE
            return (members if in_class else f"[{members}]"), None
        raise _refuse(pattern, f"\\{sign}")

    while position < len(source):
        sign = source[position]
        if sign == "\\":
            text, _ = escape(position, in_class=False)
            out.append(text)
            position += 2
            quantifiable = True
        elif sign == "[":
            position += 1
            negated = position < len(source) and source[position] == "^"
            position += negated
            members: list[str] = []
            while True:
                if position >= len(source):
                    raise _refuse(pattern, "an unclosed class")
                if source[position] == "]":
                    break
                if source[position] == "\\":
                    text, low = escape(position, in_class=True)
                    position += 2
                else:
                    low = ord(source[position])
                    text = _unit(low)
                    position += 1
                if (position + 1 < len(source) and source[position] == "-" and source[position + 1] != "]"):
                    if low is None:
                        raise _refuse(pattern, "a range from \\s or \\S")
                    if source[position + 1] == "\\":
                        _, high = escape(position + 1, in_class=True)
                        position += 3
                    else:
                        high = ord(source[position + 1])
                        position += 2
                    if high is None:
                        raise _refuse(pattern, "a range to \\s or \\S")
                    if high < low:
                        raise _refuse(pattern, "a range out of order")
                    text = f"{_unit(low)}-{_unit(high)}"
                members.append(text)
            if not members:
                raise _refuse(pattern, "an empty class")
            out.append(f"[{'^' if negated else ''}{''.join(members)}]")
            position += 1
            quantifiable = True
        elif sign == "(":
            opener = source[position:position + 3]
            if opener in {"(?:", "(?=", "(?!"}:
                out.append(opener)
                groups.append(opener == "(?:")
                position += 3
            elif opener.startswith("(?"):
                raise _refuse(pattern, f"the group {opener!r}")
            else:
                out.append("(")
                groups.append(True)
                position += 1
            quantifiable = False
        elif sign == ")":
            if not groups:
                raise _refuse(pattern, "an unopened )")
            quantifiable = groups.pop()
            out.append(")")
            position += 1
        elif sign == "|":
            out.append("|")
            position += 1
            quantifiable = False
        elif sign == "^":
            out.append(r"\A")
            position += 1
            quantifiable = False
        elif sign == "$":
            out.append(r"\Z")
            position += 1
            quantifiable = False
        elif sign in "*+?{":
            bounded = QUANTIFIER.match(source, position) if sign == "{" else None
            if sign == "{" and bounded is None:
                raise _refuse(pattern, "a { that is no quantifier")
            if not quantifiable:
                raise _refuse(pattern, f"the quantifier {sign!r} on nothing it can repeat")
            if bounded is not None and bounded[3] and int(bounded[3]) < int(bounded[1]):
                raise _refuse(pattern, f"the quantifier {bounded[0]!r} out of order")
            end = bounded.end() if bounded is not None else position + 1
            out.append(source[position:end])
            position = end
            if position < len(source) and source[position] == "?":
                out.append("?")
                position += 1
            quantifiable = False
        elif sign in ".]}":
            raise _refuse(pattern, repr(sign))
        else:
            out.append(_unit(ord(sign)))
            position += 1
            quantifiable = True
    if groups:
        raise _refuse(pattern, "an unclosed group")
    return "".join(out)


@lru_cache(maxsize=None)
def _compiled(pattern: str) -> re.Pattern[str]:
    return re.compile(_translate(pattern))


def matches(pattern: str, text: str) -> bool:
    """What ``new RegExp(pattern).test(text)`` answers in the page, for a pattern of the subset."""
    return _compiled(pattern).search(_units(text)) is not None
