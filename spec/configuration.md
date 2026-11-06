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
- `input.styleFolder` optionally selects a vault-relative style module for a project.
  Its value is a folder containing `style.css`; null selects the packaged generic module.
  A command-line style selection overrides this project setting for one build; the source
  archive never records it ([[input-model#Optional reproduction archive]]).
- The `timings` section holds the relative and absolute thresholds a stage must both
  exceed before a build warns about it; baselines and stage names are owned by
  [[architecture#Build stage timings]].

See [[cli]] and [[architecture]].
