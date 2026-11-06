from obs_html.bars import BarDefinition
from obs_html.bars._query import render_query_input


SHORTCUT_HELP = (
    "Keyboard: Ctrl+F opens Search and selects its text (again closes it), "
    "F3 and Shift+F3 step to the next and previous result, Esc closes Search."
)


def render() -> str:
    return (
        '<div role="search">'
        f'{render_query_input("search", "Search", SHORTCUT_HELP, "Control+F F3 Shift+F3 Escape")}'
        '<p class="search-status" data-search-status aria-live="polite">Type to search.</p>'
        '<ol class="search-results" data-search-results data-transient-content></ol>'
        '</div>'
    )


BAR = BarDefinition(
    key="search",
    label="Search",
    icon="search",
    help="Search the content (Ctrl+F)",
    order=30,
    render=render,
)
