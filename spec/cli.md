# CLI

The executable help is the CLI reference. Option semantics, examples, prerequisites,
diagnostics and operation restrictions belong to its parser, not this note.

````cmd
uv run obs-html-interim --help
````

This command fence derives the artifact's reference from the running CLI.
See [[input-model]] for source semantics, [[artifact-ui]] for presentation requirements,
and [[configuration]] for configuration ownership.

## Command fences through the core

obs's CLI note owns how a build through the core authorizes command fences.

The adapter then renders from the Document alone, so `obs-html` has no command options and one
Document renders the same through `obs-document --adapter html` and through `obs-html`. The
interim `obs-html-interim --execute-commands` still runs its own fences until the cutover.

## Attachments per build

`--embed-attachments` is the build half of the attachment rule in [[input-model]]: authors mark
files with `![label](file)` or `![[file]]`, and only a build with the flag embeds them. One vault
therefore yields a light edition and a self-contained evidence edition without editing Markdown,
and a source archive rebuilds with the flag it was built with.

`obs-html --embed-attachments` makes the same choice on a Document, which carries every marked
file's bytes (obs's architecture, Asset bytes: [[obs-specification|obs's specification]]): with it, the evidence edition, each marked attachment
is a download of those bytes showing its name, type and size; without it, the light edition, the
attachment shows its label and vault path and its bytes stay out of the HTML. Through the core,
`obs-document --adapter html` builds the light edition, and with `--adapter-option
embed-attachments=true`, the option `adapter.json` declares, the evidence edition (obs's CLI,
Adapter options: [[obs-specification|obs's specification]]).

## Several artifacts per call

A caller that builds several artifacts passes repeated `--source`/`--output` pairs in one
call rather than starting obs-html-interim once per artifact. Each start pays the Python start with
its imports (about 1 s), uv's environment check (0.1–0.3 s) and the generator's git
provenance.

One process pays them once and shares the packaged parser and schema caches, which are
independent of the vault.

Repeated options were chosen over a job file. Callers already assemble argument arrays,
and a job file would be a second input format with its own schema and path rules. The
only per-artifact option besides the pair, the trusted runtime bundle, repeats in the same
order; every other option applies to all artifacts of the call.

`--timings` attributes a call's time to its internal stages so callers can see where
convert time goes. Durations are exclusive: a nested stage, such as figures inside
rendering, is not counted again in its enclosing stage.

Callers that start obs-html-interim repeatedly use one `uv sync` and then the environment's
`.venv\Scripts\obs-html-interim.exe` (or `uv run --no-sync`), which skips uv's per-start check.
`uv run --frozen` only skips lock resolution and saves little.

## Running from any folder

Authors install the CLI once as a uv tool and then run `obs-html-interim` from any folder:

```powershell
uv tool install --editable C:\path\to\obs_html
uv tool update-shell   # once, puts uv's tool folder on PATH
obs-html-interim --source C:\path\to\vault --output C:\path\to\document.html
```

The editable install runs the checkout's sources, so `git pull` updates it, the
generator provenance names the checkout commit and `--embed-source` works. After a
dependency change in `pyproject.toml`, rerun the install with `--reinstall`.

A plain `uv tool install` copies the package instead. It generates artifacts but has no
checkout: `--embed-source` refuses, the default source and output point nowhere useful
and the provenance carries only the package version. Either form resolves dependencies
from the ranges in `pyproject.toml`, not from `uv.lock`; builds that must match the lock
run `uv run` in the checkout. Remove the tool with `uv tool uninstall obs`.

## PDF output

Generation writes HTML only; a PDF comes from `--export-pdf` on the generated HTML. Generation
therefore refuses an `--output` ending in `.pdf` instead of writing HTML into a file a reader
would open as a PDF, and its message names the two-step remedy. Refusing was chosen over
exporting in the same call because it is the smaller change and keeps generation independent
of a browser.

## Rendered check

`--check` proves the source; `--check-rendered` proves that the delivered HTML opens
without console errors and how many pages it prints. It replaces ad-hoc Playwright
scripts, so callers can gate a build on its exit code.

The page count comes from the print path that `--export-pdf` uses, so it equals the
pages of an exported PDF and does not depend on the reader's scrolling container.

## Printing a chapter

`--print-chapter HTML ID` prints one chapter of a built artifact to stdout, as HTML or, with
`--chapter-format text`, as plain text. Tests and agents check what an artifact shows, for
example that a link resolves, directly from the command instead of a browser script; the
artifact's data island is packed, so reading it by hand needs a decoder.

It prints the chapter as the generator stored it in the artifact's data, without starting a
browser: what the reader runtime changes on load, such as interactive table controls, is not
included; `--check-rendered` covers the opened page. Chapter ids are the note slugs the artifact's table of
contents uses; an unknown id lists the available ones.

`obs-html --print-chapter HTML CHAPTER` and `obs-html-interim --print-chapter HTML ID` take the
same input and print the same form, so one instruction works for an artifact from either.
`obs-html` reads the built artifact, not a Document: a build through the core, `obs-document
--adapter html`, writes the artifact and no Document file, and the artifact stores the chapters
as the adapter rendered them from its Document. `obs-html` also takes a chapter's title for
CHAPTER; a title that two chapters share lists their ids. Like `--extract-comments`, it renders
nothing, so it refuses DOCUMENT and the rendering options.

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
    & uv run --quiet obs-html-interim --source $manifest --output $html
} finally {
    $ErrorActionPreference = $previous
}
if ($LASTEXITCODE -ne 0) { throw "obs-html-interim failed with exit code $LASTEXITCODE." }
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
  `scripts/new-worktree.ps1` checks this list in its preflight and takes its default browser
  from it; no other script repeats a tool id or path.

Both switches take no obs-html-interim arguments. `RUNME.sh` has no setup mode; winget is Windows-only.
