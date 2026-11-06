from html import escape

from obs_html.bars import BarDefinition
from obs_html.bars._query import QUERY_HELP
from obs_html.storage import warning_markup


def render() -> str:
    return f"""
<section class="comment-section comment-review-controls">
  <label class="comment-author-label" for="comment-reviewer">
    <span>Reviewer</span>
    <span class="comment-author-control">
      <input id="comment-reviewer" type="text" autocomplete="name" data-comment-author data-bar-autofocus>
      {warning_markup("reviewer")}
    </span>
  </label>
  <div class="comment-save-controls">
    <div class="comment-section-actions comment-save-controls-left">
      <button type="button" data-comment-save aria-label="Download HTML" title="Download HTML">Save</button>
      <button type="button" data-comment-load aria-label="Load reviewed HTML" title="Load reviewed HTML">Load</button>
      <input type="file" accept=".html,text/html" multiple data-comment-files hidden>
    </div>
    <button class="comment-copy-button" type="button" data-comment-copy>Copy comments to clipboard</button>
  </div>
  <p class="comment-save-guidance" data-review-save-guidance role="status">No unsaved review changes. Download HTML to keep review comments, decisions, and property edits.</p>
  <p class="visually-hidden" aria-live="polite" data-comment-announcer></p>
</section>
<section class="comment-section comment-browser">
    <div class="query-input-row comment-query-row">
        <button class="icon-button comment-add-button" type="button" aria-label="Add comment" title="Select chapter text to add a comment" data-comment-add disabled><span class="resource-icon" data-icon="add" aria-hidden="true"></span></button>
    <label class="visually-hidden" for="comment-filter">Filter comments</label>
    <input id="comment-filter" type="search" placeholder="Filter comments" autocomplete="off" data-comment-filter-input>
    <span class="query-help">
      <button class="icon-button query-help-button" type="button" aria-label="Query language help" data-hover-help="{escape(QUERY_HELP)}"><span class="resource-icon" data-icon="help" aria-hidden="true"></span></button>
    </span>
  </div>
    <div class="comment-review-summary" data-review-summary>
        <button type="button" data-review-summary-state="accepted"><span>Accepted</span><strong data-review-summary-count>0</strong></button>
        <button type="button" data-review-summary-state="rejected"><span>Rejected</span><strong data-review-summary-count>0</strong></button>
        <button type="button" data-review-summary-state="waiting"><span>Waiting</span><strong data-review-summary-count>0</strong></button>
    </div>
    <p class="comment-review-guidance" data-review-modifier-guidance>Normal click affects one item. Shift-click Accept or Reject applies to still-waiting items in this section, or the chapter introduction or whole chapter when applicable. Ctrl+Shift-click applies to all still-waiting items.</p>
  <p class="comment-filter-state" data-comment-filter-state></p>
  <div class="comment-list" data-comment-list data-transient-content></div>
</section>
"""


BAR = BarDefinition(
    key="comments",
    label="Comments",
    icon="comments",
    help="Review selected text",
    order=40,
    render=render,
)
