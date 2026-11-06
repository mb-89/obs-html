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
  manifest depth. Expand/collapse controls appear only for rows with children or details.
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

  Details are lazy, collapsed initially, and independent
  of source-parent and group expansion.

  Rows without children or details have no disclosure.

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

  A view's `obsHtml.groupOrder` lists `groupBy` values in their display order; unlisted values
  follow in the `groupBy` direction. It requires `groupBy`. A sort directive on the grouped
  property overrides it while active, as it overrides the grouping direction.
- Group headings and source-tree parents each have independent expand/collapse controls. Groups
  default expanded and retain their own state during filtering, pagination, and column changes.
  A collapsed group remains reachable even when it has no currently rendered child rows.
- Group headings have stable internal anchors `table-group--<table-key>[--row--<source-row-key>]--<property-slug>--<value-slug>`,
  repeating the property/value pair for nested groups. Each slug lowercases and replaces
  non-ASCII-alphanumeric runs with `-`, then trims edge hyphens; an empty slug becomes
  `value`.

  Internal chapter links may target the id with the existing `@id` route after
  applying a table-local filter. When filtering leaves no matching group, navigation
  focuses the targeted table shell instead.

  Array-valued properties remain one composite group value; views requiring a group per
  membership project canonical membership rows rather than duplicating table records.
- Sorting is an ordered list of field and direction directives. It sorts siblings within their current
  parent or group; it never flattens hierarchy. Equal values retain canonical source order.
- Clicking a column header toggles primary ascending/descending sort; Enter or Space does the same.
  Shift-click adds or reverses a secondary sort level. Headers expose their sort state accessibly.
  Dragging and resizing never trigger sorting.
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
  at the same edge as shorter neighboring values.
- The final displayed column is flexible and absorbs unused table width.
  An explicitly declared equal-column view instead divides the available subject
  width equally by the CURRENT displayed subject-column count, not a hard-coded
  number. Hidden/irrelevant roles do not reserve a share; user resizing still works.

  Schema-validated view presentation
  options are owned by [[input-model#Compact declarative table presentation]].

  Earlier columns retain their
  content-sized widths until manually resized, and the same rule reapplies after columns are reordered.

  Initial columns size to readable content rather than a uniform fixed width; long prose wraps.

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

  Group headings
  and source-tree ancestor context remain with page items without consuming their page quota.

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

## Chapter integration

- A table appears at the exact position of its source fence inside an ordinary chapter. Surrounding
  prose remains authored chapter content and is reviewable normally; the table projection is not.
- Authored chapter labels, order, hierarchy, and whether a parent is called Appendix come only from
  the manifest. Generated artifact pages are owned by [[input-model]]; the generator contains no
  predefined Appendix or register chapter list.
- Ordinary authored links navigate to the chapter containing a table. Table filters are owned by
  that table, independently of chapter navigation and the artifact-wide Filter.