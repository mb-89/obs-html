# Agent guide

This repository is obs's HTML adapter, the component `obs-html`. obs's `AGENTS.md` applies here in full:
its public safety policy, authored-prose rule, invariants and commit identity. This file adds only
what is specific to the adapter. The [README](README.md#core) owns how the adapter depends on a core
release and how its tests reach the core's checkout.

## Commands

Run from this folder:

```powershell
uv run obs-html --help
uv run pytest
```

The spec artifact's reading checks hold the rows of features.md that name them; the module
docstring is their reference: `uv run pytest test/test_parity_browser.py`.
[test/parity/features.md](test/parity/features.md) lists every feature of this adapter and how it
differs from the interim adapter it replaced; its gate, `test/parity/test_parity_table.py`, says
what each status needs.

After `cmp` finds two builds of the same source different, run this to name what changed in a
field report:

```powershell
uv run python test/compare_builds.py BEFORE.html AFTER.html
```

For a change that must leave obs's other pages as they were, run this and quote its output in the
field report; obs's spec fetches its two remote badge images on each side, so a fetch that fails on
one side only shows in that page's report:

```powershell
uv run python test/unchanged_output.py [--base REF] [--head REF] [--keep FOLDER]
```

## Browser tests

A browser test takes its page and its artifact from the shared fixtures, runs on the headless shell unless the named full-Chromium set holds it, adds no init script and reads timings only from the artifact's own performance marks; [test/structure/test_quality.py](test/structure/test_quality.py) refuses one that does not.

## Learnings

- Right: if pytest setup on Windows fails while creating its required component symlink with `WinError 1314`, report the blocker; wrong: substitute a junction or enable Developer Mode.
- Right: serve a temporary artifact from loopback when the integrated browser rejects `file://` outside a trusted folder, then stop the server; wrong: leave a helper server running.
- Right: use escaped output or UTF-8 file output for rendered Unicode in Windows PowerShell; wrong: assume the current console encoding accepts it.
- Right: preserve both source nodes' block anchors when combining a heading and paragraph; wrong: test only that the old separate tags disappeared.
- Right: render a paragraph heading's paragraph through the shared paragraph renderer; wrong: render only its inline text and lose marks and register records.
- Right: keep a manifest chapter title as a heading before converting the note body's deepest heading; wrong: turn a chapter's only title into a paragraph heading.
- Right: test arrows after explicitly opening Home and include it in the reader's walk; wrong: assume the top-level chapter page list contains Home.
- Right: check authored prose against the local public-safety terms before committing; wrong: assume a common word cannot match a private term.
- Right: scope a top-level chapter assertion before its nested-section wrappers; wrong: count descendant markup as if it belonged to the parent.

## Reader features

A new reader feature, part, table view option or figure kind follows
[Rendering and runtime](spec/architecture.md#rendering-and-runtime) and
[Interactive engineering figures](spec/artifact-ui.md#interactive-engineering-figures).
