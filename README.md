# obs-html

The HTML and PDF output adapter for obs. It renders a contract-valid JSON Document, and nothing
else, to portable HTML or PDF.

## Core

This adapter is the `adapters/html` folder of obs and a member of its uv workspace: it depends on
the core of the same commit through a workspace path dependency, so a core change and its adapter
change land together. Its tests run from this folder and test only the adapter:

```powershell
uv run pytest
```

## Adapter

obs's root `adapters.json` registers the `html` adapter and `adapter.json` declares the contract version,
the `obs-html` command and the capability identifiers it renders. `uv run obs-html --help` is the
command reference. Run the focused contract check with:

```powershell
uv run pytest test/test_adapter_manifest.py
```

`uv run obs-html-inspect --help` is the reference of the PDF inspection tools, which read a
generated PDF without a viewer so print output can be verified automatically:

```powershell
uv run pytest test/test_pdf_inspect.py
```

The adapter's own features are documented as capability notes in
[spec/capabilities](spec/capabilities), for example the trusted extension
[attachment replacement](spec/capabilities/attachment-replacement.md).

The artifact runtime's DOM tests run in Node over a test-only DOM adapter; install it once with
`npm --prefix test/browser ci`, then `uv run pytest -m dom` runs that tier alone.

The artifact verification harness, `test/browser/artifact-harness.cjs`, opens a rendered artifact in that
DOM and drives it step by step (data, chapter, table, page mode, print and presentation geometry);
its header comment is its reference.

## Images and attachments

Reader: whoever puts images in a Document for obs-html or changes how it renders them.

An image renders from the bytes of its Document asset
([Asset bytes](../../spec/design_input/architecture.md#asset-bytes)) as a `data:` URL, whatever
its origin, a vault file or a remote image the build fetched; the artifact never reads the vault
and never loads an image URL, so it shows every image without the network. An image whose asset
has no bytes, a remote image the build could not fetch, shows its alt text as a visible label in
its place (its URL as text where it has none); the core's build warning names the remedy. Any other
attachment renders as provenance text: its label and its vault-relative path. Whether a referenced
file exists and stays inside the vault is the core's input check, not the adapter's.

## Command fences

Reader: whoever builds an artifact with `--execute-commands` or reads captured command output in one.

A generated artifact never contains the build machine's absolute paths. Before captured command
output (stdout and stderr) is embedded, obs-html replaces:

- paths inside `--command-root` with paths relative to it (the root itself becomes `.`);
- the home folder with `~`;
- every other absolute path, such as temporary and virtual-environment folders, with the
  placeholder `<local-path>`.

Commands run with a minimal environment, so an environment dump carries nothing machine-specific
beyond the paths replaced above. They inherit only `PATH`, `PATHEXT`, `SYSTEMROOT`, `WINDIR`,
`COMSPEC` (to find and start programs), `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA` (per-user
tool settings and caches), `TMPDIR`, `TEMP`, `TMP` (temporary folders) and `LANG`, `LC_ALL` (text
encoding), where they are set; a command that needs more sets it itself.

Every build then checks the finished artifact, the HTML and the decoded artifact data, for the home
folder, the user name as a path component and the command root, and fails naming where it found
one and the remedy, before anything is written. A hit in captured output is an obs-html defect;
a hit in authored content is fixed in the source.

## Registers

Reader: whoever embeds a `.base` file in a note built with obs-html, or changes how obs-html shows one.

A register renders from its `registers` node alone (obs
[capabilities/registers](../../spec/capabilities/registers.md), "Document node"): each view shows
the rows the core selected for it, and obs-html evaluates no selection of its own. A view's
`obs.members` only labels those rows as `obsHtml.label`; the core sends them in member order,
which obs-html keeps ([generic-tables](../../spec/design_input/generic-tables.md)). A `documentMetadata` view also shows
obs-html's generation rows (`timestamp`, `generator`, `target`) that its filter selects, since the
core has none. A query the reader edits in the table's Query view narrows the register's rows.
Members need the core's rows, so a `base` fence whose view declares them fails the build; the
remedy is to move the Base into a `.base` file and embed it.

## License

[MIT](LICENSE).
