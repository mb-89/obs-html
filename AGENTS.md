# Agent guide

This folder is the HTML adapter of the obs repository. The repository's
[AGENTS.md](../../AGENTS.md) applies here in full: its public safety policy, authored-prose rule,
invariants and commit identity. This file adds only what is specific to the adapter.

## Commands

Run from this folder:

```powershell
uv run obs-html --help
uv run pytest
```

Integrations also run the parity gate against the interim reference; its module docstring is
its reference: `uv run pytest test/test_parity_browser.py`.
[test/parity/features.md](test/parity/features.md) lists every interim feature and its status here;
its gate, `test/parity/test_parity_table.py`, says what each status needs.

## Browser tests

A browser test takes its page and its artifact from the shared fixtures, adds no init script and reads timings only from the artifact's own performance marks; [test/structure/test_quality.py](test/structure/test_quality.py) refuses one that does not.
