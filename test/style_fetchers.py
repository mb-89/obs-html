"""The fake style fetcher: serves a declared style's commit from files a test gives it, never the network.

Reader: whoever writes a test that renders a Document declaring a style (spec/configuration.md,
Declared style). test_styles.py holds it to the same contract as the real git fetcher.
"""
from __future__ import annotations

from pathlib import Path

from obs_html.declared_style import DeclaredStyles


class FakeFetcher:
    """Fetches ``url`` at ``ref`` from ``trees[(url, ref)]``, a mapping of POSIX path to text, and
    records each call in ``calls``; for an unknown commit it returns a reason, as for an unreachable one."""

    def __init__(self, trees: dict[tuple[str, str], dict[str, str]] | None = None) -> None:
        self.trees = trees or {}
        self.calls: list[tuple[str, str]] = []

    def fetch(self, url: str, ref: str, destination: Path) -> str | None:
        self.calls.append((url, ref))
        if (url, ref) not in self.trees:
            return f"the fake fetcher holds no commit {ref} of {url}"
        for name, text in self.trees[(url, ref)].items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return None


def fake_styles(cache: Path, trees: dict[tuple[str, str], dict[str, str]] | None = None) -> DeclaredStyles:
    """Declared styles fetched by a FakeFetcher into ``cache``, a test's own folder."""
    return DeclaredStyles(FakeFetcher(trees), cache)
