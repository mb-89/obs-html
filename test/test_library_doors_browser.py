"""Each browser library's door holds its contract, with the real library and with the door's fake.

Reader: whoever changes a library door (architecture.md, Library doors), a library's version, or
a door's fake (test/fakes/; test/library_fakes.py).

Every test runs twice: on a page that embeds the real library and its door as the artifact does
(obs_html/libraries.py), and on one that embeds the door's fake, as every other test's artifact
does. Each contract is what the artifact relies on: for the plotting door a chart's size, plot
area, legend, traces, events, image and purge; for the maths door its complex operations, as
Python's cmath computes them in the same principal branches, and the syntax tree of a reader's
expression; for the PDF door an attachment it finds again and the PDFs it refuses. The real PDF
library's attachment is also read back with pypdf, which no fake is held to.
"""
import base64
import cmath
import io
import math
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject

import library_fakes
from obs_html import libraries

pytestmark = pytest.mark.browser

MODES = ("real", "fake")


@pytest.fixture(scope="module")
def door_pages(tmp_path_factory, shared_reader_browser):
    """``door_page(key, mode)``: the module's one page per library and mode, holding only the door
    of the library ``key``: the library and its door, or its fake. A test draws on charts of its own."""
    pages = {}

    def door_page(key: str, mode: str):
        if (key, mode) not in pages:
            if mode == "real":
                with library_fakes.real():
                    element = libraries.element(key)
            else:
                element = library_fakes.fake(key)
            page_file = tmp_path_factory.mktemp("doors") / f"{key}-{mode}.html"
            page_file.write_text('<!doctype html><html><body style="margin: 0">'
                                 f'<div id="hosts"></div>{element}</body></html>', encoding="utf-8")
            page = shared_reader_browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(page_file.as_uri())
            pages[key, mode] = page, errors
        return pages[key, mode]
    return door_page


# A chart of its own in a host 600 px wide, as each plotting test's page script starts.
CHART = """const host = document.createElement("div"), chart = document.createElement("div");
host.style.width = "600px"; host.append(chart); document.getElementById("hosts").replaceChildren(host);
const door = obsPlotly;"""


TRACES = [{"type": "scatter", "x": [0, 1, 2], "y": [0, 1, 4], "name": "a"},
          {"type": "scatter", "x": [0, 1, 2], "y": [1, 2, 3], "name": "b"}]


@pytest.mark.parametrize("mode", MODES)
def test_the_plotting_door_draws_a_chart_of_its_size_with_its_legend_and_traces(door_pages, mode):
    page, errors = door_pages( "plotting", mode)
    drawn = page.evaluate("async (traces) => {\n" + CHART + """
        const available = door.available(), before = door.layout(chart);
        const events = [];
        await door.plot(chart, traces, {height: 450, autosize: true}, {responsive: true});
        door.on(chart, "afterplot", () => events.push("afterplot"));
        const legend = door.legend(chart);
        return {available, before, layout: door.layout(chart), traces: chart.querySelectorAll(".scatterlayer .trace").length,
            legend: legend && legend.getBoundingClientRect().width > 0, inChart: chart.contains(legend), events};
    }""", TRACES)
    assert drawn["available"] is True and drawn["before"] is None
    layout = drawn["layout"]
    assert (layout["width"], layout["height"], layout["showlegend"]) == (600, 450, True), layout
    assert 0 < layout["plot"]["width"] < 600 and 0 < layout["plot"]["height"] < 450, layout
    assert all(isinstance(layout["legend"][axis], (int, float)) for axis in ("x", "y")), layout
    assert drawn["traces"] == 2 and drawn["legend"] and drawn["inChart"], drawn
    assert errors == []


@pytest.mark.parametrize("mode", MODES)
def test_the_plotting_door_relayouts_and_says_so_through_its_events(door_pages, mode):
    page, errors = door_pages( "plotting", mode)
    changed = page.evaluate("async (traces) => {\n" + CHART + """
        await door.plot(chart, traces, {height: 450});
        const events = [];
        door.on(chart, "afterplot", () => events.push("afterplot"));
        door.on(chart, "relayout", update => events.push(["relayout", Object.keys(update).sort()]));
        await door.relayout(chart, {width: 500, height: 300});
        const sized = door.layout(chart);
        await door.relayout(chart, {"legend.x": 0.1, "legend.y": 0.9});
        const moved = door.layout(chart).legend;
        await door.relayout(chart, {showlegend: false});
        const hidden = {showlegend: door.layout(chart).showlegend, legend: door.legend(chart)};
        return {sized: [sized.width, sized.height], moved, hidden, events};
    }""", TRACES)
    assert changed["sized"] == [500, 300]
    assert changed["moved"] == {"x": 0.1, "y": 0.9}
    assert changed["hidden"] == {"showlegend": False, "legend": None}
    relayouts = [event[1] for event in changed["events"] if isinstance(event, list)]
    assert relayouts == [["height", "width"], ["legend.x", "legend.y"], ["showlegend"]], changed["events"]
    assert "afterplot" in changed["events"]
    assert errors == []


@pytest.mark.parametrize("mode", MODES)
def test_the_plotting_door_redraws_resizes_draws_an_image_and_purges(door_pages, mode):
    page, errors = door_pages( "plotting", mode)
    done = page.evaluate("async (traces) => {\n" + CHART + """
        await door.plot(chart, traces, {height: 450, autosize: true}, {responsive: true});
        await door.react(chart, traces.slice(0, 1), {height: 450, autosize: true, showlegend: true}, {responsive: true});
        const redrawn = chart.querySelectorAll(".scatterlayer .trace").length;
        host.style.width = "400px";
        await door.resize(chart);
        const resized = door.layout(chart).width;
        const image = await door.image(chart, {width: 900, height: 450});
        door.purge(chart);
        return {redrawn, resized, image: decodeURIComponent(image), purged: [door.layout(chart), door.legend(chart)]};
    }""", TRACES)
    assert done["redrawn"] == 1 and done["resized"] == 400, done
    assert done["image"].startswith("data:image/svg+xml,<svg"), done["image"][:80]
    assert 'width="900"' in done["image"] and 'height="450"' in done["image"]
    assert done["purged"] == [None, None]
    assert errors == []


# Each operation's arguments; the expected values are Python's cmath in the same principal branches.
OPERATIONS = {
    "add": [(1 + 2j, 3 - 1j)], "mul": [(1 + 2j, 3 - 1j), (-2, 0.5)],
    "pow": [(2, 0.5), (-8, 1 / 3), (-2, 3), (1j, 2), (0, 2)],
    "exp": [(1.5,), (1j * math.pi,)], "log": [(2,), (-1,), (1j,)],
    "sin": [(0.5,), (1 + 1j,)], "cos": [(0.5,), (1 + 1j,)], "tan": [(0.5,), (1 + 1j,)],
    "asin": [(0.5,), (1 + 1j,)], "acos": [(0.5,), (1 + 1j,)], "atan": [(0.5,), (2j + 0.5,)],
    "sinh": [(0.5,), (1 + 1j,)], "cosh": [(0.5,), (1 + 1j,)], "tanh": [(0.5,), (1 + 1j,)],
    "abs": [(3 + 4j,), (-2,)],
}
CMATH = {"add": lambda a, b: a + b, "mul": lambda a, b: a * b, "pow": lambda a, b: 0j if a == 0 else cmath.exp(b * cmath.log(a)),
         "abs": abs, **{name: getattr(cmath, name) for name in
                        ("exp", "log", "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh")}}
# Arguments on a branch cut, where the side a library takes may differ from cmath's: the page only
# needs each result to be no real number (equations.js takes a point only where im vanishes).
BRANCH_CUTS = [("asin", (2,)), ("acos", (-2,)), ("log", (-3,)), ("pow", (-8, 0.5))]


def close(value: complex, expected: complex) -> bool:
    return abs(value - expected) <= 1e-9 * max(1, abs(expected))


@pytest.mark.parametrize("mode", MODES)
def test_the_maths_door_computes_in_complex_numbers_on_principal_branches(door_pages, mode):
    page, errors = door_pages( "maths", mode)
    pairs = lambda arguments: [[complex(value).real, complex(value).imag] for value in arguments]
    cases = [[name, pairs(arguments)] for name, arguments_list in OPERATIONS.items() for arguments in arguments_list]
    cut = [[name, pairs(arguments)] for name, arguments in BRANCH_CUTS]
    results = page.evaluate("""([cases, cut]) => {
        const door = obsMaths;
        const made = door.complex(1, 2);
        const result = ([name, args]) => {
            const value = door.operations[name](...args.map(([re, im]) => door.complex(re, im)));
            return typeof value === "number" ? [value, 0] : [value.re, value.im];
        };
        return {available: door.available(), made: [made.re, made.im], real: door.complex(3).im,
            results: cases.map(result), cut: cut.map(result)};
    }""", [cases, cut])
    assert results["available"] is True and results["made"] == [1, 2] and results["real"] == 0
    wrong = []
    for (name, arguments), (re, im) in zip(cases, results["results"]):
        expected = complex(CMATH[name](*(complex(*argument) for argument in arguments)))
        if not close(complex(re, im), expected):
            wrong.append(f"{name}{tuple(complex(*argument) for argument in arguments)} = {complex(re, im)}, cmath {expected}")
    assert wrong == [], "\n".join(wrong)
    assert [abs(im) > 1e-6 for _re, im in results["cut"]] == [True] * len(BRANCH_CUTS), results["cut"]
    assert errors == []


def operator(name: str, symbol: str, *args: dict) -> dict:
    return {"operator": name, "symbol": symbol, "args": list(args)}


X, Y = {"name": "x"}, {"name": "y"}
# A reader's expression and its syntax tree, as equations.js reads it (maths-door.js, parse).
EXPRESSIONS = {
    "2*x + 1": operator("add", "+", operator("multiply", "*", {"number": 2}, X), {"number": 1}),
    "x - y - 1.5": operator("subtract", "-", operator("subtract", "-", X, Y), {"number": 1.5}),
    "-x^2": operator("unaryMinus", "-", operator("pow", "^", X, {"number": 2})),
    "2^3^x": operator("pow", "^", {"number": 2}, operator("pow", "^", {"number": 3}, X)),
    "(x + y) / 2e-3": operator("divide", "/", operator("add", "+", X, Y), {"number": 0.002}),
    "+sin(x)": operator("unaryPlus", "+", {"call": "sin", "args": [X]}),
    "atan2(y, x)": {"call": "atan2", "args": [Y, X]},
    "2x": operator("multiply", "*", {"number": 2}, X),
    "sqrt(x) * pi": operator("multiply", "*", {"call": "sqrt", "args": [X]}, {"name": "pi"}),
}
UNPARSABLE = ["2 *", "(x", "sin(x,", ")"]


@pytest.mark.parametrize("mode", MODES)
def test_the_maths_door_parses_a_readers_expression_into_its_syntax_tree(door_pages, mode):
    page, errors = door_pages( "maths", mode)
    parsed = page.evaluate("""([texts, bad]) => ({
        trees: texts.map(text => obsMaths.parse(text)),
        refused: bad.map(text => { try { obsMaths.parse(text); return null; } catch (error) {
            return error instanceof Error && error.message.length > 0; } }),
    })""", [list(EXPRESSIONS), UNPARSABLE])
    assert dict(zip(EXPRESSIONS, parsed["trees"])) == EXPRESSIONS
    assert parsed["refused"] == [True] * len(UNPARSABLE)
    assert errors == []


def blank_pdf(signed: bool = False) -> bytes:
    """A one-page PDF; ``signed`` marks it as a signed one does, with a /Perms dictionary."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    if signed:
        writer._root_object[NameObject("/Perms")] = DictionaryObject()
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize("mode", MODES)
def test_the_pdf_door_attaches_a_file_it_finds_again_and_refuses_a_signed_or_attached_pdf(
        door_pages, mode):
    page, errors = door_pages( "pdf", mode)
    found = page.evaluate("""async ([plain, signed]) => {
        const bytes = text => Uint8Array.from(atob(text), char => char.charCodeAt(0));
        const door = obsPdf, filename = "obs-html-source.zip";
        const options = {filename, mimeType: "application/zip", description: "The vault's source files"};
        const refusal = async (source) => {
            try { await door.attach(source, bytes("UEsFBgAAAAAAAAAAAAAAAAAAAAAAAA=="), options); return null; }
            catch (error) { return error.message; }
        };
        const result = await door.attach(bytes(plain), bytes("UEsFBgAAAAAAAAAAAAAAAAAAAAAAAA=="), options);
        let binary = "";
        for (const byte of new Uint8Array(result)) binary += String.fromCharCode(byte);
        return {available: door.available(), before: await door.attached(bytes(plain), filename),
            after: await door.attached(result, filename), other: await door.attached(result, "other.zip"),
            head: binary.slice(0, 5), result: btoa(binary),
            again: await refusal(result), signed: await refusal(bytes(signed))};
    }""", [base64.b64encode(blank_pdf()).decode("ascii"), base64.b64encode(blank_pdf(signed=True)).decode("ascii")])
    assert found["available"] is True and found["head"] == "%PDF-"
    assert (found["before"], found["after"], found["other"]) == (False, True, False)
    assert found["again"] == "PDF already contains obs-html-source.zip; choose the PDF as printed."
    assert found["signed"] == "Signed PDFs cannot be modified; attach the ZIP before signing."
    if mode == "real":  # The real library writes a PDF attachment any reader finds.
        attachments = PdfReader(io.BytesIO(base64.b64decode(found["result"]))).attachments
        assert attachments == {"obs-html-source.zip": [base64.b64decode("UEsFBgAAAAAAAAAAAAAAAAAAAAAAAA==")]}
    assert errors == []


@pytest.mark.parametrize("key", sorted(libraries.LIBRARIES))
def test_each_doors_fake_answers_every_call_of_its_door_and_no_other(door_pages, key):
    """A fake without its contract does not count: each library's door has its fake in test/fakes,
    whose global answers exactly the door's calls, each held to the contract above."""
    door = libraries.LIBRARIES[key].door.removesuffix("-door.js")
    name = {"plotly": "obsPlotly", "maths": "obsMaths", "pdf": "obsPdf"}[door]
    calls = {}
    for mode in MODES:
        page, errors = door_pages(key, mode)
        calls[mode] = page.evaluate(f"""() => Object.fromEntries(Object.entries(globalThis.{name}).map(
            ([call, value]) => [call, typeof value === "function" ? "function" : Object.keys(value).sort()]))""")
        assert errors == []
    assert calls["fake"] == calls["real"]
