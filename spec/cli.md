# CLI

The executable help is the CLI reference. Option semantics, examples, prerequisites,
diagnostics and operation restrictions belong to its parser, not this note.

````cmd
uv run obs-html --help
````

This command fence derives the artifact's reference from the running CLI. `obs-html` renders
one Document; a build from a vault is the core's one-call build, `obs-document --adapter html`
(obs's CLI, One-call build: [[obs-specification|obs's specification]]).

See [[input-model]] for source semantics, [[artifact-ui]] for presentation requirements, and
[[configuration]] for configuration ownership. The [parity table](../test/parity/features.md)
records how both differ from the interim adapter they replaced.

## Command fences through the core

obs's CLI note owns how a build through the core authorizes command fences.

The adapter then renders from the Document alone, so `obs-html` has no command options and one
Document renders the same through `obs-document --adapter html` and through `obs-html`.

## Attachments per build

`--embed-attachments` is the build half of the attachment rule in [[input-model]]: authors mark
files with `![label](file)` or `![[file]]`, and only a build with the flag embeds them. One vault
therefore yields a light edition and a self-contained evidence edition without editing Markdown,
and a source archive rebuilds with the flag it was built with.

`obs-html --embed-attachments` makes the same choice on a Document, which carries every marked
file's bytes (obs's architecture, Asset bytes: [[obs-specification|obs's specification]]): with it, the evidence edition, each marked attachment
is a download of those bytes showing its name, type and size; without it, the light edition, the
attachment shows its label and vault path and its bytes stay out of the HTML.

Through the core,
`obs-document --adapter html` builds the light edition, and with `--adapter-option
embed-attachments=true`, the option `adapter.json` declares, the evidence edition (obs's CLI,
Adapter options: [[obs-specification|obs's specification]]).

## Source archive per build

The source archive follows the Document: `obs-document --embed-source` puts the vault's source
files into it (obs's architecture, Source archive: [[obs-specification|obs's specification]]), and
obs-html packages and embeds them whenever they are there
([[input-model#Optional reproduction archive]]).

A `.pdf` destination of such a Document carries the ZIP as a PDF attachment, so
`obs-document --embed-source --adapter html --destination artifact.pdf` attaches it in one call.

`obs-html --export-pdf HTML --output file.pdf` prints an existing artifact the same way: it
attaches the ZIP the HTML embeds, and prints an HTML without one with no attachment.

`obs-html --attach-source-to-pdf PDF --source-artifact HTML --output file.pdf` attaches the ZIP an
artifact embeds to a PDF saved from it; in the HTML, Settings + exports does the same
([[artifact-ui]]).

It is an operation on two existing
files, like `--export-pdf`, not a choice about rendering a Document, so `adapter.json` declares no
option for it: through the core the PDF destination attaches already, and an option would only
repeat what the Document says.

## Building its own specification

`obs-html --build-own-spec DESTINATION` builds this specification, which the package ships as
package data ([[architecture#Packaged browser assets]]), into DESTINATION, from the installed
package alone.

It starts the core of its own environment, `python -m obs.document --source
<packaged specification>/manifest.md --document <temporary file> --execute-commands`, whose
capability reference is the one the core ships, and renders that Document as `obs-html DOCUMENT
DESTINATION` does; `--style`, `--config` and `--embed-attachments` apply as they do there.

The core runs the specification's command fences, so its environment puts the running Python's
scripts folder first on `PATH`: a fence finds the programs installed beside obs-html. A package
whose build wrote no specification fails naming the missing manifest and the remedy, to build the
package again; a failed core build names the core's message.

The command exists so that a vault can carry this specification without reaching outside itself:
obs's specification builds it into its References with this command (obs's appendix, obs-html
specification: [[obs-specification|obs's specification]]), so its source archive rebuilds it with
the installed obs at the recorded commit ([[input-model#Optional reproduction archive]]).

## One Document per call

`obs-html DOCUMENT DESTINATION` renders one Document into one destination, the adapter call
the core makes (obs's architecture, Adapter call: [[obs-specification|obs's specification]]).

A caller that builds several artifacts passes repeated `--source`/`--destination` pairs to one
`obs-document` call (obs's CLI, Several documents per call:
[[obs-specification|obs's specification]]), which pays the core's start once and this adapter's
once per document.

`--timings` attributes a call's time to its internal stages so callers can see where
convert time goes. Durations are exclusive: a nested stage, such as figures inside
rendering, is not counted again in its enclosing stage.

Callers that start `obs-document` or `obs-html` repeatedly use one `uv sync` and then the
environment's `.venv\Scripts\obs-document.exe` (or `uv run --no-sync`), which skips uv's
per-start check. `uv run --frozen` only skips lock resolution and saves little.

## Running from another folder

The one-call build reads the adapter registry `adapters.json` from the current folder, the
repository root, so it runs from there. From another folder, a call names the checkout's project
and its registry:

```powershell
uv run --project C:\path\to\obs obs-document --adapter-config C:\path\to\obs\adapters.json `
    --adapter html --source C:\path\to\vault\manifest.md --destination C:\path\to\document.html
```

It runs the checkout's sources with the dependencies `uv.lock` pins.

## PDF output

A DESTINATION ending in `.pdf` prints the rendered HTML to PDF in the same call, through
`obs-html` and through `obs-document --adapter html` alike; any other name receives HTML.
`--export-pdf` prints an HTML built before. The PDF row of the
[parity table](../test/parity/features.md) records the issue that decided it.

## Rendered check

`--check` proves the source; `--check-rendered` proves that the delivered HTML opens
without console errors and how many pages it prints. It replaces ad-hoc Playwright
scripts, so callers can gate a build on its exit code.

The page count comes from the print path that `--export-pdf` uses, so it equals the
pages of an exported PDF and does not depend on the reader's scrolling container.

## Printing a chapter

`--print-chapter HTML CHAPTER` prints one chapter of a built artifact to stdout, as HTML or, with
`--chapter-format text`, as plain text. Tests and agents check what an artifact shows, for
example that a link resolves, directly from the command instead of a browser script; the
artifact's data island is packed, so reading it by hand needs a decoder.

It prints the chapter as the adapter stored it in the artifact's data, without starting a
browser: what the reader runtime changes on load, such as interactive table controls, is not
included; `--check-rendered` covers the opened page.

It prints the artifact's static text, so it
cannot show a label the artifact computes at runtime, such as a count or a figure number that
depends on the reader's filter. Chapter ids are the note slugs the artifact's table of
contents uses; an unknown id lists the available ones.

`obs-html` reads the built artifact, not a Document: a build through the core, `obs-document
--adapter html`, writes the artifact and no Document file, and the artifact stores the chapters
as the adapter rendered them from its Document.

`obs-html` also takes a chapter's title for
CHAPTER; a title that two chapters share lists their ids. Like `--extract-comments`, it renders
nothing, so it refuses DOCUMENT and the rendering options.

## Serving answers

`obs-html serve ARTIFACT` serves a built artifact and the files beside it on `127.0.0.1` and takes
the reader's answers from its page ([[capabilities/answers|answers]]). With `--wait` it is the
command an agent runs and waits on: it exits with the answers on stdout once the reader sends them,
so the agent continues without being told.

````cmd
uv run obs-html serve --help
````

The server is a plain local web server, so the page works in any browser, VS Code's built-in
browser too, and Claude Code and Copilot take the same path. It is a subcommand rather than an
option, as the other operations are, because it runs until answers arrive instead of returning a
result. Through the core, `obs-document --serve` reaches it after the build.

## PowerShell callers

The CLI writes diagnostics, such as warnings, to stderr; uv adds progress lines there,
for example "Building obs-html" after a version change. Only the exit code reports
failure.

Windows PowerShell 5.1 turns each stderr line into an error record when the caller
redirects streams (`2>&1`, `*>`). Under `$ErrorActionPreference = 'Stop'` the first
such line aborts the caller even though the command succeeds. Run the native command
with `Continue` in scope and judge it by `$LASTEXITCODE`:

```powershell
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    & uv run --quiet obs-document --source $manifest --adapter html --destination $html
} finally {
    $ErrorActionPreference = $previous
}
if ($LASTEXITCODE -ne 0) { throw "obs-document failed with exit code $LASTEXITCODE." }
```

`--quiet` keeps uv's own progress off stderr; warnings from the CLI still use it.
The project's PowerShell scripts and wrappers follow this rule for every native command.

## Setup

`RUNME.ps1` declares the tools a contributor or agent needs once, each with its winget id and
its check (a command on `PATH` or known install paths): uv, Git, Node.js, GitHub CLI (`gh`)
and Chrome for the browser tests. Every run installs uv when it is missing.

- `.\RUNME.ps1 -Setup` installs each missing declared tool with winget, reports every tool as
  present, installed or missing, and exits; the exit code is 0 only when all are present.
- `.\RUNME.ps1 -Tools` lists the declared tools with their resolved paths and installs nothing.
  No other script repeats a tool id or path.

Without either switch, `RUNME.ps1` and `RUNME.sh` pass their arguments to `uv run obs-document`;
both switches take none. `RUNME.sh` has no setup mode; winget is Windows-only.
