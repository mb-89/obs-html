"""An artifact carries only the runtime its Document uses, and opens cleanly without the rest.

Reader: whoever changes which runtime a reader feature ships (obs_html/features.py) or what one
runtime script calls in another.

Each Document here uses some features and not others; its artifact must carry none of the
others' code or elements, and must open, show every chapter and run what it carries with no page
error and no console error: a script left out leaves no call behind (architecture.md, Rendering and
runtime).
"""
import pytest

from artifacts import artifact_html
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.features import FEATURES, included
from test_features import PUGH, SANKEY, plain, with_figure, with_guided_card
from obs_html.render import render

pytestmark = pytest.mark.browser

# Document -> the selector of what its features draw once its chapter shows.
DOCUMENTS = {
    "plain": (plain, None),
    "decision figure": (lambda: with_figure("pugh", PUGH), ".figure-pugh-ready"),
    "Base table": (with_guided_card, "[data-data-table]"),
    "Sankey figure": (lambda: with_figure("sankey", SANKEY), ".sankey-node"),
}


@pytest.mark.parametrize("name", DOCUMENTS)
def test_a_document_without_a_feature_ships_none_of_it(name: str) -> None:
    source = DOCUMENTS[name][0]()
    html = render(source, load_config())
    shipped = {feature.key for feature in included(decode_artifact_data(html), False)}
    for feature in FEATURES:
        if feature.key in shipped:
            continue
        assert not any(f'id="{element}"' in html for element in feature.elements), (feature.key, name)
        assert f'id="canary-{feature.key}"' not in html, (feature.key, name)


def test_the_reader_reaches_table_code_only_through_the_tables_feature() -> None:
    """The reader's Base-table code is the tables feature's script (tables.js): a Document without a
    Base table carries none of it, and one with a table carries it once, attached by the reader's
    core (architecture.md, Rendering and runtime)."""
    without, with_table = (render(source, load_config()) for source in (plain(), with_guided_card()))
    for name in ("renderChapterTables", "tableSearchHits", "savedPresentations", "richMetadata"):
        assert name not in without, name
        assert with_table.count(f"const {name} = ") == 1, name
    assert "globalThis.obsTables = " not in without
    assert with_table.count("globalThis.obsTables = ") == 1


@pytest.mark.parametrize("name", DOCUMENTS)
def test_an_artifact_without_some_features_opens_without_errors(name: str, tmp_path, reader_browser) -> None:
    build, drawn = DOCUMENTS[name]
    artifact = tmp_path / "artifact.html"
    artifact.write_text(artifact_html(build()), encoding="utf-8")
    page = reader_browser.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.goto(artifact.as_uri())
    page.wait_for_function("document.documentElement.dataset.artifactStatus === 'ready'")
    for slug in page.evaluate("obsArtifact.records.filter(record => record.slug).map(record => record.slug)"):
        page.evaluate("slug => obsArtifact.activateChapter(slug)", slug)
        page.wait_for_selector("[data-active-chapter]")
    if drawn:
        page.evaluate("slug => obsArtifact.activateChapter(slug)", "one")
        page.wait_for_selector(f"[data-active-chapter] {drawn}")
    assert errors == []
