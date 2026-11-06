"""An inline authored drawing's ``<style>`` scoped to its own figure: authored content never styles
anything outside itself.

Reader: whoever changes how an inline figure's styles apply (artifact-ui.md, Links inside a
figure).

The CSS is parsed with tinycss2. Each selector of each rule becomes ``:where(#<anchor>) <selector>``,
so it matches only inside the figure's frame and keeps its authored specificity; rules inside
the conditional group rules in ``NESTING`` are scoped the same way. ``@keyframes`` names take the
anchor as prefix, together with the drawing's own animation names that use them. Every other
at-rule is global and is dropped; each drop is a warning in the one message form (errors.py)
naming the note, ``figure.style`` and the figure's anchor.
"""
from __future__ import annotations

import re
import sys
from html import unescape
from xml.sax.saxutils import escape

import tinycss2
from tinycss2.ast import AtRule, CurlyBracketsBlock, IdentToken, LiteralToken, QualifiedRule, StringToken, WhitespaceToken
from tinycss2.serializer import serialize_identifier

from .errors import InputError

FIELD = "figure.style"
"""The field a warning names: the ``<style>`` elements of the figure's drawing."""
NESTING = frozenset({"media", "supports", "container"})
"""Conditional group rules: their own condition is not global, their rules are scoped one by one."""
ANIMATION = frozenset({"animation", "animation-name"})
"""The declarations that name a ``@keyframes`` rule."""
STYLE = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.DOTALL)
"""A ``<style>`` element as figure_links.py's serializer writes it: its text is escaped, so no
``</style>`` occurs inside it."""


def scope_styles(markup: str, anchor: str, source: str) -> str:
    """``markup``, an inline drawing as figure_links.py writes it, with each ``<style>`` scoped to
    the figure ``anchor``; ``source`` is the note of its figure fence, as a warning names it."""
    scoped = _Scope(anchor, source)
    return STYLE.sub(lambda found: found[1] + escape(scoped.stylesheet(unescape(found[2]))) + found[3], markup)


class _Scope:
    def __init__(self, anchor: str, source: str) -> None:
        self.anchor, self.source = anchor, source
        self.prefix = f":where(#{serialize_identifier(anchor)}) "
        self.keyframes: dict[str, str] = {}

    def warn(self, problem: str) -> None:
        error = InputError(self.source, FIELD, f"figure {self.anchor} {problem}",
                           "Style only the drawing, with rules that select its own elements")
        print(f"Warning: {error}", file=sys.stderr)

    def stylesheet(self, css: str) -> str:
        rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
        self.keyframes = {}
        self._collect(rules)
        return self._rules(rules)

    def _collect(self, rules: list) -> None:
        for rule in rules:
            if isinstance(rule, AtRule) and rule.content is not None:
                if rule.lower_at_keyword == "keyframes":
                    name = _keyframes_name(rule)
                    if name is not None:
                        self.keyframes[name] = serialize_identifier(f"{self.anchor}--{name}")
                elif rule.lower_at_keyword in NESTING:
                    self._collect(_rule_list(rule.content))

    def _rules(self, rules: list) -> str:
        return "".join(self._rule(rule) for rule in rules)

    def _rule(self, rule) -> str:
        if isinstance(rule, QualifiedRule):
            return self._qualified(rule)
        if not isinstance(rule, AtRule):
            return ""  # A parse error, which a browser ignores as well.
        keyword = rule.lower_at_keyword
        if keyword in NESTING and rule.content is not None:
            return f"@{rule.at_keyword}{tinycss2.serialize(rule.prelude)}{{{self._rules(_rule_list(rule.content))}}}"
        name = _keyframes_name(rule) if keyword == "keyframes" else None
        if name is not None:
            return f"@{rule.at_keyword} {self.keyframes[name]}{{{tinycss2.serialize(rule.content)}}}"
        self.warn(f"has the at-rule @{rule.at_keyword}, which applies to the whole page and cannot be "
                  "scoped to the figure; it is dropped")
        return ""

    def _qualified(self, rule: QualifiedRule) -> str:
        selectors = _split(rule.prelude)
        if any(not tinycss2.serialize(selector).strip() for selector in selectors):
            return ""  # An empty selector makes the rule invalid; scoped, it would select the frame.
        prelude = ",".join(self.prefix + tinycss2.serialize(selector).strip() for selector in selectors)
        return f"{prelude}{{{tinycss2.serialize(self._renamed(rule.content))}}}"

    def _renamed(self, tokens: list) -> list:
        """The rule's block with each animation name of a scoped ``@keyframes`` renamed, also in
        nested rules."""
        if not self.keyframes:
            return tokens
        result, declaration, start = [], None, True
        for index, token in enumerate(tokens):
            if isinstance(token, CurlyBracketsBlock):
                token = CurlyBracketsBlock(token.source_line, token.source_column, self._renamed(token.content))
                declaration, start = None, True
            elif isinstance(token, LiteralToken) and token.value == ";":
                declaration, start = None, True
            elif isinstance(token, IdentToken) and start:
                following = next((after for after in tokens[index + 1:] if not isinstance(after, WhitespaceToken)), None)
                declaration = token.lower_value if isinstance(following, LiteralToken) and following.value == ":" else None
                start = False
            elif isinstance(token, IdentToken) and declaration in ANIMATION and token.value in self.keyframes:
                token = IdentToken(token.source_line, token.source_column, self.keyframes[token.value])
            elif not isinstance(token, WhitespaceToken):
                start = False
            result.append(token)
        return result


def _rule_list(tokens: list) -> list:
    return tinycss2.parse_rule_list(tokens, skip_comments=True, skip_whitespace=True)


def _keyframes_name(rule: AtRule) -> str | None:
    names = [token for token in rule.prelude if not isinstance(token, WhitespaceToken)]
    if len(names) == 1 and isinstance(names[0], (IdentToken, StringToken)):
        return names[0].value
    return None


def _split(prelude: list) -> list[list]:
    """A selector list's selectors, split at its top-level commas."""
    selectors = [[]]
    for token in prelude:
        if isinstance(token, LiteralToken) and token.value == ",":
            selectors.append([])
        else:
            selectors[-1].append(token)
    return selectors

