"""Every error obs-html raises goes through its one formatter, errors.py (InputError).

Reader: whoever adds a raise to the adapter. A raise names an InputError (or a subclass), a
function that returns one, a caught error it re-raises, or SystemExit for an exit status.
"""
from __future__ import annotations

import ast
import builtins
import importlib
import inspect
import json
from pathlib import Path

import pytest

from obs_html import cli
from obs_html.errors import InputError
from obs_html.render import render

from documents import chapter, document, paragraph
from obs_html.config import load_config

CONFIG = load_config()


PACKAGE = Path(importlib.import_module("obs_html").__file__).parent
MODULES = sorted(PACKAGE.rglob("*.py"))


def _callee(module: object, call: ast.expr) -> object:
    """The object a raise's call names, resolved in its module, or None for a local name."""
    parts: list[str] = []
    while isinstance(call, ast.Attribute):
        parts.insert(0, call.attr)
        call = call.value
    if not isinstance(call, ast.Name):
        return None
    parts.insert(0, call.id)
    value = vars(module).get(parts[0], getattr(builtins, parts[0], None))
    for part in parts[1:]:
        value = getattr(value, part, None)
    return value


def _refused(module: object, returns: dict[str, str], raised: ast.expr) -> str | None:
    """Why a raise does not go through the formatter, or None. ``returns`` maps each function the
    module's source defines (methods and local functions too) to its return annotation."""
    if not isinstance(raised, ast.Call):
        return None  # A re-raise of a caught error, or a name bound to an InputError.
    callee = _callee(module, raised.func)
    if callee is SystemExit:
        return None
    if inspect.isclass(callee):
        return None if issubclass(callee, InputError) else f"raises {callee.__name__}"
    if callable(callee):
        returned = inspect.signature(callee).return_annotation
        return None if "InputError" in str(returned) else f"raises what {callee.__name__} returns"
    name = raised.func.attr if isinstance(raised.func, ast.Attribute) else getattr(raised.func, "id", "")
    if name in returns:
        return None if "InputError" in returns[name] else f"raises what {name} returns"
    return f"raises {ast.unparse(raised.func)}, which its module does not define"


@pytest.mark.parametrize("path", MODULES, ids=lambda path: path.relative_to(PACKAGE).as_posix())
def test_every_raise_in_the_adapter_goes_through_the_formatter(path: Path) -> None:
    name = ".".join(("obs_html", *path.relative_to(PACKAGE).with_suffix("").parts)).removesuffix(".__init__")
    module = importlib.import_module(name)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    returns = {function.name: ast.unparse(function.returns) if function.returns else ""
               for function in ast.walk(tree) if isinstance(function, ast.FunctionDef)}
    refused = [f"{path.name}:{statement.lineno}: {reason}"
               for statement in ast.walk(tree)
               if isinstance(statement, ast.Raise) and statement.exc is not None
               for reason in [_refused(module, returns, statement.exc)] if reason]
    assert refused == [], "raise errors.InputError(source, field, problem, remedy) instead"


def test_every_adapter_error_class_is_an_input_error() -> None:
    for path in MODULES:
        name = ".".join(("obs_html", *path.relative_to(PACKAGE).with_suffix("").parts)).removesuffix(".__init__")
        for value in vars(importlib.import_module(name)).values():
            if inspect.isclass(value) and issubclass(value, BaseException) and value.__module__.startswith("obs_html"):
                assert issubclass(value, InputError), f"{value.__module__}.{value.__name__}"


def test_a_document_integrity_failure_names_the_document_the_node_path_and_the_remedy() -> None:
    """A node the core never writes: the Document is stale or not the core's."""
    callout = {"type": "callouts", "attrs": {"kind": "shout", "title": ""}, "children": [paragraph("Inside.")]}
    source = document("Doc", chapter("one", "One", paragraph("Before."), callout))
    with pytest.raises(InputError) as failure:
        render(source, CONFIG)
    assert (failure.value.source, failure.value.field) == ("Document of manifest.md",
                                                           "chapters[0].content[1].attrs.kind")
    assert "obs-document" in failure.value.remedy and "manifest.md" in failure.value.remedy


def _stale_document(tmp_path: Path) -> Path:
    """A Document whose callout kind the core never writes, so rendering it fails naming the Document."""
    callout = {"type": "callouts", "attrs": {"kind": "shout", "title": ""}, "children": [paragraph("Inside.")]}
    path = tmp_path / "document.json"
    path.write_text(json.dumps(document("Doc", chapter("one", "One", callout))), encoding="utf-8")
    return path


def _note_error_document(tmp_path: Path) -> Path:
    """A Document whose manifest profile is invalid, so rendering it fails naming the manifest note."""
    source = document("Doc", chapter("one", "One", paragraph("Text.")), metadata={"obsHtml": {"layout": "sideways"}})
    path = tmp_path / "document.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    return path


@pytest.mark.parametrize(("build", "source"), [(_stale_document, "Document of {}"), (_note_error_document, "{}")])
@pytest.mark.parametrize(("arguments", "root"), [(["--vault-root", "spec"], "spec/"), ([], "")])
def test_the_vault_root_the_core_passes_prefixes_the_vault_relative_paths_of_a_message(
        tmp_path, capsys, build, source, arguments, root) -> None:
    """The core passes the vault root as its user gave it, only for messages (architecture.md,
    Adapter call); a direct call on a Document names vault-relative paths."""
    with pytest.raises(SystemExit):
        cli.main([str(build(tmp_path)), str(tmp_path / "out.html"), *arguments])

    assert capsys.readouterr().err.splitlines()[-1].startswith(f"{source.format(root + 'manifest.md')}: ")


def _dropped_import_document(tmp_path: Path) -> Path:
    """A Document whose note ``chapter.md`` inlines a linked drawing with an ``@import``, which
    figure_styles.py drops with a warning naming the note."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><style>@import url(a.css);</style>'
           '<text x="1" y="5">See [[chapter]].</text></svg>')
    link = {"type": "wikilinks", "attrs": {"target": "chapter", "chapter": "chapter", "heading": "",
                                           "label": "chapter", "svg": "[[chapter]]"}, "children": []}
    figure = {"type": "figures", "attrs": {"kind": "svg", "alt": "Drawing"},
              "children": [{"type": "svg", "attrs": {"svg": svg}, "children": [link]}]}
    source = document("Doc", chapter("chapter", "Chapter", figure),
                      records=({"id": "chapter", "type": "note", "path": "chapter.md", "fields": {}},))
    path = tmp_path / "document.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    return path


@pytest.mark.parametrize(("arguments", "root"), [(["--vault-root", "spec"], "spec/"), ([], "")])
def test_the_vault_root_the_core_passes_prefixes_the_note_a_warning_names(tmp_path, capsys, arguments, root) -> None:
    """A figure-style warning is an adapter message like an error: it names its note below the vault root."""
    cli.main([str(_dropped_import_document(tmp_path)), "--check", *arguments])

    warnings = [line for line in capsys.readouterr().err.splitlines() if line.startswith("Warning: ")]
    assert [line.split(": ")[1:3] for line in warnings] == [[f"{root}chapter.md", "figure.style"]]
