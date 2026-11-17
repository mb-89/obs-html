# Generic tables

Pagination selects the current row page before rendering its cell content or detail
panels. Grouping and ordering still consider the complete retained population; print
uses the same renderer without screen pagination. Initial filtering must not first
render an unused unfiltered body.

Pagination totals use the complete retained population before current-page cell
hydration. The first ready view must show the correct page count, not a stale
`1 of 1`; while the count is genuinely pending, do not present it as final.

Filtering and items-per-page changes update the total and controls together.
Next/Previous and direct-page controls change the displayed row population on
their first activation, including the first ready visit and HTML Pages mode.
Projected controls must stay connected to the owning table state, not stale clones.

The current-page label opens a keyboard-accessible direct page input; First/Last
use the same table-local page owner. Detail toggles derive totals from the retained
full row population, not only the already mounted current-page rows.

An icon action may name a fixed action ID registered by the explicitly selected
trusted application bundle; the trust and transaction boundary is owned by
[[input-model]]. The action receives the row's exact canonical note identity and
the selected file. Optional `helpProperty` resolves current record instructions.

Optional `card` declares a guided action card ([[input-model]], [[artifact-ui]]) whose
Apply passes the staged file and declared text value to that same action.
Singular and composed icon cells use this same dispatch, without authored callbacks.

The opt-in record query profile specified in [[input-model]] also filters table rows backed
by canonical notes in its declared population. Rows outside that population and the default
chapter-filter mode retain their existing behavior. Live and document/PDF table projections
consume the same applied global Filter; a table's local query remains independently editable.

## Purpose and ownership

- This implementation is the reference for future table UIs: reuse its runtime and semantic
  visual primitives where possible, and use this contract plus its interaction tests when
  integrating elsewhere. Do not fork another table design for the same behavior.
- A generic table is the artifact's reusable tree-view projection over canonical records. It is not
  a second data store and never discovers records from rendered HTML.
- The standalone HTML embeds canonical source records and table definitions, including their queries;
  it does not embed precomputed table result sets. Opening a table resolves its source collection,
  compiles its base query, and computes the current tree in the browser.
- One browser table runtime owns filtering, grouping, sorting, hierarchy, column order, and table
  interaction. Embedded Bases adapters supply declarative table definitions to that runtime.
  Definitions come from `base` fences and embedded `.base` files in ordinary notes.
- The runtime may delegate mechanics to an established table framework such as Tabulator when that
  reduces implementation risk.

  The framework sits behind the artifact adapter: it does not own query
  semantics or canonical records, and its controls and states are restyled with artifact design tokens.
  A packaged or embedded dependency must preserve the standalone artifact's portability contract.
- Table state is local to one table instance. A table filter, group, sort, expanded row, or column
  order never changes the artifact-wide Filter, another table, the table of contents, or source data.
- Canonical notes are independent of the tables displaying them. Table membership and authored
  row order belong to the view definition, never migration-only `table`, `position`, or `origin`
  properties on a note. Use the note's file identity rather than duplicating it in an `id`
  property.

  A title, when present, describes the subject; a citation number is a view label,
  not a reference's title. References own their document, description, and semantic kind.
- Link previews expose the destination's meaningful content, including rendered document and
  description properties for frontmatter-only references. They must not spend their limited
  preview space on migration bookkeeping or repeat only the citation label.

## Table definition

- A table definition selects one canonical record collection and contains:
  - a stable table key and title;
  - a base query that determines the table's initial rows;
  - ordered column definitions with a field or rendered-cell provider;
  - optional initial grouping and sibling-sort directives;
  - an optional hierarchy field or parent relation;
  - optional fixed table-local filter clauses, such as `type: open_point`.
- A definition is shaped like an Obsidian Bases table view: records are rows, properties are columns,
  and the view owns its filters, groups, sorting, formulas, and summaries.

  A base may declare several table views, each with a unique nonempty `name` and its own
  `order`, `filters`, `groupBy`, `sort`, view `obs` and view `obsHtml`; base-level `filters`,
  `properties`, `obs` and `obsHtml` apply to every view. Generation includes the notes that any view selects.

  With more than one view, a compact pill selector of the view names sits above the table;
  the first view is the default. Choosing a view remounts the table with that view's columns
  and rows and resets the visible-column presentation and session widths. Printing uses the
  selected view, and reviewed copies retain its name beside the visible columns.

  Initial support covers rows,
  columns, filters, grouping, sorting, links, rendered cells, and hierarchy.

  Formulas and summaries are
  later extensions of the same definition rather than separate table implementations.
- obs's input model owns how a `base` fence or an embedded `.base` file is read and which
  rows a view's `obs.members` selects (Base fences, Base files and members); the `obsHtml`
  mapping holds this adapter's table options.
- Display labels for columns and grouped properties are presentation metadata over the
  existing field keys. Headers/group captions need not expose dotted storage paths;
  renaming a display label never changes filters, canonical properties or stable routes.
- A reference-cell presentation may render the linked canonical record's identifier and
  subject title together, without copying those values into every referencing row.
  The full label remains clickable, readable and available to detail tabs.
  The exact declarative fields are owned by [[input-model#Canonical reference presentation]].

  In explicit column-detail mode, only displayed columns declaring `obsHtml.detail`
  become tabs, in current column order. Arrow keys, Home and End move among tabs;
  each panel is labelled by its tab and resolves canonical content lazily.

  In this declared mode, clicking a reference cell opens/selects that row's
  subject tab without navigating to an implementation note. Ordinary reference
  navigation outside the declared mode and source links within subject content
  keep their existing behavior.

  Tab selection is transient table-instance state, never another serialized source.
  By default omit tabs whose referenced subject has no meaningful permitted content.
  The opt-in disabled-empty-tab contract is owned by [[input-model]].
  Subject tabs are recognizable accessible tabs, not a second multi-column detail matrix.

  During an expansion, reserve the measured height of the tallest permitted tab so
  switching tabs does not make the row jump; remeasure for changed content or width.

  The declared mode's current expansions and selected subject keys project into printing
  during the open session. This stores only row/column identities, not subject payloads;
  ordinary note tables retain their existing collapsed print default.

  Selection comments inside a subject panel include its column key in the existing
  table/row/detail target, so navigating a comment reopens that subject even after
  switching or hiding the column. This is projection identity, not another source record.

  An authored, nonempty owning row body remains below its subject panels, without
  projecting the row's relation metadata. This preserves existing review editors
  without treating computed relations as subject documents.

  Compact icon slots retain their size across missing values and present an explicit,
  accessible unavailable reason rather than a broken link or false operational result.
- A table view may declare `obsHtml.wide: true`. This is a page-composition hint,
  not a second dataset or a font-scaling instruction. Paged HTML and PDF orientation
  behavior belong to [[artifact-ui]]; unmarked tables retain their default orientation.

## Query and filtering

- The base query and interactive table filter use the shared artifact query language and the table's
  row fields. They do not use or mutate the artifact Filter expression.
  Field suggestions use the same curated artifact catalog when the table selects its
  declared record population, rather than advertising flattened internal metadata.
- Base-query evaluation is lazy. A chapter computes its table rows when activated and may recompute
  them when reopened; its query definition is the only view-specific data baked into HTML.
- The base query is reapplied before the interactive filter. Clearing the interactive filter restores
  the complete base-query result, not records outside that table definition.
- Filtering a tree retains a matching row and its ancestor path so the result remains understandable.
  Nonmatching descendants are hidden unless they match independently.
- Invalid table queries preserve the last valid row set and report the error beside that table.
- An applied nonempty interactive table filter gives that table an orange outline
  and a compact filter-icon `Filtered` badge with an accessible clear-X action,
  at the top-right page margin beside the table. Use the shared semantic filtering
  accent, not artifact-specific colors.

  This is a generic table behavior for all
  artifacts, including unpaged views and all continuation sheets of a paged table.
  Keep badges associated with their own table and usable without overlapping
  adjacent content, table controls or another table's badge.

  The X clears only that table's interactive predicate and actual query input
  through the existing table state owner; it leaves the base query, global filter,
  other tables, sort/group settings and review data intact. Fixed authored base
  constraints alone do not claim a user-clearable interactive filter.

  A predicate remains visibly active even if it matches all or zero rows; an
  invalid draft cannot hide the preceding valid applied predicate. Clearing
  removes this local warning only when that local predicate is actually cleared.
- A view's `obsHtml.passing` ([[input-model]]) folds the rows that pass. The table lists the rows
  its passing filter does not match; the matching rows fold into one line under the table,
  `<p> of <t> <label>`, such as `264 of 266 verified`. Readers see what fails first, and the
  passing rows cost one line.

  The line is one button with `aria-expanded`, usable by pointer and keyboard. Opening it puts the
  passing rows back in the table at their sorted and grouped place; closing it folds them again.
  When every row the filters keep passes, the table shows no body rows and the line is the
  sentence `All <t> <label>.` in the positive tone (`--color-positive`); it is the same button. When
  no row passes, the line still counts them and has nothing to open. A view with no rows keeps
  the empty result and draws no line.

  Both numbers count the rows the global Filter and the table-local filter keep: the fold applies
  after them, as a further presentation step, so with the fold open `<t>` equals the n of the
  footer's `n of m items`. A listed row keeps its group heading and its ancestor path, as a
  table-local filter keeps them; a passing ancestor shown for that reason still counts as passing.
  With `obsHtml.showEmptyGroups`, a listed value whose rows all pass has rows, so while folded it
  draws no caption, not `(0)`: only a value no row has is a hole.

  Only the all-pass sentence takes the positive tone: no row and no count line does. A Search hit
  in a folded row and a `?tableFilter=` link into the view (a metric drill-down among them) open
  the fold, so the link still shows exactly the rows it counted ([[artifact-ui]], Dock menu). The
  open or folded state is session-only reader state, like the table-local filter; print keeps it:
  a folded table prints its line or sentence and no passing rows, an opened one prints its rows.

### Bases filter grammar

obs's input model owns the supported filter grammar (Base fences, Bases filter grammar); this
adapter's browser evaluator runs the same conformance fixture.

## Editable query view

- Every table's options menu offers a Query view toggle between the rendered table and an editable
  representation of its complete `base` YAML definition, not only the interactive filter string.
  Generated tables use this same surface and definition contract.
- Leaving the editor or toggling back validates the definition and rerenders from canonical records
  when valid. Invalid YAML or unsupported semantics reports a visible error, preserves the draft
  for correction, and retains the last valid table definition/results.
- Edits are local to that table in the open artifact, survive chapter navigation during that session,
  and never write to vault files. Reloading the artifact restores its generated definitions.
- Editing uses the same supported definition semantics as authored `base` fences; it does not
  execute arbitrary code or introduce another query dialect.
- A shared definition schema owns the supported YAML shape. Browser YAML parsing is bundled
  with the artifact so query editing works offline. Applying a definition resets that table's
  interactive controls to the edited definition's defaults.

  This includes clearing its previous visible-column order (whether changed in this session
  or restored from a reviewed copy) and its session-resized widths. Invalid edits retain
  the last valid definition and its presentation atomically; other tables are unaffected.

## Hierarchy, grouping, and sorting

- Every table is a tree view, even when all rows are roots. Rows may reference a parent or carry a
  manifest depth. Expand/collapse controls appear only for rows with children, details or a cut
  cell (Columns and cells, One line per row).
- A node representing a canonical note's own content outside the TOC has a bare disclosure icon.

  A source or chapter-reference column does not confer details: tags expand no source chapter,
  and Home tables link chapters without embedding their bodies.

  Existing
  source-tree children remain collapsible.

  A note already in the TOC uses normal navigation
  rather than duplicating its content in a detail row.

  For detail-bearing note rows, both the disclosure icon and the note label toggle details
  without navigating away; links inside the expanded content remain normal note links.

  It opens a full-width
  detail row directly underneath, rendering that note's metadata and body from the same record
  used by links and other projections.

  A view may choose which of the note's fields that row shows, in its order, or none
  (`obsHtml.detailFields`, owned by [[input-model]]).

  Details are lazy, collapsed initially, and independent
  of source-parent and group expansion.

  Rows without children, details or a cut cell have no disclosure.

  Nested links and tables inside details use the same note navigation and table runtime.

  Detail rows stay with their owner through grouping, filtering, pagination, and column changes;
  they never count as extra items.

  Detail expansion does not copy records into table data.

  Projected details share their owning row's review decision.

  Selection comments remain
  available inside details without introducing independent paragraph checkmarks.
- A declarative column-detail mode may expose an expanded row as accessible tabs
  corresponding to its displayed subject columns. Tabs render referenced canonical
  records' meaningful metadata/body through the existing note renderer, without copied
  payloads or internal path/join bookkeeping. Empty cells have an explicit empty state.

  Detail editors, comments, links and review ownership remain usable; grouping, pagination,
  column changes and print projection must preserve the correct owning record.
  Ordinary note-detail expansion remains the default unless this mode is declared.

  Opening a row or switching its subject tab updates that row's existing detail
  view; it must not rebuild the artifact, rerun unrelated tables/queries, recompute
  all review items or reconstruct the canonical model.

  Reuse prepared tab content while the owning canonical revision and view are
  unchanged; invalidate at their actual mutation boundary. Preserve the stable
  largest-tab height, current editors/comments and links.

  Verify expansion and repeated tab-switch latency
  in the actual large artifact against the legacy reader, with rebuild/review-pass
  counts as well as native timings; a tiny fixture or source substring is not
  sufficient evidence of large-artifact interaction performance.

  Selection-only detail events preserve prepared page numbering and review
  controls; opening/collapsing reflows the live chapter without preparing other
  chapters. Cached detail DOM belongs to that row's current table view and is
  discarded when canonical rows are replaced or the view is remounted.
- Grouping inserts derived group nodes without copying or mutating records. Multiple group directives
  form nested group levels in directive order.
- A group caption reads `<label>: <value> (<count>)`, where the label is the grouped property's
  `displayName`, else its key; an empty `displayName` shows only `<value> (<count>)`.

  On screen a caption is one line, as a collapsed row is (Columns and cells, One line per row):
  its label is cut where it does not fit, ends in an ellipsis and keeps its whole caption as its
  hover title, and its count stays in view.

  A view's `obsHtml.groupOrder` lists `groupBy` values in their display order; unlisted values
  follow in the `groupBy` direction. It requires `groupBy`. A sort directive on the grouped
  property overrides it while active, as it overrides the grouping direction.

  With `obsHtml.showEmptyGroups: true` the declared order is a completeness check: every
  `groupOrder` value that no row has gets a caption in its place, `<label>: <value> (0)` (or
  `<value> (0)`), so a missing value shows as a visible zero. It requires `groupOrder`; omitted,
  it is off and no empty caption is drawn.

  An empty caption is muted and has no expand or collapse control. It is drawn only in the
  table's top-level group pass, for the first authored group level: never under a source-tree
  parent, and not once the reader removes that level from Group by. Its count is taken after
  the table-local and global filters, as every group's is, so a filter that removes every row
  of a listed value shows that value with `(0)`. A reader sort on the grouped property orders
  empty captions with the others.
- Group headings and source-tree parents each have independent expand/collapse controls. Groups
  default expanded and retain their own state during filtering, pagination, and column changes.
  A collapsed group remains reachable even when it has no currently rendered child rows.
- Group headings have stable internal anchors `table-group--<table-key>[--row--<source-row-key>]--<property-slug>--<value-slug>`,
  repeating the property/value pair for nested groups. Each slug lowercases and replaces
  non-ASCII-alphanumeric runs with `-`, then trims edge hyphens; an empty slug becomes
  `value`. An empty caption of `obsHtml.showEmptyGroups` has the same anchor as any group, so
  a link to it lands on that caption.

  Internal chapter links may target the id with the existing `@id` route after
  applying a table-local filter. When filtering leaves no matching group, navigation
  focuses the targeted table shell instead.

  Array-valued properties remain one composite group value; views requiring a group per
  membership project canonical membership rows rather than duplicating table records.
- Sorting is an ordered list of field and direction directives. It sorts siblings within their current
  parent or group; it never flattens hierarchy. Equal values retain canonical source order.
- Clicking a column header toggles primary ascending/descending sort; Enter or Space does the same.
  Shift-click adds or reverses a secondary sort level. Headers expose their sort state accessibly.
  A header carries no hover help: it names its column and no instructions, so a tap on a phone
  sorts and opens no card. Dragging and resizing never trigger sorting.
- A sort directive for a grouped property orders that level's group labels, overriding the grouping
  direction while active. Other sort directives order rows inside groups. Nested group levels and
  source-tree descendants keep their hierarchy during these operations.
- Filtering, grouping, and sorting compose in this order: base query, table-local filter, group tree,
  sibling sort.

## Columns and cells

- The Properties pill picker begins with the authored default displayed columns, in
  their header order, followed by the remaining available fields. Selected state and
  direct show/hide activation remain clear; reordering suggestions must not change
  query semantics or canonical data.
- Filter-field pills share one value-selection interaction across global and local
  filter surfaces: activation exposes applicable values and their item counts;
  choosing a value applies the existing query to that surface's own scope. Property
  visibility pills remain direct visibility controls, not a second filter action.

  Counts are distinct records containing each value, not occurrences in array
  fields. Local values/counts use the authored base population under the global
  filter, before the local predicate; global values use the global scope population.

  Multiple values of one field combine with OR and fields with AND, preserving
  the preceding typed expression. The existing discriminative-facet cutoff remains.
- Composed icon actions are a tight, aligned group inside one column. Missing actions
  retain compact explicit slots; instruction popovers do not consume cell width.
  Keep the table within its available card width without hiding actionable icons.

  Verify actual horizontal overflow (`scrollWidth` versus `clientWidth`), not only
  the icon bounds. Compact action columns fit their adjacent controls without
  duplicated menu/header padding or surplus reserved space.

  Compact text columns must be resizable small enough for their content; an
  unrelated global minimum must not force an otherwise fitting card table to scroll.
  Do not mask overflow or remove working header/options/resize controls to pass
  this check.
- Subject tab lists look like joined tabs above their panel, not unrelated pill
  buttons. Preserve keyboard/ARIA behavior, stable panel height and row-local cached
  selection. Disabled empty tabs use the input-model opt-in.
- Detail metadata excludes empty values according to [[input-model]], while real
  source links and meaningful false/zero values remain available.
- Columns have stable keys, labels, and cell providers. Cells may contain plain values, trusted
  build-time inline Markdown, or internal source links.
- Users may move columns with pointer or keyboard controls. Column movement changes presentation only
  and remains local to the table instance.
- Pointer users reorder columns by dragging their headers and resize them by dragging a header-edge
  handle. Keyboard interaction on the same header and handle provides equivalent movement and sizing;
  persistent move or size buttons do not occupy the table header.
- Data cells have visible borders and align content to the top so wrapped or multi-line values begin
  at the same edge as shorter neighboring values: an opened row's cells, and every cell in print.
- The final displayed column is flexible and absorbs unused table width.
  An explicitly declared equal-column view instead divides the available subject
  width equally by the CURRENT displayed subject-column count, not a hard-coded
  number. Hidden/irrelevant roles do not reserve a share; user resizing still works.

  Schema-validated view presentation
  options are owned by [[input-model#Compact declarative table presentation]].

  Earlier columns retain their
  content-sized widths until manually resized, and the same rule reapplies after columns are reordered.

  Initial columns size to readable content rather than a uniform fixed width.

  **One line per row** (`artifact.tableRowsOneLine`, on as packaged by the owner's decision of
  17 Nov 2026; [[architecture#Rendering and runtime]]). On screen a collapsed data row is one
  line. Each text cell shows what fits on one line of its column, cutting a wrapped word and a
  `<br>` between references alike; it ends in an ellipsis where it is cut and keeps its whole
  text in the page, as its hover title too, so filters, copy and screen readers read all of it.
  Opening the row shows its cells in full. A row with a cut cell and neither children nor details
  has the disclosure too, and opening it only shows its cells in full: it adds no detail row. A
  parent row opens to its children with its cells in full; a detail row's fields are those
  `obsHtml.detailFields` picks, below the opened row's own cells in full.

  The lines, controls and pictures the author chose keep their height: under `leadingLines`
  each leading line and the value are one line each, and icon and editor cells hold controls,
  not text. A `singleLine` cell is cut as it was, with its title. Links in a cut cell stay
  links. A cut never widens a column: the column plan, `columnSize`, `compact` and `maxRows`
  are unchanged, and a table that fits never scrolls sideways.

  A cell is cut where its clamped content overflows. A table's cuts are measured on the
  rendered rows after every render of its body (a sort, a filter, a grouping, a page of
  pagination, a parent opened or closed, rows set anew by a live source, a property edit),
  whenever sizing recomputes, and on a row hidden when they were measured, once it shows. Where
  the disclosure a cut adds needs first-column width the plan lacks, the table is planned once
  more, never in a loop.

  A Search hit or a chosen comment in a cut cell opens its row, so the highlight shows. Every
  row the reader is taken to, by a Search hit, a chosen comment or a mark icon's link to its tag
  row, opens to its cells in full, wherever the hit lies; it opens its details only where the hit
  lies in them or the comment targets a detail's record field, as with the option off. On
  screen means the continuous view and the sheets shown as pages, where opening a row grows its
  sheet as opening details does; the static view, from which the print book and PDF are drawn
  and their pages counted, never cuts, and shows details as the print default has them. Which
  rows are open is session state: nothing new is saved. With the option off a table is as it
  was before it: long prose wraps.

  First-column sizing includes hierarchy indentation, disclosure control and its gap using the
  table's actual font and shared style metrics. The disclosure and value share one row even
  when an explicit narrow width requires the value itself to wrap.

  Content sizing also reserves the actual inline space occupied by header controls, their
  gaps and the resize handle. In particular, the final column's options icon must not steal
  the label's measured width or force a short label such as "Open" into letter-by-letter
  wrapping. Recompute this reservation when columns move or visibility changes.

  **A table that can fit never shows a horizontal scrollbar.** This holds for every table in
  every artifact, on screen and in print, at any browser zoom, display scaling or device pixel
  ratio.

  A table can fit when its required width fits the available width: explicit and
  content-sized column widths plus the flexible column's minimum, cell borders and resize
  handles included. Its rendered table box then never extends past its scroller, not even by
  a sub-pixel.

  Horizontal scrolling appears only for genuine overflow: required content minimums or
  reader-resized widths that exceed the container.

  The flexible column's surplus is layout fill, never a minimum: the enforced table minimum
  excludes it, so later container narrowing or rounding cannot turn fill into overflow.
  Widths derive from the available width rounded down, with a safety allowance for integer
  `clientWidth` rounding and device-pixel border snapping.

  Sizing recomputes when the container or table resizes (dock open/close, chapter or page
  activation, window resize), when fonts finish loading and when columns change.

  Resize handles stay inside header boundaries, including the last column, so controls never create
  horizontal overflow on an otherwise fitted table.
- The compact table-options icon sits at the top-right of the final visible column header, vertically
  centered without increasing header height.

  Space is reserved beside the label and inside the resize
  handle so the controls do not overlap.

  Its concealed panel opens downward immediately below the
  icon, right-aligned and constrained to the available viewport; native popover insets are reset.

  Column changes reuse the same control in the new final header without closing the panel.

  No separate toolbar or top row-count line consumes reader space.
- The options surface conceals independent Filter, Group/Sort, and Properties panels until selected.

  Properties discovers fields from the base-query records, including fields not initially displayed,
  and offers searchable toggle pills.

  Toggling a property changes columns without closing its panel;
  at least one column remains visible.

  Group/Sort offers field pills with explicit selected levels
  and direction controls, including fields not currently displayed.

  All state stays table-local.
- Reviewed copies retain the ordered visible-column keys and the selected view name for each
  stable table key; never serialize result rows.

  Reader-resized widths survive chapter navigation in that session. Legacy saved `widths`
  mappings are accepted and ignored. Whether a resized width is saved, a change or reader
  state is owned by [[artifact-ui#What counts as a change]].
- No column width is hard-coded. At startup each displayed column is sized from its rendered
  content across ALL base rows (not just the current page), unwrapped, plus header label,
  cell chrome, tree controls and editor chrome.

  Columns whose content fits an equal share get their full content width; the rest share
  the remainder (never below the configured minimum), and the flexible final column absorbs
  surplus. Print/PDF refits the same plan in the actual paper container from the static cells.

  A view's optional Obsidian `columnSize` (pixels per property) is read as relative weights:
  its columns share the width the other columns leave, in those proportions, never below
  their header label. Their share is fill, not a minimum, so a fitting table never scrolls.

  Columns without `columnSize` keep content sizing, a reader's resize still wins, and
  `columnSize` cannot be combined with `columnSizing: equal`.

  Validate the complete saved presentation before applying it: at least one unique known
  column.
  Reject invalid presentation atomically, show a table diagnostic, and retain authored
  defaults until the reader supplies a valid column change.
  A malformed saved-table mapping or unknown table key is also an error, never a
  presentation to apply to every table.

  These settings survive chapter rematerialization but never affect another table or fresh
  generation. They are reader state, not dirty review annotations. Local filter/group/sort,
  page position/size, expansion and edited base definitions remain session-only.
- The table filter exposes its available fields as compact pills; queries use the shared language's
  nested parentheses, AND, OR, and NOT. Group levels subdivide recursively, sort levels settle ties,
  and source-tree parent/child placement survives grouping rather than flattening descendants.
- Standard view `groupBy` and `sort` directives initialize the same interactive state. The Tags note
  owns its default grouping and columns, not the table runtime.
- A compact footer shows filtered/base item totals, the current page, previous/next arrows, and a
  freely editable positive-integer page size.

  The view's `obsHtml.pageSize` (a positive integer) sets its initial size; otherwise the
  configured artifact default `artifact.tablePageSize` applies. A view cannot combine
  `pageSize` with `pagination: false`.

  Filtering resets to page one; grouping and sorting are evaluated before pagination.

  While a view's passing rows are folded (`obsHtml.passing`), the item count and the pages count
  only the listed rows; opening the fold counts every row again and resets to page one, as
  filtering does.

  Group headings
  and source-tree ancestor context remain with page items without consuming their page quota.
  An empty caption (`obsHtml.showEmptyGroups`) consumes none either and adds nothing to the item
  count; it shows on the page of the row or collapsed group just before it, or on page one when
  nothing comes before it.

  Empty results remain on page one with both arrows disabled.

  Pagination is table-local.
  A view may explicitly disable pagination and the entire count/page footer for a
  small complete table. It must not merely hide controls while retaining a page limit.

  When every base row fits on one page at the configured page size, the page navigation and
  page-size controls are hidden; the item count remains. A larger table keeps its controls
  even when filtering shrinks the result to one page, and so does a table whose reader
  enlarged the page size, so the size can be reduced again.

  A collapsed group takes one navigation slot so it can still be expanded, without changing item
  totals.

  Following a source link to a paginated row reveals its page and expands its ancestors.
- Tables remain semantic HTML tables. Hierarchy is conveyed by indentation and expand/collapse state
  in the first visible column; accessible names expose row depth, groups, and column manipulation.
- Narrow layouts keep headers and cells readable through a table-local horizontal scroller rather
  than overflowing the artifact reader.
  Compact action collections share one final labelled column. The table-options
  control belongs to the actual last displayed column, not the last ordinary text field.

  Continuation-sheet headers retain functional resize controls. A resize applies
  consistently across one table's continuation projections; an inert copied handle
  or a change that appears only on the first sheet is not acceptable.
- A view may opt into a vertical viewport through `obsHtml.maxRows`, a positive
  ordinary-row threshold under the artifact-specific `obsHtml` namespace. It limits visual height
  without changing the page size, record population, grouping, or filtering.

  Pagination and scrolling may both be active: for example, twenty page items in a viewport
  of about ten ordinary rows. Variable-height rows and details scroll rather than being
  clipped. Keep the header usable and controls outside the scrolling body.

  No additional on-table setting is required. Omission preserves current behavior; invalid
  values are errors. Printing removes the viewport constraint and retains the current table
  projection.

## Pipe tables

A pipe table, which the renderer writes from a note's Markdown, is no generic table: its header
row, its equal columns and its cells' alignment are as written. Yet on screen, under
`artifact.tableRowsOneLine`, its body rows follow One line per row (Columns and cells).

- The pipe tables of the chapter body outside a Base table take the rule; one in an opened Base
  row's details is part of that expansion and stays as it is.
- Each body cell's content sits in one box clamped to one line, so a hard line break or a wrapped
  word is cut as in a Base cell, and a cut cell takes its whole text as its hover title. A cell
  that holds an image or display math keeps its height.
- A row with a cut cell has a Base row's disclosure at the start of its first cell, named
  "Expand" or "Collapse" and the first cell's text; a row without one has none. Opening the row
  shows its cells in full and closing cuts them again; an open row stays open, and a closed row
  left with no cut cell loses its disclosure.
- Its cuts are measured when its chapter is shown and its deferred content placed, after the
  sheets are laid out, when a section opens, when the table resizes (a dock, the window, fonts)
  and on a row hidden when they were measured, once it shows.
- A Search hit and a chosen comment in a cut cell open its row before the page scrolls to it.
- The rule touches only the live reading view, the chapter's own nodes in the continuous view
  and on the sheets; the print book and PDF, drawn from the notes' HTML, show every cell in
  full. Which rows are open is session state, and the page's data and a saved copy are as without
  the rule.

## Chapter integration

- A table appears at the exact position of its source fence inside an ordinary chapter. Surrounding
  prose remains authored chapter content and is reviewable normally; the table projection is not.
- Authored chapter labels, order, hierarchy, and whether a parent is called Appendix come only from
  the manifest. Generated artifact pages are owned by [[input-model]]; the generator contains no
  predefined Appendix or register chapter list.
- Ordinary authored links navigate to the chapter containing a table. Table filters are owned by
  that table, independently of chapter navigation and the artifact-wide Filter.
## Current data

A Base's rows are the build's. `obsHtml.liveSource` declares where newer values of those rows are
read when the page opens; [[capabilities/live-data]] is its authoring note. The rows the build
selected stay underneath: values read later are only laid over them in the open page, never saved
into it. A Base without the option renders exactly as it would without this section.

A row carries no date, by the owner's decision of 17 Nov 2026 (dates are private): the page
compares a read item's values with its saved row's, and asks the source for what changed since the
page was made. No digest is stored either: the page holds each row's values, so comparing them is
the same test with nothing more stored.

### Declaration

`obsHtml.liveSource` sits on a Base, in a `base` fence and in a `.base` file a register embeds
alike. `live-source.schema.json` (packaged) owns its keys, with `additionalProperties: false` at
every level:

- `name` (required): the source's name as reader sentences say it, such as `Example Tracker`.
- `key` (required): 1 to 4 property names that identify an item.
- `notePath` (required): the vault-relative path of an item's note, a template over `key`
  properties only, so a path follows from the key. The path is a row's identity.
- `refreshMinutes` (optional): a whole number of at least 5, default 10.
- `lookbackHours` (optional): a whole number from 1 to 720, default 1: how long before the page's
  generation timestamp a read starts. It is a duration, not an instant, so it carries no date.
- `fields` (required): `{target: path}` or `{target: {path, lowercase: true}}`.
- `derive` (optional): `{target: [case, ...]}`. A case is `{where?: conditions, value}`,
  `{where?, path}` or `{where?, keep: true}`. The first case that matches wins; a case without
  `where` is the default and comes last.
- `fillNew` (optional): `{target: path}`, applied only to rows the build did not have.
- `bodyPath` (optional): the path of the expanded text of a row the build did not have. It is
  never a property; a row the build had keeps its expanded text until the next build.
- `exclude` (optional): conditions; an item that meets them is ignored.
- `accept` (optional): conditions a new item must meet to become a row.
- `changes` (required): 1 or 2 routes, tried in order.
  - Connector: `{provider: connector, server, tool, rows, requests: [{set, input}], next?:
    {cursor, more, input}, maxPages, fields?}`. `tool` is one of an enum of read tools, today
    `list_issues`; adding one is a reviewed schema change.
  - Web: `{provider: web, requests: [{set, url}], rows?, next?: link, maxPages, fields?}`. `rows`
    is the path of the answer's list; without it the answer itself is the list.
  - `maxPages` is 1 to 5. A route's own `fields` replaces the path of a target that `fields`
    already maps, for that route's answers only, and adds no target.

No key for headers, tokens or credentials exists anywhere, and none names an instant.

The renderer removes `liveSource` from the definition it embeds, and `obsHtml` with it when
nothing else is left there, so the Query view never shows the option and a reader's edit cannot
change it. The table entry carries the declaration as `live`, with no time beside it, so an
unchanged rebuild stays byte-identical.

### Paths, templates and conditions

One grammar each:

- **Paths**: dotted keys plus `[]`, which maps over a list, at most 8 steps (a key or a `[]` is
  one step each). A key is read only as the value's own key. An object is absent, never a value.
  Scalars keep their JSON type, and a list of scalars stays a list. A path that is absent or
  `null` on an item removes the property from the row.
- **Templates**: `{name}` only, naming a key property, a mapped field or `since`; no other
  braces. Values are URL-encoded inside a `url`. A connector `input` value that is one template
  alone takes the value as it is; any other is text.
- **Conditions**: exactly the shape of capabilities/queries (Conditions), as
  [[obs-specification|obs's specification]] defines it: `{field, equals, matchCase?}` or
  `{field, exists: true}`, with exactly one of `equals` and `exists`. The page evaluates them with
  `obsQuery.compileConditions` (query.js), its one conditions evaluator, over the mapped fields as
  a note's frontmatter (`{frontmatter: fields}`).

### Build refusals

Each is the one input error form, naming the Base's note (or its `.base` file) and the field under
`base.obsHtml.liveSource` (`obsHtml.liveSource` in a `.base` file). The build first checks the
rest of the definition against `base.schema.json`
([[input-model#Compact declarative table presentation]]), then the declaration. It refuses:

- a schema violation of `live-source.schema.json`, and a case without `where` that is not last;
- a view with `obs.members`, or `obs.records` other than `note` on the Base or a view;
- a `fields`, `derive`, `fillNew` or `set` target that is not a plain name
  (`^[A-Za-z][A-Za-z0-9_ .-]{0,63}$`), that is `__proto__`, `constructor` or `prototype`, or that is
  a name the runtime or the core reserves: `title`, `slug`, `text`, `content`, `body`, `depth`,
  `chapter`, `sourcePath`, `recordType`, `frontmatter`, `frontmatter.*`, `file.*`, `mark`,
  `mark.*`, and `obs`, `obs.*` or an adapter namespace `obs<Name>` (obs's input model, Core and
  adapter namespaces);
- a target that a property of the same Base declares `editable`, as a `reference`, as a
  `metadataFormats` source or as a `linkProperty`;
- a `key` property, or a field a condition names, that no `fields` or `set` target maps;
- a `notePath` naming a property outside `key`, or any template naming a field that is neither a
  key property, a mapped field nor `since`;
- a path of more than 8 steps;
- a `url` that is not `https`, that carries a user name or password, or that has a query name
  matching `token|key|secret|password|auth|sig|code` (ignoring case), and a connector `input` key
  that matches the same names;
- a view that groups by a derived target whose `obsHtml.groupOrder` lists a value no case of that
  target produces, unless the target has a `keep` case.

The adapter imports no core module, so these are shape checks only; the mapping is checked in the
page (below).

### Mapping and merging

`live-data.js` is the pure layer, `globalThis.obsLiveData`: it uses no page and no network, and no
function of it returns HTML, because fetched text is data. Later pieces call it by these names,
which stay stable:

- `LIMITS`: `{items: 2000, fieldBytes: 65536, pathSteps: 8, answerBytes: 8 * 1024 * 1024}`.
- `readPath(value, path)`: the value at a path, or `undefined` where it is absent.
- `fillTemplate(template, values, {url})`: the filled text, or `undefined` where a name has no
  scalar value; with `url: true` each value is URL-encoded.
- `notePath(declaration, fields)`: the note path the key fields give, or `undefined`.
- `extract(declaration, route, request, item)`: what one item gives the declaration and nothing
  else of it, `{path, set, fields, derive, fillNew, body?}`: its note path, its `set` and `fields`
  values (with the route's own paths and `lowercase`), its `derive` path values by path, its
  `fillNew` values and its `bodyPath` text; `null` for an item that is no object.
- `mapItem(declaration, route, request, item, shownFor)`: one item as `{path, fields, body}`, or
  `null`. It takes the request's `set`, then `fields` with the route's own paths and
  `lowercase`, then `exclude`, then `derive` and, for a new item (`shownFor(path)` gives no row),
  `fillNew`, `bodyPath` and `accept`. A `keep` case keeps the shown row's value; a new item whose
  `derive` lands on `keep` is `null`, because the page cannot know its value.
- `lower(text)`: raw text as the safe content nodes `paragraph`, `text`, `lineBreak` and `link`
  with an `https` URL, and no others. A blank line starts a paragraph, a newline is a line break
  and a bare `https` URL becomes a link; Markdown markers stay visible as text.
- `validateNodes(nodes)`: the nodes when each is of that subset, else a `TypeError`.
- `since(declaration, generationTimestamp)`: the one `since` of every request of the page: the
  page's generation timestamp (`document.generation.timestamp`, which every page carries and the
  provenance check exempts by name) minus `lookbackHours`, in whole seconds, written
  `YYYY-MM-DDTHH:MM:SSZ` in UTC.
- `merge(declaration, route, request, items, saved, {extracted})`: the rows one request's latest
  result changes, its items fetched or, with `extracted: true`, as `extract` gave them, by note path, as `{rows, partial}`, computed from the saved rows and that result alone.
  An item is compared with its saved row: its `set` and `fields` targets and the saved note's
  frontmatter values of the same targets, each as canonical JSON (keys sorted, a list in its order,
  a target that is absent, `null` or an empty list left out). Equal, the saved row is shown as
  built, its built cells included; different, the item is laid over it. An item with no saved row
  is a new row, built from the latest result each time, so its `fillNew` and `bodyPath` values
  follow the source. `derive` targets are not compared: they follow from the mapped ones, which the
  check proves for every saved row. An item read more than once in one read keeps its last
  occurrence. Nothing of this is stored, and no hash is computed. Past a limit (more than 2000
  items in a read, or a value over 64 KiB) the item is dropped and the read is `partial`.
- `check(declaration, population)`: the failures of the check below, each `{notePath, check,
  field}`.
- The web route's ([[#The web route]]): `webUrl(route, request, since)`, the filled URL;
  `nextLink(header, current, declared)`, a `Link` header's next URL as `{url}`, or `{foreign: true}`
  on another origin; `refusal(status, header, now)`, `{key: "wait", until}`, `{key: "unavailable"}`
  or `{key: "notNow"}`; `answerList(contentType, text, route)`, an answer's list or `undefined`;
  `readBody(body)`, a streamed body's text or `undefined` past `answerBytes`; `keptKey(title,
  declaration)`; and `webReader(...)`, the route itself.

A row is `{sourcePath, frontmatter}`, the shape conditions read.

Both sources filter on an item's last update: the connector's `list_issues` lists issues updated
at or after `since`, the REST list those updated after it. An item changed after the build
therefore always comes back. The default hour covers a read of the source and a build made in one
run and a difference between the build's clock and the source's; items of that interval that the
build already had compare equal and change nothing, so the look-back costs more items, never a
wrong row. Where `SOURCE_DATE_EPOCH` fixes an earlier build time, the read starts earlier and
returns more items, never fewer.

### The check

When the page starts, the tables feature's `live-source` part hands `obsLiveData.check` each live
table's population, whether or not its chapter is shown. A register's population is the union of
the core's rows of the views its table entry carries: all of them, or the one view a heading names.
A fence's population is the note rows its Base-level `filters` select. The check proves, for every
row:

- every key property is present and nonblank, and the key is unique (`key`);
- `notePath` over the key reproduces the row's `sourcePath` (`notePath`);
- each `derive` target reproduces the row's own value (`derive`); a `keep` case, and a `path`
  case, which reads an item the row does not have, count as reproducing.

It also proves that each request's `set` values occur in at least one row (`set`). Each failure
logs one console error naming the table, the note path, the check and the field, and turns that
table's routes off for this page; its saved rows are shown as they are. `obs-html --check-rendered`
fails on such a page ([[cli]]), so an author runs it after declaring a source.

### Reading

The tables feature's `live-source` part reads a live table's first connector route in Claude's
artifact viewer (where `claude.use` exists), and its first web route on an `http:`, `https:` or
`file:` page outside it ([[#The web route]]); [[capabilities/live-data]] says what each host gives
a page and how to publish one. In the viewer a web route makes no request, because the viewer
refuses every connection a page opens itself: a table whose routes are all web routes shows
"Newer updates cannot be shown here" there. Outside the viewer a connector route reads nothing. A
page with neither route its host can read, or opened anywhere else, shows its saved rows with no
line of its own. A table whose check failed reads nothing either, and a page that a headless
print opens ([[cli#PDF output]], [[cli#Rendered check]]) reads nothing and shows no line.

`obsLiveData.reader` is the route, with the viewer's namespaces handed in, so it is tested without
a viewer. Its steps:

- **Reaching the source:** it awaits `claude.use("mcp")` and `claude.use("permissions")`. A `null`
  from `use("mcp")` leaves the saved rows and adds "newer updates cannot be shown here".
- **Consent:** it reads `permissions.state("mcp:<server>")`, a rejected read counting as
  `unavailable`. `granted` reads at once. `prompt` offers the button "Show current data", whose
  click makes the first call with `callTool`, the one call that asks the viewer; a watch never
  asks. `denied` adds "current data is turned off for this page". `unavailable` adds "newer
  updates cannot be shown here". The page never asks by itself.
- **Read tools only:** once the viewer has allowed the source, `listTools(server)` must report the
  route's tool with `readOnlyHint: true`; otherwise the tool is not called again on this page.
- **Pages:** each request's first page is a `watchTool` with `cache {staleTime, gcTime}` both
  `refreshMinutes` in milliseconds and no `refetchInterval`, its input the request's `input` with
  `{since}` filled. Later pages follow `next` with `callTool` and the same cache, one after
  another, up to `maxPages`. A read that stops there while more remain adds "showing the first
  <n> changes".
- **Return:** when the page is shown again and its newest read is older than `refreshMinutes`, it
  unsubscribes its watches and registers them again.
- **Freshness** is a result's `cache.storedAt`, or else the time it arrived. A result older than
  the one shown for the same request is dropped. Freshness stays in memory and is never shown.
- **Refresh:** the table's options hold the key "Check for updates" beside the menu. It reads every
  request again at once with `callTool` and `cache.refresh`. In `prompt` it does what "Show
  current data" does; where consent is `denied` or `unavailable`, or `use("mcp")` gave `null`, the
  key is not shown. It is disabled while a read runs.

Each failure is read by its code:

| Code | Rows | Line adds |
|---|---|---|
| `needs_reauth` | saved | "sign in to <name> again in Claude" |
| `server_not_connected`, `selection_required`, `server_not_found` | saved | "connect <name> in Claude to see current data" |
| `blocked_by_policy` | saved | "newer updates cannot be shown here", and one notice |
| `not_in_manifest` | saved | consent read again: `denied` "current data is turned off for this page", else "newer updates cannot be shown here" |
| `approval_required` | saved | the button again |
| `not_granted`, `capability_disabled`, `capability_removed` | saved | as a `null` from `use("mcp")` |
| `rate_limited` with `retryAfterMs` | shown | "<name> asks to wait before the next check"; no call before that time |
| any other code | shown | after a read, the line reads "Could not check for updates; showing the data read earlier"; else "could not check for updates now" |

A retryable error on a later page is tried once more, after `retryAfterMs` where given. At most
one notice per page is posted, through `obsNotices.post`, in reader words and only for
`blocked_by_policy`.

### The web route

`obsLiveData.webReader` is the web route, with `fetch`, the page's storage and its clock handed in,
so it is tested without a network. It runs once per open of the page. Its steps:

- **Request:** each request's `url` with `{since}` and each `set` value filled in and URL-encoded,
  asked with `fetch` and `credentials: "omit"`, `referrerPolicy: "no-referrer"`,
  `redirect: "error"`, `mode: "cors"` and `Accept: application/json` only. The page sends no
  other header, and so no token. Requests run one after another; tables of the same declaration
  share one read.
- **Paging:** with `next: link`, the page follows the answer's `Link` header's `rel="next"` URL,
  up to `maxPages`, only where that URL has the origin of the declared `url`. A next page of
  another origin is not followed: the read stops there as at `maxPages`, and the line adds
  "showing the first <n> changes". A redirect is a failed read, wherever it leads.
- **Headers:** across origins a page reads a response header other than the CORS-safelisted ones,
  such as `Content-Type`, only where the answer names it in `Access-Control-Expose-Headers`. A
  header the page cannot read counts as absent: without a readable `Link` a read stops after its
  first page, and without a readable `x-ratelimit-reset` or `Retry-After` a refusal has no time.
- **Answer:** an answer counts only with status 200 to 299, a JSON content type
  (`application/json` or a `+json` type) and a body of at most 8 MiB, counted while the body
  streams, `Content-Length` or not. It is parsed as JSON, as data. Its list is the top-level array,
  or the value at the route's `rows` path where the route has one. Anything else is a failed read.

Each answer that does not count is read by its status:

| Answer | Rows | Line adds |
|---|---|---|
| 403 or 429 with `x-ratelimit-remaining: 0` and a readable `x-ratelimit-reset` (epoch seconds) | shown | "<name> asks to wait before the next check"; no request before that time |
| 403 or 429 with a readable `Retry-After` (seconds or an HTTP date) and no readable reset | shown | the same, waiting until the `Retry-After` time |
| 403 or 429 with neither readable | shown | as any other failure |
| 401 or 404, such as from a private repository | saved | "newer updates cannot be shown here" |
| a request the page's Content Security Policy refuses (a `securitypolicyviolation` event for the declared origin) | saved | "newer updates cannot be shown here", and one notice |
| any other failure: another status, a redirect, a network error, a non-JSON or oversized answer, no list | shown | after a read, the line reads "Could not check for updates; showing the data read earlier"; else "could not check for updates now" |

The one notice is posted through `obsNotices.post`, in reader words, at most once per page; every
other failure is shown in the line only. The line never says when to check again: no text of it
holds a time.

**The kept result.** The page keeps the last good read in this browser's `localStorage`, so a
reopened page stays within the endpoint's request limit:

- **Key:** `obs-live:` followed by the page's title (the Document's title, else the page's
  `<title>`, as bless.js keys its storage) and the declaration's canonical JSON (keys sorted). `file:` pages can share one
  storage origin, so the key does not rely on the origin. No digest is computed, because
  `crypto.subtle` is missing on a plain `http:` page. A changed declaration is a different key,
  so its kept result is never applied.
- **Entry:** `{read, wait?, results}`: the time of the read and any time the endpoint asked to
  wait until, each in milliseconds, and per request its `partial` flag and its mapped items. A
  mapped item holds its note path and its `set`, `fields`, `derive` path, `fillNew` and `bodyPath`
  values, with `lowercase` applied, and nothing else: never the answer itself, so a value the
  declaration does not map, such as `updated_at`, is never stored.
- **Applying:** a kept result is applied only when its `read` is after the page's generation
  timestamp, and then by `merge`'s rule: an item applies only where its values differ from its
  saved row's. Its time stays in this browser's storage and never enters the page; a fresh read
  replaces it.
- **Reopening:** a page reopened within `refreshMinutes` of its last read applies the kept result,
  sends no request, and its line reads "Showing current data"; one reopened before a kept `wait`
  time sends no request and adds "<name> asks to wait before the next check". Otherwise the page
  shows the kept result, reads again and, where that read fails, the line reads "Could not check
  for updates; showing the data read earlier".
- **Storage optional:** every storage access is wrapped in `try`/`catch`. Where storage is
  blocked, the page still reads and shows the rows, and keeps nothing.

**Headless printing.** pdf.py's `_browser_page` sets `globalThis.obsLiveOff` before the page loads,
for a PDF build, `--export-pdf` and `--check-rendered` alike, and the flag turns every route of the
page off: the tables show their saved rows and no line, and the check above still runs. As a
backstop it aborts every request to an origin that a web route of the page declares, read from the
page's data island (`live_source.web_origins`); every other request goes through as without a live
source, so a page without a web route prints as before.

### Projection

Each arrival merges every request's latest items over the saved rows (`merge`), and
`obsLiveData.project` turns the result into pseudo-notes for that one table key:

- **A matched row** keeps its note's `slug`, `sourcePath`, `title`, marks and expanded text and
  takes the merged values as its frontmatter. Its `frontmatterHtml` keeps only fields no target
  maps, sets or derives; a target's entry goes with its flattened children (`labels.0` ...).
- **A new row** gets a slug no chapter can take, `live~<table key>~<n>`, kept for its path while the
  page is open, the file name of its path as its title, and as expanded text
  `renderSafeCanonicalContent` over the nodes `lower` gave.
- **No editing:** a pseudo-note carries no `editableProperties`, `tables` or `safeContent`.

The page builds each pseudo-note with `makeRecord` and its row with the row builder `noteTableRows`
uses, so cells, values, label and search text all come from it; a matched row keeps its row key
`note:<slug>`, so opened rows, collapsed groups and the page stay. A new row's label is text in the
static view, never a link. Chapters, hover cards, record cards, counts, figures, global facets and
the page's chapter search keep the canonical notes; reference targets resolve to them too.

- **One owner lookup:** `ownerOf(row, tableKey, canonical)` gives the table's pseudo-note for the
  row, or `canonical`, the row's canonical note. Every site of tables.js that reads a row's note
  reads through it.
- **One selection:** once a projection is active, one compiled filter, the Base's `filters` and the
  view's together, runs over the population and the new rows, as an edited register's query does,
  and `setRows(rows, {baseQuery})` hands the mounted table that selection.
- **Known columns:** the Properties picker and the field catalog come from the build's rows and the
  declared targets (`set`, `fields`, `derive` and `fillNew`), never from rows read later, so a
  column a reader adds and saves is known whenever the page reopens.
- **Arrival:** it bumps the table state's `liveRevision`, so print rebuilds the table, resets the
  row text cache, calls `setRows` on every mounted instance and dispatches
  `obs-table-rows-change {key}`. The search index, comments, pages and each mounted table listen to
  it as to `obs-table-definition-change`, which still means "the reader applied a new query". An
  arrival waits while a print or an export is being prepared.

### Never saved

Nothing read goes through `stageCanonicalTransaction`, and `readerState` does not change: Download
HTML and Save reviewed HTML hold the saved rows, byte for byte as without a read, the generation
timestamp does not move and no changed-HTML notice appears.

While the Comments bar is open, live tables show their saved rows with the line "Showing the saved
version while comments are open", and return to the current rows when it closes. A comment
therefore always anchors to saved text, which survives Save reviewed HTML and reopening.

### Status line

Each live table has one line under it, outside its controls, which the static view and print keep
without the button. `READER_TEXT` in live-data.js holds every text it shows, and
`obsLiveData.statusLine` composes them from the reader's state. No text of the line holds a date or
a time, of the page, of its rows or of a read: the owner considers dates private (17 Nov 2026).

- before a read, or without one, the line has no text of its own and takes no space;
- after a read: "Showing current data";
- after a later check fails while an earlier read's rows are shown: "Could not check for updates;
  showing the data read earlier";
- each further part follows " · "; with nothing before it the line starts with the part, its first
  letter capitalised, as in "Newer updates cannot be shown here";
- a table whose check failed shows "Newer updates cannot be shown here".

The line uses `--color-text-muted`, and `--color-warning` where a check failed or the source asks
for an action. No reader text names a declaration, a connector, a capability or how the page is
made.
