"""Metadata renders from the Document's ``field`` nodes, never from the authored strings.

The core parses every nonempty frontmatter string into one ``field`` node of inline nodes
(obs markdown-frontmatter.md, Document node); the cover, the title page, the running header and
the frontmatter panels render those nodes, so the strings in ``attrs.metadata`` are data only.
"""
import base64
import inspect
import json
import re
import subprocess
import sys
from importlib.resources import files

from conftest import PIXEL, built_once
from obs_html.artifact_data import decode_artifact_data
from obs_html.config import load_config
from obs_html.render import render


CONFIG = load_config()
SUBTITLE = "A **bold** $x^2$ ![Mark](media/pixel.png)"


def _vault_document(folder, core_root) -> None:
    """A Document the core builds from a manifest and a chapter whose metadata holds Markdown and TeX."""
    vault = folder / "vault"
    (vault / "media").mkdir(parents=True)
    (vault / "media" / "pixel.png").write_bytes(base64.b64decode(PIXEL))
    (vault / "manifest.md").write_text(
        f'---\ntitle: Fields\nsubtitle: "{SUBTITLE}"\ndocument type: "*Spec*"\n'
        'product:\n  name: "**Widget**"\nconfidentiality: "`internal`"\nauthors: ["**Ada**", Lin]\n'
        'organization: Org & Co\n---\n- [[chapter]]\n', encoding="utf-8")
    (vault / "chapter.md").write_text(
        '---\nformula: "$a+b$"\nraw: "<b>raw</b>"\nrank: 2\nsource: "https://example.org/a?b=1&c=2"\n---\n'
        '# Chapter\n\nText.\n', encoding="utf-8")
    (vault / "extra.md").write_text(  # A note no chapter includes: a record-only note.
        '---\nrelated: "see [[chapter]]"\nbadge: "![Mark](media/pixel.png)"\n---\nExtra.\n', encoding="utf-8")
    run = [sys.executable, "-m"]
    subprocess.run([*run, "obs.capabilities", "--notes", str(core_root / "spec" / "capabilities"),
                    "--output", str(folder / "capabilities.json")], check=True)
    subprocess.run([*run, "obs.document", "--source", str(vault / "manifest.md"),
                    "--document", str(folder / "document.json"),
                    "--capability-reference", str(folder / "capabilities.json")], check=True)


def _model(tmp_path_factory, core_root) -> dict:
    """The island of the core's Document whose metadata strings no longer say what the nodes say:
    whatever renders from a string shows the tampered text."""
    folder = built_once(tmp_path_factory, "metadata-fields", lambda path: _vault_document(path, core_root))
    document = json.loads((folder / "document.json").read_text(encoding="utf-8"))
    frontmatter = next(node for node in document["manifest"]["abstract"] if node["type"] == "markdown-frontmatter")
    for metadata in (document["manifest"]["metadata"], frontmatter["attrs"]["metadata"]):
        metadata.update({"subtitle": "tampered", "document type": "tampered", "product": {"name": "tampered"}})
    chapter = document["chapters"][0]
    for metadata in (chapter["metadata"], chapter["content"][0]["attrs"]["metadata"]):
        metadata["formula"] = "tampered"
    for record in document["records"]:
        if record["type"] == "note":
            record["fields"] = {name: "tampered" if isinstance(value, str) else value
                                for name, value in record["fields"].items()}
    return decode_artifact_data(render(document, CONFIG))


def test_a_subtitle_renders_bold_text_a_formula_and_an_image_from_its_nodes(tmp_path_factory, core_root) -> None:
    model = _model(tmp_path_factory, core_root)
    home = next(note for note in model["notes"] if note["slug"] == "home")["html"]
    subtitle = home.split('<div class="document-subtitle">', 1)[1].split("</div>", 1)[0]
    assert subtitle.startswith("A <strong>bold</strong> <span class=\"math inline\"><math")
    assert "<mi>x</mi>" in subtitle and "<mn>2</mn>" in subtitle
    assert subtitle.endswith(f'<img src="data:image/png;base64,{PIXEL}" alt="Mark">')
    assert '<p class="cover-type"><em>Spec</em></p>' in home
    assert '<dd><strong>Ada</strong>, Lin</dd>' in home
    assert "tampered" not in home


def test_the_running_header_and_the_page_frame_read_the_metadata_html(tmp_path_factory, core_root) -> None:
    metadata = _model(tmp_path_factory, core_root)["document"]["metadataHtml"]
    assert metadata["document type"] == "<em>Spec</em>"
    assert metadata["product.name"] == "<strong>Widget</strong>"
    assert metadata["confidentiality"] == "<code>internal</code>"
    assert metadata["authors"] == "<strong>Ada</strong>, Lin"
    assert metadata["organization"] == "Org &amp; Co"


def test_the_frontmatter_panel_renders_field_nodes_and_values_without_one_as_text(
        tmp_path_factory, core_root) -> None:
    note = next(note for note in _model(tmp_path_factory, core_root)["notes"] if note["slug"] == "chapter")
    panel = note["frontmatterHtml"]
    assert panel["formula"].startswith('<span class="math inline"><math') and "<mi>a</mi>" in panel["formula"]
    assert panel["raw"] == "&lt;b&gt;raw&lt;/b&gt;"
    assert panel["rank"] == "2"
    assert panel["source"] == '<a href="https://example.org/a?b=1&amp;c=2">https://example.org/a?b=1&amp;c=2</a>'


def test_a_record_only_note_renders_its_values_from_its_record_field_nodes(tmp_path_factory, core_root) -> None:
    note = next(note for note in _model(tmp_path_factory, core_root)["notes"] if note["slug"] == "extra")
    panel = note["frontmatterHtml"]
    assert panel["related"] == 'see <a class="internal-link" href="#chapter">Chapter</a>'
    assert panel["badge"] == f'<img src="data:image/png;base64,{PIXEL}" alt="Mark">'


METADATA_RENDERERS = ("_frontmatter", "_cover", "_frontmatter_html", "_field_html", "_definition_html")
"""The render.py functions that turn metadata into HTML; each reads field nodes or shows text."""
PYTHON_PARSING = re.compile(r"\b(?:re|INLINE|WIKILINK|IMAGE_TAG|NOTE_HREF|urllib|urlparse|unquote|mathml)\b"
                            r"|\b_(?:inline|frontmatter_link|metadata_image|note_href)\(|renderInline|MarkdownIt")
JS_PARSING = re.compile(r"RegExp|\.(?:match|matchAll|replace|replaceAll|split|search)\(|new URL\(|markdown|"
                        r"/[^/\n*]+/[gimsuy]*\.(?:test|exec)\(", re.IGNORECASE)


def test_no_metadata_renderer_parses_markdown_tex_or_urls_out_of_a_string() -> None:
    """Requirement: metadata renders from nodes. The running header's script and the page frame's
    header and footer block in pages.js render the metadata's display HTML the same way."""
    import obs_html.render as module
    found = [f"render.py {name}: {match[0]!r}" for name in METADATA_RENDERERS
             for match in PYTHON_PARSING.finditer(inspect.getsource(getattr(module, name)))]
    package = files("obs_html")
    pages = package.joinpath("pages.js").read_text(encoding="utf-8")
    frame = pages[pages.index("const metadataHtml = data.document.metadataHtml;"):pages.index("sheet.append(footer);")]
    for name, source in (("running-header.js", package.joinpath("running-header.js").read_text(encoding="utf-8")),
                         ("pages.js page frame", frame)):
        found += [f"{name}: {match[0]!r}" for match in JS_PARSING.finditer(source)]
    assert not found, ("adapters/html/src/obs_html: a metadata renderer parses a string; render the value's "
                       f"field node instead (obs markdown-frontmatter.md, Document node): {found}")


TITLE_RENDERERS = ("_callout", "_cards", "_attr_nodes", "_metric_quantity")
"""The render.py functions that render callout titles, card titles and metric labels and values;
each reads inline nodes (obs capabilities/callouts, capabilities/cards-metrics, Document node)."""


def test_no_callout_or_card_renderer_parses_a_title_or_label_out_of_a_string() -> None:
    """Requirement: titles and labels render from nodes, in render.py and in the metric slots
    cards.js fills."""
    import obs_html.render as module
    found = [f"render.py {name}: {match[0]!r}" for name in TITLE_RENDERERS
             for match in PYTHON_PARSING.finditer(inspect.getsource(getattr(module, name)))]
    cards = files("obs_html").joinpath("cards.js").read_text(encoding="utf-8")
    slot = cards[cards.index("const slot = card.querySelector("):cards.index("slot.append(")]
    found += [f"cards.js metric slot: {match[0]!r}" for match in JS_PARSING.finditer(slot)]
    assert not found, ("adapters/html/src/obs_html: a callout or card renderer parses a string; render the "
                       f"title's or label's inline nodes instead (obs capabilities/markdown.md, Document nodes): {found}")
    assert "label.innerHTML = metric.labelHtml" in slot, "cards.js: render a metric label from its labelHtml"
