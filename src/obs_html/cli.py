"""obs-html: render a JSON Document as HTML or PDF; print or check existing HTML."""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Sequence

from obs_html.comments import CommentError, extract_comments
from obs_html.config import ConfigError, load_config
from obs_html.exposure import check_artifact
from obs_html.figure_svg import document_figures, figure_svg
from obs_html.figures import FigureError
from obs_html.render import RenderError, render
from obs_html.artifact_data import same_artifact_content
from obs_html.timings import recording, stage


EPILOG = """Rendering:
  DOCUMENT is a JSON Document (the core's obs-document writes it); it is the only input.
  DESTINATION ending in .pdf prints the rendered HTML to PDF; any other name receives HTML.
  The core calls this command as an adapter with exactly DOCUMENT and DESTINATION.
  obs-html never runs a command: a command fence shows the output the core captured while it
  built the Document (obs-document --execute-commands), and a Document without it fails.
  An artifact that names the build machine's home folder or user name fails before writing
  (README, "Command fences").
  --check renders without writing output.
  Document diagnostics are printed to stderr, never into the HTML.
  --style FOLDER selects an external style module: a folder with style.css, laid over the
  packaged base stylesheet, and an optional assets.json semantic asset index. It must not
  declare page geometry (@page, size, --paper-*, --sheet-*); the Document's profile owns it.

Editions:
  Without --embed-attachments, the light edition: a marked attachment (![label](file) or
  ![[file]]) shows its label and vault path. With it, the self-contained evidence edition: the
  attachment is a download of the bytes the Document embeds, with its name, type and size.
  Images always render from their bytes. The core's obs-document --adapter html builds the light
  edition.

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

PDF operations:
  --export-pdf HTML --output file.pdf prints existing HTML with local Chrome/Edge/Chromium
  or Playwright Chromium. If no browser is installed: uv run playwright install chromium
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
  obs-html document.json --export-figures figures

Exit status:
  0: success (including --help); 2: invalid options, input or operation failure.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="obs-html",
        description="Render a JSON Document as portable HTML or PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument("document", type=Path, nargs="?", metavar="DOCUMENT",
                        help="JSON Document to render.")
    parser.add_argument("destination", type=Path, nargs="?", metavar="DESTINATION",
                        help="Output file: .pdf for PDF, otherwise HTML.")
    parser.add_argument("--config", type=Path, help="Settings JSON merged over the packaged cfg.json.")
    parser.add_argument("--check", action="store_true", help="Render without writing output.")
    parser.add_argument("--style", type=Path, metavar="FOLDER",
                        help="Style module folder containing style.css (and optionally assets.json); "
                             "replaces the packaged generic style.")
    parser.add_argument("--embed-attachments", action="store_true",
                        help="Embed files marked with ![label](file) or ![[file]] as downloads.")
    parser.add_argument("--trusted-runtime-bundle", metavar="ID=PATH",
                        help="Embed one explicitly trusted local JavaScript bundle.")
    parser.add_argument("--export-figures", type=Path, metavar="FOLDER",
                        help="Write each figure of DOCUMENT as a byte-stable SVG into FOLDER.")
    parser.add_argument("--extract-comments", type=Path, metavar="HTML",
                        help="Print comment candidates from a returned, reviewed artifact.")
    parser.add_argument("--export-pdf", type=Path, metavar="HTML", help="Print existing HTML to PDF.")
    parser.add_argument("--output", type=Path, metavar="PDF", help="PDF written by --export-pdf.")
    parser.add_argument("--check-rendered", type=Path, metavar="HTML",
                        help="Open existing HTML headless; report console errors and printed pages.")
    parser.add_argument("--timings", action="store_true", help="Print the duration of each stage.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    options = parser.parse_args(argv)
    started = perf_counter()
    try:
        config = load_config(options.config)
        with recording() as recorded:
            if options.extract_comments:
                _extract(parser, options)
            elif options.export_figures:
                _export_figures(parser, options)
            elif options.check_rendered or options.export_pdf:
                _browser_operation(parser, options, config)
            else:
                _render(parser, options, config)
    except (CommentError, ConfigError, RenderError, OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    if options.timings:
        for name, seconds in {**recorded.durations, "total": perf_counter() - started}.items():
            print(f"Timing: {name} {seconds:.3f} s")
    return 0


def _render(parser: argparse.ArgumentParser, options: argparse.Namespace, config) -> None:
    if options.output:
        parser.error("--output is only used with --export-pdf; give DESTINATION instead.")
    if options.document is None:
        parser.error("DOCUMENT is required.")
    if options.check and options.destination:
        parser.error("--check cannot be combined with DESTINATION.")
    if not options.check and options.destination is None:
        parser.error("DESTINATION is required unless --check is given.")
    if options.destination and options.destination.resolve() == options.document.resolve():
        parser.error("DESTINATION must not overwrite DOCUMENT.")
    try:
        document = json.loads(options.document.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RenderError(f"Invalid Document {options.document}: {error}") from error
    artifact = render(document, config, style_folder=options.style,
                    trusted_runtime=_trusted_runtime(parser, options.trusted_runtime_bundle),
                    embed_attachments=options.embed_attachments)
    check_artifact(artifact)
    for diagnostic in document["diagnostics"]:
        print(f"{diagnostic['level'].title()}: {diagnostic['message']}", file=sys.stderr)
    if options.check:
        print(f"Checked {options.document.resolve()}; no output written.")
        return
    destination = options.destination.resolve()
    if destination.suffix.lower() == ".pdf":
        from obs_html.pdf import export_pdf
        # Print beside the destination, so the Document's relative asset links resolve.
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent,
                                         prefix=f".{destination.stem}.", suffix=".html",
                                         delete=False) as temporary:
            temporary.write(artifact)
        html = Path(temporary.name)
        try:
            pdf = export_pdf(html)
        finally:
            html.unlink()
        _write_if_changed(destination, pdf)
    else:
        existing = _read_existing(destination)
        if existing is None or not same_artifact_content(artifact, existing):
            _write_if_changed(destination, artifact.encode("utf-8"))
    print(f"Generated {destination}.")


def _browser_operation(parser: argparse.ArgumentParser, options: argparse.Namespace, config) -> None:
    if (options.document or options.destination or options.check or options.style
            or options.trusted_runtime_bundle or options.embed_attachments
            or options.check_rendered and options.export_pdf):
        parser.error("--export-pdf and --check-rendered are separate operations without DOCUMENT.")
    from obs_html.pdf import check_rendered, export_pdf
    if options.export_pdf:
        output = options.output
        if output is None or output.suffix.lower() != ".pdf":
            parser.error("--export-pdf requires --output file.pdf.")
        if output.resolve() == options.export_pdf.resolve():
            parser.error("PDF output must not overwrite the source HTML.")
        _write_if_changed(output.resolve(), export_pdf(options.export_pdf))
        print(f"Generated PDF {output.resolve()}.")
        return
    if options.output:
        parser.error("--output is only used with --export-pdf.")
    result = check_rendered(options.check_rendered, config.rendered_check_timeout_seconds)
    for error in result.console_errors:
        print(f"Console error: {error}", file=sys.stderr)
    print(f"Rendered {options.check_rendered.resolve()}: status {result.status}, "
          f"{len(result.console_errors)} console errors, {result.pages} pages.")
    if result.status != "ready" or result.console_errors:
        failures = [f"status {result.status}"] if result.status != "ready" else []
        if result.console_errors:
            failures.append(f"{len(result.console_errors)} console errors")
        raise RenderError(f"Rendered check failed: {', '.join(failures)}.")


RUNTIME_ID = re.compile(r"[a-z][a-z0-9-]{0,63}")


def _trusted_runtime(parser: argparse.ArgumentParser, bundle: str | None) -> tuple[str, str] | None:
    if bundle is None:
        return None
    runtime_id, separator, runtime_path = bundle.partition("=")
    if not separator or not RUNTIME_ID.fullmatch(runtime_id) or not runtime_path:
        parser.error("--trusted-runtime-bundle must use the form ID=PATH.")
    path = Path(runtime_path)
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".js":
        raise RenderError("Trusted application runtime must be a regular .js file.")
    return runtime_id, path.read_text(encoding="utf-8")


def _export_figures(parser: argparse.ArgumentParser, options: argparse.Namespace) -> None:
    if (options.document is None or options.destination or options.check
            or options.style or options.trusted_runtime_bundle or options.embed_attachments
            or options.export_pdf or options.check_rendered or options.output):
        parser.error("--export-figures takes only DOCUMENT: obs-html DOCUMENT --export-figures FOLDER.")
    try:
        document = json.loads(options.document.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RenderError(f"Invalid Document {options.document}: {error}") from error
    folder = options.export_figures.resolve()
    exported = 0
    for name, descriptor in document_figures(document):
        try:
            svg = figure_svg(descriptor)
        except FigureError as error:
            raise RenderError(f"{options.document} ({name}): {error}") from error
        _write_if_changed(folder / f"{name}.svg", svg.encode("utf-8"))
        exported += 1
    if not exported:
        raise RenderError(f"Document {options.document} has no figure-descriptor node, so there is "
                          "nothing to export; author a figure fence with a FigureDescriptor.")
    print(f"Exported {exported} figure{'' if exported == 1 else 's'} to {folder}.")


def _extract(parser: argparse.ArgumentParser, options: argparse.Namespace) -> None:
    if any((options.document, options.destination, options.check,
            options.style, options.trusted_runtime_bundle, options.embed_attachments,
            options.export_pdf, options.check_rendered, options.output, options.export_figures)):
        parser.error("--extract-comments is a separate operation without DOCUMENT.")
    print(extract_comments(options.extract_comments.resolve()), end="")


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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=output_path.parent, prefix=f".{output_path.name}.", suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(data)
            temporary_path = Path(temporary.name)
        temporary_path.replace(output_path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
    return True


if __name__ == "__main__":
    raise SystemExit(main())
