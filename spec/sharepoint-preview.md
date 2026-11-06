# SharePoint and OneDrive preview: feasibility research

Status: findings record. SharePoint/OneDrive preview stays a desired experience, but is not
investigated further (user, 4 Nov 2026). No generator or delivered artifact changes made.

## Desired experience

Readers should be able to open an artifact from a SharePoint document library or
OneDrive without downloading it first.

Distinguish two targets: readable document preview and full interactive artifact
execution. Neither is guaranteed merely because the service accepts an HTML upload.

## Findings

### What a limited preview host can do

A document-library preview can run an uploaded HTML file in a framed sandbox that allows
scripts but not same-origin access. In such a host, classic and module scripts, JSON
islands with DOM initialization, event listeners, inline event attributes, MutationObserver,
canvas, inline CSS/SVG and data-URI SVG can work, while both localStorage and
sessionStorage throw SecurityError. An external CDN script can fail to load there, and
the failure alone does not distinguish network, CSP, CORS and integrity causes. Blanket
JavaScript blocking is therefore not a safe assumption for such a host.

A library embedded in the artifact can run in such a sandbox: an embedded-minified Plotly
renders its graph in a local allow-scripts iframe sandbox without allow-same-origin, with
storage denied and zero network requests. A syntax error in an embedded variant is a build
failure, not a host limitation; rule it out locally before blaming the host.

Storage implications: current application-level localStorage use is remembered
appearance (`src/obs_html_interim/bars/settings.js`) and reviewer name
(`src/obs_html_interim/bars/comments.js`), both already catch access failures. Review data
is saved in downloaded HTML, not localStorage. In-memory state can support editing
for the lifetime of the open preview but cannot survive reload. Download/save
permission in the actual sandbox is not established by Blob URL creation alone;
test it independently before promising review persistence there.

The current generator emits an empty chapter container and stores chapter HTML in
a JSON script island; JavaScript populates the visible artifact
(`src/obs_html_interim/renderer.py:213-214,240`). This affects the entire artifact, not
only Plotly or CDN-backed diagrams.

In Chrome with JavaScript disabled, a generated artifact exposes only the menu icon as
visible body text. This reproduces an important failure mode locally, but does not prove
a host uses that exact restriction. An artifact that loads no external script fails the
same way, so CDN removal alone can neither explain nor fix it.

## Microsoft documentation and limits

- [Allow or prevent custom scripts](https://learn.microsoft.com/en-us/sharepoint/allow-or-prevent-custom-script):
  custom script is restricted by default on modern SharePoint sites and OneDrive.
  Temporary allowance on a SharePoint site resets within 24 hours; individual
  OneDrive custom-script allowance is not available.
- [Security considerations of allowing custom script](https://learn.microsoft.com/en-us/sharepoint/security-considerations-of-allowing-custom-script):
  Microsoft discusses scripts in HTML pages in document libraries and recommends
  SharePoint Framework (SPFx) for governed interactive solutions.
  Importantly, it also says blocking custom script does not stop scripts already
  inserted. These administrative controls must not be equated with a precise
  description of the file-preview sandbox or its runtime script policy.

The reviewed documentation does not establish the exact HTML click-to-preview
pipeline of a given host: sanitization, iframe sandbox, CSP, forced download,
and supported markup/assets remain unverified. Upload acceptance does not prove
preview support. Neither changing a filename extension nor moving scripts to/from
a CDN is a supported way to bypass host restrictions.

## Feasible directions, pending evidence

1. A pre-rendered, script-independent artifact surface could make content readable
   when JavaScript is unavailable, provided the actual preview accepts the HTML
   and required styling/images. Enhance that surface when scripts can execute.
   Query tables and diagrams must be rendered too, not just chapter headings.
   This would be a preview representation, not a restoration of all interactions.
2. If the service refuses useful HTML preview altogether, provide a PDF companion.
   That is a separate viewing artifact, not native interactive HTML support.
3. Full interaction may require approved web hosting or an SPFx viewer. That is a
   deployment/integration project, not a formatting-only fix.
   Do not weaken a host's security settings as a generator prerequisite.

Do not reverse the approved optional CDN delivery decision on speculation.
Inlining dependencies helps only when script execution is permitted and external
asset loading is the actual failure.

## Proposed requirement, not yet approved

### Constraints

- Validate with small files uploaded to the real host location, reporting what is
  visible and which interactions work.
- The artifact works as an uploaded file: it needs no host configuration change,
  no host-side deployment and no approval to run code. SPFx is therefore not the
  chosen route.
- Do not duplicate artifact data or store parallel static diagram fallbacks merely
  for preview compatibility.
- Prefer one readable HTML/DOM representation enhanced by JavaScript, if feasible.
  Without JavaScript, unavailable dynamic features should have a concise message
  telling readers to download the HTML and open it directly in a browser.
- Script cannot detect a blocked-script environment if it never runs. Baseline
  content and any no-script notice must exist before runtime initialization.
  A no-script notice alone does not cover every sanitizer/sandbox, so validate the
  real host path rather than relying on automatic "preview mode" detection.
- First determine whether scripts are blocked at all in the actual preview.
  A local disabled-JavaScript experiment is a hypothesis, not host evidence.

### Design direction where embedded libraries run

- Loss of remembered appearance and reviewer name is acceptable in preview.
- Centralize optional browser-storage access behind a shared capability boundary.
  Appearance persistence is superseded by the opening-state rule in [[artifact-ui]]:
  appearance is session-only and has no storage warning. The capability boundary
  and warning below now apply only to remembered settings such as reviewer name.
  If storage is unavailable, keep the control usable with in-memory state and show
  a small yellow exclamation indicator beside the affected control. Its tooltip
  should explain that the setting will not be remembered in this environment.
  Make the explanation available on keyboard focus and to assistive technology.
  Storage denial alone must not be labelled definitive proof of SharePoint preview.
  Suggested wording: "This setting cannot be remembered in this environment.
  Download the HTML and open it directly in your browser for full functionality."
  Do not promise persistence locally if that browser also denies storage.
- Embedded libraries are a viable compatibility option for such a host. This does
  not yet prove the entire artifact works: investigate current-artifact
  initialization and test navigation, tables, review, edited-HTML download and
  printing separately in the same preview.
- Minified generated HTML, CSS and JavaScript are acceptable; generated output
  need not be readable. Keep authored sources readable and reproduction archives
  faithful to those sources. Evaluate proper syntax-aware minification at the
  build boundary, not regex whitespace removal. Preserve licenses, script-island
  data, meaningful text whitespace, identifiers used across scripts, and reviewed
  HTML save/reopen behavior.
- Measure size and generation-time impact before selecting tooling. Vendored
  Plotly is already minified; minifying it again is not a meaningful saving.
  These are future implementation directions, not changes to today's delivery.

### Recommended next check

Use a diagnostic copy of an actual generated artifact, not another generic API
spike. Keep published deliverables untouched. Embed the existing minified
dependencies and expose initialization errors visibly in that diagnostic copy.
First reproduce it locally in an allow-scripts sandbox without allow-same-origin;
then upload the same copy to the target host. Fix demonstrated failures
surgically rather than adding a separate static representation.

Check content/navigation, tables/filtering, diagrams/expansion, appearance and
reviewer-name controls, comments/decisions/field edits, downloaded edited HTML
reopened locally, and PDF export. Mark host-restricted actions explicitly with
the download-and-open remedy.

The artifact now does this itself: see [Artifact UI](artifact-ui.md#dock-menu),
the notice center, for which features it includes and how their canaries report a
host's limits. Defer minification until compatibility works so
format transformations do not obscure diagnosis.

For agreed SharePoint/OneDrive viewing paths, artifacts should offer a readable,
script-independent representation of chapters, tables, and diagrams without
requiring a download. Preserve the existing interactive standalone artifact when
scripts are available. If HTML preview is unsupported by the target service,
document that boundary and offer an explicit PDF viewing alternative instead of
claiming native compatibility.

Acceptance must include the real host viewing path, not just a local browser
test with JavaScript disabled. Reading support and interactive support must be
reported separately.

## Next evidence to collect (if the investigation resumes)

A diagnostic probe tests static content, script execution, DOM/JSON initialization,
graphics, browser APIs and pinned CDN loading independently, and carries no artifact
data and no automatic telemetry. Compare local-browser results with the same file in
the host's preview. A probe is research, not a generator behavior change.
Keep actual-artifact diagnostic generation reproducible from ordinary generated HTML
without changing chapter data or authored generation settings. Its error banner
must not intercept artifact controls.

Visible computed values in a host's preview are evidence against blanket script
blocking only once it is established that the file computes them on opening rather
than storing them in its saved markup. Prioritize a selective
script/API/asset/initialization failure comparison before proposing an HTML-first
redesign.

- Compare a working file and a failing file in the same library, browser, and
  opening method; record whether links open a preview frame, raw document, or
  download.
- Determine which actions actually work: chapter switching, filtering, editing,
  and diagram rendering. Visible text alone is not proof scripts execute.
- Inspect browser console/network errors and response headers, including CSP and
  iframe sandbox restrictions, without uploading private artifacts elsewhere.
- Use a tiny probe in the same host to test static text, embedded
  styling/images/SVG, inline JavaScript, and version-pinned external JavaScript
  separately. No host configuration changes are needed for this diagnosis.
- Only then select static preview, PDF companion, or approved interactive hosting.
