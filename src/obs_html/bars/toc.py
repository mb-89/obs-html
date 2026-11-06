from obs_html.bars import BarDefinition
from obs_html.semantic_assets import markup


def render() -> str:
    return '<nav class="toc-tree" aria-label="Chapters" data-toc-tree></nav>'


HEADER_ACTIONS = (
        '<div class="toc-actions" role="group" aria-label="Table of contents controls">'
        '<button class="disclosure-toggle toc-action" type="button" data-toc-action="collapse" '
        f'aria-label="Collapse all" title="Collapse all">{markup("collapsed")}</button>'
        '<button class="disclosure-toggle toc-action" type="button" data-toc-action="expand" '
        f'aria-label="Expand all" title="Expand all">{markup("expanded")}</button>'
        "</div>"
    )


BAR = BarDefinition(
    key="toc",
    label="Table of contents",
    icon="toc",
    help="Browse chapters",
    order=10,
    render=render,
    header_actions=HEADER_ACTIONS,
)
