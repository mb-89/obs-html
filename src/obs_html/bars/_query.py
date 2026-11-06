from html import escape
from obs_html.semantic_assets import markup


QUERY_HELP = (
    'Bare terms search all fields. Use name:value, "quoted text", val*, /regex/, '
    'and, or, not, -, and parentheses. Matching ignores case; /regex/c matches case. Fields include title, '
    'text, slug, depth, and every frontmatter field. Quote field names containing spaces: '
    '"project status": result.'
)


def render_query_input(kind: str, label: str, extra_help: str = "", shortcuts: str = "") -> str:
    input_id = f"artifact-{kind}"
    keys = f' aria-keyshortcuts="{escape(shortcuts)}"' if shortcuts else ""
    help_text = f"{QUERY_HELP} {extra_help}".strip()
    return (
        '<div class="query-input-row">'
        f'<label class="visually-hidden" for="{input_id}">{escape(label)}</label>'
        f'<input id="{input_id}" type="search" placeholder="{escape(label)}" '
        f'autocomplete="off" data-{kind}-input data-bar-autofocus{keys}>'
        '<span class="query-help">'
        f'<button class="icon-button query-help-button" type="button" '
        f'aria-label="Query language help" data-hover-help="{escape(help_text)}">{markup("help")}</button>'
        '</span></div>'
    )