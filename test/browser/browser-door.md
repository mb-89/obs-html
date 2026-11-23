# The browser door

Reader: whoever writes, moves or reviews a browser test of this adapter, or works one of the
packages below.

The browser is an outside thing, like the network or GitHub, and gets one door with a fake held to
its contract, as the [library doors](../../spec/architecture.md#library-doors) already have (obs's
`spec/design_input/quality.md`, Testing boundaries). One real Chromium serves only the hot tests:
they check what obs-html expects of the browser and record the browser's answers. Every other page
test runs against a fake browser, happy-dom in Node, which answers what it cannot compute from
those recordings.

The person's requirement, word for word: "We start one browser instance, run hot tests against
them, and if the browser behaves as expected, then everything else can run against mocks."

This note is the design. [test_browser_door.py](../structure/test_browser_door.py) holds its
classification to the tests as they are: every browser test file has one row, with its class, its
package and its reason. Once its package has landed, a row's package reads ``moved by `<package>` ``
(``added by `<package>` `` for a file written on the fake browser), and the file's tests take
`fake_page` and no real browser.

## What a browser test asks today

Counted on 22 Nov 2026 at main `547285c`, by pytest's collection: 52 test files drive a real
Chromium, with 487 collected tests. 51 take a page from `test/conftest.py`'s pools (or
`pdf_browser`), and one, the chapter sweep, starts its own sweep child. The work issue counted 79
files with a wider text search. The other matches of that search are not browser tests: the
helpers they import (`browser/viewer.py`, `chapter_sweep.py`, `serving.py`), the measurement tools
under `test/measure/`, and the tests of the DOM tier, which already run in Node over linkedom.

The runtime asks the browser for layout far more often than the tests do. In `src/obs_html`'s
scripts: 49 calls of `getBoundingClientRect`, 7 of `getClientRects`, 37 reads of `clientWidth` and
`clientHeight`, 14 of `scrollWidth` and `scrollHeight`, 32 of `getComputedStyle`, 12 uses of
`ResizeObserver`, 23 of `requestAnimationFrame` and one canvas text measurement (`table.js`). A
fake that answers 0 to all of them would send the runtime down other branches than the real
browser does. So the recordings serve the runtime, not only the tests.

## Classification

`logic` files test obs-html's own work: the DOM it builds, its state, its events and the payloads
it hands over. They move to the fake browser. `hot` files test the browser's own work: layout,
painted colour, scrolling, printing, what a sandbox enforces, real paint timing and the real
libraries. They stay in the one real Chromium and record. A file's class is where most of its
tests go. The reason names each test that goes the other way.

| File | Class | Package | Reason |
|---|---|---|---|
| `test_answers_browser.py` | logic | `more-logic-to-fake-browser` | The answers' sink and the served page's post are payload and routing logic; no test measures the page. |
| `test_appearance_browser.py` | hot | `hot-tests-record` | Each appearance's painted colours, opaque and readable, in each system scheme and in print: computed colour is the browser's cascade. Its recordings are the colours the fake's cascade is checked against. |
| `test_artifact_browser.py` | hot | `hot-tests-record` | The print book, a centred title page, a bar that follows the pointer and gutters clear of the arrow are layout. Except `test_figures_draw_their_plot_and_sankey` and `test_base_tables_evaluate_document_records_and_marks_show_their_icon`, which move to the fake. |
| `test_attachment_editions.py` | logic | `viewer-logic-to-fake-browser` | The editions' download offers and their bytes. The undecided-downloads help needs the viewer frame's recorded refusals. |
| `test_attachment_replacement_browser.py` | logic | `more-logic-to-fake-browser` | The trusted extension's one transaction over records; no layout. |
| `test_bars.py` | logic | `layout-logic-to-fake-browser` | Bar discovery and the dock's order are DOM. Except `test_native_splitter_anchors_and_neighbor_only_geometry`, which measures the splitter's geometry and stays hot. |
| `test_bless_browser.py` | logic | `layout-logic-to-fake-browser` | Verdicts, drafts in session storage, Send's payload and the swipe walk are runtime state; the swipe's coordinates come from recorded boxes. Except the band and pill fits: `test_the_pill_and_keys_show_only_on_asking_chapters_and_the_page_fits_a_phone`, `test_the_band_holds_every_key_in_one_row_at_phone_width_with_the_notices_shown`, `test_the_pill_keeps_its_text_while_the_band_has_room`, `test_the_band_of_a_nested_bless_chapter_fits_at_360_px`, `test_the_pill_names_the_pick_by_its_short_name_where_the_band_has_room`, `test_the_deck_opens_in_screens_on_a_phone_that_fit_and_walk_by_swipe_and_keys` and `test_printing_from_screens_prints_each_screen_from_a_new_page_without_a_page_frame`, which stay hot. |
| `test_browser_door.py` | logic | added by `browser-door-recorder` | The conformance check: the fake's computed answers held to the recordings, and the fake answering a recorded box, text width and refusal. |
| `test_callouts_embeds_attachments.py` | hot | `hot-tests-record` | Two of its three browser tests are painted tones and a bottom line that leads its page in every layout. Except `test_a_parent_s_preview_begins_with_its_bottom_line_and_holds_no_child_s_lead`, which moves to the fake. |
| `test_cards_counts_quantities_browser.py` | logic | moved by `fake-browser-door` | Counts and drill-downs over the selection chain: pure runtime logic. |
| `test_chapter_sweep_browser.py` | hot | `hot-tests-record` | Every chapter opens and scrolls at real viewports with and without reduced motion, and a locked page fails its sweep: the browser's scrolling and main thread. |
| `test_columns_browser.py` | hot | `hot-tests-record` | Side by side at the weights, stacked when narrow and printed side by side are layout. Except `test_a_comment_on_a_block_in_the_right_column_anchors_to_it_after_a_reload` and `test_search_finds_a_columns_text_and_the_filter_reads_its_marked_paragraph`, which move to the fake. |
| `test_comments_browser.py` | logic | `viewer-logic-to-fake-browser` | The resolved model, review items, selections, resolve state and painted quotes are DOM and runtime state; selections are made with the fake's Selection API, not by dragging the mouse. Some open the viewer frame. |
| `test_document_number_browser.py` | logic | `more-logic-to-fake-browser` | The running footer's text and the copied comments: DOM and clipboard on a top-level page. |
| `test_door_recordings_browser.py` | hot | `browser-door-recorder` | It records each top-level state in the one Chromium with `--record`: what Chromium answers is its subject. |
| `test_empty_groups_browser.py` | logic | moved by `fake-browser-door` | Group order, muted empty groups, zero counts and the table's row pages are runtime logic; the muted tone is a computed style the fake's cascade gives. |
| `test_equation_figures_browser.py` | hot | `hot-tests-record` | It embeds the real math.js and Plotly (structure/test_quality.py's real-library set): Plotly needs a real layout engine to draw, zoom and print. |
| `test_fake_browser.py` | logic | added by `fake-browser-door` | The fake browser's own contract: the facade's refusals, the stand-ins, the page's clock, the default answers in the report and the blocked network. |
| `test_feature_layout_browser.py` | hot | `hot-tests-record` | The faults the feature fixture's card group found at their widths: buttons apart, clear of the arrow, scrolled into view. Except `test_the_home_chooser_closes_on_a_click_on_the_menu_or_a_docked_bar`, which moves to the fake. |
| `test_features_browser.py` | logic | `viewer-logic-to-fake-browser` | What each canary says about a refusing host, from the viewer frame's recorded refusals. Except `test_a_host_stand_in_is_in_place_before_the_artifacts_first_script`, which is the order of scripts in a srcdoc frame and stays hot. |
| `test_figure_frame.py` | hot | `hot-tests-record` | One frame and caption position for every kind, a border token, and a legend moved back inside after a resize are layout. Except `test_only_kinds_with_options_show_the_tables_options_menu_whose_changes_stay_in_the_view`, which moves to the fake. |
| `test_figure_links.py` | logic | `layout-logic-to-fake-browser` | A link inside a figure shows its hover card and navigates: the card's place comes from recorded boxes, its content and the navigation are runtime logic. |
| `test_file_offers_browser.py` | logic | `viewer-logic-to-fake-browser` | Every offer saves through the host's save path, or is hidden with its warning: runtime logic against the viewer's recorded refusals. |
| `test_images_from_assets.py` | logic | `viewer-logic-to-fake-browser` | An image renders from its asset's bytes and a failed one shows its label. The decoded size is a recorded answer. |
| `test_library_doors_browser.py` | hot | `hot-tests-record` | The library doors' contract suite: it runs each door against the real library, and Plotly draws only in a real layout engine. |
| `test_limited_host_browser.py` | logic | `viewer-logic-to-fake-browser` | The banner's text in a sandbox without storage or scripts: logic against the recorded refusals, and a fake that runs no script. |
| `test_live_connector_browser.py` | logic | `viewer-logic-to-fake-browser` | A live table's line for each answer of the viewer's connector: runtime logic in the viewer frame. |
| `test_live_rows_browser.py` | logic | `viewer-logic-to-fake-browser` | A read's rows, groups, inert text, the refresh key and print's rows follow from the runtime; print is the print events, not print layout. |
| `test_live_source_browser.py` | logic | `more-logic-to-fake-browser` | A live source's rows, groups and its one logged error: runtime logic on a top-level page. |
| `test_live_web_browser.py` | logic | `viewer-logic-to-fake-browser` | The web route's requests, kept results and rate limits over a served page and in the viewer: network and storage logic; blocked storage is a recorded refusal. |
| `test_local_themes_browser.py` | hot | `hot-tests-record` | A theme's painted colours in each appearance, and a themed page that prints light: the browser's cascade and print. |
| `test_notice_center_browser.py` | logic | `layout-logic-to-fake-browser` | Icons, counts, lists, lines and their replacement are runtime state. Except `test_icon_opens_its_list_an_entry_expands_and_escape_closes` (full Chromium's named set), `test_a_confirmed_send_shows_the_sinks_name_under_the_band_and_the_line_goes` and `test_in_a_figure_overlay_the_line_shows_with_the_notice_icons`, which place the line on the screen and stay hot. |
| `test_page_pool_browser.py` | hot | `browser-door-recorder` | It tests the door's own pool: a real browser's reuse, crash and hang. |
| `test_parity_browser.py` | hot | `hot-tests-record` | The reading rows and the covered-control sweep in preview frames at their widths, with overlay scrollbars: what lies over what is layout. |
| `test_pdf.py` | hot | `hot-tests-record` | The PDF path prints with full Chromium; a print is the browser's own work. It records the fixture's printed PDF. |
| `test_pdf_inspect.py` | logic | `layout-logic-to-fake-browser` | The inspection tools read a PDF; they read the fixture's PDF that `test_pdf.py` recorded instead of printing one. |
| `test_property_editors_browser.py` | logic | `more-logic-to-fake-browser` | Canonical edits that survive a reviewed copy: runtime state and the copy's markup. |
| `test_pugh_figures_browser.py` | logic | `layout-logic-to-fake-browser` | The decision engine's verdicts, weights, marks, vetoes, tabs and the printed verdict are runtime logic. Except `test_at_phone_width_the_matrix_is_rows_and_a_wide_table_scrolls_with_its_criteria_held`, which stays hot. |
| `test_pugh_phone_browser.py` | hot | `hot-tests-record` | Rows over columns, nothing scrolls sideways, both tabs fit and one line per row on a phone are layout. Except `test_on_a_phone_a_mark_a_weight_and_a_pick_take_one_tap_each`, `test_a_link_to_a_section_in_a_tab_opens_the_tab_at_it_and_the_contents_lists_it`, `test_the_readers_changes_survive_a_resize_between_the_table_and_the_rows`, `test_the_options_list_says_each_name_once` and `test_the_options_list_and_the_popover_say_each_name_once`, which move to the fake. |
| `test_pugh_solutions_browser.py` | logic | `layout-logic-to-fake-browser` | Sections, the options list, hover-card content, the chart's question and the print's sections are runtime logic; a folded part's empty client rects follow from its computed display. Except `test_a_counts_hover_card_lies_over_the_matrix_unclipped_and_a_tap_elsewhere_hides_it` and `test_each_options_row_holds_its_radio_arrow_letter_and_name_on_one_centre_line`, which stay hot. |
| `test_reader_text.py` | logic | moved by `fake-browser-door` | The reader-facing text names no kind, and damaged data says so: text in the DOM. |
| `test_reading_shell_browser.py` | logic | `layout-logic-to-fake-browser` | The title page, the contents walk and shown sections are DOM and runtime state. Except `test_every_top_control_is_one_square_size_in_one_row` and `test_a_whole_note_self_link_scrolls_back_to_its_heading`, which stay hot. |
| `test_references_browser.py` | logic | `more-logic-to-fake-browser` | The hover card's reference link and glossary definition: its content. |
| `test_register_passing_browser.py` | logic | moved by `fake-browser-door` | Passing rows fold into one count line that follows the filters, search and print: runtime logic; the tones are computed styles the fake's cascade gives. |
| `test_sandboxed_preview_browser.py` | hot | `browser-door-recorder` | What a scripts-only sandboxed srcdoc frame refuses is the browser's enforcement. It records those refusals for the fake's viewer frame. Except `test_the_same_artifact_opened_normally_shows_no_notice`, `test_applying_or_clearing_a_filter_does_not_claim_the_html_changed` and `test_opening_a_preview_fails_at_once_when_the_artifact_cannot_start`, which move to the fake. |
| `test_selection_rule_set_browser.py` | logic | moved by `fake-browser-door` | Drill-downs, filters, distinct counts and facet pills select through the one rule set: runtime logic. |
| `test_shipped_features_browser.py` | logic | moved by `fake-browser-door` | An artifact carries only the runtime its Document uses and opens without errors: the page's scripts and DOM. |
| `test_source_files_browser.py` | logic | `viewer-logic-to-fake-browser` | The source file row's link, the new page it opens and a saved copy's row: DOM and window opening, partly in the viewer frame. |
| `test_startup_browser.py` | hot | `browser-door-recorder` | The first chapter's paint within a second in full Chromium: real paint timing, which no fake has. |
| `test_structural_nodes.py` | logic | `viewer-logic-to-fake-browser` | Its one browser test counts the notice center's warnings per unknown node type, in the sandboxed frame. |
| `test_table_detail_fields_browser.py` | logic | moved by `fake-browser-door` | The fields an opened row shows and what the filter box finds: runtime logic. |
| `test_table_headers_browser.py` | logic | `more-logic-to-fake-browser` | Headers sort on click, shift-click, Enter and a tap, and show no card: events and DOM. |
| `test_table_rows_one_line_browser.py` | hot | `hot-tests-record` | One line per row at 390 px, cut cells and the print book's full cells are text layout. |
| `test_theme_choice_browser.py` | logic | `layout-logic-to-fake-browser` | The offered themes, restyling, re-measured columns, session-only choice and a saved copy are runtime logic; the columns come from recorded text widths per font. Except `test_the_theme_select_is_as_wide_as_its_options_as_the_appearance_select_is` and `test_export_to_pdf_prints_the_chosen_theme_in_light`, which stay hot. |
| `test_timeline_figure_browser.py` | logic | `layout-logic-to-fake-browser` | Rows in order, the drill-down, the filter and print's rows are runtime logic. Except `test_the_today_row_is_in_view_when_the_chapter_opens_and_a_block_link_wins` and `test_at_390_by_844_nothing_scrolls_sideways_with_every_row_open`, which stay hot. |

That makes 35 logic files with 299 collected tests and 17 hot files with 188. Of the named
exceptions, 36 collected tests of logic files stay hot and 19 of hot files move to the fake. Once
every package has landed, 205 of the 487 run in the one real Chromium, and a landing runs them only
when a recording is stale (below).
`browser-door-recorder` added two files: `test_browser_door.py`, logic, with 5 tests, and
`test_door_recordings_browser.py`, hot, with one test per top-level state.

## The fake browser

**Picked: happy-dom 21.0.4** (published 20 Oct 2026). It runs in Node, as the DOM tier does, and
the probe below shows it gives most of the answers the runtime needs on its own.

The probe ran the three candidates on 22 Nov 2026: happy-dom 21.0.4, jsdom 31.0.1 and linkedom
0.18.12, the version the DOM tier pins.

| Answer | happy-dom | jsdom | linkedom |
|---|---|---|---|
| `getComputedStyle` from the page's stylesheets, `var()` resolved | yes | yes | throws |
| media rules in the cascade, and `matchMedia` | yes | `matchMedia` throws | throws |
| `ResizeObserver`, `IntersectionObserver`, `scrollIntoView`, `setPointerCapture`, `Element.animate` | yes | none | none |
| focus, a checkbox's click, a summary's click, `dialog.showModal` | yes | all but `showModal` | none |
| `localStorage` and `sessionStorage` | yes | throws in a page without a URL | none |
| `navigator.clipboard` and `crypto.subtle` | yes | none | `crypto.subtle` only |
| layout: boxes, client and scroll sizes | 0 | 0 | 0 or none |

happy-dom also has `PointerEvent`, `TouchEvent`, the `Selection` API and `window.open`; the probe
asked those of happy-dom alone. It lacks the Popover API and CSS highlights.

Run on the feature fixture built with the library fakes, happy-dom ran the artifact's own runtime
to its `obs-startup ready` mark in about 0.4 s, with no error. It needed three stand-ins: the
compression streams and `structuredClone` taken from Node, the `Option` constructor, and a canvas
text measure. Not picked: jsdom, which lacks the observers, `matchMedia`, `scrollIntoView`, the
clipboard and `dialog.showModal` that the runtime calls; and linkedom, which has no computed style, focus or
form behaviour. The DOM tier stands those in by hand today, with every element 384 by 24 pixels
(`artifact-harness.cjs`).

**What happy-dom cannot give, and the recordings supply:**

- every layout answer: an element's box and client rects, its client, scroll and offset sizes,
  the window's inner size, and the entries a `ResizeObserver` reports (happy-dom answers 0);
- where an element ends up after `scrollIntoView`, with its scroll margin and the sticky band;
- text widths: happy-dom has no canvas context, and `table.js` sizes columns by `measureText` in
  the theme's font;
- a decoded image's natural size;
- print layout: page breaks and the printed PDF, which `test_pdf_inspect.py` reads;
- what the viewer's scripts-only sandboxed frame refuses (storage, separate windows, modal
  dialogs, downloads, the clipboard, printing): happy-dom enforces no sandbox;
- `document.fonts`: happy-dom has none, so its ready state is recorded.

**What the fake's stand-ins add without a recording:** the `Option` constructor; the Popover API
(`showPopover`, `hidePopover`, `:popover-open` and light dismiss), which happy-dom 21 lacks;
`window.print`, which fires `beforeprint`, applies print media and fires `afterprint`; and Node's
compression streams, `structuredClone` and `crypto`. Each stand-in is held to an expectation
below, so its behaviour is checked against the recorded Chromium, not just written down.

The probe also found that happy-dom kept a media rule's colour after a viewport change. So the fake
opens a page at its state's viewport instead of resizing it, and a test that resizes stays hot
unless a recording covers each size.

**How a test drives it.** The fake is a Node process per test worker that hosts happy-dom, as the
page pool hosts Chromium. A `fake_page` fixture in `test/conftest.py` hands each test a Page-like
facade:

- `goto`, `evaluate`, `wait_for_function`, `keyboard.press`, `mouse` at a recorded box,
  `set_viewport_size` (it reopens the page) and `emulate_media`;
- `locator` with CSS selectors and `click`, `fill`, `press`, `text_content`, `get_attribute`,
  `count` and `is_visible`, where visible means a computed display and visibility that are not
  hidden and a box that is not empty.

Playwright's text and role selectors do not exist there: a test that moves rewrites them as CSS
and a text filter. A method the facade lacks fails, naming the method and this note. The fake
blocks the network as `network_guard.py` does, through happy-dom's fetch interceptor, and lets
through only the local servers a test starts.

**As built** (`fake-browser-door`): the host is [fake-browser.cjs](fake-browser.cjs), the facade
[fake_page.py](fake_page.py) with its `expect`, and `fake_page` in `test/conftest.py` hands a test
one page; the moved files carry the `dom` mark instead of `browser`. Four things the design above
did not name were needed:

- **The page's clock.** A page's timers, animation frames and idle callbacks run on a virtual
  clock. A wait runs the page until its condition holds, moving the clock to the next task only
  when the page has nothing else to do, and fails once nothing is left to run or the clock passes
  the timeout; between two requests one frame passes. Work the page awaits outside happy-dom, its
  compression streams and digests, keeps it busy until it ends. No wait reads wall time.
- **`light-dark()`.** happy-dom 21 drops a colour it cannot parse, so every colour the stylesheets
  give through `light-dark()` computed empty. The fake resolves it by the root's computed
  `color-scheme` and the device's preference, light in print; the colours it gives are hex, where
  Chromium gives `rgb()`, so a test compares two computed colours, never a colour with a literal.
- **Scoped selectors.** A locator inside another matches within the outer element's subtree only,
  as Playwright's do, so an ancestor outside it never satisfies a descendant selector.
- **User-agent rules.** happy-dom 21 has no rule for `[hidden]` or a closed popover; the fake adds
  Chromium's, display `none` at the user-agent level, so an author's display still wins.

happy-dom's cascade matches every style rule against every element it computes, which made a page
of 266 rows several times slower than Chromium; the host skips a rule whose subject needs an id,
class or tag the element lacks. The fake is still slower than the headless shell on large tables:
`test_register_passing_browser.py` took 38 s alone where Chromium took 13 s, mostly in the
runtime's own `getComputedStyle` calls.

happy-dom also asks a preflight `OPTIONS` before every cross-origin request, where Chromium asks
only before one that is not simple: a local server a test starts for a file page answers it. And
`print()` fires `beforeprint` and `afterprint` with no print media in between, since nothing is
laid out for print; `emulate_media` gives print media.

The default answers are listed in each test's report, in the section "fake browser: default
answers", as `<call> <element key> -> <answer> (<times>x)`; the key is
[door-key.js](door-key.js)'s, which the recorder and the replay share.

**As built** (`browser-door-recorder`): replay, below, and the stand-ins its conformance check
required, each found where the fake answered otherwise than the recorded Chromium:

- **`popstate`.** Chromium fires `popstate` and then `hashchange` on a fragment navigation;
  happy-dom fires only `hashchange`, and the runtime opens a chapter on `popstate`. The fake fires
  `popstate` just before it.
- **Focus.** `focus()` on an element that cannot take focus (a plain `span`, a hidden or disabled
  control) does nothing, and a dialog that opens focuses its first focusable descendant and gives
  focus back to the element that had it as it closes; happy-dom focused anything and moved no
  focus for a dialog.
- **Initial values.** happy-dom leaves a computed property that no rule sets empty; the fake gives
  the initial value of each the runtime reads (padding, margin and border widths `0px`, visibility
  and overflow `visible`, a transparent background).
- **The window's own properties.** A getter that throws, defined on happy-dom's window object, reads
  as `undefined` inside the page; the viewer frame's refusals are defined on the page's own global.

**As built** (`more-logic-to-fake-browser`): three things the moved files asked of the fake, each
held by `test_fake_browser.py`:

- **`TextEncoder`.** happy-dom's is Node's, whose bytes are Node's `Uint8Array`, so the runtime's
  `bytes instanceof Uint8Array` refused them. The stand-in hands them over as the page's own.
- **Requests.** `on("request")` hears each request the page makes through happy-dom's fetch, as
  Playwright's does. happy-dom's CORS preflight passes the same interceptor, where Playwright
  reports none, so no `OPTIONS` request is reported.
- **Downloads.** A click on a link with a `download` attribute that no listener prevented downloads
  its blob: or data: URL instead of navigating, and `expect_download` hands the file over, with its
  `suggested_filename` and `save_as`.

## The browser door's expectations

An expectation is one thing obs-html relies on the browser for. They live in
[expectations.yaml](expectations.yaml), in the form of the fakes decision of 22 Nov (kern#8,
`expectations-pooled-by-name`): each holds its **name**, its id; the **given** precondition, the
context a state must have for it to be asked there (`frame: top`, `frame: viewer`, and `step: last`
for one asked only after a state's last step); and the minimal **answer** the runtime relies on.
It names no engine: the one Chromium and the fake answer the same expectation. Each also has its
**statement**, a sentence, its **probe**, a page function that asks it, and its **kind**:
**supplied** (the fake answers from the recording) or **computed** (happy-dom or a stand-in
answers, and the conformance check holds that answer to the recording). An expectation states only
what would break its reader if it changed: `cascade` records each property the runtime read of each
element, not every property of it.

| Name | obs-html expects | Kind | Runtime callers |
|---|---|---|---|
| `box` | An element's border box and client rects, in viewport pixels. | supplied | `pages.js`, `table.js`, `figures.js`, `hover-card.js`, `options-menu.js`, `pugh-figure.js`, `timeline-figure.js`, `bars/comments.js` |
| `sizes` | An element's client, scroll and offset sizes, its offsets and its scroll position; the window's inner size. | supplied | `pages.js`, `table.js`, `pipe-tables.js`, `artifact.js`, `equations.js` |
| `resize` | A `ResizeObserver` reports an observed element's content and border box once after it is observed. | supplied | `figures.js`, `table.js`, `pipe-tables.js`, `pugh-figure.js`, `equations.js` |
| `scroll-into-view` | After `scrollIntoView`, the element's top and the document's scroll position. | supplied | `artifact.js`, `bars/search.js`, `bars/comments.js` |
| `text-width` | A canvas 2D context measures a text's width in a font. | supplied | `table.js` |
| `image-size` | An image of an asset decodes to its natural width and height. | supplied | the image tests (`test_images_from_assets.py`) |
| `fonts` | `document.fonts.ready` resolves, and the font set's status is loaded, before the first chapter is painted. | supplied | `pages.js`, `table.js` |
| `viewer-frame` | In a scripts-only sandboxed srcdoc frame, storage, cookies and history throw, `window.open` returns `null`, modal dialogs and print return at once and fire nothing, and the clipboard refuses. | supplied | the canaries, `capabilities.js`, `storage.js` |
| `cascade` | Each computed value the runtime reads of an element, such as its `display`, `visibility`, `font`, `lineHeight`, `paddingLeft`, side borders, overflow and `--hover-card-gap`. | computed | `pages.js`, `table.js`, `figures.js`, `hover-card.js`, `pugh-figure.js`, `artifact.js`, `bars/comments.js` |
| `media` | `matchMedia` matches each query the runtime asks and each media rule of the stylesheets at the state's context. | computed | `notices.js`, the stylesheets |
| `events` | A click on a button, a checkbox, its label and a summary fires its events in order and toggles the checkbox and the details. | computed | every control |
| `focus` | `focus()` moves `activeElement` to a focusable element and not to a disabled or plain one, and a modal dialog takes focus and gives it back when it closes. | computed | `artifact.js`, `bars/search.js`, `guided-card.js`, `notices.js` |
| `popover` | `showPopover` opens a popover and `:popover-open` matches it, an `auto` popover closes when another opens and a `manual` one stays, and `hidePopover` and `togglePopover` close and open it. | computed (stand-in) | `filter-fields.js`, `hover-card.js`, `options-menu.js` |
| `frames` | `requestAnimationFrame` callbacks run once each, in order, a nested one in a later frame, and a cancelled one never. | computed | `artifact.js`, `pages.js`, `figures.js`, `artifact-data.js` |
| `storage` | `localStorage` and `sessionStorage` keep a value of the page's origin. | computed | `storage.js`, `bless.js`, `tables.js` |
| `print` | `window.print()` fires `beforeprint` first. The printed PDF of a state is a supplied answer that `test_pdf.py` records. | computed | `pages.js`, `figures.js`, `hover-card.js` |

A probe asks only what a page function can: the light dismiss of a popover on Escape or a
pointerdown outside it, Tab's order and Enter or Space on a button need trusted input, which a page
function cannot give, so they are no probe's answer. The one Chromium fires `beforeprint` on a
page's first `print()` only and never `afterprint`: the `print` probe runs once, after a state's
last step, and ends the print with an `afterprint` of its own, so the runtime leaves its print
preparation.

Two kinds of hot check record nothing the fake replays: paint timing (`test_startup_browser.py`)
and the page pool's own behaviour (`test_page_pool_browser.py`). They stay hot because only a real
browser shows them, and carry the `hot` mark.

## Recording and replay

**A state** is what a recording is taken in: a fixture artifact, a context (viewport, device scale,
touch, colour scheme, reduced motion, screen or print media, top-level page or viewer frame) and
the steps that lead there (open the page, open a chapter). Step 0 is always the opened page. The
states are those the hot tests visit, plus one per fixture and context that the logic tests open:
desktop 1280 by 720, the viewer frame 1100 by 700, and a phone 390 by 844.
[expectations.yaml](expectations.yaml) holds them; `browser-door-recorder` recorded two,
`features-desktop`, the feature fixture opening `figures` and then `prose`, and
`preview-viewer-frame`, the preview of `test_sandboxed_preview_browser.py` in the viewer frame.
The phone needs a phone context of the one Chromium, which `hot-tests-record` adds.

**An element's key** is the same in both engines: the id of its nearest ancestor that has one,
then its tag and position among its siblings of that tag below it. `test/browser/door-key.js`
computes it and finds the element a key names; both the recorder and the fake load it.

**Recording.** `uv run pytest -m hot --record` runs the hot tests that record:
[test_door_recordings_browser.py](../test_door_recordings_browser.py) for each top-level state and
`test_sandboxed_preview_browser.py` for the viewer frame; without `--record` they skip and start no
browser. [door.py](door.py) records a state. First the fake runs it, on the door's defaults and
with the previous recording where there is one, and lists, by step, each key and call the runtime
asked, and the stylesheets' media rules. Then the one Chromium opens the state, takes each step
and, after it, runs every expectation's probe over those keys. It writes
`test/browser/recordings/<state>.yaml`:

```yaml
state: features-desktop
artifact: test/fixtures/documents/features.json
context: {viewport: [1280, 720], scale: 1, touch: false, scheme: light, motion: no-preference, media: screen, frame: top}
steps:
- open: page
- {open: chapter, id: figures}
- {open: chapter, id: prose}
artifactDigest: sha256:…
chromium: <version> (Playwright <version>)
answers:
- step: 0
  asked:
    box:
    - '#overview > div:1'
    cascade:
    - html:1 > body:1|font
    - html:1|fontSize
  box:
    '#overview > div:1':
      border: [0, 64, 1265, 316.52]
      rects: [[0, 64, 1265, 316.52]]
  text-width:
    16px Georgia, "Times New Roman", serif|10: 16
  cascade:
    html:1 > body:1|font: 16px Georgia, "Times New Roman", serif
    html:1|fontSize: 16px
```

`artifactDigest` is the SHA-256 of the artifact the state opens, built with the library fakes and
the build time fixed by `SOURCE_DATE_EPOCH`. It is built from its own folder, outside this
checkout: a build records the commit and version of the repository it runs in as its target
(spec/artifact-ui.md, Generation provenance), which made every commit change every digest. Built
so, two builds were byte-identical across a commit on 22 Nov 2026. The page still records
obs-html's own version, so a landing that bumps the version changes every digest: the staleness
rule below meets that. The recordings are committed: every landing reads them without a browser.

**Replay.** The fake opens a state with its recording. A step counts as reached as it begins, and
from then on the fake answers every supplied call for a key from the latest step reached that
recorded it: boxes and client rects, sizes and offsets, the window's inner size, the observers'
entries, text widths by font and text, decoded image sizes, `document.fonts` and where
`scrollIntoView` scrolls the document. It keeps no call order: a logic test asserts no layout, so it
needs answers that send the runtime down the real browser's branches, not a replay of one run. A
recorded scroll position is not replayed: the runtime sets its own.

A key with no recorded answer gets the door's default: an empty box for an element whose computed
display is `none` or that is not in the document, else the DOM tier's 384 by 24 box. The fake lists
each default it gave in the test's report. In a viewer-frame state each call the recording lists
under `viewer-frame` is applied as it says: it throws, returns its value (`null` for
`window.open`) or rejects, and fires the events recorded with it.

**Conformance.** [test_browser_door.py](../test_browser_door.py) runs without a browser in every
landing. For each state, it opens the state in the fake with its recording and, after each step,
asks every computed expectation with the keys the recording lists, and compares with the recorded
Chromium answer, naming the state, the step, the key and both answers where they differ; where the
state's artifact no longer builds to the recording's digest, it says that too. This is the proof
that the fake answers like the browser for what obs-html relies on.

## When hot tests run

- **On a landing, when a recording is stale.** A recording is stale when its `artifactDigest`
  differs from its state's artifact as the tree builds it, or its `chromium` from the version the
  hot tests' Chromium reports. The landing then fails, naming each stale state, with the remedy
  `uv run pytest -m hot --record`. The worker runs that and commits the recordings. CI's job `hot`
  runs the hot tests on that landing and checks that the committed answers are the ones Chromium
  gives. A landing with no stale recording starts no browser.
- **When the browser changes.** A Playwright pin that `uv.lock` moves gives another revision, so
  every recording is stale and the hot tests run, as above.
- **Nightly.** CI runs the hot tests against main and fails, naming each expectation whose answer
  changed, so a drift in the installed browser shows before a landing meets it.

The hot tests share one xdist group, so one worker starts the one Chromium for all of them, as the
core's diagram tests share one session. It is full Chromium, the browser the PDF path finds and the
one a reader opens. The phone is a context of the same instance. The overlay-scrollbar sweep of
`test_parity_browser.py` needs a launch flag; `hot-tests-record` makes it a context of the same
instance where Chromium allows that, and otherwise keeps it as the one second launch.

## Packages

In order. Each is a work issue of its own, sized small to medium. Its title is the name given, and
it updates the Package column of the rows it moves.

1. **`fake-browser-door`**: the fake browser. happy-dom 21.0.4 pinned in
   `test/browser/package.json` and its lockfile, the Node host, the `fake_page` facade, the
   stand-ins and the door's default answers. It moves the first logic files that need no
   recording, those of tables and counts on a top-level page: `test_cards_counts_quantities_browser.py`,
   `test_empty_groups_browser.py`, `test_reader_text.py`, `test_register_passing_browser.py`,
   `test_selection_rule_set_browser.py`, `test_shipped_features_browser.py` and
   `test_table_detail_fields_browser.py`. A file moves only where each of its tests passes on the
   default answers and asserts no layout.
2. **`more-logic-to-fake-browser`**: the other logic files that need no recording:
   `test_answers_browser.py`, `test_attachment_replacement_browser.py`,
   `test_document_number_browser.py`, `test_live_source_browser.py`,
   `test_property_editors_browser.py`, `test_references_browser.py` and
   `test_table_headers_browser.py`.
3. **`browser-door-recorder`**: the expectations (`test/browser/expectations.yaml`), `door-key.js`,
   the `hot` mark, the recorder on the one Chromium with `--record`, the recordings' format, replay
   in the fake, and the conformance check `test/test_browser_door.py`. It records the viewer frame
   from `test_sandboxed_preview_browser.py` and marks the hot tests that need no change
   (`test_page_pool_browser.py`, `test_startup_browser.py`).
4. **`viewer-logic-to-fake-browser`**: the logic files that open the viewer frame or need a
   recorded refusal or decode: `test_attachment_editions.py`, `test_comments_browser.py`,
   `test_features_browser.py`, `test_file_offers_browser.py`, `test_images_from_assets.py`,
   `test_limited_host_browser.py`, `test_live_connector_browser.py`, `test_live_rows_browser.py`,
   `test_live_web_browser.py`, `test_source_files_browser.py` and `test_structural_nodes.py`.
5. **`layout-logic-to-fake-browser`**: the logic files that need recorded layout, with the states
   they open. Their hot tests move into the hot set: `test_bars.py`, `test_bless_browser.py`,
   `test_figure_links.py`, `test_notice_center_browser.py`, `test_pdf_inspect.py`,
   `test_pugh_figures_browser.py`, `test_pugh_solutions_browser.py`,
   `test_reading_shell_browser.py`, `test_theme_choice_browser.py` and
   `test_timeline_figure_browser.py`.
6. **`hot-tests-record`**: the hot files become hot tests that record, and their logic tests move
   to the fake: `test_appearance_browser.py`, `test_artifact_browser.py`,
   `test_callouts_embeds_attachments.py`, `test_chapter_sweep_browser.py`,
   `test_columns_browser.py`, `test_equation_figures_browser.py`,
   `test_feature_layout_browser.py`, `test_figure_frame.py`, `test_library_doors_browser.py`,
   `test_local_themes_browser.py`, `test_parity_browser.py`, `test_pdf.py`,
   `test_pugh_phone_browser.py` and `test_table_rows_one_line_browser.py`.
7. **`hot-tests-on-change`**: the run rules above. The staleness check in the landing, CI's job
   `hot` and its nightly run, `structure/test_quality.py` refusing a real-browser fixture outside
   the hot set, the pools reduced to the one instance, and the README's Browser tests.
8. **`dom-tier-on-fake-browser`**: the DOM tier (`artifact-harness.cjs`, `artifact-ui.cjs` and the
   tests that run them) moves from linkedom to the fake browser and its recordings, and linkedom
   and its constant geometry go.
