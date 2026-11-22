# Configuration

obs-html's settings have their defaults in its packaged `adapters/html/src/obs_html/cfg.json`,
with accepted structure and limits in the adjacent `cfg.schema.json`. The core's own settings
(`input`, `execution`) are the core's configuration, `src/obs/config.schema.json`. A vault
overrides either in its project configuration ([[#Vault settings]]).

These are repository-relative owner locations, not vault attachments. This note owns the
configuration design principles and how the layers merge; the
[parity table](../test/parity/features.md) records each settings key against the interim
adapter's.

## Principles

- Configuration is JSON for deterministic parsing and native JSON Schema support.
- Every field is explicit and schema-documented.
- Unknown fields are rejected to catch misspellings.
- Packaged configuration is complete and supplies defaults for every project.
- Project configuration is partial: mappings merge recursively, while arrays and scalar
	values replace their packaged defaults.
- The merged effective configuration is validated against the complete packaged schema.
- Vault conventions shared by every source, such as the `manifest.md` filename, belong in
	the core's configuration.
- Reusable filter presets may be packaged as defaults; project-specific preset arrays belong
	in the vault override and replace those defaults.
- Document decisions belong to the document, not to configuration: paper and margin are the
	manifest's `obsHtml.print` ([[input-model#Artifact presentation profile]]).
- Configuration owns only the cross-cutting catalogue such decisions choose from
	(`artifact.print.paperSizes`) and the physical limits in `cfg.schema.json`.
- A removed configuration key that moved to the manifest is rejected with a diagnostic naming
	its manifest replacement.
- A renamed configuration key (`report` became `artifact`) is rejected, in the packaged or
	`--config` file as in the vault override, with a diagnostic naming the old key, the new key
	and the file. No alias reads the old key.
- The maximum distinct-value/populated-record ratio for enumerated Filter facets is a packaged
	default that projects may override.
- Semantic presentation resources use one optional project asset-index selection.
  The [[semantic-assets]] owner defines reference, inheritance, state and color
  semantics; the shared configuration/schema owns its default and path constraints.
  Do not maintain separate project icon and color registries.
- The style is not configuration: the manifest declares it as `obs.style`
  ([[#Declared style]]), and no settings key names a style module folder. Local themes are no
  setting either: obs-html finds them in a fixed folder of the build machine ([[#Local themes]]).
- The `timings` section holds the relative and absolute thresholds a stage must both
  exceed before a build warns about it; baselines and stage names are owned by
  [[architecture#Build stage timings]].

## Vault settings

A vault sets obs-html's settings for every build in its project configuration, `cfg.json` in the
manifest's folder.

The core reads that file on every build,
applies its own keys (`input`, `execution`) and carries every other top-level key unread in the
Document's `projectConfig` (obs's architecture, Project configuration), so the settings reach the
artifact through the Document alone, in a one-call build as in `obs-html` on a Document.

The settings merge in this order, each layer recursively over the one before (mappings merge,
arrays and scalar values replace):

1. the packaged `src/obs_html/cfg.json`;
2. `--config FILE`, a direct call's settings file;
3. the Document's `projectConfig.settings`, the vault's file.

`--config` is an override of the packaged file, and the vault's file wins over it. A
project-specific `artifact.filterPresets` array therefore replaces the packaged presets and those
of `--config`. `artifact.checkExceptions` merges like every array, the vault's list replacing that
of `--config`; the local file of exceptions is no layer of the settings but adds its exceptions to
them ([[architecture#Exceptions]]).

The merged settings are validated against
`cfg.schema.json`: a key it does not know, or a value outside its limits, fails the build naming
the vault's file below the vault root (`spec/cfg.json`), the field path and the remedy, as a
failure in the `--config` file names that file. A renamed key (`report`) is refused there as in
`--config`.

The vault's file travels in the source archive, so a rebuild from the archive applies
it; `--config` does not.

## Declared style

obs's components note (`spec/design_input/components.md`) replaces the style named by its address: a
style becomes a component the manifest names by name alone, installed on the machine by obs's component
command, and obs-html no longer fetches a style itself. Until its implementation lands, this
section describes the build as it is.

obs-html styles a build with one style module, chosen in this order:

1. `--style FOLDER`, for this one build. The source archive never records it
	([[input-model#Optional reproduction archive]]), so a rebuild from the archive uses the
	declared style.
2. The style the Document declares: its `style`, which the core takes from the manifest's
	`obs.style` (`url`, `ref`, a full commit SHA, and optionally `path`; obs's architecture,
	Declared style).
3. The packaged `generic` module.

Whichever is chosen takes the same place: its `style.css` follows the packaged base stylesheet,
and the CSS snippets the manifest lists in `obsHtml.cssSnippets` follow it
([[input-model#Artifact presentation profile]]).

The declared module is fetched once per commit: obs-html fetches `url` at `ref` with git into
a cache folder named by the commit, `obs-html/styles/<ref>` in the user's cache folder
(`$XDG_CACHE_HOME` or `~/.cache` on Linux, `~/Library/Caches` on macOS, `%LOCALAPPDATA%` on
Windows), never inside a checkout.

A build whose commit is cached fetches nothing, so the
network is reached once per commit on a machine. A fetch is complete or absent: a failed one
leaves nothing in the cache. `path` names the module's folder inside the fetched tree; an
absolute `path` or one with `..` is refused before any fetch.

Every failure is an input error
of the Document's manifest: a fetch that fails names `style.url` and `style.ref`, with the
remedy to check the declaration or to pass `--style FOLDER`; a `path` that leaves the tree or
holds no `style.css` names `style.path`. No other style replaces a declared one that fails.

`src/obs_html/declared_style.py` holds the fetcher, the one door to a style repository; tests
replace it with a fake and never reach the network.

## Local themes

A build machine may hold themes of its own, which no committed file names: each is a named layer
of colours and rules over the style module, which a page carries beside Default
([[artifact-ui#Styling]]).

obs-html's local folder is `obs-html` in the user's configuration folder: `$XDG_CONFIG_HOME` or
`~/.config` on Linux, `~/Library/Application Support` on macOS, `%APPDATA%` on Windows.
`OBS_HTML_LOCAL_FOLDER`, where set and not empty, names that folder instead: the folder that holds
`themes` and `local.json` itself, not its parent.

Each folder in its `themes` folder whose name does not start with a dot is a theme named by its
folder; files and dot-named entries are skipped. No `themes` folder, or an empty one, is no theme.

The start theme is named in `local.json` beside `themes`, `{"startTheme": "<name>"}`, checked by
the packaged `src/obs_html/local.schema.json`. Without the file, the start theme is Default
(`default`). A `local.json` that is no JSON object, has another key, or names neither `default`
nor a theme fails the build, naming `obs-html local folder: local.json`, the field and the themes
there.

A theme is checked when it is read. Every refusal is an input error whose source names the file
from the local folder (`obs-html local folder: themes/<name>/assets.json`,
`obs-html local folder: themes/<name>/style.css`, or `obs-html local folder: themes/<name>` for
the folder and its entries), never an absolute path, with the field and the remedy:

| Part | Rule | A break names |
|---|---|---|
| Name | 1 to 32 lowercase letters, digits and dashes, starting with a letter or digit, and not `default` | `themes/<name>`, field `name` |
| Entries | `assets.json`, `style.css` and dot-named entries only, each file optional | `themes/<name>`, field the entry's name |
| `assets.json` | Valid by the packaged `assets.schema.json`; holds only children of `color`, each a colour the packaged `assets.json` declares, each `value` a `{light, dark}` pair. An icon, an appearance, a single hex value, a `ref` or a colour the packaged index does not declare is refused. | `themes/<name>/assets.json`, field `assets.color.children.<name>` |
| `style.css` | No page geometry, as a style module's `style.css` holds none ([[#Declared style]]) | `themes/<name>/style.css`, field the declaration or at-rule, as for a style module |
| At-rules | Only `@media` and `@supports`; `@import`, `@font-face`, `@page`, `@keyframes`, `@layer`, `@container` and every other at-rule are refused. Figure styles scope `@container`; a theme does not, as a container query answers to the elements the packaged stylesheet makes containers, which no theme owns | `themes/<name>/style.css`, field `@<keyword>` |
| URLs | Every `url()` and `src()` holds a `data:image/` URI; `image-set()` and `-webkit-image-set()` are refused. A logo is such an image in the theme's CSS, for example a monochrome SVG as `mask-image` on `.cover-organization` painted with `background-color: var(--color-text)`, so it follows the appearance. | `themes/<name>/style.css`, field `url` |
| Text | It parses as CSS with no parse error and holds no `</style` | `themes/<name>/style.css`, field `line <n>` |
| Fonts | Named only, in `--font-content`, `--font-interface` and `--font-code` or in rules; never embedded, as no `@font-face` is read | (the at-rule row) |
| Colours | No colour literal in a declaration's value outside `light-dark()`: a hash token, a CSS named colour, or a function `rgb`, `rgba`, `hsl`, `hsla`, `hwb`, `lab`, `lch`, `oklab`, `oklch` or `color` that is not an argument of `light-dark()`. A colour is `var(--color-…)`, `light-dark(<light>, <dark>)`, `currentcolor` or `transparent`. `color-mix()` is no literal of its own: the colours it mixes are checked as any value's, so a mix of colours that follow the appearance passes and a mix that holds a literal is refused. | `themes/<name>/style.css`, field `line <n>` |
| Appearance | No `color-scheme` declaration and no `prefers-color-scheme` media feature: the appearance is the reader's | `themes/<name>/style.css`, field `color-scheme` or `prefers-color-scheme` |

A theme's `style.css` reaches the page scoped to the theme's name, without its comments
([[artifact-ui#Styling]]).

Every render of `obs-html` on a Document reads the folder: a DESTINATION, a `.pdf` DESTINATION and
`--check`, so every build through `obs-document --adapter html` on that machine.
`--build-own-spec` reads none: the adapter's specification is the same page on every machine, and
obs's specification attaches it.

The settings have two layers of style. The committed layer is the packaged `generic` module or
the declared style ([[#Declared style]]); the local layer is this folder. Nothing in a vault, its
settings, its manifest, the Document, the source archive or its build record names a local theme
or says whether one exists: obs-html finds them by the fixed folder alone. A rebuild from the
archive on another machine has Default only. A page that a command fence builds with obs-html on
that machine is that fence's output and carries the machine's themes, like any page built there.

A page carries the themes of the machine that built it, as text: their names, colours and rules,
never a path. A theme's rules, like its name and colours, enter no Document, source archive or
message the page shows; a refusal of its `style.css` names the theme only on the machine that
holds it. The exposure and provenance checks read them as any other part of the page, so a local
term in a theme's name warns, or refuses under `artifact.refuseProvenance`. Such a finding names
its place (`HTML line <n>`, such as a line of `style-choice-styles`, or
`artifact-data reading.styles[<n>]`). Its remedy is the local file of exceptions
([[architecture#Exceptions]]), which may cover a `local-term` finding, or a theme folder name
without the term.

A machine without the folder builds every page byte for byte as before. On a machine with it,
`OBS_HTML_LOCAL_FOLDER` set to an empty folder builds a page without them, for a page meant for
readers elsewhere.

`src/obs_html/style_choice.py` reads the folder and checks what it holds; `render()` takes what it
chose and reads no folder itself.

See [[cli]] and [[architecture]].
