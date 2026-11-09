# HTML input model

Reader: whoever authors a vault for the HTML adapter, or changes how the adapter reads its options.

obs's input model, part of obs's specification, owns the input semantics every adapter shares. This
note owns what only the HTML adapter reads or presents: its `obsHtml` options, its runtime
interfaces and what its artifact does with the input. Its sections moved here from obs's input
model with their text.

## Trusted presentation projections

Trusted application runtimes may save a named selection through
`obsArtifact.setViewSelection(key, selected, choices)` and read it through
`viewSelection(key)`.

Values are unique strings from the supplied finite choices; they live in
`readerState.views`, not canonical notes, filter expressions or record
stores. Unknown/stale saved choices are rejected by the application against its
current catalog.

`obsFigures.setProjection(sourceNote, graph)` supplies a transient graph through the
same dynamic Sankey renderer and canonical record predicates as the authored
`sourceNote`.

`obsCards.setProjection(key, fieldsBySourcePath)` supplies transient field
predicates for a declared metric key, not precomputed numeric values. Its
counts still use the shared aggregate evaluator over filtered canonical records.
Neither API commits canonical data; removing a projection restores canonical fields.

A trusted runtime may likewise project a table's visible columns from its saved view
selection by dispatching `obs-table-set-columns` on the table host. That projection is
derived view state: it becomes the table's current default and is not itself saved table
presentation.

Only explicit reader column changes that differ from the current projection are
retained as reader state, so reopening and
re-projecting a saved selection starts unchanged.

## Artifact presentation profile

Author presentation decisions live in the manifest frontmatter's reserved `obsHtml`
mapping, the same namespace that notes and Bases fences use for obs-html-only options. The
core does not read it ([[#Core and adapter namespaces]]).

Obsidian keeps it as ordinary frontmatter, so the author edits it in Properties or source.
The adapter's packaged profile schema, `profile.schema.json`, constrains it and owns the
defaults; the converter
contains no front-page titles, labels or opening mode of its own.

```yaml
obsHtml:
  layout: paged              # or scrolling, screens
  heading: cover             # or compact
  pages:
    - {page: cover}
    - {page: abstract, title: Abstract}
    - {page: contents, title: Contents}
  figures: {numbering: none, label: Figure}
  print: {paper: A4, margin: 20mm}
  cssSnippets: [house-style] # .obsidian/snippets/house-style.css
```

- `layout` chooses the view every opening starts in: `paged` (paper sheets), `scrolling`
  (continuous reading) or `screens` (one chapter per screen). Readers can still switch during
  the session; that choice is not saved as the next opening's state. It replaces the removed
  `artifact.reading.paged` setting.

  Use `screens` for an artifact read on a phone one chapter at a time, such as a deck of
  decisions that each fit one screen; use `paged` for a document that is read and printed as
  pages. Without `layout`, a manifest whose listed chapters all ask for a bless opens in
  `screens` and any other in `paged`; [[artifact-ui#Screens]] owns that rule and the view.
- `heading` presents the cover metadata at the top of Home. `cover` (default) is the title box,
  which `pages` can also place as the title sheet.

  An empty cover field (blank text, null, an empty list or mapping, or a `product` whose
  name and version are blank) is left out of the cover, the compact line and the artifact's
  metadata. The core keeps it in the Document; leaving it out is this adapter's choice.

  `compact` is one line: organization, product
  name and version, document type and title (subtitle last), separated by `·`; the other cover
  fields (template, people, document number, legal entity, copyright, confidentiality) are not shown.

  The compact line is never a sheet of its own: in the paged and PDF projections it opens the
  first declared front page, so `pages` must declare at least one page and no `cover`.
- `pages` is the ordered list of generated front pages of the paged and PDF projections.
  Each kind (`cover`, `abstract`, `contents`) appears at most once.
  - `cover` is the title sheet built from the cover metadata. It has no `title`; its heading is
    the document title.
  - `abstract` places the abstract Markdown: its lead sheet followed by one page group per
    top-level second-level heading. The optional plain-text `title` becomes the lead sheet's
    heading and running-header section; without it the lead sheet has no generated heading.
    A manifest whose abstract contains Markdown must declare `abstract`; authored prose is
    never silently dropped from the PDF.
  - `contents` is the generated chapter list with measured page numbers; the optional
    plain-text `title` is its heading.
  - An omitted kind produces no page. `pages: []` is valid for a manifest without abstract
    Markdown.
- `figures` numbers captioned `figure` fences. `numbering` is `none` (default), `document`
  (`Figure 1`, `Figure 2`, … in contents order) or `chapter` (`Figure <n>.<m>`, where `<n>` is the
  top-level contents position of the chapter, its subchapters included, and `<m>` counts within
  it).

  `label` is the plain-text word before the number (default `Figure`, for example `Abb.`);
  `labelPlural` precedes merged references (default `Figures`).

  The number precedes the first caption paragraph; uncaptioned figures and notes outside the
  contents (record notes, reproduction copies) are not numbered. Authors never type numbers.
- `print` sets the paper of the paged and PDF projections: `paper` is a portrait paper name
  from configuration's `artifact.print.paperSizes` and `margin` the margin
  on every side in millimetres (`20mm`). Omitted keys use the defaults; configuration owns the
  margin limits. It replaces the removed project `artifact.paper` setting.
- `cssSnippets` lists CSS snippet names, without `.css`, from the vault's snippet folder
  (configuration's `input.cssSnippetFolder`, Obsidian's `.obsidian/snippets` by default).
  obs-html reads them from the Document, whose `cssSnippets` carries every snippet of that folder
  (obs's architecture, CSS snippets: [[obs-specification|obs's specification]]).

  The HTML embeds them in list order after its own styles, every packaged stylesheet including
  the figure styles, so they style screen, pages and PDF and win at equal specificity. Snippet CSS
  applies page-wide by design: unlike a figure's authored styles it is the author's styling of
  the whole artifact.

  Obsidian's own enabled-snippet list is a per-device
  appearance choice and is not read: the document declares what it needs.

  A listed snippet that is missing, or that contains `</style`, is an input error. A missing one
  names the manifest, the field (`obsHtml.cssSnippets[1]`) and, in its remedy, the snippets the
  vault has; one that contains `</style` names its snippet file. The default is none.
- Generated abstract sections are [register](#registers) embeds in the abstract Markdown.
- Vaults that declare none of these keys keep the packaged defaults shown above, which reproduce
  the established cover, "Abstract", "Contents", and paged opening.

  The default is compatibility: an existing vault keeps its artifact unchanged until its author
  decides otherwise. Attachments are not a profile key; see the attachment rule under
  [Document home and abstract](#document-home-and-abstract).
- The profile is presentation configuration, not document metadata: it is neither a Document
  metadata row nor shown in Home's frontmatter.

  On an ordinary note (for example a copied manifest inside a reproduction folder) the
  document-level keys are inert; only the selected
  manifest's profile applies.

## Artifact behavior

- Generation produces exactly one HTML file containing the artifact shell and all chapters.
- `artifact.dataCompression` selects `gzip` (the default) or `none` for canonical
  artifact-data transport. Gzip uses one base64-encoded island; a plain JSON island
  remains valid and may be used when compression would increase the encoded size.

  This changes storage, not note/query/review semantics or the original downloaded
  evidence bytes. Both formats are self-contained and use one decoding owner.
  Unsupported decoding or malformed payloads produce a visible initialization
  error, not an apparently successful empty artifact.

  All dependent runtimes wait for validated decoding. Save reviewed HTML encodes
  a consistent snapshot of the current canonical model and reader/review state,
  keeps it compressed, and removes disposable materialized views rather than
  embedding another raw model. Async compression must not lose file-picker user
  activation, clear unsaved state after failed writes, or mark later edits saved.

  Reopen, read-only extraction and source reproduction use the same format contract.
  The island retains its `artifact-data` identity. During opening its decoded JSON
  replaces the encoded text in memory; saving replaces that disposable projection
  with exactly one encoded current snapshot. Plain transport remains readable
  without browser compression support.

  Gzip requires native stream decompression; unavailable support is an explicit
  opening error, never a network fallback.
  A save captures model, review and dirty baseline together before awaiting work.
  Only a successfully closed file may advance that captured baseline; a download
  cannot confirm completion, and edits arriving later remain unsaved.
- The authored chapter order follows the manifest; presentation of headings is owned by
  [[artifact-ui]].
- Exactly one chapter or subchapter is visible at a time.
- The active chapter has its own scroll range; content never continues into the next one.
- Left and right controls walk the chapter sequence (obs's input model, Manifest contract).
- Selecting a table-of-contents item or changing chapters resets content scroll to the top.
- Stable URL fragments identify chapters so browser history and direct links work.
- Home is always a reachable navigation destination, including when a filter leaves
  one or no matching authored chapters. Previous/next, breadcrumb/Home and both
  sidebar/artifact contents derive from the same retained navigation sequence.

  A still-visible active chapter cannot be stranded outside that sequence.
  Artifacts may explicitly scope their global query to record data rather than
  authored chapters; that scope preserves chapter navigation and PDF chapter inclusion.
  The ordinary artifact's chapter-filter behavior remains the default.
- The manifest frontmatter's `obsHtml.query` owns the optional global query profile
  (schema: the adapter's profile schema); project configuration rejects a `artifact.query`.

  Instead of the profile, the manifest may name one internal note link, such as an
  adapter's generated configuration note, whose own `obsHtml.query` holds the profile.

  `scope` is `chapters` (default) or `records`. In record scope, optional `where`
  selects the count/facet population using the same exact, AND-combined record conditions
  as dynamic figures. It does not remove authored chapters or document/PDF sections.

  Optional `fields` is a curated discoverable catalog of `{field, source?, label?}`:
  `field` is the query alias, `label` defaults to that alias, and `source` defaults to
  `field`, or is a nonempty array of source paths whose scalar values are unioned.

  Source paths address canonical fields and may follow a canonical internal note reference
  prefix into the target's remaining metadata path, including arrays of references.

  For example, `roles.origin.item.disciplines` follows `roles.origin` to its canonical
  note, then reads `item.disciplines`; target metadata is never copied into path notes.
  Alias values are derived again after canonical edits, never serialized as another dataset.

  An explicit catalog limits discoverable fields but does not bypass the ordinary
  discriminative-facet rule: constants, single-value fields and near-unique fields
  are not attribute pills. The default distinct-value upper fraction is one half
  of the applicable population, owned by configuration/schema.

  Text and identifiers remain directly queryable even when not offered as facets. Raw
  metadata remains
  queryable without becoming discoverable noise.
  Example: `{"scope":"records","where":[{"field":"kind","equals":"path"}],
  "fields":[{"field":"discipline","source":["roles.origin.item.disciplines",
  "roles.destination.item.disciplines"],"label":"Discipline"}]}`.
- Styles, scripts, and local assets are embedded so the HTML file is portable.
  Artifacts may opt into version-pinned, integrity-checked CDN delivery of Plotly through
  `artifact.figures.plotlyDelivery: cdn`; the default `embedded` preserves offline graph
  interaction.

  CDN-backed Plotly plots do not embed a duplicate static image; printing uses an on-demand SVG of
  the interactive graph, not a stored fallback. CDN failure displays an explicit
  interaction-unavailable notice. Local attachments are unaffected.

  `artifact.embedPdfs` defaults to `true`. Setting it to `false` leaves PDF links pointing
  to the local source files instead of embedding their bytes; those PDFs do not travel
  with the standalone HTML. Other attachment types are unaffected.

### Optional reproduction archive

An explicitly requested reproduction archive captures the selected vault and generator inputs.
CLI invocation and prerequisites are owned by [[cli]]; controls and PDF presentation by
[[artifact-ui]]. The source boundary is defined here.

obs-html packages the vault files a Document's `sourceArchive` carries; the core selects them
(obs's architecture, Source archive: [[obs-specification|obs's specification]]) by the boundary
below, and a file the Document holds as an asset takes that asset's bytes.

The ZIP holds each file at `vault/<path>`, the `source-inventory.json` the reader's archive transactions update (its
`generator` list empty), `build-config.json`, `reproduce.py` and `REPRODUCE.txt`, which says how
to run it.

Every member has one fixed timestamp, so the same files give the same ZIP. The reader downloads it as
`obs-html-source.zip`, the interim's name, and a PDF carries it under that name. An archived file
naming an asset the Document lacks is an input error naming `sourceArchive.files[i].asset`.

obs-html's archive refers to the generator instead of copying it, from the Document's
`sourceArchive.build` record (obs's architecture, Source archive).

`build-config.json` holds the Document's `schemaVersion`, obs's `repository` and `commit`, the recorded `lockfiles` versions,
the adapter's own options (`adapterOptions`), the exact `command`: `obs-document --source
vault/<manifest path>` followed by the recorded arguments, and, where the manifest declares one,
the `style` the build record names (obs's architecture, Declared style).

A style module obs-html is given for one build with `--style FOLDER` is not recorded, so a rebuild from the archive never
uses it.

`python reproduce.py`, which needs git
and uv only, clones obs from that repository (`--repository URL` names another, such as a local
clone), checks out the commit, installs it with that commit's `uv.lock` (`uv sync --frozen`) and
runs the command from the extracted folder. A failed clone, checkout or install names the commit,
the repository and the remedy.

A command with `--execute-commands` runs only when `reproduce.py`
is given `--execute-commands` too, so the vault's fences never run unreviewed. A Document whose
arguments name no `--adapter` was written by a call without one, so no recorded command rebuilds
the artifact: that is an input error naming `sourceArchive.build.arguments`, whose remedy is the
one-call build.

The generator's package source, project manifest, lockfile, README and wrappers, which the
interim adapter copied into `generator/`, are not carried; that difference from the interim is
listed in [[architecture#Known differences from the interim]].

It discloses the selected vault's explicit directory snapshot, including scripts/data not
in the TOC, whether or not that vault has Git metadata. Installed dependency directories,
Python environments identified by `pyvenv.cfg`, Python caches, generated
`data_output`/`design_output` and compiled executables are excluded.

Generic names such as `output`, `outputs`, `build` or `cache` do not establish that a declared
source is disposable.
Dot folders such as `.obsidian` stay excluded, except the CSS snippets the manifest lists:
they are declared inputs of the document.

Extracted source archives carry a source inventory so rebuilding without `.git` preserves
the same selection.
Their build configuration is a complete, schema-valid configuration of the original
build's settings, including `input.styleFolder`, so a rebuild from the extracted archive
validates.

Symlinks are rejected, never followed outside that boundary.

The generator's package source,
project manifest, uv lockfile, README and platform bootstrap wrappers accompany
the vault snapshot.

Implementation-source selection follows the owning Git-tracked source tree and any explicitly
included new implementation files, schemas, and other source resources needed by this build,
not a recursive copy of the checkout.

Do not collect build products, environments, installed dependencies, caches, unrelated binaries,
other project inputs or worker state. A selected external/non-Git vault remains supported;
its declared source boundary must not be silently reduced to visible chapters alone.

Original attachments have one embedded payload owner shared by reader downloads and source
reproduction. Source packaging must not embed another full copy of those bytes.

Compression or references are packaging only: downloaded evidence is byte-identical to the
supplied original,
and the downloaded ZIP remains a complete, ordinary reproducible archive. Missing or corrupt
payloads produce explicit errors rather than incomplete successful downloads.

With source embedding, reader assets use `obs-asset:` references into a descriptor map.
Each descriptor declares `archivePath`, `mime` and original-byte `sha256`; its owning ZIP
member is stored once with ZIP deflate compression.

The download remains that complete ZIP, not a thin archive requiring sidecars. Browsers
hydrate references with native decompression
and digest validation to local Blob URLs; reviewed-save retains descriptors and the ZIP,
not those process-local URLs.

Missing members, unsupported/encrypted compression, malformed ZIP metadata and digest
mismatches fail explicitly. This transport changes no authored
input semantics and does not make archived originals the authority for edited model state.

The embedded ZIP is a generic compressed source store, not an adapter-specific attachment
mechanism. Its central directory owns member paths and sizes; do not serialize another file
inventory or raw/base64 member bodies into the reader.

The complete ordinary ZIP can be downloaded for source/configuration authoring outside the
HTML. There is no source-file
browser or configuration editor in the reader or Settings.

Explicit attachment links can download one selected member after local decompression and
integrity validation through the same generic owner. Individual downloads preserve the
original bytes and basename; source/script files are downloads, not executable previews.
A missing or corrupt selected member fails explicitly, without a successful empty download.

An adapter-supported input refresh must not require downloading or extracting this archive.
The reader parses a newly selected input and calculates from current canonical records.

On successful replacement, the canonical update and the changed owning archive entry must
be committed at one revision; old unreferenced bytes and decoded URL caches are superseded,
not retained as a second payload. Cancellation or failure preserves the previous revision.

Saving/reopening the HTML must retain that same current owner and permit another update.
Compressed storage is not a reason to require a source-archive authoring workflow.

Effective configuration and a rebuild script accompany the sources; bundle instructions give
explicit vault/settings paths for the wrappers rather than using the checkout's default spec.

The generator checkout must be available; an incomplete archive is an error.

Hidden files, external absolute-path dependencies and OS/Python executables are not collected.
Non-hidden source files are included without secret detection; authors must inspect the archive
before distributing it.

Command authorization is recorded but rerunning commands still requires an explicit
rebuild flag. uv/Python and downloadable locked dependencies remain prerequisites; this is a
source reproduction bundle, not an offline VM or a promise of byte-identical timestamps.

Network resources and external tools are not made offline by this flag.

Never execute embedded files automatically.

## Canonical reference presentation

### Named icon resources

Icons are one projection of the shared [[semantic-assets]] index, not a separate
catalog or glyph/drawing map in behavior code. That owner specifies typed assets,
named references, nested inheritance, state defaults, semantic colors, confined
file dependencies and validation. Its generic `artifact.assetIndex` replaces the
unreleased icon-only configuration proposal.

File-resource coloration and its bounded monochrome opt-in follow that same
owner; Base references use its shared semantic-identifier profile.

Existing Obsidian Base declarations reference semantic identifiers through
`obsHtml.icon.name` and composed `obsHtml.icons[*].name`. Identifiers are not
restricted to today's built-in icon-name enum. An artifact author can change the
catalog or select another named resource without editing application code.

Do not introduce a separate inline-Markdown dialect for this change; ordinary
file-image references retain their existing resource semantics.

Asset appearance never selects an action, navigation target, download mode,
accessible label or permission. Those remain explicit properties of the
existing control/action declaration. Link-backed icon declarations may explicitly
request `download: true` or `false`.

Preserve the legacy `snapshot` link slot's download behavior when that field is
omitted, normalize this compatibility at
the input boundary, and use an explicit download declaration in maintained
adapter output. Changing or overriding its glyph must not change its behavior.

The existing action owner supplies active/inactive or other declared state to
that resolver; state selection does not duplicate action or record semantics.
Typography/layout and application of the resolved colors remain stylesheet
responsibilities. Resource ownership and source reproduction follow [[semantic-assets]].

Base property declarations may add `obsHtml.reference: {label: [item.id, item.name]}`.

The ordered field names are resolved on the existing linked canonical note, not on the
referencing row. `file.name` denotes its source filename stem and `title` its subject title.
The input remains an ordinary wiki/Markdown link or list of links; presentation never
copies target records into relation rows.

Optional `reference.metadata: [item]` selects canonical metadata fields/subtrees
by prefix, preserving the target's field order and displaying labels relative to
the selected subtree. The default retains all ordinary note metadata; projections
may exclude transport/query wrappers without runtime knowledge of those wrappers.

`properties.<field>.obsHtml.detail: true` makes that reference eligible for the explicitly
declared `views[0].obsHtml.details: columns` mode. Missing references are empty, not
synthetic subject documents. Existing `displayName` labels apply to group captions too.

`views[0].obsHtml.wide: true` marks table composition only; [[artifact-ui]] owns orientation.

Icon slots use `properties.<slot>.obsHtml.icon` with a catalog resource `name`
and accessible `label`, plus one of `linkProperty` with `unavailable`,
`action: sourceArchive`, a fixed action ID registered by the explicitly selected
trusted runtime (with `unavailable` when its `card` declares a `link`, see
[Trusted floating-content actions](#trusted-floating-content-actions)), `help`
(plain text), or `unavailable` alone.

`helpProperty` may replace static help text with the canonical row's field,
using its existing trusted rich-metadata projection rather than flattening
formatted values or links to plain text. Optional `help` appends a shared
plain-text explanation. Presentation reuses the shared rich-hover owner defined
in [[artifact-ui]], not a separately styled instruction popup.

Help alone remains informational;
an action ID selects an existing handler, never an authored callback.
Compact slot width is owned by `artifact.tableIconWidthPixels`
in the shared configuration/schema.

Link properties consume existing safe rendered links, sourceArchive consumes the
existing original-source download owner, and unavailable slots remain explicitly disabled.
An authored action ID never grants runtime registration or script trust.
Default appearances, including unavailable slots, are owned by the icon catalog,
not this contract or an action-name switch.

An unavailable slot retains its explicit reason and disabled state when its appearance is
overridden.
Tooltips identify the operation as well as any row-specific instructions.
An import/replacement icon is not a claim that the browser reproduces an external
export. Icon changes preserve the same trusted action and shared rich-hover help.

### Compact declarative table presentation

A view may explicitly disable pagination (including its item totals/footer), request
equal initial widths for its displayed subject columns, and select a smaller point
size for expanded subject details. These are schema-validated `obsHtml` view options;
omitting them preserves the existing table defaults.

Shared bounds/defaults belong in configuration and its schema, not duplicated
constants.
The declarations are `pagination: false`, `columnSizing: equal`, and
`detailFontSize: 10` (points) under the view's `obsHtml` mapping.
One final labelled property may compose several existing icon actions in a compact
cell; it retains each action's accessibility and unavailable state.

This is data-only composition of existing actions, not executable authored content.
Its `obsHtml.icons` array contains existing icon declarations; singular `icon`
remains supported. They are alternative declarations for the same property.
Canonical reference metadata selection supports a human-facing ordered allowlist
without copying the selected values into relation notes.

Missing fields are omitted; safe URLs remain links and rendered descriptions are not
repeated as raw HTML.
Blank strings, nulls and empty collections are also omitted from detail metadata;
false and zero remain meaningful values.

Record-backed tables can use the existing artifact query catalog for field discovery
when it describes the same population; other tables retain their own field scopes.

An explicitly empty property `displayName` suppresses its visible header text while
retaining an accessible field label. It does not erase the field identity or its values.
`showEmptyDetailTabs: true` under the view's `obsHtml` preserves every displayed
detail-subject column as a tab; tabs without permitted content are visibly disabled
and cannot be activated.

The omitted/default setting retains the existing omission behavior for other artifacts.
`screenPageBreaks: false` under the view's `obsHtml` keeps the current table page,
including expanded details, together on one variable-height HTML sheet. This is a
screen pagination hint, not text `nowrap` or a change to row pagination. PDF retains
normal physical-paper splitting and repeated headers.

`compact: true` opts into shared compact table sizing: tightly measured composed
icon slots/header controls and the configured compact minimum text-column width.
It does not suppress overflow or remove controls; ordinary tables retain their
configured ordinary minimum. Both minima are schema-bounded shared configuration.

An opt-in `properties.<field>.obsHtml.editable: true` uses the canonical note's
already-declared property editor directly in the table cell. The owning editable
property, validation/projection and save lifecycle remain authoritative; a table
does not create another editable value or trigger downloads on edits.

`editor: singleLine` alongside `editable: true` requests a one-line text input.
An existing multiline canonical value is preserved on untouched focus/blur;
only an actual edit commits the input's one-line text through the existing owner.
`singleLine: true` on a reference property requests an ellipsized one-line cell label, with
the complete text retained as its accessible text and hover title.

`properties.<field>.obsHtml.leadingLines: [otherField, ...]` composes a plain cell:
each listed property of the same row renders as its own line, in order, before the
property's own value.

A missing, null, blank or empty leading value renders no line, so rows without it show no
empty first line. The leading properties remain ordinary
row properties; the column keeps its own field identity for sorting, filtering and
property editors, and canonical values are never concatenated or rewritten.

It is presentation only, shared by screen, static and printed tables, and applies to
plain and `linkProperty` values. Combining it with `icon`, `icons`, `reference` or
`editable` is rejected. Example: `description: {obsHtml: {leadingLines: [evidenceDate]}}`
shows the evidence date above its description.

An optional `reference.linkProperty` resolves a safe source URL on the referenced
record for its displayed label. Explicit subject-tab activation still selects
the tab; the identifier inside that subject uses the source URL. Raw identity
fields remain unchanged. `obsHtml.linkProperty` on an ordinary property similarly
links its label through another field on the same record.

Decided 29 Oct 2026: a `linkProperty` that resolves to an external URL is replaced
by linking the record's own note, which carries the `url`
(reference notes: obs's input model, Reference notes and link text, [[obs-specification|obs's specification]]). The URL then appears only in the hover card. Until
migrated, such a `linkProperty` is a lint warning.

An optional `reference.metadataFormats` mapping gives displayed metadata fields
an explicit `format` (`html` or `table`) and an optional raw `source` field path.
Missing raw sources retain the original plain value; canonical fields are never
rewritten by formatting. HTML is parsed inertly and copied through a finite
passive-element/attribute allowlist.

Sole entity-escaped markup may be decoded through its bounded HTML/XML layers; ordinary
percentages and prose are not
percent-decoded. A table source is the existing data-only `{headers, rows}` shape,
with scalar cells; its markup-valued cells use the same safe HTML formatter.
Empty structured tables are omitted rather than replaced by flattened schema text.

Imported image references use explicit non-fetching placeholders. Only absolute
HTTP(S) and mail links remain active; relative source links are not guessed
against the generated artifact's location.
Formatting is shared by initial, filtered, printed and canonically refreshed
subject details and must not add another query or canonical data owner.

Table `obs-table-set-row-keys` presentation events may restrict a mounted view to
known row identities (or reset with null); this independent presentation scope
intersects, never replaces, its authored and interactive queries. Static exports
inherit the same scope without altering canonical records.

## Shared source-archive link

The authored Markdown link target `obs-source:archive` invokes the same current
archive-download action as the cover and Settings/exports controls; it never
addresses a second archive or a separately cached copy. The source owner resolves
the current bytes at activation, including after a committed evidence replacement.

When the initial build omits the archive, generated artifact guidance must not claim
that a complete source ZIP is available or expose a broken download. A later
partial evidence archive retains its truthful partial label.

## Trusted runtime and canonical replacement

The builder alone may select one regular vault-local JavaScript bundle with
`--trusted-runtime-bundle ID=PATH`. Markdown, Base definitions, metadata, ordinary
assets and uploaded evidence never authorize executable code.

Through the core the builder names it with `obs-document --adapter html --adapter-option
trusted-runtime-bundle=ID=PATH`, PATH relative to the vault: `adapter.json` declares the option
as a vault-file option, so the core refuses a file outside the vault and passes the resolved file
(obs cli.md, Adapter options). The Document never carries the bundle.

The bundle registers its selected ID and unique fixed actions before
`obs-html-ready`; missing, malformed,
duplicate and mismatched registration fails visibly. Authored action declarations
are data, not callbacks. Source reproduction records the original explicit selection
in its rebuild command; it does not infer trust from the extracted manifest.

`obsArtifact.stageCanonicalTransaction({expectedRevision, notes, assetChanges,
sourceChanges})` stages a detached complete canonical-note candidate and its single
owning ZIP. The framework validates safe content, identities, attachment references
and confined source changes before returning a revision-checked commit handle.

The commit updates notes, archive and descriptors together, invalidates derived views
and emits one canonical change. Parsing, source projection, compression, validation,
cancellation or revision failure leaves the prior state unchanged. This does not
relax the narrower existing-field property-editor contract.

Runtime text uses text nodes and allowlisted semantic content, never uploaded HTML
assigned as executable markup. Selected action handlers artifact synchronous throws and
asynchronous rejection through the same visible application error notice.

Dynamic Sankey fences may declare `sourceNote`, an exact extensionless vault-relative
Markdown identity whose `frontmatter.graph` supplies current graph data.

The collector includes that confined dependency even without a navigation/link
reference. Manifest
`canonicalNotes` selects other exact canonical dependencies. These declarations select
data only, never scripts; traversal, missing files, duplicate declarations, aliases and
slug guesses are not dependency identities.

### Trusted floating-content actions

Builder-selected trusted actions may use a shared framework floating-content host;
its presentation and browser fallbacks belong to [[artifact-ui]]. This is a reusable
host for safe content and controls, not a new authored scripting language, form DSL,
workflow engine or parallel canonical store.

Markdown still selects registered action IDs and owns instructions, source links and
content-aware composition. Uploaded files,
ordinary metadata and Base declarations do not gain permission to execute rendering code.

A Base action icon may add `card` to turn its activation into a guided action card
instead of an immediate file picker. The declaration contains only bindings to the
row's existing canonical fields and fixed labels:

required `title` and `submit` (the Apply label), optional `subject` (field shown as the card
subject), `content` (fields rendered as rich instructions through the shared rich-metadata
owner), `link` (field whose safe rendered links open the source in a new tab), and
`input: {property, label}` (one required, nonblank text value prefilled from that
field).

Unknown keys are rejected. The card shows the source link first, above the
subject and instructions, because the reader opens the source before following them.

A declared `link` is a precondition of the card: a row whose `link` field renders no
safe link gets no card, and its action slot is disabled (not dispatched) with the
icon's authored `unavailable` reason, like other unavailable slots. An action icon
whose card declares `link` therefore requires `unavailable`.

The author decides which rows qualify through the row data and this declaration; the
generator does not recognise particular rows. Choosing or dropping a file only stages it.
Apply passes `{noteId, file, values, signal, artifact}` to the same registered
action handler; `values` contains only the declared input property. The handler,
not the card, validates and commits.

Actions without `card` keep the existing file-picker behavior.
`obsArtifact.openFloatingWindow({use, title, mount, returnFocus})`
shows trusted content in the artifact's one [[artifact-ui#Floating window|floating window]];
`use` names the header ("Evidence collection" for guided action cards).

`mount(container, session)` mounts trusted controls once and the session exposes `active`,
`mode`, an abort `signal` and idempotent `close()`, which removes that content from the
window's history (closing the window when nothing else is left).

A floating action's draft remains transient until explicit submission. File bytes
and required accompanying metadata are validated and staged through the existing
revision-checked canonical transaction, then committed together.

Failure, cancellation or stale revision leaves the previous canonical model and
archive
unchanged. Closing a card must not allow pending asynchronous work to commit later.
Successful submission uses the existing canonical-change and unsaved-HTML owners.
Do not serialize helper windows, draft files or a second copy of evidence payloads.

### Current source projection after a trusted update

A complete source archive must rebuild the updated canonical result, not an earlier
normalized vault. The trusted adapter stages its current generated Markdown and
original-input filename mappings together with the evidence replacement.

The generic transaction validates vault-local source changes, preserves unrelated
members, updates
the source inventory and commits all bytes at the same checked canonical revision.

Source Markdown contains ordinary local attachment paths, never process-local Blob URLs.
An archive first created by upload without initial sources remains a partial evidence
archive; it must not acquire complete-source instructions or claims.

## Shared input as this adapter presents it

obs's input model states these rules for any adapter; each passage below is the HTML adapter's
part of the obs input-model section it is named after, moved from there.

### Core and adapter namespaces

An adapter's options live in its own namespace, `obs` followed by its name in camelCase
(`obsHtml` for obs-html).

### Document home and abstract

Document links to external things go through reference notes; the only direct external link is
the one inside the [[artifact-ui#Link hover card|hover card]].

Two-column blocks (`|||`): their paged/mobile presentation is owned by [[artifact-ui]].

The generation field `generator` of this adapter reads, for example:

```text
name:    obs-html
version: v0.3-2-g1a2b3c4
commit:  1a2b3c4
```

Which front pages exist, their order and titles are declared by the
[artifact presentation profile](#artifact-presentation-profile); their paged rendering and
Contents are owned by [[artifact-ui]].

  [[artifact-ui#What counts as a change]] owns which edits are content changes.

### Profiles

The presentation keys of the [artifact presentation profile](#artifact-presentation-profile)
are today's single, implicit profile. First one-pager pieces (4 Nov 2026): a manifest without a
TOC (Home alone) and `heading: compact` in the presentation profile.

### Registers

`obsHtml.macros` is rejected with a migration message; obs's spec vault's `registers.base` is
the starter.

Keys under `obs:` and `obsHtml:`, which Obsidian ignores, make obs_html render the rich register,
for example one row per marked paragraph instead of one per note.

Filters, columns, titles and grouping are authored in the view. obs_html owns no default columns or
filters for registers.

- Rendering the `obsHtml` keys inside Obsidian itself (a plugin) is a possible later step, not
  planned.

### Chapter content

A link to a record-only note shows its [[artifact-ui#Link hover card|hover card]] and, when
clicked, the note in the [[artifact-ui#Floating window|floating window]] (reference notes, decided
29 Oct 2026).

Clicking a document link to an unlisted note shows it in the floating window; the page stays.
A direct browser fragment still opens an unlisted note in the same reader with a Home breadcrumb
and browser history.

### Callouts

Registers, cards, hover cards and profiles select callouts by type from the shared record
projections.

Callout presentation follows [[artifact-ui]].

- Each type declares its HTML presentation (rail icon as today's marks, box, collapsed box or
  inline badge); nothing is inferred from content.

- `important` keeps its established obs_html meaning: an untitled emphasis box for key
  takeaways, not Obsidian's alias of `tip`.

### Remaining chapter content

Figure numbering itself is the manifest's `obsHtml.figures` decision
([Artifact presentation profile](#artifact-presentation-profile)); `obsHtml.figures.labelPlural`
names the plural of merged references (default `Figures`).

Confirmed default (4 Nov 2026, `spec/backlog/review-figure-defaults.md`):

- CDN-delivered Plotly stays opt-in and shows an explicit notice when the network fails:
  the embedded default keeps one HTML file interactive offline, so only an author who
  accepts the network dependency trades size for it, and a reader never sees a silent gap.

SVG figure interaction and visual-parity requirements belong to [[artifact-ui]].

See [[artifact-ui]] for Sankey diagram interaction and print behavior.

### Markdown body and frontmatter

Obsidian's `cssclasses` are projected onto that note's rendered container, as [[artifact-ui]]
places it. Styles come only from the CSS snippets the manifest lists (see
[Artifact presentation profile](#artifact-presentation-profile)); obs-html gives the classes no
meaning of its own.

### Mark tags

The icon rail and optional box of mark tags are owned by [[artifact-ui#Content sections]] (box
opt-in per kind: `artifact.borderedTags` in `cfg.json`).

### Base fences

A `note` projection adds the artifact's own note fields to the canonical note rows (see
[[generic-tables]]).

The separate artifact UI's notion of an assigned value is not a redefinition of standard Base
equality.

The option is `obsHtml.expandProperties`.

The Base option is `obsHtml.viewProjection`.

Artifact-only additions live under a top-level `obsHtml` mapping so normal Bases syntax remains
portable and can expand independently.

An `obs.members` entry's `label` is exposed only as the derived `obsHtml.label` cell.

Artifact-specific Base behavior is permitted only under `obsHtml`.

The core evaluates Bases filters in Python when it builds the Document. The browser evaluates
again because readers can edit Base definitions and canonical values in the open HTML; the
browser Query view reports an unsupported filter as invalid.

  `obsHtml.maxRows` is an optional positive integer specifying the approximate number of
  ordinary body rows in the table's vertical viewport. It constrains visual height only;
  page size, filtering, grouping, sorting, and row membership remain independent. Omission
  preserves the unbounded current table presentation, and invalid values or unsupported
  `obsHtml` properties fail validation.

### Input model

Source selection
and runtime defaults are owned by [[cli]] and [[configuration]], respectively.

### Reference notes and link text

note without one opens in the [[artifact-ui#Floating window|floating window]] and the page
  stays put.

- A hover shows a card with the note's `description` and its external link
  ([[artifact-ui#Link hover card|hover card]]).



## The next Obsidian extension as this adapter presents it

The HTML adapter's part of obs's input-model section Next Obsidian extension, moved from there.

### Next Obsidian extension

The side-by-side adapter stages normalized notes in `.obs-html/vault` and writes
`artifact-obs-html.html`.

Display math written inside a paragraph stays inside that paragraph: obs_html writes it as
phrasing content shown as a block, since HTML allows no block element inside a paragraph.

Reader presentation of the side-by-side edition follows [[artifact-ui]].

The side-by-side edition's figure numbers use `obsHtml.figures.numbering: chapter`.

See [[artifact-ui]] for the side-by-side edition's presentation.

## Cover metadata and history

obs's input model (Cover metadata and history) owns the fields, their validation and the
`documentMetadata` and `documentHistory` records. How this adapter presents them moved here from
there.

These values populate the cover;
empty strings, nulls and empty lists/mappings are treated as unassigned and omitted.

Title/subtitle and
cover fields are excluded from the residual Key / Value table to avoid repeating their presentation.

The organization remains manifest-owned even though its value is displayed on the cover and
page frame rather than repeated in that table.

Revision labels and dates appear in History, not on the cover.

Both normal HTML
and document/PDF views render the same canonical history through the shared query-table engine
(`obs.records: documentHistory`, columns `version`, `date`, `author`, `change`).

In document view it occupies its own section
after the abstract and before Contents; normal Home displays it after the abstract.

## Reviewed copy

obs's input model (Reviewed copy) owns the property-editor contract. This adapter's reviewed
copy, its review state and the runtime that commits edits moved here from there.

The initial use is a text explanation for a finding. Edits must update dependent views
and survive standalone HTML download and reopen,
together with existing review comments and decisions. Serialize the current canonical
data safely, without stale duplicate values, executable input or copied transient DOM.

This extends the existing reviewed-copy export rather than adding a competing saver.
The concrete editor declaration and validation belong to the implementation ticket.

The canonical reviewed-copy model also saves the last successfully applied global filter
expression as finite reader state, separate from notes and review annotations.
Reopening compiles that expression through the shared query runtime and restores the actual
Filter input and open bar. Empty or closed filters reopen unfiltered with the bar closed.

Invalid input drafts never replace the last valid expression in saved state.
If a stored expression cannot compile, show it and its error in the open Filter bar rather
than silently discarding it. Fresh generation remains unfiltered; appearance always starts
Light with Pages. [[artifact-ui#What counts as a change]] owns whether reader state marks
the artifact changed.

An absent trusted view selection means an empty selection. Registering that empty
default does not add a persisted override.

Returning to an implicit empty default removes its override; explicitly saved
selections retain their loaded baseline. Initialization must not rebase genuine
reader or canonical edits made while other startup work is still finishing.

Reviewed reader state also retains visible column keys in display order, keyed by the
table's stable identity. How resized column widths are classified is owned by
[[artifact-ui#What counts as a change]].

The table owner validates and rebuilds these settings against its current column catalog;
saved rows or rendered DOM
are not a second data source. Invalid settings show a table diagnostic, not silent success.

Fresh artifacts keep authored defaults. Table-local filter, grouping, sorting, pagination,
expansion and edited base definitions remain session-only in this bounded contract.

Enter or leaving the editor commits text; query fields and metadata caches are refreshed.
Saved copies replace the artifact data island from the canonical model, not rendered inputs.
Markdown and HTML are never interpreted in
edited text; stale per-property rendered metadata is invalidated.

The runtime applies an edit and its selected projection as one transaction. It validates all
target notes and fields, checks values against the existing field types, and rebuilds every
affected query record before changing canonical data.

Only then are all notes and records updated together, table caches invalidated, one
canonical-change notification emitted, and
the active artifact filter reapplied once.

Object values, nested arrays, undeclared fields, note creation/deletion, and HTML or figure
mutation are rejected. Projections serialize in the same reviewed-copy model as property edits.

The browser treats review annotations, per-reviewer decisions, and changes committed
through these canonical property editors as unsaved reviewed-copy state.

An artifact opened from a generated or reviewed HTML file starts clean. A semantic change marks it dirty;
reverting all changes to the loaded state clears that state. Edits that do not change a
canonical value do not make semantic review state dirty. The changed-HTML notice and unload
confirmation follow [[artifact-ui#What counts as a change]].

The artifact-level comparison also covers the current embedded source archive, when present,
through its existing archive owner rather than a second serialized payload.
Importing reviewed copies marks it dirty only when the merged comments
or decisions change.

A successful File System Access write establishes the new clean baseline; opening the save picker, cancelling it, or a
failed write does not. A browser's standard download API
provides no signal that the user accepted, completed, or retained the downloaded file, so
initiating a download does not establish a clean baseline.

The page remains dirty after download initiation; reopening the downloaded artifact starts a new clean baseline. On unload,
unsaved artifact state requests the browser's native confirmation without relying on custom text.
The Comments bar persistently explains how to save and that leaving with dirty or
unconfirmed changes risks losing them.

- A reviewed copy is a generated standalone HTML artifact whose one `obs-comments` JSON island
  holds its comments and review decisions in the core's format, created through the Comments
  bar; [Comments and the core model](#comments-and-the-core-model) says how.
- Rendered headings may receive exact-text comments but are not checklist items and carry no
  Accept or Reject decision.
- The named reviewer's state is derived across every chapter and exposed to the browser query
  model as the `review` field. The aggregate state remains a display property of each item;
  neither derived state is persisted as a second copy of reviewer decisions.
- Batch decisions use the same per-reviewer item decisions as individual actions, never
  a parallel acceptance state store. A batch rejection has one scoped comment, whose
  `batch` keeps the scope and the exact affected items. The gesture and waiting-only scope
  are owned by [[artifact-ui]].

### Comments and the core model

obs's input model owns the comment and decision format, the review semantics and the block
ids (Comments and reviews, Block node ids). This adapter owns only the mapping between them and
its page, and this section says it once.

**Where the core ends.** The core hands the adapter the Document's `comments`, the resolved
union of every overlay file. Its fields, ids, times, targets, replies and batches, and what a
decision means for an item's state, are the core's. The adapter adds no field and keeps no
second schema.

**Export.** The build writes the Document's `comments` into the `obs-comments` island
unchanged; a Document without comments gets an empty model of the same version. The page's
Comments bar maps it, in `comment-model.js`, onto the threads it shows: a root comment and its
replies, nested by `inReplyTo`, and the decisions as they are. Saving the reviewed copy maps
the threads back and writes the island in the core's format.

**Review items are blocks.** A review item is a Document block, and its review id is the
block's core id, which the rendered element carries as `data-node-id`.

- Items are derived in document order from rendered list items, table data rows,
  standalone code blocks and command outputs, figures, and paragraphs that are not inside one
  of those units; a paragraph or code block inside another unit is no second item.
- Markdown images remain part of their containing paragraph; standalone media may use a
  figure item. Visual line wrapping never creates another item.
- A row of a register or Base table is the keyed row `<table id>:<record id>`; the table's
  node id and the record id come from the build.
- An element without a core id is no item: the hidden status paragraph of a data table is the
  adapter's own, not Document content.

A decision and a whole-item comment target `{chapter, node}`; a text selection inside one item
targets that item with positions in the item's text, and a selection across items targets
the chapter with positions in the chapter's text. Nothing targets a chapter and a quote in
place of a node.

**Import.** `obs-html --extract-comments HTML` reads the island as untrusted data, never runs
the artifact, and prints a deterministic text list of its threads for triage.

With `--overlay FILE` it also writes the overlay file of the principal the file name names
(obs's input model, Overlay files): every comment and decision of the island that no other
overlay file of the manifest holds with the same payload. The core's comment schema checks it
before it is written.

An island the core's schema refuses, an entry another principal's file holds with a
different payload, and an island of the retired version 2 are input errors naming the
reviewed HTML, the island's field path and this section. Version 2 targets items by
position (`item-N`), which no Document can resolve once the text above them changes.

## Output-format statements of obs's input model

obs's input model states these rules without naming an output format; each passage below is
the HTML wording of the obs input-model section it is named after, moved from there.

### Document home and abstract

The generation `timestamp`: each committed canonical change in the HTML (for example an evidence
replacement or a description edit) sets it to the time of that change, and a saved HTML keeps that
time.

### Numeric-value notes

Authors reference an unlabelled `[[alias]]` rather than copying the number or its unit into prose.
HTML renders that link as the canonical value followed by its unit, retaining normal note
navigation, previews and details.

Everything a query computes runs live in the HTML, so a reader's change updates it at once.

### Reference notes and link text

The link lint runs with the paragraph warnings on every build (stderr, never in the HTML).

### Remaining chapter content

The figure lint prints its warnings on stderr; none changes the HTML.

### Command-derived content

- Command output is HTML-escaped and rendered as preformatted content; it cannot inject
  artifact markup or styles. It is `<pre><code>`, like every other code block.
