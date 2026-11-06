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
  ([[#Declared style]]), and no settings key names a style module folder.
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
of `--config`.

The merged settings are validated against
`cfg.schema.json`: a key it does not know, or a value outside its limits, fails the build naming
the vault's file below the vault root (`spec/cfg.json`), the field path and the remedy, as a
failure in the `--config` file names that file. A renamed key (`report`) is refused there as in
`--config`.

The vault's file travels in the source archive, so a rebuild from the archive applies
it; `--config` does not.

## Declared style

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

See [[cli]] and [[architecture]].
