# Configuration

Cross-project defaults are owned by `src/obs_html_interim/cfg.json`, with accepted
structure and limits in its adjacent `cfg.schema.json`.
The optional vault override is described by `src/obs_html_interim/project.schema.json`.
These are repository-relative owner locations, not vault attachments. This note owns only
configuration design principles.

## Principles

- Configuration is JSON for deterministic parsing and native JSON Schema support.
- Every field is explicit and schema-documented.
- Unknown fields are rejected to catch misspellings.
- Packaged configuration is complete and supplies defaults for every project.
- Project configuration is partial: mappings merge recursively, while arrays and scalar
	values replace their packaged defaults.
- The merged effective configuration is validated against the complete packaged schema.
- Vault conventions shared by every source, such as the `manifest.md` filename, belong in
	configuration.
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
- The style is not configuration: the manifest declares it ([[#Declared style]]). The interim's
  `input.styleFolder`, a vault-relative style module folder in its project configuration, has no
  obs-html counterpart; a vault that set it declares the module as `obs.style` instead.
- The `timings` section holds the relative and absolute thresholds a stage must both
  exceed before a build warns about it; baselines and stage names are owned by
  [[architecture#Build stage timings]].

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
