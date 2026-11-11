"""The PDF inspection tools, run on the fixture Document's printed PDF."""
import base64
import json
from pathlib import Path

import pytest
from PIL import Image, ImageChops
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, StreamObject

from conftest import FIXTURE
from obs_html import cli, pdf_inspect


PIXEL = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
LETTER = (612, 792)  # The fixture's paper, in PDF points.


@pytest.fixture(scope="module")
def printed(pdf_browser, tmp_path_factory) -> Path:
    """The fixture Document printed once by this repository's own PDF path."""
    folder = tmp_path_factory.mktemp("printed")
    (folder / "images").mkdir()
    (folder / "images" / "logo.png").write_bytes(base64.b64decode(PIXEL))
    pdf = folder / "artifact.pdf"
    cli.main([str(FIXTURE), str(pdf)])
    return pdf


@pytest.mark.browser
def test_render_writes_the_page_as_a_raster_at_the_scale(printed, tmp_path, capsys) -> None:
    output = tmp_path / "page.png"
    pdf_inspect.main(["render", str(printed), "--page", "1", "--scale", "1.5", "--output", str(output)])
    with Image.open(output) as image:
        assert image.size == (918, 1188)
        darkest, lightest = image.convert("L").getextrema()
        assert darkest < lightest  # Printed content, not a blank page.
    assert f"Wrote {output} (918x1188 px, page 1, scale 1.5)." in capsys.readouterr().out


@pytest.mark.browser
def test_render_names_the_pages_a_pdf_has(printed, tmp_path, capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        pdf_inspect.main(["render", str(printed), "--page", "99", "--output", str(tmp_path / "x.png")])
    assert exit_info.value.code == 2
    _refused(capsys, printed, "--page")


def _refused(capsys, source: object, field: str) -> None:
    """A refusal names where it comes from: the message starts with the source and the field."""
    error = capsys.readouterr().err
    assert f"\n{source}: {field}: " in f"\n{error}", error


@pytest.mark.browser
def test_crop_renders_a_region_in_points_from_the_top_left(printed, tmp_path, capsys) -> None:
    page, region = tmp_path / "page.png", tmp_path / "region.png"
    pdf_inspect.main(["render", str(printed), "--page", "1", "--scale", "2", "--output", str(page)])
    pdf_inspect.main(["crop", str(printed), "--page", "1", "--box", "100,50,300,250",
                      "--scale", "2", "--output", str(region)])
    with Image.open(page) as whole, Image.open(region) as part:
        assert part.size == (400, 400)
        aligned = whole.convert("L").crop((200, 100, 600, 500))
        shifted = whole.convert("L").crop((204, 104, 604, 504))
        assert _mean_difference(aligned, part) < 0.5 < _mean_difference(shifted, part)
    assert f"Wrote {region} (400x400 px, page 1, box 100,50,300,250 pt, scale 2)." in capsys.readouterr().out


def _mean_difference(first: Image.Image, second: Image.Image) -> float:
    """Mean grey difference in 0-255; anti-aliasing differs slightly between renders."""
    histogram = ImageChops.difference(first.convert("L"), second.convert("L")).histogram()
    return sum(level * count for level, count in enumerate(histogram)) / sum(histogram)


@pytest.mark.browser
@pytest.mark.parametrize("box, in_pdf", [("1,2,3", False), ("300,50,100,250", False), ("0,0,700,100", True)])
def test_crop_refuses_a_box_it_cannot_cut(printed, tmp_path, capsys, box, in_pdf) -> None:
    """A malformed box is the argument's fault; one outside the page names the PDF."""
    with pytest.raises(SystemExit):
        pdf_inspect.main(["crop", str(printed), "--page", "1", "--box", box, "--output", str(tmp_path / "x.png")])
    _refused(capsys, printed if in_pdf else "obs-html-inspect", "--box")
    assert not (tmp_path / "x.png").exists()


@pytest.mark.browser
def test_text_prints_the_page_text_in_reading_order(printed, capsys) -> None:
    pdf_inspect.main(["text", str(printed), "--page", "1"])
    lines = capsys.readouterr().out.splitlines()
    assert lines.index("Fixture document") < lines.index("Authors") < lines.index("Ada, Lin")
    assert not any("\r" in line for line in lines)


@pytest.mark.browser
def test_text_writes_the_named_file(printed, tmp_path, capsys) -> None:
    output = tmp_path / "page-1.txt"
    pdf_inspect.main(["text", str(printed), "--page", "1", "--output", str(output)])
    assert "Fixture document\n" in output.read_text(encoding="utf-8")
    assert capsys.readouterr().out == f"Wrote {output} (page 1 text).\n"


@pytest.mark.browser
def test_paths_lists_the_vector_paths_in_points_from_the_top_left(printed, capsys) -> None:
    pdf_inspect.main(["paths", str(printed), "--page", "1"])
    inspection = json.loads(capsys.readouterr().out)
    assert (inspection["page"], inspection["size"]) == (1, list(LETTER))
    paths = inspection["paths"]
    assert paths and all(segment["type"] in {"move", "line", "curve", "close"}
                         for path in paths for segment in path["segments"])
    for path in paths:
        x0, y0, x1, y1 = path["bounds"]
        assert 0 <= x0 <= x1 <= LETTER[0] and 0 <= y0 <= y1 <= LETTER[1]
    # The running header's rule: a thin filled bar across the top margin, not at the bottom.
    rules = [path for path in paths if path["fill"] and path["bounds"][3] - path["bounds"][1] < 1
             and path["bounds"][2] - path["bounds"][0] > 400]
    assert any(path["bounds"][1] < 72 for path in rules)
    assert rules[0]["segments"][0] == {"type": "move", "point": rules[0]["bounds"][:2]}


@pytest.mark.browser
def test_annotate_draws_labelled_boxes_onto_a_raster(printed, tmp_path, capsys) -> None:
    page, marked = tmp_path / "page.png", tmp_path / "marked.png"
    pdf_inspect.main(["render", str(printed), "--page", "1", "--scale", "2", "--output", str(page)])
    pdf_inspect.main(["annotate", str(page), "--box", "100,100,200,150=rule", "--box", "50,300,80,330",
                      "--scale", "2", "--colour", "#0000ff", "--output", str(marked)])
    with Image.open(page) as before, Image.open(marked) as after:
        before, after = before.convert("RGB"), after.convert("RGB")
        assert after.size == before.size
        assert after.getpixel((200, 250)) == after.getpixel((399, 299)) == (0, 0, 255)  # Box edges, in pixels.
        assert after.getpixel((100, 600)) == (0, 0, 255)  # The second box's left edge.
        inside = (210, 210, 390, 290)
        assert ImageChops.difference(after.crop(inside), before.crop(inside)).getbbox() is None
        above = (200, 170, 400, 198)
        assert ImageChops.difference(after.crop(above), before.crop(above)).getbbox()  # The label.
    assert f"Wrote {marked} (2 marks on {page})." in capsys.readouterr().out


@pytest.mark.browser
@pytest.mark.parametrize("option, value", [("--colour", "reddish"), ("--box", "0,0,9999,10")])
def test_annotate_refuses_marks_it_cannot_draw(printed, tmp_path, capsys, option, value) -> None:
    page = tmp_path / "page.png"
    pdf_inspect.main(["render", str(printed), "--page", "1", "--output", str(page)])
    arguments = {"--box": "1,1,2,2", "--colour": "red", option: value}
    with pytest.raises(SystemExit):
        pdf_inspect.main(["annotate", str(page), "--box", arguments["--box"], "--colour", arguments["--colour"],
                          "--output", str(tmp_path / "marked.png")])
    _refused(capsys, page if option == "--box" else "obs-html-inspect", option)


@pytest.mark.browser
def test_every_tool_writes_only_the_files_it_is_named(printed, tmp_path, capsys) -> None:
    folder = tmp_path / "out"
    folder.mkdir()
    pdf_inspect.main(["render", str(printed), "--page", "1", "--output", str(folder / "page.png")])
    pdf_inspect.main(["crop", str(printed), "--page", "1", "--box", "0,0,100,100", "--output", str(folder / "c.png")])
    pdf_inspect.main(["text", str(printed), "--page", "1"])
    pdf_inspect.main(["paths", str(printed), "--page", "1"])
    pdf_inspect.main(["annotate", str(folder / "page.png"), "--box", "1,1,9,9", "--output", str(folder / "a.png")])
    assert sorted(path.name for path in folder.iterdir()) == ["a.png", "c.png", "page.png"]
    assert sorted(path.name for path in printed.parent.iterdir()) == ["artifact.pdf", "images"]


@pytest.mark.browser
def test_raster_tools_need_an_output(printed, capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        pdf_inspect.main(["render", str(printed), "--page", "1"])
    assert exit_info.value.code == 2
    _refused(capsys, "obs-html-inspect render", "arguments")


@pytest.mark.parametrize("arguments, source, field", [
    (["text", "{tmp}/missing.pdf", "--page", "1"], "{tmp}/missing.pdf", "PDF"),
    (["render", "{pdf}", "--page", "1", "--output", "{tmp}/absent/page.png"], "{tmp}/absent/page.png", "--output"),
    (["render", "{pdf}", "--page", "1", "--output", "{tmp}/page.raster"], "{tmp}/page.raster", "--output"),
    (["paths", "{pdf}", "--page", "1", "--output", "{pdf}"], "{pdf}", "--output"),
])
@pytest.mark.browser
def test_paths_are_explicit_and_checked(printed, tmp_path, capsys, arguments, source, field) -> None:
    def fill(text: str) -> str:
        return text.format(tmp=tmp_path, pdf=printed)

    with pytest.raises(SystemExit) as exit_info:
        pdf_inspect.main([fill(argument) for argument in arguments])
    assert exit_info.value.code == 2
    _refused(capsys, fill(source), field)
    assert sorted(path.name for path in tmp_path.iterdir()) == []
    assert printed.stat().st_size > 0


def test_paths_include_paths_inside_form_xobjects(tmp_path, capsys) -> None:
    """Chromium prints no forms today; a hand-built page draws a square through one, moved 100 pt."""
    writer = PdfWriter()
    page = writer.add_blank_page(200, 200)
    form = StreamObject()
    form.set_data(b"0 0 m 10 0 l 10 10 l 0 10 l h f")
    form.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Form"),
                 NameObject("/BBox"): ArrayObject([NumberObject(0), NumberObject(0), NumberObject(10),
                                                   NumberObject(10)])})
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/XObject"): DictionaryObject({NameObject("/Fm0"): writer._add_object(form)})})
    content = StreamObject()
    content.set_data(b"q 1 0 0 1 100 50 cm /Fm0 Do Q")
    page[NameObject("/Contents")] = writer._add_object(content)
    pdf = tmp_path / "form.pdf"
    writer.write(pdf)
    pdf_inspect.main(["paths", str(pdf), "--page", "1"])
    [square] = json.loads(capsys.readouterr().out)["paths"]
    assert square["bounds"] == [100, 140, 110, 150]  # 50 pt up from the bottom of a 200 pt page.


def test_a_file_that_is_no_pdf_is_named(tmp_path, capsys) -> None:
    html = tmp_path / "artifact.html"
    html.write_text("<!doctype html>", encoding="utf-8")
    with pytest.raises(SystemExit):
        pdf_inspect.main(["text", str(html), "--page", "1"])
    _refused(capsys, html, "PDF")
