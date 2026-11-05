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

Reader: whoever renders a Document with command fences or reads captured command output in one.

obs-html never runs a command. The core runs command fences while it builds the Document
(`obs-document --execute-commands`), replaces the build machine's paths in their captured output
and puts it into the node; obs-html renders that output as preformatted text. The core's
capability note `spec/capabilities/command-fences.md` owns the rules.

Every build then checks the finished artifact, the HTML and the decoded artifact data, for the home
folder and the user name as a path component, and fails naming where it found one and the remedy,
before anything is written. A hit in captured output is an obs defect; a hit in authored content
is fixed in the source.

## License

[MIT](LICENSE).
