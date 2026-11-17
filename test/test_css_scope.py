"""The shared CSS scoping helpers (css_scope.py), which figure_styles.py and style_choice.py import:
CSS text in, tokens or facts out.

Reader: whoever changes how a figure's styles or a local theme's rules read a selector.
"""
import pytest
import tinycss2

from obs_html.css_scope import leading_root, names_page, rule_list, split

@pytest.mark.parametrize("selector, root", [
    (":root", 2), (":root.paged .chapter", 2), ("html", 1), ("HTML body p", 1),
    (".chapter :root", 0), ("body p", 0), ("::root", 0), (":is(:root) p", 0), ("htmlx", 0),
])
def test_a_leading_root_is_the_tokens_of_its_first_compound(selector, root) -> None:
    assert leading_root(tinycss2.parse_component_value_list(selector)) == root

def test_a_selector_list_splits_at_its_top_level_commas_and_names_the_page() -> None:
    found = split(tinycss2.parse_component_value_list(".a, :is(.b, .c) > html, body"))
    assert [tinycss2.serialize(selector).strip() for selector in found] == [".a", ":is(.b, .c) > html", "body"]
    assert [names_page(selector) for selector in found] == [False, True, True]
    assert not names_page(tinycss2.parse_component_value_list(":not(:root) p"))

def test_a_rule_list_drops_comments_and_whitespace() -> None:
    rules = rule_list(tinycss2.parse_component_value_list("/* x */ p { margin: 0 } /* y */"))
    assert [rule.type for rule in rules] == ["qualified-rule"]
