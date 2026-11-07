# HTML architecture

Reader: whoever changes how the HTML adapter renders and runs.

obs's architecture, part of obs's specification, owns the flow from vault to Document, the
repository layout and the Document-adapter contract. This note owns the HTML adapter's rendering
and runtime architecture; its sections moved here from obs's architecture note with their text.

Domain adapters own their evidence parsing, calculations, and artifact content; obs-html owns
reusable rendering and interaction behavior. An adapter's migrated artifact must provide its
required interactions within the obs-html edition.


## Filter and navigation owners

The global Filter owns one compiled query and its applied expression. Figure gestures and
facets use that same owner; invalid drafts do not replace it. The optional profile contract
is owned by [[input-model]] and constrained by the configuration schema. Canonical field
aliases follow the shared Bases reference/value adapters, not copied target metadata.

Chapter/paragraph totals derive from canonical chapter content; reader and print clones
are disposable views. One retained navigation sequence includes Home and supplies arrows,
breadcrumbs, sidebar and artifact contents; record scope leaves authored sections intact.

## Build stage timings

The named build stages are registered once, in `src/obs_html/timings.py`; the `--timings` help
and the baseline file read that registry, and a baseline for an unregistered stage is an error.
Stages are non-overlapping: a nested stage pauses its enclosing one, so a call's stage durations
sum to at most its total.

Per-stage baselines live in one tracked data file, `src/obs_html/timing-baselines.json`, package
data read through `importlib.resources` and validated by its adjacent
`timing-baselines.schema.json`: an object of stage name to baseline seconds. A stage without a
baseline is not compared.

Each baseline is the median of five runs, on the machine of the
change that sets it, on the adapter's own specification, each run into a new file:
`uv run obs-html --build-own-spec spec.html --timings` for render and write, the same with
`spec.pdf` for print, and `uv run obs-html --check-rendered spec.html --timings` for open.

The specification has no figure, so figures has no baseline. Whoever changes a stage's cost measures
it so and writes the new median there; there is no command for it, as the interim had none.

With `--timings`, a stage that exceeds its baseline by both the relative and the absolute
threshold of the [[configuration]] `timings` section prints a warning to stderr through the
adapter's one message form: the baseline file, `stages.<stage>`, the stage's time and baseline,
and the remedy. It never fails the call.

Either threshold alone stays silent, so small stages
and small absolute changes do not cause noise.

## The interim adapter

The interim adapter, which built artifacts directly from a vault, was deleted once the
integrated adapter reached parity with it (obs#3); `obs-html` is the only HTML adapter.

### Known differences from the interim

The [parity table](../test/parity/features.md) owns every difference from the interim adapter.

## Rendering and runtime

The renderer emits the nested table of contents and ordered chapter data once;
client-side navigation shows exactly one chapter and manages previous/next controls, URL
fragments, browser history, scroll reset, and docked-bar state.

One embedded central stylesheet owns the component rules described in [[artifact-ui]].
The [[semantic-assets]] index owns named presentation values and their inheritance;
stylesheet variables and DOM are derived views of that owner.

Success, failure, waiting, and annotation colors are semantic tokens; components never own
parallel literals for those meanings.

Icons, colors and stateful appearances share that typed semantic resource owner,
resolved for generated markup and browser controls. Consumers reference names,
not glyph/graphic/color literals. Obsidian action compatibility belongs to
[[input-model#Named icon resources]]; resource semantics belong to [[semantic-assets]].

One embedded data-table runtime owns table filtering, hierarchical rows, rendered cells, and column
order.

An artifact carries only the runtime its Document uses. Each script, stylesheet or page element
that only some Documents use belongs to a reader feature of the registry (`features.py`), which
declares the condition that ships it, its code, its styles and the page elements the renderer
writes for it; the renderer keeps no list of its own. A Document without a Base table carries no
data-table runtime, Bases schema or YAML library, one without a figure no figure runtime, and a
figure kind's own script (the Sankey drawing, the decision engine) ships only with that kind. A
runtime that calls into a feature's script does so only where the feature's content is on the
page, so a script left out leaves no call behind.

The reader's own Base-table code (a note's tables, their saved presentation and their rows in
search) is the tables feature's script, `tables.js`. The reader's core (`artifact.js`) reaches it
through one hook: it calls `globalThis.obsTables.attach(core)` once, where `core` holds what the
tables read of the reader (its records, notes and helpers, and getters for the active filter and
the visible chapters, which change as the reader filters), and uses only the object `attach`
returns: `definition`, `states`, `render`, `searchHits` and `shown`. Without the feature the hook
is absent, no note has a table, and each call the core makes into it is guarded.

The Markdown parser adapts each `base` fence into a declarative table definition attached to
its ordinary chapter; the runtime has no Appendix or named-register knowledge.

The Markdown table-authoring contract is owned by [[input-model]]. Domain adapters
project records; authored Markdown owns queries and composition. Application runtimes
update canonical data without replacing the authored table selection. Framework default
content follows the same contract instead of constructing hidden table definitions.

The artifact embeds
those definitions and their queries, not precomputed result rows.

The browser evaluates a definition
lazily against canonical artifact records when its containing chapter is opened.

Platform wrappers contain only bootstrap logic and dispatch to the same CLI.

Trusted application registration and revision-checked canonical/archive transactions
follow [[input-model]]. The generic artifact owns action dispatch and atomic replacement;
domain adapters own parsing, shared semantic projection and their generated source
changes.

Figures resolve declared canonical graph owners from live records, not a second startup
graph. Cover, authored source links and Settings use one current-archive
download action; activation resolves bytes from the existing payload owner.

Dockable bars are extension modules discovered from the `obs_html.bars` package. Each
module exports one definition containing its key, label, icon, help text, and content
factory. The renderer derives both menu entries and parked bar markup from those
definitions; it never keeps a second list. See obs's quality note ([[obs-specification|obs's specification]]).

A bar's optional browser runtime is the sibling `<module>.js` package resource;
discovery attaches it, and a definition carrying script text is rejected.

Browser runtime code lives only in package `.js` resources read through
`importlib.resources`, never in Python string literals, so the JavaScript syntax check
covers every runtime file. Values reach a runtime through data islands or attributes;
the pre-paint reader startup substitutes JSON values for its placeholders.

Review comments and per-reviewer block decisions live in one embedded JSON island separate
from the canonical artifact data.

The Comments bar is the only browser-side owner of that
island.

Review-item identifiers are deterministic derived views of rendered chapter blocks,
not a parallel copy of source content.

Saving a reviewed copy rewrites the island in the
standalone HTML; it never changes source Markdown or canonical chapter data.

CLI extraction
reads only this island and never executes artifact scripts or parses comments from rendered
prose.

Command execution is owned by a separate runner boundary. Markdown parsing supplies the
command and receives escaped output; it does not own process invocation, timeout policy,
or authorization.

## Packaged browser assets

Every browser asset the renderer embeds (its scripts and styles, the icons, the vendored Plotly,
pdf-lib and js-yaml, and the maths library) is package data of `obs_html`, and the renderer reads
it only through `importlib.resources`, so an installed wheel renders what a checkout renders.
Most are tracked files in `src/obs_html`.

An asset that comes from a lockfile is built into the
package by the adapter's build hook, `hatch_build.py`, on every build of the package, editable ones
included.

It unpacks math.js and its licences from the mathjs tarball `maths/package-lock.json`
pins (that package alone, checked against the lockfile's integrity) in a temporary folder and
writes them to `src/obs_html/vendor/maths/`.

Those files are generated beside the package that ships them, as the core's capability reference is
(obs's cli.md, One-call build), and ignored.

The hook's `PACKAGED` table names each generated
folder of the package and what fills it, so another one is one entry.

Besides the browser assets
it copies this specification, `spec/`, into `src/obs_html/spec/`, which `obs-html
--build-own-spec` builds ([[cli#Building its own specification]]). uv builds the package again
when the hook, the lockfile or a file of this specification changes (`[tool.uv] cache-keys`).

A build without npm, whose `npm pack` fails or whose tarball is not the pinned one, stops and names the lockfile and the remedy. `test/test_installed_wheel.py`
renders and builds this specification with the installed wheel and fails when anything is read
from the repository tree.

## Artifact data ownership

- The generated HTML embeds one canonical note store with identifiers, normalized frontmatter,
	and rendered content; its separate ordered TOC contains note identifiers, not copied records.
	Manifest and link resolution semantics are owned by [[input-model]].
- Repeated embedded data-URI payloads are stored once in the canonical artifact data and referenced
  by opaque local tokens. Browser views resolve those tokens before presentation, keeping artifacts
  self-contained and preserving standalone/PDF access.
- The single-payload rule also applies across reader attachments and an embedded reproduction
  archive. Do not embed the same original evidence once for downloads and again in a separate
  source payload. References or a reconstructed archive may share the owning bytes; compression
  must preserve exact original downloads, standalone opening and source reproduction.
- With source embedding, the ordinary compressed ZIP is the byte owner. Reader asset
  descriptors name a ZIP member, its media type and SHA-256; local Blob URLs are disposable
  browser projections, never serialized owners. The browser validates the ZIP entry and
  original-byte digest before exposing it, and printing awaits pending asset hydration.

  Canonical notes remain the authority for model edits and exports. Evidence replacement
  must atomically rewrite the owning ZIP entry and its descriptors, removing superseded
  unreferenced bytes; appending a second asset store or retaining stale originals is not
  a valid replacement operation. This transport alone does not implement evidence upload.
- The reader, table of contents, filters, database views, and future render modes derive
	their state from that store. They do not receive copied chapter datasets or maintain
	parallel metadata.
- Only the active chapter is materialized in the reader. Screen pagination moves its live
	nodes so table state and review interactions survive view changes; static PDF projections
	render from the canonical store rather than hidden chapter documents.
- New views consume the generic store contract and keep only view-local state.
- Derived indexes may be built in memory at runtime but are not serialized as duplicate
	artifact data.
- Canonical artifact data has one transport codec shared by generation, source-archive
  handling, read-only extraction and reviewed saving. The default gzip/base64
  transport compresses that semantic JSON, not only its original attachments.

  Decoding is a bootstrap boundary; views initialize from the decoded canonical
  store in their normal order. Decoded data and DOM are disposable in-memory
  projections, not extra serialized owners. Reviewed saving encodes the current
  model and does not retain an inflated copy or stale startup payload alongside it.
- Python owns one parsed semantic chapter model containing normalized frontmatter, paragraph
  semantic tags, diagnostics, and authored Markdown. Rendered chapters,
	generated projections, query records, and lint output consume that model; browser code does
	not rediscover source semantics from HTML.

- Table cells displaying note metadata use Markdown rendered by the same Python semantic
  renderer as chapter content. Derived HTML remains attached to the canonical note, keyed
  by flattened field path; raw values remain authoritative for filtering and sorting.
  Glossary projections retain their owning note's additional fields and ordering metadata.

See [[product]], [[configuration]], and [[input-model]].

## Output-format statements of obs's architecture

obs's architecture states these without naming an output format; the HTML wording moved here.

### Flow

HTML rendering is the integrated adapter in `adapters/html`.

Render one self-contained HTML file with an embedded chapter navigator (obs's architecture,
Flow, step 8).

### Safety boundaries

Generated HTML never refers to source-machine local files.
