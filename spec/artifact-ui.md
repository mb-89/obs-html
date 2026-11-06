---
kind: design-input
area: artifact-ui
---

# Artifact UI

The notice center's applied-filter entry is the artifact-wide applied-filter status owner.
Do not also show a redundant green applied-filter badge/pill on the menu icon.
This does not remove useful selected states from filter/value controls.

Filter-field pills use the shared value/count selection interaction specified by
[[generic-tables]], including in dock bars and table-local filter controls.

Trusted view selections project existing figure, card and table primitives without
filtering authored chapters or modifying canonical records. Selection controls use
the normal accessible filter-pill buttons and explicit pressed states. Query-backed
numeric references remain ordinary authored text and ordinary note-navigation links.

A refreshed expanded Sankey refits its live visual on `obs-figure-render` without
closing or replacing the figure dialog.

Canonical reference labels, per-column subject-detail tabs and compact icon slots
compose the shared table/note primitives; [[input-model#Canonical reference presentation]]
owns their data-only declarations and [[generic-tables]] owns their interactions.

`data-table-wide="true"` on the table host is the semantic projection of
`views[0].obsHtml.wide: true`, consumed by the page-composition owner.

Data-only card groups compose the existing `content-card` primitive in responsive columns,
with headings, authored Markdown, and optional artifact-filtered metrics. Metrics use compact,
wrapping label/value rows; at ordinary desktop widths each metric should remain one compact
label/value line, with wrapping reserved for narrow layouts or genuinely long labels.
A card group extends within the reader and clear of the chapter controls, as a figure does.

Within a metric block, labels share one aligned column and values share another;
do not position every label/value pair independently.
Compound quantity values inherit the row's ordinary font and line height rather
than paragraph typography. Compact card padding and inter-column spacing preserve
the ordinary one-line desktop metric without shrinking reader text.

Cards may opt into compact metric pills for legacy-style summaries while retaining
the same filtered values and internal links. Markdown columns may declare a positive
integer weight pair on their opening delimiter (for example, `||| 1:2`); weighted
columns stack at narrow reader widths.

Horizontal Sankey outcomes use the midpoint between their incoming origin stage
and declared destination stage, not the destination column itself.

A terminal `above`/`below` outcome may point to an earlier stage; ordinary flow
edges must
still advance stages. Terminal outcomes cannot have outgoing links. This preserves
origin-adjacent placement without interpreting adapter-specific outcome names.

Explicitly authored two-column blocks retain side-by-side content within ordinary
desktop paper width. They stack only when the available reader width cannot support
readable columns; the default single-column card layout is not imposed over that
authored composition.

Content-card grids must not make a short metrics card as tall as an adjacent evidence-table
card; cards follow their content height while retaining responsive columns. Embedded tables
in cards use the shared table runtime with compact, readable row spacing, not the full-density
spacing intended for stand-alone reading tables.

Metric spacing must not consume evidence-table width unnecessarily. Small declaratively
unpaged evidence tables with combined action cells should fit ordinary desktop paper
without an avoidable inner scrollbar; do not hide real overflow or drop actions.

A compact metrics column need not occupy half a two-column overview: let a
content-sized compact pill block leave more width for its evidence neighbour.
Preserve semantic light/dark metric pills at a page-fitting density through shared
primitives, without hard-coded artifact names or deleting metric links.

An optional metric value link uses the existing internal chapter and table-filter route; its
`?tableFilter=` is the metric's conditions in the reader language (`obsQuery.conditionsExpression`
over the metric's `from` chain and `where`, obs's cards-metrics capability, Drill-downs), so the
table shows exactly the counted rows.

A series metric's link is built the same way from its own
conditions, the series' `where` and its group's label. A projected metric's link adds
`&projection=<name>`: the linked table then matches each `note.` clause against its row's note
as that projection shows it (`obsCards.project`), the same records the value counted.

Typing, clearing or replacing the table's filter drops the projection; a projection changed after
the drill-down opened applies when it is opened again.
Static evidence cards do not change under filtering.

Card-body base fences use the canonical query/table runtime. Per-record Sankey
links preserve line identity and categorical outcome/origin colors; adjacent segments share
highlighting.

Framing, expansion and printing continue to use the shared figure owner.

The artifact is understated and content-first. Its visual system is defined once in a
central stylesheet embedded into the generated HTML.

## Reader-facing text

Reader-facing text names no kind: a label, placeholder or fallback title says "Search",
"Filter" or "Untitled", not which kind of thing it searches, filters or lacks a title.
An error message the artifact shows names its source and a remedy; the core's contract
failures have their form in [[input-model#Chapter content]].

## Styling

- A style module is a folder containing `style.css`, with optional fonts, assets, and configuration
  defaults. The converter embeds its CSS into each output.

  The packaged `generic` module is the
  default; a manifest may declare a module pinned to a commit, and `--style` selects an
  explicit module folder for one invocation ([[configuration#Declared style]]). No artifact component names a style.

  Page geometry (paper size, orientation, sheet dimensions, margins, and `@page`) belongs only to
  the structural stylesheet; a style module must not declare or assume it.
- All colors are semantic custom properties projected from [[semantic-assets]].
- Components consume semantic tokens; color literals do not appear in component rules or
  generated markup.
- Light and dark token values can follow the operating-system preference through
  `color-scheme`.

  A discovered Settings bar offers System, Light, and Dark appearance.

  Choosing an appearance updates every semantic token, including browser-native controls,
  without changing content or individual component rules.

  The root's `color-scheme` is the chosen appearance: `light`, `dark`, or `light dark` for
  System; no `color-scheme` meta overrides it.

  `html` and `body` paint an opaque background
  and a text colour from the semantic tokens in every appearance, so nothing the reader sees
  inherits a colour from the host, such as Claude's artifact viewer in a dark scheme. Light is
  a white page with black text; Dark is a near-black page with white headings, light grey body
  text and thin grey rules. The token values are owned by [[semantic-assets]].

  Every opening starts in Light appearance and in the manifest's declared `obsHtml.layout`
  (paged by default; [[#Screens]] for a deck), regardless of the operating-system theme or previously selected reader
  appearance. Reader controls may switch appearance and viewing mode during the current
  session; those choices do not override the next opening's Light/declared-layout starting state.

  Appearance is session-only: do not read or write the old remembered appearance
  key or show an appearance-storage warning. Reviewer-name persistence is unchanged.

  The removed `artifact.reading.theme` and `artifact.reading.paged` configuration keys are
  rejected with a diagnostic naming the replacement (Light is not configurable; the layout is
  the manifest's `obsHtml.layout`). Other reading settings retain their meaning.
- Typography, spacing, borders, focus states, and control sizes are shared stylesheet
  rules rather than inline styles.
- Generated markup uses semantic elements and purpose-based class names.
- Expand/collapse affordances throughout the artifact are bare disclosure icons, not boxed buttons:
  no fill, border, radius, or button chrome, including on hover.

  One shared disclosure style owns
  their appearance across breadcrumbs, headings, TOC branches/all controls, and table groups/items.

  Hover changes icon emphasis only; focus remains visible and keyboard operation plus expanded-state
  semantics are retained.

  Native disclosure markup is used where the content structure permits it.
- Presentation is never inferred from source content or frontmatter. The packaged
  stylesheet defines the same visual system for every vault.
- Source notes cannot provide inline styles, style tokens, themes, or component classes.
- Authors style an artifact explicitly, as in Obsidian: the CSS snippets the manifest lists
  ([[input-model#Artifact presentation profile]]) follow the packaged stylesheet.

  A note's `cssclasses` are classes on the element containing that note's rendering: the
  reading `article.chapter` while the note is open, and every paper sheet of the note in
  pages and PDF. Front-page sheets (cover, abstract, contents) carry the manifest's classes.

  Packaged rules give these classes no meaning; only author snippets do, so a vault without
  snippets keeps the shared visual system.
- Navigating to a metadata-only note automatically opens the existing frontmatter panel.
  Its canonical fields remain readable without requiring duplicated body prose; notes
  with body content retain the normal collapsed-panel default.

## Takeaways and orientation

- An artifact presents its subject, not its migration, benchmark, or tool-comparison history.
  Keep development provenance in build/review files, not in the reader's subtitle or prose.
- A subtitle can orient an unfamiliar reader with a small set of existing subject figures:
  for example, the physical system and an illustrative result/distribution.

  Linked images
  are cover figures sharing the full text width in equal columns; their height follows their
  aspect ratio, without cropping or a fixed-height cap.

  The title precedes this image row,
  followed by title-page metadata.

  Their links lead to the supporting chapters.

  Unlinked inline icons retain their compact size.

  Images use the same embedded
  assets and print-readiness path as chapter figures.
- An authored `> [!important]` callout is a reusable emphasis box, not a quotation or warning.

  Render its Important heading inside the shared card primitive with an accent-colored background and border,
  ordinary high-contrast text, and an accessible Important label.

  Its emphasis must survive light,
  dark, paged and print views without relying on color alone.

  Plain blockquotes and other
  callout-like text keep their existing behavior; do not infer emphasis from position or bold text.
- The other callout types of [[input-model#Callouts]] reuse the same card primitive with their
  title as the card heading and an accessible label naming the canonical type.

  Their tone comes from the shared semantic colors: accent for note, abstract, info, todo, tip and example;
  success for success; warning for question and warning; failure for failure, danger and bug;
  and neutral border and text colors for quote.

  A soft fill, matching border and the title carry
  the tone, so the type remains identifiable without color. Callouts keep these colors in light,
  dark, paged and print views.
## Interactive engineering figures

- A shared figure presentation owns images, screenshots, plots, and diagrams, not only
  engineering plots. Standalone content images use it; inline icons and linked title-page
  image rows retain their existing inline and cover behavior.
- One figure frame. Every figure kind of the Document's `figures` node (obs input-model,
  Figure input direction) renders in the same frame, `src/obs_html/figures.py` (`frame`): one
  `figure` element whose caption, generated number, expansion button, options menu, print sizing
  and frame style it owns, while each kind renders only its body inside it.

  One stylesheet rule (`.obs-figure` in `figures.css`) styles every frame from the frame style tokens
  (`--figure-frame-border-block`, `--figure-frame-border-inline`, `--figure-frame-background`,
  `--figure-frame-padding-block`, `--figure-frame-padding-inline`), so a border set once, in a
  style module's `:root` for example, frames every kind.

  A kind is one entry of the kind
  registry (`FIGURE_KINDS`): its body renderer, its view options and the reader features it
  needs (`features.py`); adding one never changes the frame.

  A kind that registers view options gets the figure options menu below its expand button;
  a kind without options shows none. The menu is the tables' options menu, one component
  (`options-menu.js`) with the same control, placement and behaviour. What it changes (a plot's
  legend, for example) is classified in [[artifact-ui#What counts as a change]].

  A diagram figure (`mermaid`, `plantuml`) shows the SVG the core drew at build time as an
  image, like an `svg` figure without panels; no diagram library ships in the artifact and the
  kind needs no reader feature.

  Links inside a figure. A figure whose body has links (obs capabilities/wikilinks, Links
  inside a figure) shows its SVG inline instead of as an image, since an image cannot be
  clicked into (decided 6 Nov 2026); a figure without links stays an image.

  `src/obs_html/figure_links.py` owns it: each resolved link becomes the same chapter link as
  in prose, with its hover card and navigation, in the frame, in the expanded view, which
  closes as the link navigates, and in the panel inspector, which shows a copy of the inline
  drawing. Wikilink text shows its label; a link whose note is missing is shown unlinked.

  The inline SVG is never executable: scripts, embedded documents, event and animation elements,
  event-handler attributes and every target but a resolved link, a fragment of the drawing, a
  web or mail address or a data image are removed.

  Authored content never styles anything outside itself.

  An inline authored drawing (an `svg`
  figure or an SVG `image`) keeps its `<style>` elements, scoped to its own figure by
  `src/obs_html/figure_styles.py` with a CSS parser (tinycss2), never a pattern: each selector
  of each rule becomes `:where(#<anchor>) <selector>`, so it matches only inside the figure's
  frame and keeps its authored specificity.

  Rules inside `@media`, `@supports` and `@container`
  are scoped the same way; `@keyframes` names are prefixed with the anchor, together with the
  drawing's own animation names that use them.

  Every other at-rule (`@import`, `@font-face`,
  `@property`, `@layer`, `@namespace`, `@page` and any other) is global and cannot be scoped:
  it is dropped, and a warning in the one message form names the note, `figure.style` and the
  figure's anchor.

  A selector whose compound names `:root`, `html` or `body` outside a
  pseudo-class's arguments can only match the page, never the drawing: it is dropped with the
  same warning.

  The frame style tokens are therefore never changed by a figure: a scoped rule
  reaches only the frame's descendants, and a custom property set there (a
  `--figure-frame-border-block`, say) is inherited downward only, so the frame itself reads the
  page's value.

  A diagram figure's SVG (`mermaid`, `plantuml`) is the core's output, which
  scopes its own styles by the diagram's id: it is left as drawn.

  An anchor is `<note-slug>--block-<name>` for a figure with a block id, otherwise
  `<note-slug>--figure-<name>`, where name is a plot's descriptor id or the figure's position
  among the note's figures.
- Every figure has one small, always discoverable top-right expand button using the
  four-corner expand icon. It opens the figure in a viewport-filling overlay with an
  accessible close action, Escape handling, keyboard focus containment and focus return.

  The overlay close button sits at the top-right, consistent with the expand button's
  placement; reserve its space so it does not overlap plot controls or labels.
  Enlargement is generic and does not depend on the plot engine or Fullscreen API.
  Preserve live figure state rather than creating an independent second interactive copy.
- Expanded responsive plots reflow their plotting area to use the available overlay width
  and height, reserving space for controls, labels and caption. An overlay that fills the
  viewport while leaving its plot at reading-view height does not satisfy enlargement.
  Center the expanded figure horizontally and vertically within the usable overlay area,
  accounting for controls and caption.

  Fixed-aspect visuals use the largest undistorted fit in that area and remain centered when
  letterboxing is necessary; preserve available
  zoom/pan inspection. Responsive plots fill the usable area rather than letterboxing
  to their reading-view aspect ratio.
  Recompute on viewport changes and restore reading-view sizing on close without losing
  zoom or trace visibility.

  Images and aspect-constrained geometry retain their proportions. An expanded image (an image
  figure or standalone content image) can be magnified about the
  pointer with the wheel or `+`/`-` (1× to 8×), panned by dragging or with the arrow keys once
  focused, and reset by double-click, `0` or Home. Magnification is view-local, is reset on close
  and never changes the reading view or print.

  Plot legends can be repositioned by dragging their frame, without interfering with trace
  toggling or plot panning; provide a keyboard-accessible equivalent. Legend position is
  view-local and survives expand/close in the session; print retains the authored default.
- Figures are centered on the available reader viewport and may extend equally to either
  side of the prose column, within the reader and clear of the chapter controls, which a
  figure's own controls never lie under. Plot coordinate areas should occupy
  approximately the prose width; their labels and margins may extend beyond it.

  Do not distort aspect or enlarge inline images merely to fill space. Narrow screens
  constrain
  figures to the available width without horizontal page overflow. The prose-width
  multiplier and viewport gutter are shared artifact configuration, not figure-local styling.
- Use the shared semantic border tokens for a restrained figure frame, including top and
  bottom separators. Center the caption horizontally below the visual inside the frame,
  then draw the bottom separator after the caption. Plot legends have a visible border.

  Preserve caption text and links rather than duplicating or truncating them.
  Caption membership must come from explicit source semantics, not italic styling or
  proximity alone. Migrate legacy caption prose into its figure's canonical caption owner;
  do not retain a short generated caption plus a second authored caption outside the frame.

  Ordinary explanatory prose following a figure stays ordinary prose outside the frame.
  When the manifest enables figure numbering, a bold generated number (for example
  `Figure 2.4:`) precedes the first caption paragraph and block-id references to the figure
  link to its anchor, scrolling it below the reader's top controls.

  The adapter numbers every captioned figure of the contents chapters before it renders any
  note, so a reference shows the number of a figure further on.

  A block-id reference (the core's wikilink with a `figure` target) renders as a link to `#<note-slug>/block-<name>`:
  labelled, with its label; unlabelled, with the manifest's `label` and the figure's number
  (`Figure 2.4`), and an unlabelled reference to a figure without a number is an input error
  that names the Document node and the remedy.

  Adjacent unlabelled references merge as obs's
  input-model ("Figure captions and references") says, with the manifest's `labelPlural` and the
  conjunctions in `cfg.json` (`artifact.figureReferences.conjunctions`, words or phrases such as
  `as well as`, at most 64; a phrase's words stand one space or one line break apart in the prose):
  `Figures 2.4 and 2.5`, `Figures 2.4–2.6`.
- Use the expand affordance as the common artifact-level figure control. Remove persistent
  custom inspection/reset/zoom button rows from the normal reading view; keep necessary
  pan, zoom, reset and subplot selection available within the enlarged view and existing
  engine interaction.

  Do not remove trace toggling or keyboard access. Print contains the default visual and
  caption without overlay chrome or interaction controls; an equation figure prints the
  reader's view ([[#Equation figures]]).
- Web figures preserve the engineering content and essential appearance of their existing
  Python-generated counterparts. Reverse-engineer the generating code, geometry inputs,
  calculations and annotations before migration; do not ask authors to redesign each figure.
- A figure is a composition of plots, not necessarily one plot. Support subplot grids,
  unequal column widths, row/column spans, per-panel titles and annotations, shared figure
  titles and legends, and multiple axes within a panel. Preserve equal geometric aspect,
  logarithmic scales, units, limits, secondary axes, line styles and collision shading.
- The initial interaction is zoom with reset and usable pan. Readers can inspect individual
  subplots without losing the overall composition; navigation must not silently synchronize
  unrelated axes or distort geometric aspect. Keep labels and controls usable at artifact width.
- Ordinary plots are authored through Markdown fences declaring
  equations and plot details. Support legend-click trace visibility alongside zoom, pan and
  reset; hiding a trace must not delete its data. Complex geometry compositions may continue
  to come from artifact-owned scripts, using the same generic figure presentation layer.
- Use a reusable figure interaction owner, not figure-specific event handlers. Leave room for
  later capabilities without implementing speculative controls or changing engineering models.
- Data-driven diagrams may project fields from the artifact's canonical record store.
  Their generic view recomputes from the shared artifact-wide filter; it does not create a
  second filter or duplicate artifact records. Table-local filters remain independent.
- Interactive figure state is view-local. A dynamic diagram's portable and print rendering
  shows the authored unfiltered default; browser filter changes update only its live view.
- The shared figure framework applies in both paged and continuous reading views.
  Ordinary figures retain readable bounds in either mode: fit the available reader width
  and viewport height while preserving aspect ratio, without stretching small source images.

  The normal image height limit is shared artifact configuration; print retains paper-specific sizing.
  Wider-than-prose presentation is not unrestricted enlargement. Only the explicit expand
  control requests viewport-filling inspection; switching pages off must not implicitly
  enlarge an image or bypass the shared figure sizing rules.
- Normal artifact and PDF presentation retain the complete default composition, captions and
  provenance. Interactive state is view-local; zoom does not alter source data or calculations.
  Static source figures remain available until visual and numerical parity is verified.

### Equation figures

Decided by the user, 5 Nov 2026 (work issue `feature/equation-figures-live-20261105`): the
reader explores an equation figure through its options menu; there are no 3D plots.

An equation figure (obs capabilities/equation-figures) is plotted live from the Document's
expression trees by `src/obs_html/equations.js`, with the plotting library of stored-data plots
(Plotly) for drawing, zoom and pan, and one maths library, math.js, for complex arithmetic and
for parsing the reader's expressions.

The maths library is pinned in `maths/package-lock.json`,
built from it into the package when the package is built
([[architecture#Packaged browser assets]]) and embedded whole, with its licence, only in an
artifact that holds an equation figure: it is the reader feature `equations` (`features.py`),
whose canary reports a host that does not run it. An artifact never loads it from elsewhere.

- Evaluation: a tree evaluates with the variables' SI values in complex arithmetic with
  principal branches; a result is a point of the plot where its imaginary part vanishes
  (`|im| <= 1e-9 * max(1, |re|)`), elsewhere the curve has a gap.

  Real-only operators (`atan2`,
  `sign`, `min`, `max`, `heaviside`) take real arguments only; `heaviside(0)` is its second
  argument, 1/2 without one, and `sign(0)` is 0.

  A piecewise tree takes its first case whose
  condition holds; a relation compares real values, `eq` within `1e-9` of the larger magnitude.
  The shared test vectors of the core pass with this evaluator.
- Sampling: each curve has 241 points spread over the swept variable's visible range. At every
  zoom and pan the visible range of the swept variable's axis is sampled again, so detail grows
  as the reader zooms in; the range never leaves the variable's range.
- Solving: exact branches are evaluated; each branch is a curve. Where the exact solution's
  numeric condition holds for a curve's values, its numeric system solves that curve instead,
  as one branch. Algebraic residuals are
  solved at each point by Newton's method with a halving line search, seeded from the defaults
  (the Document's guess) and continued from the previous point.

  A differential system is integrated from its start with an adaptive Runge–Kutta method (Dormand–Prince 5(4), relative
  tolerance 1e-9), stepping onto every sampled point. Curves compute in slices of at most about
  12 ms between which the page runs on; a status line counts the curves while they compute.
- Axes and names: an axis shows a plotted variable in its authored unit, from its quantity's
  range or value, and any other expression in SI base units. A family curve is named by its
  expression and its value, `T, throttle = 0.5`.
- The options menu adds to the plot's Legend:

  - **Add trace** (an expression over the figure's
    variables, parsed by the maths library, on the first or the second y axis; an expression it
    cannot read names itself, the reason and the variables it may use),
  - **Second y axis** (its
    side, right or left, the first axis taking the other side, and each authored y expression's
    axis),
  - **Swap x and y**, and
  - **Family** (a third movable variable by a number of steps spread
    over its range, or by values in its unit; None removes it).

  Every choice, and the zoom, is
  a choice in a figure's options menu as [[artifact-ui#What counts as a change]] classifies
  it, kept per figure anchor while the artifact is open.
- Parallel coordinates: the figure's grid (obs input-model, Equation figures) shows above its
  curves where the fence sets `parallelCoordinates: true`, or where the reader presses
  **Parallel coordinates** in the options menu.

  Each line is one combination, each axis a grid
  variable or a computed axis, scaled from its lowest to its highest value; every axis shows a
  histogram of the combinations' values in ten bins. The runtime computes the computed axes:
  an expression at the combination's values, a summary from the combination's curve sampled
  at 241 points over the full x range, on the first solution branch.
- The cap: a plot draws at most `artifact.figures.parallelCoordinatesCap` combinations
  (`cfg.json`, 1000 by default), which only the build configuration sets.

  Above it, the plot warns and thins the rightmost grid axis to as many evenly spaced values as the cap allows
  (keeping both ends), then the next to its left. The reader drags an axis by its label to the
  left or right; the order is the cap's priority.
- Selection: dragging along an axis selects the range it covers, a click on the axis clears it,
  and ranges on several axes combine.

  The curves below are exactly the selected combinations,
  all of them while no range is selected, one trace per plotted expression whose points name
  their combination; the family option does not apply while the plot shows. Order and ranges
  are view state like the other options.
- Print and PDF show the reader's current view of an equation figure, not its initial plot;
  where that view differs from the initial plot, the caption ends with the note *View changed
  by the reader.*

### Decision figures

Decided by the user, 6 Nov 2026 (work issue `feature/pugh-decision-figure-20261106` and its two
change comments): one decision is a one-pager; the options come first; the reader changes
weights and marks in place and plays what-if; the details sit behind tabs.

A decision figure (obs capabilities/pugh-decisions) is decided in the reader's page by
`src/obs_html/pugh-figure.js` with ctrl's Pugh engine, `src/obs_html/vendor/pugh.js`, copied
unchanged from ctrl (its header names the commit). The engine is embedded, with its header,
only in an artifact that holds a decision figure: it is the reader feature `pugh`
(`features.py`), whose canary reports a host that does not run it.

Every option carries its letter, A, B, C and on in the order the fence lists them, wherever the
figure names it, its label and its short name (obs input-model, Pugh decision figures). Where
there is room, an option reads as its letter and short name, "B · Close": in the option view, the
table's column heads, the bottom line, the Raised list, the What if lines and an answer's record.
Without a short name the letter stands alone. The figure has three tabs in the adapter's tab control
(the look of a table's detail tabs), Matrix first and shown at the start, then one tab for each
of its chapter's sections after it ([[#Decision tabs from the chapter]]):

- **Matrix:** the bottom line (the winner, its total against the datum, and whether the choice
  holds or depends on the weights, with the winner's share of the weight draws); under it the
  Raised list; then the options, one at a time; then the table.
- **Checklist:** the fence's checklist items, each with its answer, passed or failed, and the
  letters of the options it fails. Without items the tab is disabled.
- **What if:** the worlds in which another option wins, which the reader rules.

The options view shows one option, "Option A of 5", with its letter and short name, its label in full and its `what` sentence.
Previous and next keys, the arrow keys while it has focus, and a horizontal swipe move between
the options; none of them walks the chapters.

The table has the options as columns, the datum first and the winner marked, an option that does
not fit greyed with its reasons in its tooltip; the criteria as rows, each with its weight; the
weighted total; then two text rows, Wins and Losses, the options' own `wins` and `losses`,
which add nothing to the totals and are said nowhere else.

The Checklist row: a failed item that names options gives each of them a mark of −1 per failed
item, at most −2, on a row "Checklist" with the fence's `checklistWeight` (3 by default). The row
is a criterion of the matrix the figure hands the engine (judged against the datum like any
other), and shows only when such an item fails.

The reader changes a weight in its field and a mark by tapping it and choosing −−, −, S, + or
++ in place, with no browser dialog. A changed weight or mark is marked as changed, everything is
decided again at once, and Reset, in the figure and in its options menu, restores the fence's
values. A changed mark is the engine's own cell override.

What if: its top line is "B wins unless …" with the closest world in which another option wins,
or "No change of weights makes another option win". Then, for each other option that may win, the
smallest change of one weight that makes it win ("A wins if Speed weighs below 0.5 instead of
2"), and the smallest change of all weights together, which weights from what to what. There is
no band: the reader rules each world "could happen" or "nonsense", and a world that could happen
asks for a tripwire, a one-line sign to watch for.

The Raised list, under the bottom line, shows only when it holds something: every failed
checklist item, every world ruled "could happen" with its tripwire, and, where the fence's
`chosen` option is not the winner, the world in which it wins, in the same form.

The changed weights and marks, the rulings and the tripwires are reader state, kept per figure
anchor while the artifact is open, and readable by the page as `obsPugh.readerState()`, by figure
anchor and with options by letter, with the winner they give, for whatever sends a reader's
verdict ([[#Bless verdicts]]).

Where the chapter asks for a bless, each option's column head other than the winner's has a
Pick key ("Pick B"). Where the chapter's answer recorded changes, the figure shows them
read-only, as print does, and Reset is disabled.

Print and PDF show the Matrix tab as the reader left it, the options as a list and the weights
and marks as text; where weights or marks changed, the caption ends with the note *View changed
by the reader.*

Inside its frame the view keeps to the prose around the figure, clear of the chapter controls. A
page layout draws a decision figure when it places it, so its page holds the whole view. Where
the table is wider than the view, it scrolls in its own box, the criterion names held at its left.

#### Decision figures on a phone

Decided by the user, 6 Nov 2026 (work issue `feature/decision-figure-on-phones-20261106`): on a
phone a reader scrolls up and down, never sideways, so the matrix prefers rows over columns.

Below 36 rem of the figure's own width (`ROWS_BELOW` in `pugh-figure.js`; the figure measures
its frame, not the device), the table becomes rows. Each criterion is two lines:

- its name over the full width;
- its weight stepper (−, the weight, +, half a step a tap), then one cell per option, headed by
  the option's letter, the winner's cell marked.

The weighted total follows the same pattern. Wins and Losses list one line per option, letter
first. The Pick keys sit in one line under the total.

A cell takes up to 2.5 rem and gives way to 1.7 rem before its line wraps: five options fit
beside the stepper in the narrowest figure, at a 360 px phone, and more wrap to a further line.
Nothing in the figure scrolls sideways.

In the rows only the letter fits, and the letter is a control. Hovering it, focusing it or
tapping it shows the option's letter and short name, its label and its `what` sentence in a small
popover under the line; a second tap or a tap elsewhere closes it, with no browser dialog. The
popover is the control's description for a screen reader.

The letter heads its cell as a control of its own, above the cell's mark key, so a tap on the
mark changes the mark and a tap on the letter opens the popover. A mark, a weight step and a Pick
are one tap each, as in the table.

The table and the rows are drawn from one decision and one reader state: a resize across the
width draws the other form with the reader's changes kept. Print shows the table.

#### Decision tabs from the chapter

Decided by the user, 6 Nov 2026 (work issue `feature/decision-figure-on-phones-20261106`): a
decision chapter's long material sits in its own tab, not under the one-pager.

In a chapter whose main content is a decision figure, its one decision figure at the top level,
each second-level section after the figure, up to a first-level one, becomes one more tab of the
figure, named by its heading; "## The record" becomes a tab "The record". `render.py` moves the
section into the figure when it renders the chapter, so its text no longer runs below.

The tab's panel carries the heading's anchor, and its deeper headings stay in it. Without such
sections the figure has its three tabs. Print shows each section under the Matrix tab, headed by
its name.

## Reading shell

- An artifact with appendices has one Appendix chapter. Its direct children are the handwritten appendices
  first, followed by generated open points, glossary and references. There is no intermediate
  generated-appendices chapter or additional glossary navigation level. Its open-point rows
  represent the canonical marked paragraphs rather than a second authored register.

  References to open points display the stable mark ID rather than repeating the question;
  clicking reveals the corresponding open-point table row, including its page and collapsed
  ancestors.

  The open-point table replaces its single Source column with Backlinks: clickable locations
  for the owning paragraph and all references to that point, including references
  in note properties used by other tables. Backlinks distinguish referring locations rather
  than repeating the same location for each generated projection.

- The viewport contains one active chapter, with scrolling confined to that chapter.
- A sandboxed preview frame (`srcdoc`, `allow-scripts` only, as in Claude's preview) is a supported
  environment: where the frame refuses URL or storage changes, navigation and settings keep working
  without them.
- Chapter/page navigation commits the destination and presents its heading, breadcrumbs
  and available static content on the next paint, before expensive table or calculated
  overview work. Results must not remain apparently unresponsive while its table loads.

  A link to a whole note opens it at its heading: the chapter is scrolled to its top and to its
  start, also where the reader had scrolled it sideways (review mode lets a wide body overflow).
  A note's link to itself is such a link: it scrolls the chapter back to its heading, and where
  the chapter is at its top already nothing moves.

  Pending table/overview regions use a shared accessible loading treatment; animation
  respects reduced-motion preferences and stops on completion or explicit failure.

  Figures deferred between placeholder and real attachment must initialize against
  their mounted view. First-ready graph content includes its canonical counts and
  filter bindings without requiring another filter, resize or navigation action.
- Repeated activation of the same pending navigation intent must not queue additional
  relative steps and skip the requested chapter. A genuinely different destination
  remains selectable without waiting for calculation. Late work for an old destination
  must not replace the active view or apply an obsolete filter. Do not solve slow
  navigation by disabling all navigation until the table finishes.
- A compact breadcrumb row appears above the active chapter heading and reflects its manifest
  ancestor path.

  A home icon is always the first crumb and links to the autogenerated Home
  defined in [[input-model]].

  Chapter labels navigate directly.

  Each native disclosure triangle, without button
  styling or button markup, opens the choices available at the following hierarchy level, including
  top-level chapters at the first triangle, so readers can switch paths without opening the table of
  contents.
- On Home, the document title is centered; authored chapter headings retain their normal alignment.
  An explicitly empty manifest title omits the visible title heading, without leaving an
  empty heading or removing any other cover element. The filename fallback continues to
  identify the artifact to browser and assistive navigation; title semantics belong to
  [[input-model]].
- Activating the current page's breadcrumb reveals its immediate children instead of reloading the
  page.

  The current Home crumb offers top-level chapters.

  A click anywhere outside the breadcrumbs, the menu and a docked bar included, closes an open
  chooser.

  A node has no child chooser; ancestor
  crumbs continue to navigate.

  Native disclosure icons and accessible expanded states remain.

  From a note outside the TOC, the Home icon always navigates Home; the note's current crumb
  neither invents a TOC path nor intercepts the Home link.
- No table of contents, filter, toolbar, or navigation bar is open initially.
- The top band is one row and holds every top control: Home, the breadcrumbs, the
  frontmatter chevron, the position indicator and title of [[#Screens]], the bless controls
  ([[#Bless verdicts]]), the notice icons and the menu.
  The notice icons sit directly left of the menu.
  The bless controls sit directly left of them.
  Every control in the band is a square of one size. No control takes a row of its own.
  Breadcrumbs that do not fit truncate on that row; each keeps its full title as its text and
  tooltip. Their choosers do not truncate: the row keeps room for one toggle per level of the
  path, so a subchapter's Choose chapter and Choose subchapter both show.

  At 360 px and wider the row holds every control the band shows, fully visible, without
  sideways scrolling. Where the squares at full size do not fit, they all shrink to one size
  that fits; no control is dropped.
- Each table-options icon shows a small, top-right funnel bubble while its interactive
  filter is active, even if it matches every record. Its label/tooltip expose that state.
  The notice center's applied-filter entry is the sole artifact-wide indicator: no
  redundant green applied-filter menu badge/indicator accompanies it.

  Clearing the filter removes its warning; invalid input preserves the last successfully
  applied filter's indicator.

  Table base queries define the source view and do not activate this indicator.

  Search, grouping, sorting, and pagination do not activate it.
- Previous and next controls sit at the left and right viewport edges. They are smaller
  than mdBook's controls and highly transparent at rest.
- Each chapter control has a larger invisible pointer area. Its arrow becomes less
  transparent when the pointer approaches, and is clearly visible on hover or focus.

  Reserve horizontal reader clearance for that pointer area in both continuous and
  paged views, including narrow screens. It must not cover prose links or table
  disclosures, resizing handles, and options. Screen clearance does not change PDF
  paper dimensions or margins.

  The coverage sweep in `test/test_parity_browser.py` holds every control to this, on every
  chapter, at four widths, in both views, with no bar and with each bar open. In each view and
  at every width it opens the contents bar on the first chapter twice, its contents collapsed
  and then expanded by the bar's own actions, so no check depends on an earlier one's state.
- On touch, a horizontal swipe of at least `artifact.reading.swipePixels` (`cfg.json`), mostly
  across, moves to the previous or next chapter of the walk: the arrows' walk, which the contents
  and the breadcrumbs share. A swipe that starts in a box that scrolls sideways (a wide table, a
  figure's table) or in a field stays with it; the decision figure's options take their own.
- Scrolling toward the top or bottom boundary reveals the available previous or next chapter
  arrow at full opacity. Wheel, touch and vertical keyboard scrolling do not change chapters
  automatically. Moving away or changing chapters clears the cue; nested scrollers and editors
  do not trigger it.
- Boundary cues also use the shared yellow attention ping: a border expands outward from
  the visible arrow frame and fades away at its configured terminal scale.
  Configuration owns the pulse period, burst count and scale; the initial effect is a short
  radar-like burst rather than a flashing fill or an indefinitely running animation.

  Terminal scale controls the final ring radius relative to the arrow frame; increasing it
  must not enlarge the arrow or its hit area. The requested larger cue doubles the previous
  final radius while preserving burst timing and cancellation.

  Further attempts can trigger another burst; continuous input must not reset each pulse.
  Moving away or changing chapters cancels it. Reduced-motion readers get a static yellow
  border instead of expansion. The attention effect is reusable without navigation knowledge.
- The collapsible TOC includes authored subheadings at every level beneath their chapter,
  alongside manifest child chapters. All branches start collapsed. Heading links open the
  chapter, expand the target's collapsed content ancestors, and scroll to that heading.
- Touch layouts keep chapter controls visible enough to discover without hover.
- A small top-center chevron follows the side controls' restrained visual behavior when the
  active chapter has frontmatter. It toggles a field/value table above the chapter body and
  reports its expanded state; changing chapters closes the table.

## Bless verdicts

Decided by the user, 6 Nov 2026 (work issue `feature/bless-verdicts-20261106` and its two change
comments): a chapter that asks for a bless (obs input-model, Bless requests) is one page of a
deck; the reader walks the deck and gives each page a verdict with a key, never with a swipe.

On such a chapter the top band shows, left of the notice icons:

- **The pill:** the chapter's state: Bless pending, Blessed, Declined, Question or Picked B,
  with the picked option's short name where the band has room ("Picked B · Close", the
  decision figure's own short name, [[#Decision figures]]), then "· sent" once sent and
  "· needs a comment" while a comment is missing.
- **The keys:** four squares of the band's size: Bless (✓), Decline (✗), Ask (?) and Pick (⇄),
  Pick only where the chapter has a decision figure.
- **The comment:** Decline, Ask and Pick open a one-line comment entry in the band, directly
  under the keys, and only then; Pick shows there the other options' letters ("Pick A"), as the
  figure's column heads do. There is no comment box in the page and no browser dialog.

A complete verdict, a Bless or another verdict with its comment (and, for Pick, its letter, the
comment confirmed with Enter), opens the next chapter of the walk.

**Send** shows in the band, on every chapter, while any chapter asks: "Send 1/2", the complete
verdicts of the asking chapters. It is disabled until one is complete, and hands one payload to
the answer sink ([[capabilities/answers]]); [[capabilities/bless]] owns its fields. A sent
verdict shows as sent until its chapter's version changes.

A chapter whose answer the build carries (`obs-document --answers`) shows it read-only under
its heading: the verdict, the picked option, the comment and the reader's changes, rulings and
tripwires; its pill reads "· recorded" and it has no keys. An outdated answer shows the same way,
marked outdated, and the chapter asks again.

When the band is short of space, the breadcrumbs shrink first. Then the pill drops what follows
its state, whole ("Picked B · Close · sent" reads "Picked B"), then the state truncates, and
then it shows only its state colour, as a square of the band's size; its label stays its
tooltip and accessible name. Only then do the band's squares shrink. No key is dropped.

## Screens

Decided by the user, 6 Nov 2026 (work issue `feature/screen-layout-for-decks-20261106`): a
decision is a one-pager, not a document page, so an artifact can be read as screens.

`obsHtml.layout: screens` ([[input-model#Artifact presentation profile]]) shows each chapter of
the walk as one screen: the chapter at the reader's full width inside a side gutter that holds
the chapter arrows, with no page frame, cover, running header, footer or page number. The
manifest's title shows only in the top band, between the breadcrumbs and the frontmatter
chevron; it truncates first, its full text its tooltip. Home shows its content without the cover.

Without a declared `obsHtml.layout`, a manifest whose listed chapters (the reading order) all
ask for a bless opens in `screens`; any other opens in `paged`. A declared layout always wins.
The adapter decides this from the Document's chapters, so the core carries nothing new; obs's
example deck (`spec/examples/bless-deck`) opens in screens by this rule.

- **The walk:** swipe and the arrows move between screens ([[#Reading shell]]); the contents
  stay in the menu. The top band shows the position on the chapters of the walk, "2 / 3", as
  one of its squares, first at the band's end; Home, which is not one of them, shows none. The
  bottom of the screen stays free for content.
- **Show as pages** switches to the paged view for the session; switching it off returns to
  screens.
- **Printing** from screens prints each chapter from a new page, as the reader sees it: no
  cover, front pages, running header, footer or page number ([[#Pages and PDF]] owns the rest).
- The feature `screens` (`features.py`) ships only in an artifact that opens in screens, with
  its canary (`canaries/screens.js`), which reports a host that gives the page no viewport.

## Internal-link previews

- Internal note links across prose, tables, breadcrumbs, and navigation share a delayed
  hover/focus preview, including links to record-only notes. Clicking the original link
  navigates to a note in the contents and shows any other note in the
  [[#Floating window|floating window]]; glossary table disclosure labels remain inline
  expanders, not links.
- Preview data is derived lazily from the canonical note, never a second serialized record.

  Show its title, a bounded set of flattened metadata values (excluding duplicated title,
  term, aliases, and definition), and a plain-text excerpt.

  Prefer the glossary definition, then prose paragraphs; omit tables, code, images, and
  interactive content.

  Limits and delays belong to packaged configuration, with project overrides.
- A single viewport-contained card is shared by all links, including dynamically rendered
  content.

  Readers can move into it and follow its title to the full destination.

  Keyboard
  focus provides the same preview. Dismissal follows the hover-card lifecycle in
  [[#Overlays|Overlays]]: Escape, a click outside, or a hover on another link.

  Touch users
  can follow links directly without a hover prerequisite.

  External and unresolved links do
  not show previews, and previews make no network requests.
- Table action/informational help uses this same rich-hover card and lifecycle,
  not per-cell popovers or multiline native-title instructions. Reuse the
  existing trigger-adjacent placement and viewport-fitting rules; help must not
  jump to the center of the screen through browser-default popover positioning.

  Preserve the operation's accessible label and render canonical help fields through the
  existing trusted rich-metadata owner, keeping their links genuinely usable.

  Readers can move into the card and follow those links; keyboard focus,
  dismissal, viewport containment and dynamic/re-rendered rows follow the same
  shared behavior. Help never activates or replaces the control's original
  action, including file selection. Transient help does not leak into saved
  source data or print projections.

## Floating action cards

The framework provides one reusable floating-content host for trusted registered
actions, not a document-type-specific workflow engine. Input and trust boundaries
belong to [[input-model]]. It can host safe instructions and ordinary accessible
controls without reinitializing the whole HTML application in another window.

Prefer Document Picture-in-Picture when available and permitted: it provides a
browser-owned always-on-top card while the reader works in another website.

Request it directly from the action's user activation. Put the source link inside
the card, first and above the instructions, so opening that source in a new tab is
a separate deliberate activation;
do not try to open both contexts from one click. External source navigation uses
opener isolation and never receives application data through a cross-site channel.

When floating mode is unavailable, use an ordinary owned helper window. If policy,
sandbox or popup restrictions prevent opening it, show the card inline in the HTML
as the fallback, with an explicit retry/open control and an honest explanation.

Do not silently claim simultaneous visibility, force OS window arrangements, embed
an arbitrary external site, inject into foreign tabs or require extensions/installations.
Browser size hints use packaged cfg/schema defaults, not duplicated constants.

Exactly one floating window exists per artifact (decided 29 Oct 2026, see
[[#Floating window|floating window]]). While it holds the card, the HTML shows no card, placeholder or status
for it. Closing the window discards an unfinished action and releases owned listeners, without
closing the unrelated source tab or committing that action.

Native helper close, parent navigation and unsupported APIs follow that same
lifecycle; forced browser crashes cannot promise delivery of close events.
A rerender must not strand the card or duplicate an active session.

Use the shared semantic styles, rich-content rendering, labeled controls, visible
keyboard focus and explicit submit/cancel actions. Tell readers when a link opens
a new tab. Do not trap focus or repeatedly steal it from the source website.
Floating cards are transient: they do not appear in printed or saved HTML.

### Floating window

Decided 29 Oct 2026, implemented 4 Nov 2026
(`spec/backlog/reference-items.md`). The floating-content host is one window per
artifact, shared by all its uses: evidence collection, context, and later context-sensitive help.
This matches the platform rule that a page has one Picture-in-Picture window. It is never a
sidebar.

- If the window is open, new content replaces its content in place. It is never closed and
  reopened, so it stays where the reader put it.
- A small header names the current use ("Evidence collection", "Context").
- Back and forward arrows move through what the window showed, across uses. An unfinished
  evidence collection replaced by other content stays in this history and Back restores it
  unchanged. Only closing the window discards it.
- Context opens the window when needed: clicking a link to a note that has no place in the
  table of contents shows that note here instead of navigating the page. Links inside the
  window replace its content the same way.
- No menu entry opens the window; it opens only when something is shown.
- The helper-window and inline fallbacks keep the same header and arrows, with minimal effort:
  current browsers support Picture-in-Picture.
- Context shows the note's title, its metadata and its body. Tables and figures, which need
  the page's runtime, are left out with a short note saying so.
- Showing new content after going Back drops the forward entries, as browser history does.
  A finished evidence collection (applied or cancelled) leaves the history; the window closes
  when nothing is left.

### Link hover card

Decided 29 Oct 2026, implemented 4 Nov 2026
(`spec/backlog/persistent-rich-hover.md`). Hovering a link to a
reference note (obs's input model, Reference notes and link text: [[obs-specification|obs's specification]]) shows a small card with the
note's short description and its external link.

The reader either follows the external link
from the card or stops because the card is enough. This card holds the only direct external
link.

Lifecycle and content (decided by the user, 4 Nov 2026, option B):

- The card is the shared [[#Internal-link previews|internal-link preview]] card (overlay tier 1,
  see [[#Overlays|Overlays]]). Once shown it stays until Escape, a click outside it, or a hover on
  another link, which replaces its content in place. Moving the pointer away does not close it.
- The external link in the card opens in a new tab, labelled as such.
- Content per kind of target:
  - reference note: title, URL, description, accessed date;
  - numeric-value note: formatted value with unit, tolerance or range, and its derivation
    (prose, command or query);
  - glossary term: term and definition;
  - mark: kind, label and the marked paragraph's text;
  - any other note: title and first paragraph, as the preview shows today.

## Overlays

Decided by the user, 4 Nov 2026: there is one overlay system with exactly two tiers, so every
hover behaves the same way.

1. **Hover card** (simple, inside the page): one shared card for every hover in the artifact.
   - Users: internal-link previews, the link hover card, table action and informational help,
     and any future hover.
   - One owner module (`hover-card.js`) places it next to its trigger, fits it into the
     viewport and renders it. Features register a trigger selector and a content resolver;
     a plain explanation needs no code: any element may carry `data-hover-help` text instead of
     a native `title`. Its show delay and excerpt limits are the `artifact.hoverCard`
     configuration.
   - Lifecycle: it stays until Escape, a click outside, or a hover on another trigger, which
     replaces its content in place. Keyboard focus opens it like hover. If its trigger scrolls
     out of view, it closes.
2. **Floating window** (complex, may float over other content and other applications): the
   [[#Floating window|floating window]] for evidence collection, context for off-TOC notes and
   later help. Document Picture-in-Picture first, with the helper-window and inline fallbacks.

No other tooltip or popover mechanism exists: no per-feature popovers, no browser-default
popover positioning, no multiline native `title` tooltips for reader-facing explanations.

Accessible names stay as `aria-label`. Data-point hover labels inside charts belong to the
figure and are not overlays. Hover cards and the floating window never appear in print or
saved source data.

Implementation decisions (4 Nov 2026, worker, reversible):

- A short single-line `title` that repeats a control's accessible name (icon buttons such as
  "Zoom in") is a name hint, not an explanation, and stays. Explanations are `data-hover-help`.
- Menus and option panels that the reader opens by clicking (table column menus, table
  options, filter value lists) are controls, not overlays, and keep their own popups.
- A disabled control's reason stays in its `title`: disabled controls receive no reliable
  hover or focus.
- The persistent card can cover links below its trigger; the reader dismisses it with Escape
  or a click outside before hovering them.
- The mark card reads kind, label, text and source from the shared tag record projection (the
  rows the mark registers show), not from tag parsing, so it follows that projection when
  callouts replace mark tags.

## Pages and PDF

- An active print projection owns its sheets throughout asynchronous asset readiness
  and the browser print lifecycle. Reader/table relayout notifications must not reuse
  or clear that projection as a screen-measurement scratch area. Defer any invalidated
  screen measurement until printing finishes.
- The screen-only unbroken-table option is owned by [[input-model]]. It permits a
  variable-height HTML sheet for the current row page, so an expanded subject stays
  with its row instead of moving onto another screen sheet. It does not change PDF
  paper dimensions or physical pagination.

- Settings + exports owns appearance (system, sun/light, moon/dark icons), paged viewing,
  and Export PDF. An artifact that opens in [[#Screens]] prints as screens.

  Export invokes the browser print dialog; select Save as PDF.

  Native
  browser printing uses the same export projection, even when paged viewing is off.

  Show as pages and Export to PDF share one row.

  Explanatory help belongs to hover tooltips,
  not persistent or click-revealed prose; actual action errors remain visible.

  Export mounts its content, waits for images to load/decode and fonts to settle before
  measuring pages, then verifies the final page images before invoking printing on the
  next animation frame.

  The readiness wait has a configured timeout and reports failures
  rather than printing missing figures or remaining busy indefinitely.

  Overlapping clicks
  do not open multiple dialogs; failed calls and closed dialogs allow a fresh attempt.
- The opening-state rule above also applies to saved reviewed HTML; session toggles
  are not saved opening preferences.

  Paged HTML is the canonical interactive view, not a static print projection.

  It moves the
  original live content onto paper-shaped sheets, preserving tables, query editing, resizing,
  details, review and heading controls.

  Tables, lists and code fences stay whole on screen;
  sheets grow when those blocks or later reader interactions need more room.

  Screen sheets also shrink to their visible content, without a paper-height minimum.

  Collapsing a section hides all its continuation fragments and empty sheets; expanding it
  restores the same live content and table state.

  Do not add visible page-break markers.

  Reviews, selection comments, nested replies, decisions, filtering, saved/imported copies
  and highlights remain available in pages.

  Their gutters may sit outside the paper, with
  reserved screen space so controls do not clip or change the paper's text width.

  PDF uses fixed measured sheets and splits lists and tables, repeating table headers and
  preserving row columns.

  Print tables, including tables nested inside cards or columns, fit their actual containing
  paper area. Interactive pixel widths and minimum widths must not push cells outside a
  printed card or sheet.

  Reflow and wrap within that area while preserving authored column proportions, complete
  data and meaningful action/source representations; clipping or
  hiding overflow is not a layout correction.

  Physical PDF text retains normal glyph proportions in body text, tables and running
  headers/footers. Do not squeeze a page or table horizontally to fit, distort font metrics
  or use a landscape-to-portrait scaling workaround.

  Use the existing wrapping and page splitting contracts. Verify
  actual PDF glyph geometry and containment,
  not only the dimensions of the preprint DOM or the PDF page boxes.

  Fill available space before breaking a container; keep headings
  with the following content.

  Use compact, consistent heading-to-content spacing without accumulating wrapper and
  heading margins. Retain a clear section hierarchy without shrinking body text to fit.

  A heading, including its collapsible wrapper, must not be stranded at a sheet bottom:
  move it with the first following content, retaining consecutive heading chains together.

  This includes a front-page group that would contain only headings, such as the declared
  Abstract title when the abstract has no content before its first second-level heading:
  it continues on the following group's first sheet instead of occupying a sheet alone.

  At a paragraph split retain at least two lines on either side when the paragraph can
  satisfy that constraint.

  Keep captions with their figures and table headers with a data row. Preserve source
  order: figures do not float past intervening prose. Content too
  large for one sheet must still progress without clipping, blank-page loops or making
  an entire ordinary section indivisible. Apply the rules in both paged HTML and PDF,
  respecting their existing live-block and fixed-sheet differences.

  Paper size and margins are the manifest's `obsHtml.print`
  ([[input-model#Artifact presentation profile]]); their catalogue and limits are configuration.

  A table explicitly marked wide starts a landscape sheet. All continuation sheets containing
  that table remain landscape, including repeated headers and expanded content, and ordinary
  content after the table returns to portrait. Do not rotate the entire artifact or infer wide
  mode from a role name or a guessed overflow threshold. Keep the table's heading/caption with
  its first rows.

  Screen sheets express the same mixed orientation within the available reader width. PDF uses
  actual swapped physical page dimensions, not a rotated/clipped portrait canvas. Mixed
  portrait/landscape page boxes, readable ID/title labels, contained columns and repeated table
  headers require native PDF verification.

  Previous/next arrows still change chapters, not individual sheets.

  Page numbers are continuous across the filtered artifact, including title, abstract, and
  contents pages; they never restart when changing chapters.
  HTML assigns its logical page numbers once for the current global filter and
  keeps them stable while rows expand, subject tabs change, local table pages
  change or the items-per-page setting changes.

  Such interactions may make the current sheet taller; they do not renumber it or later
  chapters. Progressive
  startup must not publish guessed numbers and later replace them with different
  ones. A changed global filter may establish a new numbering map. Physical PDF
  pagination remains independently calculated from complete print content.

  Logical measurement retains the HTML whole-table hint through the shared static
  source projection; it must not reserve physical PDF continuation numbers between
  two adjacent HTML chapters.
  Tables that initially span several HTML sheets retain their logical sheet allocation during
  local interaction, including column resizing.

  Existing sheets may grow to accommodate changed row/detail heights; they must not
  introduce
  duplicate, reversed or out-of-range footer numbers or overrun the next chapter's
  frozen start. This is not permission to renumber later chapters or to disable
  their normal initial sheet splitting. PDF still lays out complete physical pages.

  HTML paged viewing retains the same interactive breadcrumb navigation above the sheets,
  outside the measured paper area.

  Switching view modes reuses that navigation; PDF omits it.
- Home's paged projection is the manifest's declared front pages in their declared order
  (by default title, the "Abstract"-headed abstract sections, then "Contents"; see the
  artifact presentation profile in [[input-model]]). Generated headings and running-header
  sections use the declared titles or the authored heading text, never converter literals.

  Each top-level second-level heading in the abstract begins a separate page group,
  retaining authored order and heading text. This applies to any heading, not named
  History/Metadata exceptions; absent sections reserve no page.

  The title sheet always reserves at least one full configured paper height (A4 by default),
  even when its content is shorter. Content-sized shrinking applies to the other screen
  sheets, not the cover. A compact document heading (`heading: compact`) has no title sheet;
  it opens the first front page and is not repeated on later sheets.

  Screen sheets fit the available reader width on narrow screens rather than requiring
  horizontal reader scrolling. They reflow text without scaling it down; PDF retains the
  configured physical paper dimensions and margins.
  Screen horizontal gutters yield space to readable text and tables on narrow readers;
  page headers and footers stay aligned with that text area.

  The screen cover's minimum height remains unchanged.
  Ordinary card groups use one column within paper text width; an explicit authored
  two-column block preserves its declared composition when readable. Continuous viewing
  can use responsive columns. The title-first composition therefore intentionally
  places abstract cards below the cover, not beside it or at the first screen's top.

  History and Metadata also have headings in unpaged HTML.

  Paged Contents uses dotted leaders and the measured PDF chapter start numbers; expanded
  on-screen sheets do not promise the same physical length as PDF.

  Contents and chapters respect the applied
  global chapter filter; structural ancestors are not exported unless they match themselves.

  Front pages remain available even if Home does not match.
- Printing always uses light colors without changing the current session's screen appearance. Navigation,
  previews, review controls, and table controls are omitted. Tables show all matching rows
  rather than just the interactive table's current page; collapsed note details are omitted.

  Printed tables consume the same committed Base definition, query selection and canonical
  cell projections as their reader views. Exporting all matching rows does not discard the
  table's authored filters, substitute the unqualified canonical population or replace
  canonical reference/editable-field values with empty placeholders.

  Verify table-specific identities and displayed values against explicit expected results, not only
  artifact totals.
  The first export from a freshly opened artifact must already use settled current canonical,
  query and resource state, without first visiting every lazy chapter. Repeated export,
  canonical edits, filtering and reviewed-copy reopening preserve that contract.

  Reopening the artifact or PDF is not a correctness workaround; check the generated artifact itself.
  PDF is a presentation export, not a source distribution: it does not embed the HTML
  runtime, source archives or original evidence attachments, or expand collapsed note
  details merely for printing. Necessary rendered images and font resources remain.

  For comparable visible content, preserve the working export's compactness; investigate
  material size regressions with measured resource/stream breakdowns rather than retaining
  hidden content or duplicating fonts, images or whole-artifact payloads per sheet.

  When the PDF action opens the browser's print dialog, explain the browser-native
  Save as PDF destination. An operating-system PDF printer is not an equivalent
  export path: it may discard links, outline text or force a single paper orientation.

  Do not claim native-browser export checks also certify that driver. The page cannot
  silently choose or override the user's print destination.
  Put this guidance in concise helper text immediately under the PDF button in its
  existing controls, not a new sidebar section, warning card or modal.
- Reader-facing filenames omit `obs-html` and do not assume the content is a report;
  use the authored document identity/type or an HTML/document fallback.
- Links to exported chapters and headings become PDF-internal anchors. Other note links point
  to the companion HTML filename and its original fragment. Keep that HTML beside the PDF;
  PDF link handling is ultimately viewer-dependent. Unlisted notes are not appended.
  Table cells and repeated continuation fragments retain those same real link targets.

  The physical PDF must contain clickable link annotations, not only styled labels or
  browser-only click handlers; verify both internal and companion-note destinations.
  Embedded-file downloads link to their owning companion note, where the original
  download remains available; transient blob/data URLs are not portable PDF destinations.
- The subtitle is centered with vertically aligned images and symbols. The maintained
  manifest's metadata query explicitly excludes cover fields; editing that query changes
  the selection just like any other Base.

### Neutral artifact presentation

The generic style is a plain, content-first artifact: system serif body text, black headings,
neutral grays, simple A4 margins and no branded hierarchy. Interactive application chrome remains
separate from artifact presentation.

- Cover fields should present available product name/version, document title/type/identifier,
  authors/reviewers/approvers, organization, legal entity and confidentiality.

  These are authored facts from the manifest, not borrowed example values.

  Omit absent fields;
  renderer support does not confer approval, compliance or a controlled-document status.

  Keep absent values omitted. Generic covers use simple flowing artifact content.

  Revision/date belong only to History, not the cover; metadata belongs on its own page.

  Organization is authored only in manifest metadata and is not repeated in the metadata table.
- Retain the subject-image row and takeaway/derived-overview improvements. Do not import
  yellow placeholders, blue template instructions, approval/export dashboards, glossary-loading
  notices or the surrounding host application's interface into the artifact.
- Use a shared page frame with reserved running-header/footer areas, document/chapter
  identification and Page X of Y, including the cover in the count. Contents page numbers
  derive from final PDF layout. Hierarchical section labels remain deferred; preserve authored titles.

  Table continuation sheets and current pagination state contribute to the real artifact
  layout and page offsets. If Results ends on page 9, the next chapter starts on page 10;
  navigating or repaginating a table must not reset or overlap those page numbers.
  Screen page frames, Contents and PDF use the same final-layout numbering owner.
- No text appears twice in one view. The title page shows the document type once, under the
  title; it has no running header that repeats it. A chapter's running header never repeats its
  own visible heading.
- History belongs before Contents when supplied. Its manifest ownership and working-version
  convention are defined in [[input-model]], never inferred from Git or generation time.
- Boxes use a soft semantic fill, matching outline and an optional centered bold heading inside
  the box.

  Important callouts are untitled highlight boxes, including the abstract's first
  takeaway.

  They share this treatment, without floating
  legends or italic labels.

  Tables share a neutral shaded header and fine cell grid in ordinary
  HTML, static Markdown, document view and PDF.

  Preserve all generic table interactions.
- With an explicitly embedded reproduction archive, the cover uses a content card without a
  title, containing one inline sentence and a Download source ZIP link, never an attachment button.

  Settings + exports uses two equal-width columns: Show as pages
  above Download source ZIP, Export to PDF above Attach source ZIP to PDF.

  Do not add a source-file browser or configuration editor to Settings or the reader.
  Source/configuration authoring starts by downloading the archive and using external
  tools.

  Evidence snapshot links may download their explicitly selected original from the
  same compressed owner; supported evidence replacement happens in the HTML and
  must not require downloading sources or installing tools.
  Initialization is progressive. Show the artifact shell and available static content
  without waiting for every chapter, table, figure, search index or derived summary.

  Compression still has one asynchronous canonical-model decode boundary; controls
  that depend on that model must remain honestly unavailable until it is ready.
  Never show a blank successful artifact or enable actions against a partial model.
  The same readiness gate applies on reviewed-copy reopening; saved control DOM
  does not establish that the current model is ready.

  The opening/loading message is horizontally centered. Its document identity
  reuses the first page's running-header content and formatting owner, not a
  separate product-name/title fallback or separately maintained loading label.

  Stack the nonempty left/right header contents as centered lines rather than
  distributing them to opposite edges; omit empty lines. Header changes must
  automatically carry through to opening presentation. Keep the loading status
  accessible and available before expensive initialization.

  While derived text such as the abstract or numeric summary is being calculated,
  show a neutral, accessible pending placeholder in its normal location, not an
  invented zero or stale value presented as current. Replace it from its existing
  authoritative query/calculation owner when ready, preserving the latest selection.

  Keep the shell responsive between substantial initialization steps; scheduling
  all expensive work before the browser can paint is not progressive loading.
  Startup runs in slices: a step yields to the browser once its slice has run as long
  as a browser long task (50 ms), and only then waits until the browser has painted a
  frame; steps within a slice do not wait for frames.

  The first chapter is painted within 1 s of opening the
  spec artifact on the test machine, on the frame's own clock: the artifact marks
  `obs-startup first chapter painted` and `obs-startup ready` (User Timing), and
  `test_startup_browser.py` holds that budget from those marks and names the slowest
  startup steps when it is missed.

  Where load on the machine slows the page itself, the
  test scales the budget by a load factor it measures in the same run; its docstring owns
  how.
  Initialize nonvisible/unused views when needed and reuse existing caches rather
  than moving an unchanged whole-artifact calculation onto the first interaction.

  Static chapter projections may be reused within the current canonical revision,
  filter application and table/view presentation. Subject-content availability is
  revision-bound; changing canonical values invalidates it. Row expansion and local
  pagination must not launch unrelated whole-artifact page-measurement passes.

  Pending content must settle visibly or surface an explicit error; it cannot remain
  an indefinite loading placeholder after failure. Export/print and reviewed saving
  wait for their required canonical/derived readiness and must not persist pending
  placeholders or partial records.

  Repeated PDF requests while readiness or print preparation is pending share one
  export, rather than queueing multiple dialogs.
  Deferred startup does not omit source material,
  weaken offline reopening or create another data owner.

  Downloads use the
  browser's normal save destination (the user may choose a folder).

  Attachment asks for a saved
  PDF and downloads a new one without network processing, preserving the original.

  Do not imply
  the browser print dialog attaches sources automatically.

  Help belongs in hover; failures are
  visible.

  The PDF links back to the companion HTML.
- Code fences use a smaller configured paper font, preserving 80-column lines without soft
  wrapping. Screen overflow scrolls horizontally; PDF scales longer lines to its content width.
- Inline code spans that do not fit their line, for example paths in a narrow table column,
  break at spaces or after a run of the separators `/ \ . _ : -`; `content.py:1444` may
  break only before `py` or `1444`, never inside an identifier between separators.

  Only a single segment wider than the whole line may break elsewhere, so text never overflows its
  column; table sizing owns whether a column is that narrow. The browser's own Unicode
  break opportunities at other punctuation, such as between `!` and `[`, remain. Break
  opportunities add no characters to
  copied or searched text, and search highlights still mark a match that spans them.
- Paragraph-length diagnostics belong to the converter, never the generated HTML or PDF.

  Converter diagnostics include source location when prose exceeds its configured limit.
  CLI invocation is owned by [[cli]]; thresholds and estimation width by [[configuration]].

  Estimate wrapping at the configured prose
  width, not source-newline count; actual browser wrapping depends on fonts and viewport.

  Exclude code, tables and generated projections.

  Fix flagged authored paragraphs by splitting
  at meaningful sentence boundaries, without discarding content.

  An open-point paragraph contains its question and the decision impact, actions, known
  answers and qualifications needed to understand its current state. Keep it concise where
  possible, but do not strand these parts outside the mark or omit them from the generated
  overview merely to meet a paragraph-length preference.

## Dock menu

- Activating the menu button opens a compact menu derived from the discovered bar modules.
- Each row contains the bar icon and name followed by left, right, top, and bottom direction
  buttons in that order.
- Activating a direction docks that bar to the corresponding viewport edge without closing
  the menu. The menu remains open across docking actions and outside clicks until its own
  button toggles it closed; Escape remains the keyboard dismissal.
- Activating the currently selected direction again closes that bar.
- At most one instance of each bar exists; changing direction moves it rather than copying
  it.
- Every menu-opened bar has an accessible close-X button at the far right of its
  title row, aligned with the title and after any bar-owned header actions. The
  shared dock shell supplies it for all discovered bars, not a per-bar list.

  Activation uses the existing bar-close lifecycle, including Filter's clearing
  behavior; it does not discard comments or other state that closing normally
  preserves. Keyboard activation works and focus returns to a usable menu control.
- Every occupied dock region has an inward-edge resize handle. Pointer dragging resizes the
  region, keyboard arrows resize a focused handle, and double-click restores its default.
- Left and right docks resize horizontally; top and bottom docks resize vertically.
- Resizing is constrained so a usable portion of the reading shell remains visible.
- Adjacent bars sharing one dock region have separators that resize their relative shares.
  Side-dock separators move vertically, top/bottom separators move horizontally, keyboard
  arrows resize a focused separator. Dragging or keyboard-adjusting one separator changes
  only its two neighboring bars; all other separators stay at their existing positions.
- Bars initially share the available dock span equally, including regions with three or
  more bars. Automatically placed separators may redistribute when another bar opens.

  A separator explicitly moved by the user becomes an anchored boundary: opening another
  bar must not move it. Redistribute only within the affected unanchored span between
  anchored boundaries and the dock edges, preserving the existing bar ordering.
- Double-clicking a separator releases that separator's manual anchor and restores automatic
  sharing within its unanchored span; it does not reset other manually positioned separators.

  Existing minimum sizes and viewport bounds still apply. Clamp an anchored position only
  when those constraints require it, not merely because the number of bars changed.
  Reuse the shared dock splitter lifecycle for every edge rather than bar-specific sizing.
- The table of contents mirrors the manifest hierarchy and navigates immediately.
- Any manifest chapter with children uses the same collapsible table-of-contents interaction. A
  chapter named Appendix has no special status; when authored last in the manifest, normal depth-first
  navigation makes it the final chapter group.
- Previous/next chapter edge controls leave the reader's native vertical scrollbar gutter
  unobstructed so its track and thumb remain directly clickable.
- Table-of-contents items with children have icon-only expand/collapse controls.
- The table of contents provides icon-only `Collapse all` and `Expand all` controls.
  These share its heading row rather than reserving another row. Bar-owned header actions
  use the generic dock-header slot.
- Comments is an auto-discovered bar available through the same dock menu and directions as
  every other bar. No comment surface is open initially.
- The Comments bar has two sections separated by a rule. The first contains the locally
  remembered reviewer name plus Download HTML and Load reviewed HTML commands. Load
  accepts one or more returned HTML artifacts, validates their comment islands, merges unique
  comments and per-reviewer decisions, and assigns collision-free local comment identifiers.

  At ordinary bar widths, Save and Load share a compact row in the left half;
  `Copy comments to clipboard` occupies the right half alongside Save. Wrap
  accessibly on narrow bars instead of imposing a horizontal scrollbar.

  Copy exports the current complete comment conversation, not just visible/filter
  matches, as readable text suitable for pasting into a discussion. Each root
  comment includes document identity, chapter/section, marked quote or whole-item
  context, stable paragraph/item identity or table/row/subject-column identity,
  author and replies in context.

  Include the current artifact page when reliably resolved; a page is a supplemental locator,
  never the sole anchor. Inactive,
  filtered or unresolved targets retain their canonical anchors and an explicit
  unavailable-page/location indication rather than an invented page number.
  Copying is a local user-triggered clipboard action, not saving or marking the
  review clean.

  Report success only after the clipboard write succeeds; handle empty comments and
  denied/unavailable clipboard access explicitly using the
  existing bar diagnostics. Do not rebuild or navigate the whole artifact to copy.
  Compact visible labels are `Save` and `Load`; retain their full command names as
  accessible labels and tooltips.

  Batch comments retain their scope and affected chapter/item identities. Canonical text
  positions locate selections across blocks.
  A page is reliable only when the stored quote matches a currently visible anchor;
  expanded-detail comments use the marked detail's page, not the parent row's page.
  Copy leaves comments, review decisions, filters and reviewed-copy dirty state unchanged.
- Activating a comment target waits for the destination's lazy chapter content
  before revealing its table row, subject column, details and marked text.
- Opening Comments activates review mode.

  In Pages, its gutter sits immediately beside the paper edge, not the reader viewport edge.
  Recompute its alignment when the reader, paper or docked bars change size.
  Review controls remain visible and operable on every continuation sheet, not just the first
  sheet of a chapter; page headers and footers are not review items.

  Every derived paragraph, list item, table data row,
  standalone code block, and figure review item gains a left gutter with
  Accept, Reject, and Comment controls. A figure is one item: what it draws inside, such as a
  decision figure's rows, is none. Cards stand one below the other in the prose column, so no
  two items share a gutter line.

  Waiting items use teal, accepted items green, and
  rejected items red.

  Activating an item state again returns it to waiting.

  Normal clicks retain this item-only behavior. Shift-click on Accept or Reject applies
  that decision to still-waiting items in the current heading section, including its
  subordinate headings until the next heading of equal or higher level. Before any
  section heading, the scope is the chapter's introductory content; a chapter heading
  scopes the complete chapter.

  Ctrl+Shift-click applies to still-waiting items throughout the artifact, including
  inactive chapters. Scope follows canonical structure, not
  screen pages or current visibility. Waiting means undecided for the named reviewer;
  preserve that reviewer's existing decisions and all other reviewers' decisions.
  Repeating a batch action never toggles completed items back to waiting.

  A batch rejection with affected items opens one comment editor labelled with its
  actual scope, such as `[Full section]`, `[Full chapter]`, or `[Full document]`, rather
  than an editor per item. Preserve its affected-item association across download,
  reopen and merged reviews. An empty batch changes nothing and opens no empty comment.

  Counts, pressed button states, semantic colors and query-visible review state must
  update together after single or batch decisions; no successful-looking stale summary.
  Controls explain modifier actions through accessible help without extra toolbar clutter.

  Persistent text beneath the review counts also states that normal clicks affect one item,
  Shift-click applies to still-waiting items in the current section (or the introductory
  content/whole chapter when structurally applicable), and Ctrl+Shift-click applies to
  still-waiting items throughout the artifact.

  An unnamed reviewer uses the same fallback identity for decisions, controls and
  derived counts. Artifact review covers canonical artifact chapters, not unrelated
  vault notes merely available to table queries. Section boundaries derive from the
  unfiltered chapter structure before pagination or disclosure.

  Decisions belong
  to the named reviewer, so merged copies preserve independent reviewer state.

  The displayed
  gutter stripe uses the aggregate precedence rejected, then accepted, then waiting: a
  rejection wins, otherwise any acceptance overrides undecided reviewers.

  Rejecting an item
  immediately creates and focuses a whole-item comment card so the
  reviewer can explain the rejection.

  Paragraphs, list items at every nesting depth, code
  blocks, and figures share
  one chapter-wide state rail to the left of list markers.

  Tables share that left-side
  arrangement with one control set per data row, never per cell.

  Sorting, paging, filtering,
  and expanding a row retain its stable review identity and restore its controls.

  Expanded details inherit their owning row's checkmark, with no independent paragraph checks.

  Normal text-selection comments are supported inside details; their anchors record the table,
  row, and detail-local text offsets so collapse/re-expansion does not invalidate them.
- The Comment control creates a blank whole-item comment card.

  Its badge counts every root
  comment and nested reply intersecting that item across merged reviews.

  Adding a comment does
  not change any review decision.

  A compact summary in
  Comments shows the named reviewer's full-artifact accepted, rejected, and waiting review-item
  counts.

  Expanding or collapsing a table detail updates the affected table and active-chapter review
  controls without rebuilding static views for the full artifact. Cached review-item identities
  are invalidated when their canonical chapter content, contributing canonical table rows or
  committed table definitions change.

  Reviewer decisions and view-local filtering, sorting, paging and detail expansion do not
  invalidate those identities; review summaries and fields
  still derive their current states from the review island. Reuse the canonical and table
  owners' change boundaries rather than repeatedly serializing the whole artifact to detect edits.

  Typical native-browser detail toggles target less than 50 ms.

  Activating a summary state opens Filter and applies an exact `review:` clause for that
  reviewer across the whole artifact: matching chapters remain in navigation and only matching
  review items remain visible in the active chapter.

  The full-artifact totals do not change as
  the reader navigates chapters.
- The first section's save controls have persistent, discoverable guidance explaining that
  Save reviewed copy preserves review annotations, decisions, and canonical editable-property
  changes, and that unsaved changes risk loss when leaving.

  It reflects whether changes are currently unsaved. The browser's native unload confirmation
  is requested only while dirty;
  no custom browser warning text is required.
- The notice center is the one owner of every notice the artifact raises; no notice draws
  its own banner. Each notice is an entry with a severity (error, warning or information),
  a short title and details.

  The top of the page shows at most three icons, in that order,
  each only while it has entries and with a count pill, however many notices are raised.
  Clicking an icon opens its list; clicking an entry expands its details in place; a
  second click or Escape closes. The icons sit in the [[#Reading shell|top band]].

  Changed HTML and the applied filter are information, each limited capability is a
  warning, as is each Document node type the artifact shows only as plain text
  ([[architecture]]), and errors are reserved for real failures.

  Notices are transient UI, not printed
  content or a dirty warning embedded into a newly reopened saved HTML. The entries, icons
  and layout are owned by obs-html's `notices.js`, not repeated here.

  The changed-HTML information entry is present whenever the artifact holds a
  [[#What counts as a change|change]] since the last confirmed saved snapshot. It says that this HTML has changed, and its
  details hold a button to download the changed HTML.

  It uses the existing save/serialization owner, not a second download implementation.
  Failed or cancelled saves do not clear it;
  retain the existing distinction between confirmed file writes and unconfirmed downloads.
  The native unload warning uses that same unsaved-artifact state.

  The applied-filter information entry's details hold the filter and its clear action.
  Clearing a filter does not remove the changed-HTML entry.

  The artifact includes a host-dependent feature, with its code, controls and canary, only
  when its Document uses it or the artifact always offers it. A feature that is not included
  raises nothing.

  A canary decides or stays silent. A canary that observes a refusal raises one warning
  entry: the feature, why the host refuses it, what was observed and the remedy, for example
  "Open the HTML file directly in a browser to print".

  A canary that cannot decide raises nothing at load. The feature is tried on use, and an
  observed failure then shows the reason and remedy inline and raises the warning. Where a
  failure cannot be observed even on use, there is no notice; the control's help text names
  the remedy.

  No feature uses a browser dialog; its messages are inline. Print to PDF never stays in
  its preparing state. The registry and its entries are owned by obs-html's
  `features.py`; the list of abilities is not repeated here. A figure kind that needs a host
  ability or a library declares it there by key, never through a second inclusion mechanism.

  Generic reader-facing controls and messages call the artifact HTML, not a report.
  Where its semantic name is useful, derive it from the authored document type;
  never hardcode an application's document type into the framework. Internal API names and genuine
  authored uses of "report" are not renamed by this presentation rule.
- The second section contains a square Add comment icon button, the query input, and the
  comment list, with no persistent comment-operation status line.

  Add comment is disabled until text
  is selected in the active chapter; activating it creates an empty editable card anchored to
  that selection.

  There is no chapter-level comment command or separate comment composer.

  Text anchors store the chapter slug, quote context, and DOM text positions.

  Positions are
  canonical within the reviewed copy, including selections that cross block or heading
  boundaries; the quote is display/context data and does not gate range reconstruction.

  Anchors are not re-anchored across regenerated artifacts.

  Comment queries use the shared
  language and match only comment records, including `status`, `author`, `chapter`, `quote`,
  and comment text fields.
- The comment count is the only empty-state message. An empty list does not repeat that state
  with text such as `No comments yet` or `No comments match`.
- Every comment and nested reply renders as the same compact key/value card, with labels for
  values such as author, status, and text rather than relying on position.

  Text is directly
  editable and persists without a separate Edit command.

  Every card has Reply,
  Resolve/Reopen, and Delete commands.

  Reply immediately creates a blank child card and
  focuses its editable text value; there is no intermediate reply editor or submit command.

  Replies are visibly indented beneath their parent, may themselves receive replies, and remain
  visible whenever their parent is shown.

  Comment threads have no collapse control.
- Navigating to a comment uses the CSS Custom Highlight API when available and otherwise
  degrades to chapter navigation without mutating rendered content.

  Hovering an annotated
  source range changes its highlight and pointer cursor so its clickability is visible.

  Activating that exact range opens the Comments bar when needed, clears a comment filter that
  would hide the thread, and scrolls its corresponding root card into view.
- Saving uses the File System Access API when available and downloads a commented copy
  otherwise.
- Search and Filter use the same query runtime. All chapter frontmatter fields participate in
  bare and field-specific queries. That runtime owns the artifact's filter language.

  Terms separated by whitespace must all match. `AND`, `OR` and `NOT`, in any letter case,
  combine them, `NOT` binding tightest and `OR` loosest; parentheses group them.

  A bare term searches a chapter's whole text and `field: value` one field; a leading `-`
  negates either (`-draft`, `-status: open`). Field names and quoting follow
  [[input-model#Markdown body and frontmatter]].

  A value is a word, a quoted string or a `/regular expression/`. A word matches as a
  substring, and `*` in it matches any run of characters.

  An unclosed quote, expression or parenthesis, or a field without a value, reads as still
  being typed rather than as an error.
- A field clause selects by the one rule set (obs's bases capability, Comparisons: [[obs-specification|obs's specification]]): it resolves
  a note property and tests its text as obs's queries capability (Conditions) does.

  Words, wildcards and regular expressions ignore case; a `c` after a regular expression
  (`status: /^Open$/c`) matches case, as a condition's `matchCase` does. Ignoring case, a
  word or wildcard matches the text's case folding (obs's bases capability, Comparisons), and
  a regular expression matches the text or its folding, so `street: /^strasse$/` finds
  `Straße`.

  A name that is no note property falls back to the reader's own fields (title, text, slug,
  depth, marks, query aliases); a `note.` prefix asks for the property alone, and on a note's
  table row for that note's property.

  The runtime's selection resolver (obs's quality note, Knowledge ownership) is
  `obsQuery.propertyTexts` in `query.js`: a card's count and distinct count, a Sankey node's
  `unique`, and every drill-down's `note.` clause read a note's property through it and its
  property lookup, never through their own.
- Every query-language help button is square and exactly the same height as its adjacent query
  input.
- Filter narrows the chapter set represented by the table of contents and previous/next
  navigation. The active chapter remains visible until navigation selects a retained chapter.
- Filter is active only while its bar is open. Closing Filter clears its expression and restores
  all chapters and review items.
- Every applied global predicate, whether typed, selected from a facet or produced by a
  figure click, displays a prominent orange semantic-warning badge reading `Filtered view`
  centered in the header at the floating menu's height. Its accessible X action clears
  the applied global query and actual input through the same Filter owner.

  The badge disappears only when the predicate is cleared; invalid drafts do not hide an
  applied
  filter. It must not overlap navigation/menu controls or become a second filter store.
  Show retained/total chapter and paragraph counts in that warning, derived from the
  same canonical filter/navigation/semantic-block owners rather than current DOM
  materialization or page clones.

  Counts refresh after typed or figure-generated queries and after clearing. A
  record-scoped artifact may additionally show its
  matching/total record population; unchanged chapter counts must not conceal that
  a record filter is active. Table-local query controls remain table-local.

  Orange is the shared filtering accent throughout artifacts. A table's applied
  interactive filter is additionally visible through the scoped outline and
  margin badge specified in [[generic-tables]]; its clear action must not clear
  the global filter.

  The same applied-filter warning/counts/clear action remain visible above an
  expanded figure, including when a native dialog/top layer is used. Filtering
  an expanded figure updates its live data without making the figure disappear,
  leaving an empty overlay, or requiring Escape to recover the reader.
- Programmatic figure selection opens/updates the actual Filter expression. A node selects
  its represented records; a strand selects the exact trace rather than unrelated paths
  sharing an item. Every selection is an ordinary valid, editable query, not an invisible
  record-ID set.

  A selection writes its conditions as `note.` clauses with the same exact pattern the count
  compares with, so it retains exactly the rows its count counted, rows differing only in
  case included.
- Reviewed copies restore the last applied global query, its Filter input, and an open Filter
  bar. Cleared or closed filters reopen unfiltered with the bar closed; invalid drafts reopen
  with the preceding valid query, not the draft. A stored query that no longer compiles stays
  visible with its error rather than disappearing.

  Fresh artifacts remain unfiltered. Restoring a query does not restore session appearance:
  every opening still starts Light with Pages. Filtering is never a
  [[#What counts as a change|change]]; persistence belongs to [[input-model]].

  On reopen, rebuild Filter presets and attribute controls once from their canonical data;
  do not append them to copied rendered controls.
  Reviewed table column visibility/order follows the bounded
  table-local presentation contract in [[generic-tables]], independently of the global query.
- Opening Filter immediately shows its preset and attribute pill panel. Presets come from the
  vault's project configuration; clicking one replaces the text expression and applies it
  through the shared query runtime.

  A domain artifact supplies its own meaningful presets and configured-level controls,
  rather than inheriting irrelevant chapter/frontmatter examples. Preserve the
  source application's level-switch semantics in its record-driven views; do not
  repurpose them as authored-chapter exclusion.
- Filter attributes are derived from structured chapter fields: title, slug, depth, semantic
  fields, and every flattened frontmatter field.

  An artifact may declare a curated record-query scope and field catalog using canonical
  fields/references and display aliases. Such a catalog exposes its subject's meaningful
  fields, not storage paths, array indexes, relation bookkeeping or private intermediate
  notes.

  It does not duplicate records or move artifact-owned classification into the query
  runtime. Default artifacts retain their existing field discovery. Record-scoped queries
  preserve authored TOC/navigation/PDF chapters while narrowing record-driven views.

  Full prose remains queryable as text but is
  not enumerated as a facet value.

  A field is offered as a facet only when it has more than one
  distinct atomic value and its distinct-value count is no greater than the configured fraction
  of records where that field is populated.

  No field is special-cased.
  Curated catalogs follow this same gate; curation does not make constant or
  near-unique values discriminative. Apply the same rule to global and table-local
  suggestion surfaces while retaining valid typed queries over non-facet fields.
- Attribute pills use their content width and wrap together like filter keys rather
  than occupying one full row each.

  Each pill reports its distinct-value count and opens a
  bounded, alphabetically sorted value menu in the browser's top layer so values may cross dock
  borders without being clipped.

  Activating an open attribute pill again closes its menu.

  Selecting values produces exact field clauses that match case, because a pill counts one
  spelling; values selected from the same field are joined with `OR`.

  Facet selections remain visible as
  removable `field: value` pills after their value menu closes.

  This artifact does not provide
  grouping or sorting directives.
- Search runs as the input changes without a separate submit button. It reads the canonical
  artifact store and displays linked result excerpts inside the edge where its bar is docked.
- **Hard rule: search and filters operate on the complete content, independent of rendering,
  pagination and expansion state.**

  Anything a reader could look at is findable and filterable: chapter prose, callouts, captions
  and figure text; every table row on every table page,
  including Home tables (Evidence and Metadata), rows inside collapsed groups and
  each cell's leading lines; and the content of row detail panels and other collapsed
  sections that are not expanded yet.

  The search index is derived from the document model (the same column renderers applied to
  detached cells, plus referenced and owner note
  content for detail panels), never from the currently materialized DOM. A table hit is its
  own result, listed in document order after its chapter's prose hit.
- The global Filter, table-local filters and domain view switches (such as a level switch)
  apply to the full row population before pagination: page counts and `n of m items`
  reflect the filtered set and every retained row stays reachable through the pager.

  A table-local bare-text clause matches the same reader-visible cell and detail text as
  Search. Search hits exclude rows removed by the applied global Filter.
- Search keyboard shortcuts (listed in the Search query help and `aria-keyshortcuts`):
  Ctrl+F (Cmd+F) opens Search, focuses its input and selects the query text; pressed while
  Search is open and its input focused, it closes Search. The browser's own find therefore
  only remains reachable when the artifact Search is unavailable.

  F3 and Shift+F3 step to the next and previous result in document order, wrapping around;
  each step reveals the hit
  exactly like activating it (table page, expanded sections, scroll and highlight) and the
  status reads `n of m results.`. With no active query, F3 opens Search. Esc closes Search
  when focus is in Search or in the artifact content (not inside another control or bar).
- A half-typed or invalid query reports its error and preserves the last valid Search or Filter
  state.
- Search and Filter expose their shared language summary from a compact help control on hover
  and keyboard focus rather than occupying persistent bar space.
- Activating a Search result navigates to its chapter and highlights positive matching text in
  the rendered content.

  A table hit additionally switches the table to the page holding the row, expands its
  collapsed ancestors, groups and the detail panel holding the match,
  clears a table-local filter that hides it, then scrolls to and highlights the match; this
  works in Pages and continuous layout. Later chapter navigation clears those highlights.
- The filter bar uses a recognizable rendered funnel shape rather than a font glyph; search is
  a separate discovered bar with a search icon.
- On narrow screens, docked bars overlay the reading shell and use constrained dimensions
  so chapter controls and content remain reachable.

## What counts as a change

This section owns which actions change the artifact; every other note points here. The
changed-HTML notice entry and the native unload warning appear only while the artifact holds a
change since it was opened or last saved.

- A content edit is a change: an evidence replacement, a description or explanation edit, or a
  committed property edit. Only content edits move the document's generation `timestamp`.
- A review edit is a change: a comment, a reply or a review decision. It is not a content
  edit and leaves the `timestamp` unchanged.
- Reader state is never a change: filters, view selections, table columns,
  sorting, grouping, pagination, open or closed panels and bars, navigation, scrolling and
  appearance. It raises neither the changed-HTML entry nor the unload warning, also where a
  saved copy persists it; the applied filter has its own information entry.
- A resized column width and a choice in a figure's options menu are session-only view state:
  never saved, never a change and not reader state.
- Returning every change to its state when opened or last saved leaves no change.

## Content sections

- Dedicated prose cards use a shared semantic fill and outline with an optional centered title
  inside the card.

  The border extends beyond the prose with a small
  internal clearance, balanced by negative outer margins so prose stays aligned with surrounding
  content.

  Only vertical margins change the surrounding text flow.

  Cards share one stylesheet primitive; semantic tags retain their separate right-hand icon rail.
- Tag borders are optional presentation flags configured through `artifact.borderedTags` in the
  configuration owner.

  No tag kind draws a box by default.

  If any tag on a paragraph opts in,
  one shared card encloses that paragraph and its icon rail; its centered title names the opted-in
  kinds.

  Multiple tags never cause nested or repeated borders.

  The source syntax is unchanged.

  Authors may place ordinary Markdown links or wikilinks in that content.
- A paragraph marked with [[input-model#Mark tags]] uses an 80/20 text-and-marks layout. Authored prose occupies at most 80% of the
  row. A separated rail to its right shows every mark icon attached to the paragraph. Hovering an icon
  exposes its kind and human-readable label, and the same description is available to assistive
  technology. The source tags are not displayed in prose.
- The mark separator spans the full paragraph height. Every mark icon is a keyboard-accessible link
  to its canonical row in a source-authored tag table; navigation discovers the table by its query,
  never by a hardcoded chapter name. Glossary links use italic text without underlining.
- The generated Home follows the document contract in [[input-model]], using ordinary
  generic tables rather than a separate summary renderer.
- The generated artifact cover precedes the manifest-authored abstract. Card groups remain
  in authored abstract order; metric compaction does not promote them into or overlap the
  cover, and cards have no independent placement option.
- The dogfood abstract authors its Obsidian-to-HTML5 logo strip as ordinary Markdown with hosted
  logo images. It is vault content, not generator branding injected into other artifacts; loading
  these images requires network access.
- Markdown paragraphs consisting of multiple images and symbolic separators form a centered media
  strip. Images and separators align vertically at their centers; normal prose/image paragraphs
  retain ordinary text flow.
- Base fences use the reusable data-table runtime specified in [[generic-tables]].
- Rendered prose headings below the chapter title have icon-only collapse controls.
- Collapsing a heading hides its content through the next heading of the same or higher
  level while preserving nested section state.
- Section controls default to expanded and do not affect the Markdown source.

## Accessibility

An applied nonempty global filter shows a centered semantic-warning `Filtered view`
token at the floating-menu header height, with an accessible `Clear filter` X action.

Its retained/total authored chapter and paragraph counts derive from canonical chapter
content, never materialized reader pages or print clones. Record scope supplements
these with retained/total population counts. Invalid drafts retain the last applied
expression, token and counts; reviewed copies reopen that applied expression.

Clearing through typing, the token, or closing Filter clears the same owner. The token
must
remain clear of the menu and chapter controls on desktop and narrow viewports.
An active chapter removed by chapter filtering returns to Home, clearing stale chapter
anchors. Home remains in the retained navigation sequence even with no matches.

- Every icon-only control has an accessible name and tooltip.
  Its appearance comes from [[semantic-assets]] through the authoring contract in
  [[input-model#Named icon resources]], not a local glyph, drawing or color literal.

  A catalog override changes every occurrence consistently, including disabled,
  expanded/collapsed, late-rendered, saved and print projections, without changing
  the control's action. Active/inactive appearances inherit the parent's state
  defaults, so unrelated actions can share an inactive icon while retaining their
  individual active icons. The existing action owner supplies state.

  The stylesheet owns icon sizing, alignment, semantic-color application, focus
  and disabled treatment; actual palette values come from the shared asset index.
  Keep the current compact
  footprints, recognizable funnel and navigation/disclosure states while moving
  their definitions; do not hide missing resources or grow action columns.
- All controls are keyboard reachable with visible focus styling.
- The menu reports expanded state, docked bars are landmarks, and the active table-of-
  contents item is identified with `aria-current`.
- Reduced-motion preferences disable nonessential transitions.

See [[input-model]] and [[architecture]].
