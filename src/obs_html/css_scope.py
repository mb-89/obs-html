"""The tinycss2 helpers that scope authored CSS: an inline drawing's styles to its figure
(figure_styles.py) and a local theme's rules to its name (style_choice.py).

Reader: whoever changes how either reads a selector or a rule list. Each helper takes parsed
tokens and returns tokens or a fact about them, and reads nothing else.
"""
from __future__ import annotations

import tinycss2
from tinycss2.ast import IdentToken, LiteralToken, WhitespaceToken

PAGE = frozenset({"html", "body"})
"""Type selectors that match only the page, never an element of a drawing."""


def rule_list(tokens: list) -> list:
    """The rules of an at-rule's block, without comments and whitespace."""
    return tinycss2.parse_rule_list(tokens, skip_comments=True, skip_whitespace=True)


def split(prelude: list) -> list[list]:
    """A selector list's selectors, split at its top-level commas."""
    selectors = [[]]
    for token in prelude:
        if isinstance(token, LiteralToken) and token.value == ",":
            selectors.append([])
        else:
            selectors[-1].append(token)
    return selectors


def page_name(selector: list, index: int) -> str | None:
    """``root``, ``html`` or ``body`` where the selector's token at ``index`` names that compound,
    outside a pseudo-class's arguments; else None."""
    token = selector[index]
    if not isinstance(token, IdentToken):
        return None
    previous = selector[index - 1] if index else None
    if token.lower_value == "root" and isinstance(previous, LiteralToken) and previous.value == ":" and not (
            index > 1 and isinstance(selector[index - 2], LiteralToken) and selector[index - 2].value == ":"):
        return "root"
    if token.lower_value in PAGE and (previous is None or isinstance(previous, WhitespaceToken) or (
            isinstance(previous, LiteralToken) and previous.value in {">", "+", "~"})):
        return token.lower_value
    return None


def names_page(selector: list) -> bool:
    """Whether a compound of the selector, outside a pseudo-class's arguments, is ``:root``,
    ``html`` or ``body``."""
    return any(page_name(selector, index) for index in range(len(selector)))


def leading_root(selector: list) -> int:
    """The number of tokens of the ``:root`` or ``html`` the selector's first compound starts with,
    0 where it starts with neither; ``selector`` has no leading whitespace."""
    if selector and page_name(selector, 0) == "html":
        return 1
    if len(selector) > 1 and page_name(selector, 1) == "root":
        return 2
    return 0
