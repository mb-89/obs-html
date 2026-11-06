"""obs-html-inspect: inspect a PDF without a viewer, so print output can be verified automatically."""
from __future__ import annotations

import argparse
import ctypes
import json
import sys
from pathlib import Path
from typing import Sequence

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image, ImageColor, ImageDraw, ImageFont, UnidentifiedImageError

from obs_html.errors import InputError, Parser

PROG = "obs-html-inspect"

EPILOG = """Every input and output is a path you name: nothing is written anywhere else, no folder
is created, and text and paths print to stdout unless --output names a file. Pages are numbered
from 1. Coordinates are PDF points (1/72 inch) from the top-left corner of the page, x to the
right and y down; at --scale S one point is S raster pixels.

Examples:
  obs-html-inspect render artifact.pdf --page 1 --output page-1.png
  obs-html-inspect crop artifact.pdf --page 1 --box 72,72,300,200 --output title.png
  obs-html-inspect text artifact.pdf --page 2
  obs-html-inspect paths artifact.pdf --page 2 --output page-2-paths.json
  obs-html-inspect annotate page-1.png --box 72,72,300,200=title --scale 2 --output marked.png

paths prints JSON: the page size and, per path, its bounds, fill and stroke colour (RGBA
0-255, null when not painted), stroke width, fill rule and segments (move, line, curve with
two control points and the end point, close). Paths inside form XObjects are included.
"""


def _open_page(pdf: Path, number: int) -> pdfium.PdfPage:
    try:
        document = pdfium.PdfDocument(pdf)
    except pdfium.PdfiumError as error:
        raise InputError(pdf, "PDF", f"cannot be read as a PDF ({str(error).rstrip('.')})",
                         "Pass a PDF file") from error
    if not 1 <= number <= len(document):
        raise InputError(pdf, "--page", f"is {number}, but the PDF has {len(document)} pages",
                         f"Pass --page from 1 to {len(document)}")
    return document[number - 1]


def render_page(pdf: Path, number: int, scale: float, output: Path) -> tuple[int, int]:
    """Write page NUMBER of PDF as a raster at SCALE pixels per point; return its size."""
    image = _open_page(pdf, number).render(scale=scale).to_pil()
    image.save(output)
    return image.size


Box = tuple[float, float, float, float]


def parse_box(text: str, option: str) -> Box:
    """X0,Y0,X1,Y1 as four numbers with X0 < X1 and Y0 < Y1."""
    try:
        x0, y0, x1, y1 = (float(part) for part in text.split(","))
    except ValueError:
        raise InputError(PROG, option, f"is {text!r}, not X0,Y0,X1,Y1", "Pass four comma-separated "
                         "numbers, for example 72,72,300,200") from None
    if not (x0 < x1 and y0 < y1):
        raise InputError(PROG, option, f"is {text}, an empty box", "Pass X0 < X1 and Y0 < Y1")
    return x0, y0, x1, y1


def crop_page(pdf: Path, number: int, box: Box, scale: float, output: Path) -> tuple[int, int]:
    """Write the BOX region of page NUMBER as a raster, rendered at SCALE; return its size."""
    page = _open_page(pdf, number)
    width, height = page.get_size()
    x0, y0, x1, y1 = box
    if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
        raise InputError(pdf, "--box", f"is {_number_list(box)}, not inside page {number} "
                         f"(0,0,{width:g},{height:g} pt)", "Pass a box within the page")
    image = page.render(scale=scale, crop=(x0, height - y1, width - x1, y0)).to_pil()
    image.save(output)
    return image.size


def page_text(pdf: Path, number: int) -> str:
    """The text of page NUMBER in the order pdfium reads it, with \\n line breaks."""
    text = _open_page(pdf, number).get_textpage().get_text_range()
    return "\n".join(text.replace("\r\n", "\n").replace("\r", "\n").splitlines()) + "\n"


Matrix = tuple[float, float, float, float, float, float]
SEGMENTS = {pdfium_c.FPDF_SEGMENT_MOVETO: "move", pdfium_c.FPDF_SEGMENT_LINETO: "line",
            pdfium_c.FPDF_SEGMENT_BEZIERTO: "curve"}
FILL_RULES = {pdfium_c.FPDF_FILLMODE_ALTERNATE: "evenodd", pdfium_c.FPDF_FILLMODE_WINDING: "nonzero"}


def _matrix(handle) -> Matrix:
    raw = pdfium_c.FS_MATRIX()
    pdfium_c.FPDFPageObj_GetMatrix(handle, raw)
    return raw.a, raw.b, raw.c, raw.d, raw.e, raw.f


def _then(inner: Matrix, outer: Matrix) -> Matrix:
    """The matrix that applies INNER, then OUTER."""
    a, b, c, d, e, f = inner
    A, B, C, D, E, F = outer
    return a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F


def _colour(getter, handle) -> list[int]:
    channels = [ctypes.c_uint() for _ in range(4)]
    getter(handle, *channels)
    return [channel.value for channel in channels]


def _path(handle, matrix: Matrix) -> dict:
    """One path object; MATRIX maps its points to the inspection's coordinates."""
    a, b, c, d, e, f = matrix

    def point(segment) -> list[float]:
        x, y = ctypes.c_float(), ctypes.c_float()
        pdfium_c.FPDFPathSegment_GetPoint(segment, x, y)
        return [round(a * x.value + c * y.value + e, 3), round(b * x.value + d * y.value + f, 3)]

    segments: list[dict] = []
    points: list[list[float]] = []
    curve: list[list[float]] = []
    for index in range(pdfium_c.FPDFPath_CountSegments(handle)):
        segment = pdfium_c.FPDFPath_GetPathSegment(handle, index)
        kind = SEGMENTS[pdfium_c.FPDFPathSegment_GetType(segment)]
        points.append(point(segment))
        if kind == "curve":  # pdfium splits a curve into three segments: two control points, the end.
            curve.append(points[-1])
            if len(curve) == 3:
                segments.append({"type": "curve", "points": curve})
                curve = []
        else:
            segments.append({"type": kind, "point": points[-1]})
        if pdfium_c.FPDFPathSegment_GetClose(segment):
            segments.append({"type": "close"})
    fill_mode, stroked = ctypes.c_int(), ctypes.c_int()
    pdfium_c.FPDFPath_GetDrawMode(handle, fill_mode, stroked)
    width = ctypes.c_float()
    pdfium_c.FPDFPageObj_GetStrokeWidth(handle, width)
    xs, ys = [x for x, _ in points] or [0.0], [y for _, y in points] or [0.0]
    return {
        "bounds": [min(xs), min(ys), max(xs), max(ys)],
        "fill": _colour(pdfium_c.FPDFPageObj_GetFillColor, handle) if fill_mode.value else None,
        "stroke": _colour(pdfium_c.FPDFPageObj_GetStrokeColor, handle) if stroked.value else None,
        "strokeWidth": round(width.value, 3) if stroked.value else None,
        "fillRule": FILL_RULES.get(fill_mode.value),
        "segments": segments,
    }


def page_paths(pdf: Path, number: int) -> dict:
    """The vector paths of page NUMBER in points from its top-left corner, as JSON-ready data."""
    page = _open_page(pdf, number)
    width, height = page.get_size()
    if page.get_rotation():
        raise InputError(pdf, "--page", f"is {number}, a page rotated by {page.get_rotation()} degrees, and "
                         "paths reads unrotated pages only", "Inspect it with render")
    left, bottom, _, top = page.get_cropbox()
    paths: list[dict] = []

    def walk(handles, outer: Matrix) -> None:
        for handle in handles:
            kind = pdfium_c.FPDFPageObj_GetType(handle)
            matrix = _then(_matrix(handle), outer)
            if kind == pdfium_c.FPDF_PAGEOBJ_PATH:
                paths.append(_path(handle, matrix))
            elif kind == pdfium_c.FPDF_PAGEOBJ_FORM:
                walk([pdfium_c.FPDFFormObj_GetObject(handle, index)
                      for index in range(pdfium_c.FPDFFormObj_CountObjects(handle))], matrix)

    top_left = (1, 0, 0, -1, -left, top)  # The crop box's top-left corner becomes the origin, y down.
    walk([pdfium_c.FPDFPage_GetObject(page.raw, index)
          for index in range(pdfium_c.FPDFPage_CountObjects(page.raw))], top_left)
    return {"pdf": str(pdf), "page": number, "size": [width, height], "paths": paths}


def _paths_json(inspection: dict) -> str:
    """The paths inspection as JSON with one path per line, so it reads and diffs line by line."""
    head = json.dumps({key: value for key, value in inspection.items() if key != "paths"})[:-1]
    lines = ",\n".join(json.dumps(path) for path in inspection["paths"])
    return f'{head}, "paths": [\n{lines}\n]}}\n'


def annotate(raster: Path, marks: Sequence[tuple[Box, str]], scale: float, colour: str,
             line_width: int, output: Path) -> None:
    """Write RASTER with each mark's box drawn in COLOUR and its label above it.

    A box is in raster pixels divided by SCALE, so boxes from text or paths, in points, land on a
    page rendered at that scale."""
    try:
        ink = ImageColor.getrgb(colour)
    except ValueError:
        raise InputError(PROG, "--colour", f"is {colour!r}, not a colour",
                         "Pass a CSS colour name or #rrggbb, for example red") from None
    try:
        image = Image.open(raster).convert("RGB")
    except (OSError, UnidentifiedImageError) as error:
        raise InputError(raster, "IMAGE", f"cannot be read as a raster image ({str(error).rstrip('.')})",
                         "Pass a PNG written by render or crop") from None
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=max(12, 8 * scale))
    for box, label in marks:
        x0, y0, x1, y1 = (round(value * scale) for value in box)
        if x0 < 0 or y0 < 0 or x1 > image.width or y1 > image.height:
            raise InputError(raster, "--box", f"is {_number_list(box)}, which at scale {scale:g} is not inside "
                             f"the raster (0,0,{image.width},{image.height} px)",
                             "Pass boxes within the raster, in pixels divided by --scale")
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline=ink, width=line_width)
        if label:  # Above the box, or below it where the raster's top edge leaves no room.
            above = y0 - 2 >= font.size
            draw.text((x0, y0 - 2 if above else y1 + 2), label, fill=ink, font=font,
                      anchor="ld" if above else "lt")
    image.save(output)


def parse_mark(text: str) -> tuple[Box, str]:
    """X0,Y0,X1,Y1 with an optional =LABEL."""
    box, _, label = text.partition("=")
    return parse_box(box, "--box"), label


def check_paths(source: Path, field: str, output: Path | None, raster: bool) -> None:
    """Refuse before any work when SOURCE (the argument FIELD) or OUTPUT is not a path this
    command may use."""
    if not source.is_file():
        raise InputError(source, field, "does not exist or is not a file", "Pass an existing file")
    if output is None:
        return
    if not output.parent.is_dir():
        raise InputError(output, "--output", "is in a folder that does not exist, and nothing creates it",
                         f"Create {output.parent} or name an output in an existing folder")
    if output.resolve() == source.resolve():
        raise InputError(output, "--output", f"is the input {field}", "Name a different output file")
    Image.init()
    if raster and output.suffix.lower() not in Image.registered_extensions():
        raise InputError(output, "--output", "has no image suffix Pillow writes",
                         "Name a .png output (or another image suffix such as .jpg)")


def _number_list(values: Sequence[float]) -> str:
    return ",".join(f"{value:g}" for value in values)


def _parser() -> argparse.ArgumentParser:
    parser = Parser(
        prog=PROG, description="Inspect a PDF without a viewer.", epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    render = commands.add_parser("render", help="Render a page to a raster image.")
    render.add_argument("pdf", type=Path, metavar="PDF", help="PDF to read.")
    render.add_argument("--page", type=int, required=True, help="Page number, from 1.")
    render.add_argument("--scale", type=float, default=2.0,
                        help="Pixels per PDF point (default 2, which is 144 dpi).")
    render.add_argument("--output", type=Path, required=True, metavar="IMAGE",
                        help="Raster written, for example page.png.")
    crop = commands.add_parser("crop", help="Render a region of a page to a raster image.")
    crop.add_argument("pdf", type=Path, metavar="PDF", help="PDF to read.")
    crop.add_argument("--page", type=int, required=True, help="Page number, from 1.")
    crop.add_argument("--box", required=True, metavar="X0,Y0,X1,Y1", help="Region in points.")
    crop.add_argument("--scale", type=float, default=2.0, help="Pixels per PDF point (default 2).")
    crop.add_argument("--output", type=Path, required=True, metavar="IMAGE", help="Raster written.")
    text = commands.add_parser("text", help="Extract the text of a page.")
    text.add_argument("pdf", type=Path, metavar="PDF", help="PDF to read.")
    text.add_argument("--page", type=int, required=True, help="Page number, from 1.")
    text.add_argument("--output", type=Path, metavar="TEXT",
                      help="UTF-8 text file written; without it the text goes to stdout.")
    paths = commands.add_parser("paths", help="Extract the vector paths of a page as JSON.")
    paths.add_argument("pdf", type=Path, metavar="PDF", help="PDF to read.")
    paths.add_argument("--page", type=int, required=True, help="Page number, from 1.")
    paths.add_argument("--output", type=Path, metavar="JSON",
                       help="JSON file written; without it the JSON goes to stdout.")
    marks = commands.add_parser("annotate", help="Draw labelled boxes onto a raster image.")
    marks.add_argument("raster", type=Path, metavar="IMAGE", help="Raster to read, from render or crop.")
    marks.add_argument("--box", action="append", required=True, metavar="X0,Y0,X1,Y1[=LABEL]",
                       help="A box to draw, with an optional label; repeat for more.")
    marks.add_argument("--scale", type=float, default=1.0,
                       help="Raster pixels per box unit: the render's --scale for boxes in points "
                            "(default 1, boxes in pixels).")
    marks.add_argument("--colour", default="red", help="CSS colour of the marks (default red).")
    marks.add_argument("--line-width", type=int, default=3, help="Box outline in pixels (default 3).")
    marks.add_argument("--output", type=Path, required=True, metavar="IMAGE", help="Raster written.")
    return parser


def _deliver_text(content: str, output: Path | None, what: str) -> None:
    """Print CONTENT, or write it to the named OUTPUT file and say so."""
    if output is None:
        sys.stdout.write(content)
        return
    output.write_text(content, encoding="utf-8")
    print(f"Wrote {output} ({what}).")


def main(argv: Sequence[str] | None = None) -> None:
    arguments = _parser().parse_args(argv)
    try:
        annotating = arguments.command == "annotate"
        check_paths(arguments.raster if annotating else arguments.pdf, "IMAGE" if annotating else "PDF",
                    arguments.output, raster=arguments.command in {"render", "crop", "annotate"})
        if arguments.command == "render":
            width, height = render_page(arguments.pdf, arguments.page, arguments.scale, arguments.output)
            print(f"Wrote {arguments.output} ({width}x{height} px, page {arguments.page}, "
                  f"scale {arguments.scale:g}).")
        elif arguments.command == "crop":
            box = parse_box(arguments.box, "--box")
            width, height = crop_page(arguments.pdf, arguments.page, box, arguments.scale, arguments.output)
            print(f"Wrote {arguments.output} ({width}x{height} px, page {arguments.page}, "
                  f"box {_number_list(box)} pt, scale {arguments.scale:g}).")
        elif arguments.command == "text":
            _deliver_text(page_text(arguments.pdf, arguments.page), arguments.output,
                          f"page {arguments.page} text")
        elif arguments.command == "paths":
            inspection = page_paths(arguments.pdf, arguments.page)
            _deliver_text(_paths_json(inspection), arguments.output,
                          f"{len(inspection['paths'])} paths of page {arguments.page}")
        elif arguments.command == "annotate":
            marks = [parse_mark(text) for text in arguments.box]
            annotate(arguments.raster, marks, arguments.scale, arguments.colour, arguments.line_width,
                     arguments.output)
            print(f"Wrote {arguments.output} ({len(marks)} marks on {arguments.raster}).")
    except InputError as error:
        print(error, file=sys.stderr)
        raise SystemExit(2) from None
