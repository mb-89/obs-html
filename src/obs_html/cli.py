"""obs-html: render a JSON Document as HTML or PDF; print or check existing HTML."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from importlib.resources import as_file, files
from pathlib import Path
from time import perf_counter
from typing import Sequence

from obs_html.comments import extract_comments
from obs_html.config import load_config
from obs_html.errors import InputError, Parser, diagnostics, in_vault, vault_naming
from obs_html.exposure import check_artifact
from obs_html.figure_svg import document_figures, figure_svg
from obs_html.render import render
from obs_html.source_archive import attach, embedded
from obs_html.artifact_data import chapter_html, html_text, same_artifact_content
from obs_html.timings import recording, stage


EPILOG = """Rendering:
  DOCUMENT is a JSON Document (the core's obs-document writes it); it is the only input.
  DESTINATION ending in .pdf prints the rendered HTML to PDF; any other name receives HTML.
  The core calls this command as an adapter with DOCUMENT and DESTINATION, the vault root as
  --vault-root ROOT when it built the Document, and the options adapter.json declares.
  --vault-root ROOT names the Document's vault-relative paths below ROOT in messages
  (ROOT/manifest.md: ...); the Document and the artifact never carry it.
  obs-html never runs a command: a command fence shows the output the core captured while it
  built the Document (obs-document --execute-commands), and a Document without it fails.
  An artifact that names the build machine's home folder or user name fails before writing
  (README, "Command fences").
  --check renders without writing output.
  The Document's diagnostics are printed to stderr, never into the HTML, only when obs-html runs
  directly on a Document (no --vault-root): the core that calls it printed them already.
  --style FOLDER selects an external style module: a folder with style.css, laid over the
  packaged base stylesheet, and an optional assets.json semantic asset index. It must not
  declare page geometry (@page, size, --paper-*, --sheet-*); the Document's profile owns it.
  Without it, the style the manifest declares (obs.style) applies, fetched with git once per
  commit into the user's cache folder (obs-html/styles/<commit>); without one, the packaged
  generic style.

Sources and styles:
  A Document built with obs-document --embed-source carries the vault's source files; the HTML
  embeds them as one ZIP (vault/<path>), which the cover and Settings + exports download as
  obs-html-source.zip, and Settings attaches to a PDF saved from the HTML. The CSS snippets the
  manifest lists in obsHtml.cssSnippets follow every packaged style, in their listed order.

Editions:
  Without --embed-attachments, the light edition: a marked attachment (![label](file) or
  ![[file]]) shows its label and vault path. With it, the self-contained evidence edition: the
  attachment is a download of the bytes the Document embeds, with its name, type and size.
  Images always render from their bytes. Through the core, obs-document --adapter html builds the
  light edition, and with --adapter-option embed-attachments=true (adapter.json declares it) the
  evidence edition.

Settings:
  --config FILE merges a JSON settings file over the packaged cfg.json, validated by
  cfg.schema.json: execution limits and the print catalogue (paper sizes and default
  paper). A Document chooses its paper and margin in its profile's print mapping.

Trusted runtime:
  --trusted-runtime-bundle ID=PATH explicitly trusts one local JavaScript application
  bundle (a regular .js file, not a link) and embeds it in the HTML after the artifact
  runtime. The Document itself can never opt into executable code.

Figures:
  DOCUMENT --export-figures FOLDER writes each figure of the Document as a standalone SVG,
  FOLDER/<chapter>--figure-<id>.svg, named like the figure's anchor in the HTML artifact. The
  same figure descriptor always gives the same bytes, so exports can be committed, diffed and
  cached; unchanged files are not rewritten and other files in FOLDER are left alone.

Comments:
  --extract-comments HTML reads the comment JSON island of a returned, reviewed artifact
  without executing its scripts and prints deterministic comment candidates to stdout.

Printing a chapter:
  --print-chapter HTML CHAPTER prints one chapter of a built artifact to stdout, as the
  generator stored it, without starting a browser. CHAPTER is a chapter id, the note slug of the
  artifact's table of contents, or a chapter's title. --chapter-format text prints plain text,
  one line per block, instead of HTML. An unknown chapter fails and lists the available ids.

PDF operations:
  --export-pdf HTML --output file.pdf prints existing HTML with local Chrome/Edge/Chromium
  or Playwright Chromium, and attaches the source ZIP the HTML embeds as obs-html-source.zip.
  If no browser is installed: uv run playwright install chromium
  --attach-source-to-pdf PDF --source-artifact HTML --output file.pdf attaches the source ZIP
  that HTML embeds (a Document built with obs-document --embed-source) to a PDF saved from it,
  as obs-html-source.zip. Rendering such a Document to a .pdf DESTINATION attaches it already.
  --check-rendered HTML opens existing HTML headless, waits until it reports ready or error,
  prints console errors to stderr and the status, error count and printed page count to
  stdout. It fails (exit 2) on any console error, an error status or no status within
  execution.renderedCheckTimeoutSeconds.

Timings:
  --timings prints "Timing: STAGE SECONDS s" for render, figures, print and write.

Examples:
  obs-html document.json artifact.html
  obs-html document.json artifact.pdf
  obs-html document.json --check
  obs-html document.json artifact.html --style styles/corporate
  obs-html document.json evidence.html --embed-attachments
  obs-html --export-pdf artifact.html --output artifact.pdf
  obs-html --check-rendered artifact.html
  obs-html --extract-comments reviewed.html
  obs-html --print-chapter artifact.html intro --chapter-format text
  obs-html document.json --export-figures figures
  obs-html --build-own-spec obs-html-specification.html

Own specification:
  --build-own-spec DESTINATION builds the adapter's specification, which the package ships, into
  DESTINATION from the installed package alone: it starts the core of this environment
  (python -m obs.document --source <packaged spec>/manifest.md --execute-commands), which runs
  the specification's command fences, and renders the Document as DOCUMENT DESTINATION does.

Exit status:
  0: success (including --help); 2: invalid options, input or operation failure.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = Parser(
        prog="obs-html",
        description="Render a JSON Document as portable HTML or PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument("document", type=Path, nargs="?", metavar="DOCUMENT",
                        help="JSON Document to render.")
    parser.add_argument("destination", type=Path, nargs="?", metavar="DESTINATION",
                        help="Output file: .pdf for PDF, otherwise HTML.")
    parser.add_argument("--vault-root", metavar="ROOT",
                        help="The vault root as the core's user gave it, for messages only.")
    parser.add_argument("--config", type=Path, help="Settings JSON merged over the packaged cfg.json.")
    parser.add_argument("--check", action="store_true", help="Render without writing output.")
    parser.add_argument("--style", type=Path, metavar="FOLDER",
                        help="Style module folder containing style.css (and optionally assets.json); "
                             "replaces the declared or packaged generic style for this build.")
    parser.add_argument("--embed-attachments", action="store_true",
                        help="Embed files marked with ![label](file) or ![[file]] as downloads.")
    parser.add_argument("--trusted-runtime-bundle", metavar="ID=PATH",
                        help="Embed one explicitly trusted local JavaScript bundle.")
    parser.add_argument("--export-figures", type=Path, metavar="FOLDER",
                        help="Write each figure of DOCUMENT as a byte-stable SVG into FOLDER.")
    parser.add_argument("--extract-comments", type=Path, metavar="HTML",
                        help="Print comment candidates from a returned, reviewed artifact.")
    parser.add_argument("--print-chapter", nargs=2, metavar=("HTML", "CHAPTER"),
                        help="Print one chapter of a built artifact by id or title.")
    parser.add_argument("--chapter-format", choices=("html", "text"),
                        help="Print the --print-chapter chapter as html (default) or plain text.")
    parser.add_argument("--export-pdf", type=Path, metavar="HTML", help="Print existing HTML to PDF.")
    parser.add_argument("--output", type=Path, metavar="PDF",
                        help="PDF written by --export-pdf or --attach-source-to-pdf.")
    parser.add_argument("--attach-source-to-pdf", type=Path, metavar="PDF",
                        help="Attach the source ZIP of --source-artifact HTML to this PDF.")
    parser.add_argument("--source-artifact", type=Path, metavar="HTML",
                        help="HTML whose embedded source ZIP --attach-source-to-pdf attaches.")
    parser.add_argument("--check-rendered", type=Path, metavar="HTML",
                        help="Open existing HTML headless; report console errors and printed pages.")
    parser.add_argument("--build-own-spec", type=Path, metavar="DESTINATION",
                        help="Build the adapter's packaged specification with the core into DESTINATION.")
    parser.add_argument("--timings", action="store_true", help="Print the duration of each stage.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    options = parser.parse_args(argv)
    started = perf_counter()
    try:
        config = load_config(options.config)
        if options.source_artifact and not options.attach_source_to_pdf:
            raise InputError(PROG, "--source-artifact", "is only used with --attach-source-to-pdf",
                             "Add --attach-source-to-pdf PDF, or drop --source-artifact")
        if options.chapter_format and not options.print_chapter:
            raise InputError(PROG, "--chapter-format", "is only used with --print-chapter",
                             "Add --print-chapter HTML CHAPTER, or drop --chapter-format")
        with recording() as recorded:
            if options.print_chapter:
                _print_chapter(options)
            elif options.extract_comments:
                _extract(options)
            elif options.export_figures:
                _export_figures(options)
            elif options.attach_source_to_pdf:
                _attach_source(options)
            elif options.check_rendered or options.export_pdf:
                _browser_operation(options, config)
            elif options.build_own_spec:
                _build_own_spec(options, config)
            else:
                _render(options, config)
    except InputError as error:
        parser.print_usage(sys.stderr)
        parser.exit(2, f"{error}\n")
    if options.timings:
        for name, seconds in {**recorded.durations, "total": perf_counter() - started}.items():
            print(f"Timing: {name} {seconds:.3f} s")
    return 0


def _render(options: argparse.Namespace, config) -> None:
    if options.output:
        raise InputError(PROG, "--output", "is only used with --export-pdf", "Give DESTINATION instead")
    if options.document is None:
        raise InputError(PROG, "DOCUMENT", "is missing", "Name the JSON Document to render")
    if options.check and options.destination:
        raise InputError(PROG, "--check", "cannot be combined with DESTINATION",
                         "Drop DESTINATION to render without output, or drop --check to write it")
    if not options.check and options.destination is None:
        raise InputError(PROG, "DESTINATION", "is missing",
                         "Name the output file, or pass --check to render without output")
    if options.destination and options.destination.resolve() == options.document.resolve():
        raise InputError(PROG, "DESTINATION", "names DOCUMENT itself", "Name another output file")
    _write_artifact(_read_document(options.document), options, config, options.destination)


def _write_artifact(document: dict, options: argparse.Namespace, config, destination: Path | None) -> None:
    """Render ``document`` and write it to ``destination``, a PDF for a .pdf name; with --check, nothing."""
    paths = _vault_paths(document)
    try:
        with vault_naming(options.vault_root, paths):
            artifact = render(document, config, style_folder=options.style,
                              trusted_runtime=_trusted_runtime(options.trusted_runtime_bundle),
                              embed_attachments=options.embed_attachments)
    except InputError as error:
        raise in_vault(error, options.vault_root, paths) from error
    check_artifact(artifact)
    if options.vault_root is None:  # The core, which passes it, printed its diagnostics already.
        diagnostics(document)
    if options.check:
        print(f"Checked {options.document.resolve()}; no output written.")
        return
    destination = destination.resolve()
    if destination.suffix.lower() == ".pdf":
        # Print beside the destination, so the Document's relative asset links resolve.
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent,
                                         prefix=f".{destination.stem}.", suffix=".html",
                                         delete=False) as temporary:
            temporary.write(artifact)
        html = Path(temporary.name)
        try:
            pdf = _printed(html, artifact, destination)
        finally:
            html.unlink()
        _write_if_changed(destination, pdf)
    else:
        existing = _read_existing(destination)
        if existing is None or not same_artifact_content(artifact, existing):
            _write_if_changed(destination, artifact.encode("utf-8"))
    print(f"Generated {destination}.")


OWN_SPEC = "spec"
"""The package folder holding the adapter's specification vault, which hatch_build.py copies."""


def _build_own_spec(options: argparse.Namespace, config) -> None:
    """Build the packaged specification with the core of this environment, then render it."""
    _alone("--build-own-spec", options, "document", "destination", "check", "vault_root", "output")
    with as_file(files("obs_html") / OWN_SPEC) as vault, \
            tempfile.TemporaryDirectory(prefix="obs-html-own-spec-") as work:
        manifest = Path(vault) / "manifest.md"
        if not manifest.is_file():
            raise InputError(PROG, "--build-own-spec", f"the package ships no specification ({manifest} is missing)",
                             "Build the obs-html package again (uv sync, or reinstall it); its build hook "
                             "hatch_build.py copies the specification into it")
        document = Path(work) / "obs-html-specification.json"
        # The fences the core runs find the programs installed beside this Python first.
        scripts = os.path.dirname(sys.executable)
        environment = {**os.environ, "PATH": os.pathsep.join(filter(None, (scripts, os.environ.get("PATH"))))}
        result = subprocess.run([sys.executable, "-m", "obs.document", "--source", str(manifest), "--document",
                                 str(document), "--execute-commands"], env=environment, capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
        if result.returncode:
            raise InputError(PROG, "--build-own-spec", f"the core could not build {manifest}:\n"
                             f"{result.stderr.strip()}", "The core's message above names the cause; obs-html "
                             "runs the core installed beside it, python -m obs.document")
        sys.stderr.write(result.stderr)  # The core's diagnostics, printed once.
        options.vault_root = str(vault)
        _write_artifact(_read_document(document), options, config, options.build_own_spec)


def _attach_source(options: argparse.Namespace) -> None:
    _alone("--attach-source-to-pdf", options, "document", "destination", "check", "style",
           "trusted_runtime_bundle", "embed_attachments", "vault_root", "export_pdf", "check_rendered")
    output, pdf, html = options.output, options.attach_source_to_pdf, options.source_artifact
    if html is None:
        raise InputError(PROG, "--source-artifact", "is missing",
                         "Name the HTML whose source ZIP to attach: --source-artifact HTML")
    if output is None or output.suffix.lower() != ".pdf":
        raise InputError(PROG, "--output", "is missing or names no .pdf file",
                         "Give --attach-source-to-pdf an --output file ending in .pdf")
    if output.resolve() in {pdf.resolve(), html.resolve()}:
        raise InputError(PROG, "--output", "names an input", "Name another .pdf file")
    try:
        artifact, saved = html.read_text(encoding="utf-8"), pdf.read_bytes()
    except (OSError, UnicodeError) as error:
        raise InputError(PROG, "--attach-source-to-pdf", f"cannot read its inputs ({error})",
                         "Name an existing PDF and the HTML it was saved from") from error
    archive = embedded(artifact, html)
    if archive is None:
        raise InputError(html, "--source-artifact", "embeds no source archive", "Build it from a Document "
                         "with the sources: obs-document --embed-source --adapter html")
    _write_if_changed(output.resolve(), attach(saved, archive, pdf))
    print(f"Generated PDF {output.resolve()} with {html.name}'s source ZIP.")


def _printed(html: Path, artifact: str, source: object) -> bytes:
    """``html`` printed, with the source ZIP its ``artifact`` text embeds attached when it has one;
    ``source`` names the artifact in errors."""
    from obs_html.pdf import export_pdf
    pdf = export_pdf(html)
    archive = embedded(artifact, source)
    return pdf if archive is None else attach(pdf, archive, source)


def _browser_operation(options: argparse.Namespace, config) -> None:
    operation = "--export-pdf" if options.export_pdf else "--check-rendered"
    _alone(operation, options, "document", "destination", "check", "style", "trusted_runtime_bundle",
           "embed_attachments", "vault_root", *(["check_rendered"] if options.export_pdf else []))
    from obs_html.pdf import check_rendered
    if options.export_pdf:
        output = options.output
        if output is None or output.suffix.lower() != ".pdf":
            raise InputError(PROG, "--output", "is missing or names no .pdf file",
                             "Give --export-pdf an --output file ending in .pdf")
        if output.resolve() == options.export_pdf.resolve():
            raise InputError(PROG, "--output", "names the source HTML", "Name another .pdf file")
        try:
            artifact = options.export_pdf.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise InputError(PROG, "--export-pdf", f"cannot read its HTML ({error})",
                             "Name an existing HTML artifact") from error
        _write_if_changed(output.resolve(), _printed(options.export_pdf, artifact, options.export_pdf))
        print(f"Generated PDF {output.resolve()}.")
        return
    if options.output:
        raise InputError(PROG, "--output", "is only used with --export-pdf", "Drop it from --check-rendered")
    result = check_rendered(options.check_rendered, config.rendered_check_timeout_seconds)
    for error in result.console_errors:
        print(f"Console error: {error}", file=sys.stderr)
    print(f"Rendered {options.check_rendered.resolve()}: status {result.status}, "
          f"{len(result.console_errors)} console errors, {result.pages} pages.")
    if result.status != "ready" or result.console_errors:
        failures = [f"status {result.status}"] if result.status != "ready" else []
        if result.console_errors:
            failures.append(f"{len(result.console_errors)} console errors")
        raise InputError(options.check_rendered, "--check-rendered", f"fails: {', '.join(failures)}",
                         "Fix what the console errors above name, then render the HTML again")


RUNTIME_ID = re.compile(r"[a-z][a-z0-9-]{0,63}")


def _trusted_runtime(bundle: str | None) -> tuple[str, str] | None:
    if bundle is None:
        return None
    runtime_id, separator, runtime_path = bundle.partition("=")
    if not separator or not RUNTIME_ID.fullmatch(runtime_id) or not runtime_path:
        raise InputError(PROG, "--trusted-runtime-bundle", f"is {bundle!r}, not the form ID=PATH",
                         "Give an ID of lowercase letters, digits and hyphens, then =, then the bundle's path")
    path = Path(runtime_path)
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".js":
        raise InputError(PROG, "--trusted-runtime-bundle", f"names {runtime_path}, which is no regular .js file",
                         "Name the bundle's JavaScript file itself, not a link or another kind of file")
    return runtime_id, path.read_text(encoding="utf-8")


def _export_figures(options: argparse.Namespace) -> None:
    _alone("--export-figures", options, "destination", "check", "style", "trusted_runtime_bundle",
           "embed_attachments", "vault_root", "export_pdf", "check_rendered", "output")
    if options.document is None:
        raise InputError(PROG, "DOCUMENT", "is missing",
                         "Name the Document whose figures to export: obs-html DOCUMENT --export-figures FOLDER")
    document = _read_document(options.document)
    folder = options.export_figures.resolve()
    exported = 0
    for name, descriptor, source in document_figures(document):
        _write_if_changed(folder / f"{name}.svg", figure_svg(descriptor, source).encode("utf-8"))
        exported += 1
    if not exported:
        raise InputError(options.document, "", "has no plot figure, so there is nothing to export",
                         "Author a figure fence of kind plot with a FigureDescriptor")
    print(f"Exported {exported} figure{'' if exported == 1 else 's'} to {folder}.")


def _extract(options: argparse.Namespace) -> None:
    _alone("--extract-comments", options, "document", "destination", "check", "style",
           "trusted_runtime_bundle", "embed_attachments", "vault_root", "export_pdf", "check_rendered", "output",
           "export_figures")
    print(extract_comments(options.extract_comments.resolve()), end="")


def _print_chapter(options: argparse.Namespace) -> None:
    _alone("--print-chapter", options, "document", "destination", "check", "style",
           "trusted_runtime_bundle", "embed_attachments", "vault_root", "export_pdf", "check_rendered", "output",
           "export_figures", "extract_comments", "timings")
    path, chapter = Path(options.print_chapter[0]), options.print_chapter[1]
    try:
        artifact = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InputError(path, "HTML", f"cannot be read ({error})",
                         "Name a built artifact, written by obs-html or obs-document --adapter html") from error
    try:
        html = chapter_html(artifact, chapter)
    except InputError as error:
        raise InputError(path, error.field, error.problem, error.remedy) from error
    print(html_text(html) if options.chapter_format == "text" else html, end="")


PROG = "obs-html"
ARGUMENTS = {"document": "DOCUMENT", "destination": "DESTINATION"}


def _alone(operation: str, options: argparse.Namespace, *names: str) -> None:
    """Refuse the first of ``names`` given with ``operation``, which runs without it."""
    given = next((name for name in names if getattr(options, name)), None)
    if given is not None:
        argument = ARGUMENTS.get(given, f"--{given.replace('_', '-')}")
        raise InputError(PROG, argument, f"cannot be combined with {operation}",
                         f"Run {operation} on its own; see {PROG} --help")


def _vault_paths(document: dict[str, object]) -> set[str]:
    """The vault-relative paths the Document names: its manifest note, its notes and its files."""
    named = [document.get("manifest"), *document.get("records", []), *document.get("assets", [])]
    return {item["path"] for item in named if isinstance(item, dict) and isinstance(item.get("path"), str)}


def _read_document(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InputError(path, "", f"is not JSON ({error.msg} at line {error.lineno}, column {error.colno})",
                         "Build the Document with obs-document") from error
    except (OSError, UnicodeError) as error:
        raise InputError(path, "DOCUMENT", f"cannot be read ({error})",
                         "Name an existing JSON Document, built with obs-document") from error


def _read_existing(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


@stage("write")
def _write_if_changed(output_path: Path, data: bytes) -> bool:
    """Atomically replace output_path unless it already holds these bytes.

    Rewriting identical bytes makes on-access antivirus scanners check the file again.
    """
    try:
        if output_path.is_file() and output_path.read_bytes() == data:
            return False
    except OSError:
        pass
    temporary_path: Path | None = None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=output_path.parent, prefix=f".{output_path.name}.", suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(data)
            temporary_path = Path(temporary.name)
        temporary_path.replace(output_path)
    except OSError as error:
        raise InputError(output_path, "", f"cannot be written ({error.strerror or error})",
                         "Name an output in a folder you can write") from error
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
    return True


if __name__ == "__main__":
    raise SystemExit(main())
