# Retro draft for #80

## 1. Collect

<!-- collect: Per project, what retro.py collect read: what came back, refusals, escalations, suite times, session costs, scripts run three or more times, planning misses, the field reports' answers to the standing questions, and the last retro's classes measured again, rate before against rate now. -->

### Field feedback

## 1. Field feedback

Field feedback was not requested. Per the current instruction, this retro proceeds from issue, pull-request, test and session records without asking or waiting for feedback.

Window: the whole history up to 2026-11-25T10:49:36Z; no retro issue has closed.

### Sizes

| size | this window |
|---|---|
| closed | 23 |
| landed | 23 |
| duplicates | 0 |
| escalated | 3 |

### Landed issues

| issue | refused deliveries | escalations | suite time | field report |
|---|---|---|---|---|
| #1 unchanged-output-stands-alone | 0 | 0 | 422.1 s | #8 |
| #2 links-stay-inside-repository | 0 | 0 | 418.7 s | #9 |
| #3 own-spec-build | 0 | 0 | 422.2 s | #41 |
| #4 drop-stale-commit-allow-entries | 0 | 0 | 418.4 s | #6 |
| #5 one-bar-comments-and-fields | 0 | 0 | 411.5 s | #16 |
| #7 name-is-obs-html | 0 | 0 | 402.6 s | #13 |
| #11 block-records-from-obs | 0 | 0 | 409.8 s | #12 |
| #15 pugh-browser-test-flakes | 0 | 0 | 402.7 s | #19 |
| #17 tests-never-wait-on-time | 0 | 0 | 400.3 s | #25 |
| #22 browser-as-io-door | 0 | 0 | 421.4 s | #27 |
| #29 fake-browser-door | 0 | 0 | 440.4 s | #48 |
| #30 more-logic-to-fake-browser | 0 | 0 | 504.7 s | #52 |
| #31 browser-door-recorder | 0 | 0 | 449.4 s | #50 |
| #32 viewer-logic-to-fake-browser | 0 | 1 | 517.8 s | #64 |
| #33 layout-logic-to-fake-browser | 0 | 1 | 509.2 s | #57 |
| #34 hot-tests-record | 0 | 1 | 519.5 s | #62 |
| #35 metadata-cards-in-the-bar | 0 | 0 | 409 s | #46 |
| #38 dom-tier-on-fake-browser | 0 | 0 | 476 s | #54 |
| #42 own-spec-reason-rewritten | 0 | 0 | 417.5 s | #43 |
| #58 generic-style-component | 0 | 0 | 473.1 s | #56 |
| #67 present-templates-capability | 0 | 0 | 570.1 s | #68 |
| #69 cloud-browser-runs-the-suite | 0 | 0 | 615 s | #70 |
| #76 body-aligns-with-headings | 0 | 0 | 569.3 s | #77 |

### Rule checks

- **work-issue**: every landing pull request names a work issue that was open when it merged: broken 2 of 26
  - #79: names no work issue (Fixes|Refs <issue url>)
  - #73: names no work issue (Fixes|Refs <issue url>)
- **check**: the check `check` passed on every landing pull request's head in its last run before the merge: broken 1 of 26
  - #40: check failure
- **outside-pr**: no commit reached the integration branch outside a pull request: broken 298 of 324
  - b3f3d7bd34ef: Set up se: the project's settings in se.toml, se's pin in se.lock and se's release workflow
  - 9de9da56c710: Stand the HTML adapter alone: pin a core release, its own CI and release
  - 66f62f8193a1: Integrate styles-by-name: `obs.style: <name>` names an installed style component, and obs-html stops fetching styles, so no committed document names where a style lives.
  - d699458a802f: Integrate plugin-versions-recorded: Every Document carries the name, kind, version and commit of each component that builds it, every artifact and source-archive build record holds them
  - 937785c86832: Integrate plugin-command: `obs-components` finds every component repository under the owner (the account or organization) of each remote of the checkout, lists their tagged releases with installed and newest versions
  - 64d593ed3914: Integrate authored-block-ids: Make authored block IDs distinguishable from generated IDs without changing existing IDs or link targets.
  - 79397d9b7f15: Integrate feature/style-cover-template-20261120: Allow a style module to provide an optional cover template rendered with document values, while preserving the built-in cover for styles that do not provide one.
  - 7296a3929c3c: Integrate zero-marks-show-zero: Every place obs shows a matrix mark shows 0 as "0", so a mark reads as the number it is.
  - 77f081787725: Integrate fix/empty-title-and-provenance-public-20261120
  - 53dfce5d8239: Integrate plugins-found-on-remotes: The design notes describe one mechanism for every adapter and style, called plugins: each plugin is its own tagged repository
  - 57f122a3a9dc: Integrate screenshot-a-chapter: One documented command line saves a chapter of a built artifact as a desktop's or a phone's screenshot.
  - 9524f90cc51d: Integrate leads-under-their-links: In a bottom line's list of children's leads, each child's title stands alone on its line, with its lead on the next.
  - 5275157d4019: Integrate provenance-check-upkeep: The note says a key twice breaks the comment island's shape, and the planted path stays allowed when its line moves.
  - 8b53cbbf3dd2: Integrate comments-come-back: The extraction prints one call that brings a reviewer's comments back into the vault.
  - 7b1232f3aa82: Integrate bottom-lines-percolate: A chapter's bottom line is a `[!bluf]` callout that the reader sees first, under the chapter title
  - 96f075433f4c: Integrate unify-neutral-main: One neutral tree is shared by every copy of obs, with no account names and documentation linking owners instead of issue numbers
  - 6a5043210bd7: Integrate detail-selection-comments: A reader comments on text selected in a row's expanded note detail, a `details: columns` row body too, as before 9 Nov
  - 45edcfb9fc80: Integrate embeds-show-the-block: An embed of a block or a section shows that block or section in place, as Obsidian does
  - a5099a2fdc42: Integrate obs-recorded-gaps: Each gap obs workers recorded on 17 Nov is decided: the notes say what the page does
  - fd83a51f8bc8: Integrate dom-contract-runs-every-check: The DOM contract's default run reaches every verify step, verifyPages and then verifyComments
  - 6c795e1e4659: Integrate obs-adopts-generic-runme: Obs runs from a clean machine through the same two RUNME files as SE
  - 99048fa6253d: Integrate table-rows-one-line: With `artifact.tableRowsOneLine` on, as packaged
  - 64902ea15342: Integrate theme-choice-in-settings: On a page that carries local themes, the Settings bar offers a Theme select below Appearance
  - 9628e69b0d74: Integrate local-theme-rules: A local theme may hold a `style.css` of its own, its fonts, spacing, rules and logo
  - d44cea8395df: Integrate local-themes-folder: A page built on a machine that holds local themes carries their colours beside Default and opens in that machine's start theme
  - fcfc89db3724: Integrate starting-appearance-setting: Every page obs-html builds opens in System appearance, which follows the reader's operating-system theme
  - 64e6743da974: Integrate metadata-caret-source-link: Every page of an HTML artifact shows the faint chevron, whose table ends with a `Source file` row
  - 5f320e3eb4ba: Integrate feat/table-live-web-20261116: A table with a live source can also read current values from a public web endpoint
  - 98d4d91160f2: Integrate feat/table-live-rows-20261116: In Claude's artifact viewer, a table with a live source reads what changed since the page was made
  - e37d24003c30: Integrate check-exceptions-by-digest: An author can add an exception to obs's build checks, the provenance check first
  - a60263ed5b24: Integrate feat/table-live-source-20261116: A table can say where newer values of its rows come from, and obs checks that statement against the rows it built.
  - dad8340509d3: Integrate unchanged-output-check: A worker can show with one command which of obs's reference pages a change leaves byte for byte as they were on main
  - f6a7f076a3a2: Integrate adapter-spec-builds-clean: The HTML adapter's own specification builds without a provenance warning, and stays so.
  - f5cd54ac6568: Integrate compare-two-builds: A worker can compare two builds of an artifact with one command that says whether they are identical and
  - b579344ffba0: Integrate failed-send-plain-words: When a reader's Send fails, or sending is not available on the page, the notice center says so in plain words
  - 00510f1edce2: Integrate passing-line-ships-opt-in: A page built without the setting for Send's passing line is again what it was before that line was added
  - feeee1e0ac31: Integrate sent-line-below-bar: After Send, obs can confirm it with a short plain line under the top bar that fades after a few seconds
  - d38cf4fe3d9b: Integrate figure-column-table-notes: The design notes state three rules that obs-html's code already follows, for figures
  - 189dd182a1d9: Integrate pdf-links-without-local-paths: Links in a PDF that obs prints no longer hold a full path of the machine that built it.
  - 44f985de5167: Integrate source-date-epoch: With the standard `SOURCE_DATE_EPOCH` variable set
  - bf6524eab8bf: Integrate action-icon-rules-at-build: A page whose table action icon breaks the schema's rules for its unavailable reason fails to build
  - a567340612df: Integrate schema-pattern-parity: Obs-html checks a table definition's text patterns the way the page does.
  - 9d64f019cbfc: Integrate build-refuses-what-page-refuses: A build refuses what the page's script refuses in a table beyond the schema, unless the check needs other notes
  - 1145c7bbe767: Integrate search-skips-hidden-fields: In a table view that hides fields from its opened rows, a plain search word no longer finds a row by a hidden field.
  - 87522c92aa6b: Integrate fix/table-view-options-checked-at-build-20261116: A build that contains a view option the schema refuses fails with the core's one error form, naming the note
  - ef3e257f9bf2: Integrate feat/table-detail-shows-chosen-fields-20261116: A table view can say which fields an opened row shows.
  - 91b56d5d275c: Integrate fix/reopened-comment-highlight-lands-on-its-quote-20261116: A reopened reviewed copy paints every comment's highlight exactly on the text the comment quotes.
  - 79175c1df7cc: Integrate feat/two-column-blocks-20261116: Build the `|||` two-column block that obs's input model already specifies
  - 1f234295dae3: Integrate fix/table-headers-carry-no-sort-instructions-20261116: Column headers carry no instruction text.
  - b8da0ba4b4d7: Integrate feat/register-exceptions-first-20261116: A table view can declare which of its rows pass.
  - de2e1958ba2a: Integrate feat/timeline-figure-kind-20261116: Add a `timeline` figure kind that draws dated note records as a lane timeline inside the house figure frame.
  - b2c857332dde: Integrate feat/register-empty-declared-groups-20261116: A grouped register can list its expected group values in `obsHtml.groupOrder`
  - 5c78016e1dee: Integrate chore/neutral-home-20261116: General problem: the same tree may live on more than one Git host, so no tracked file should name where it lives.
  - bec8aca2c541: Integrate test/verdict-print-parity-and-artifact-bytes-20261114: The printed verdict that landed today is held to what the reader's page shows, in full, by one browser test.
  - d7f15e517265: Integrate feat/pugh-verdict-as-text-20261114: Obs prints the computed verdict of every decision in a Document as text and as JSON, without a reader's page
  - 68da20c091a0: Integrate feat/page-shell-limited-host-and-provenance-check-20261114: Two things for pages obs builds
  - add73ecf3b56: Integrate feat/pugh-engine-computes-the-verdict-20261114: Obs's `pugh` fence computes its decision instead of only drawing it
  - 0590f575fa7c: Integrate feat/first-chapter-second-checked-on-ci-20261113: Obs promises that a document's first chapter shows within one second.
  - 3ce2b24e577a: Integrate fix/first-chapter-test-not-runner-bound-20261113: `adapters/html/test/test_startup_browser.py:test_the_spec_artifact_shows_its_first_chapter_within_a_second` fails...
  - 9aaf8661923d: Integrate chore/pins-current-se-5-26-and-js-yaml-20261113: Keep obs's pins current and complete.
  - 8fb4a662396a: Integrate chore/vendored-libraries-pass-size-rule-20261113: Two vendored minified JavaScript libraries in obs are over SE's 200 KB file-size rule.
  - 151a290014f5: Integrate chore/relock-se-5-25-20261113: Obs pins SE 5.3.0, and SE has moved to 5.25.0 in two days.
  - 9616226b2205: Integrate docs/layout-names-measurement-scripts-20261112: Name test/measure/ as the place of measurement scripts and move the library cost...
  - 1d5cb9dae8a8: Integrate perf/load-libraries-on-first-use-20261111: Record the library cost measurement and why libraries stay evaluated at opening
  - 4f7d7ff76c7c: Bound the locked-page sweep by the page's own opening time
  - 18fd8e4a6c07: Put the tests that print a PDF in Chromium in the browser tier
  - fcb85e143966: Put the tests that build a whole Document or package in a build tier, and warn of a test far slower than its tier
  - 149984aaecb4: Build every test artifact with the library fakes, the named set with the real ones
  - 2b6276ec93e2: Give each library door a fake held to the door's contract
  - 1759cf51c5a5: Reach Plotly, math.js and pdf-lib each through one door
  - 4cdb02ff8953: Give the complete suite headroom under its time limit
  - 60b998c11386: Merge remote-tracking branch 'origin/main' into fix/no-dead-download-links-in-claude-app-20261111
  - 575bc026a1db: Save every file offer through the host's save path, so none is dead in Claude's artifact viewer
  - 807966602260: Have the two-reader export test answer the other reader's reply
  - 029ea0830cd0: Import several returned comment files in one call
  - aa6664fb6d6a: Export a reviewed copy as one comments file per author
  - 955e8bc5cc54: Hold comment entries to their file's names, times to milliseconds, Delete to own comments
  - 022cd068c62a: Merge remote-tracking branch 'origin/main' into feat/comment-abstract-target-and-state-entries-20261109
  - be4307e1e201: Comments: list state entries and abstract targets in the extracted text
  - 0f715ee512ee: Comments: target the manifest abstract, record resolves as state entries
  - d405c1539a76: Comments: the core writes a returned copy's overlay file
  - 7c867e67cfa5: HTML adapter tests: check the native thread fixtures in two core calls
  - be4741f55b8d: HTML adapter: a selection targets the block it starts in
  - bce528f40704: HTML adapter: comments and reviews through the core's model
  - ea4c73d6ef04: Give every block node a stable id
  - bd998e76af14: Deal CI's shards by committed group weights, heaviest first
  - 03453595dd2d: Draw a first page when a pool's browser launches
  - c8cb91181a61: Run CI's suite in two shards
  - 796cc46a2a67: Bound a page's release with a watchdog, not a polled evaluation
  - a136912cf2d0: Keep one sweep child per test process
  - 27aa89e68b4f: Close a pooled page that does not answer while it is released
  - d979d9437d0f: Sweep each viewport in a child of its own, the phone at device scale 1
  - c5e3dd3cf15b: Sweep every chapter at phone width too
  - 37119aba1a34: Let the plot legend correction converge
  - 38d0ccfc0d6b: Test that the plot legend correction converges
  - bb8326a4bbbc: Switch transitions off under reduced motion instead of shortening them
  - cc575476bae1: Sweep every chapter of every fixture artifact, with and without reduced motion
  - 8b0a6217ff10: Ship each feature's share of base.css only with that feature
  - 4308c65e1576: Ship the reader's Base-table code only with the tables feature
  - bfbc497d78cc: Remove unused runtime exports, unreachable style rules and an unused alias
  - 73a66f912025: Ship each runtime script, style and data island only where the Document uses it
  - 18824b41f921: Decisions carry a success criterion per option and a Proposed winner box
  - 666945610bd1: Bless and Decline take the review's acceptance and rejection colours
  - 22fe1b73b13a: Screens drop the top band's chapter counter
  - ac7bbd9de78a: Launch each page pool's browser before the first test that needs it times anything
  - e599d490e389: Prepare the test workflow with the suite's own setup
  - 8a1fc459bf47: Decision chapters read as Potential solutions, then Details
  - 5163a47bec31: A print draws from a copy of the reader's state and never writes it
  - 5afbeee926ab: Phone width: both decision tabs fit 360 px, the grid a block per option
  - 47fe2b9a4ab0: Pareto tab: the options over the criteria, drawn by the engine's plotSvg
  - d26c678667c9: Merge origin/main
  - 738ee023afc3: Sensitivity tab: the what-if prose becomes a grid of tie weights
  - 0d2768f1ddeb: Integrate feature/decision-figure-layout-20261106: adapter
  - 0b77f6d29c2f: Screens leave Home when a cleared filter or the screens view brings chapters back; the walk tests read the screens walk
  - ff25018fdf39: Test that only screens drop Home: scrolling and paged artifacts open on it
  - b3f4ebc2d5dd: None of the above: Pick offers it beside the letters, it needs a comment, and the answers file records option none
  - 4d778314bc27: Verdicts toggle: the active key or pick, chosen again, clears to pending; pick, picked and obs-bless-change for the figure
  - a48025d4a976: A verdict never walks: the chapter stays after a bless or a confirmed comment
  - bd446eb220b6: Screens open on the first chapter: no title screen, Home goes to chapter 1
  - 180ed8ba099c: Record each passed test's tier and time per suite run
  - 02a4a19134b7: Deal each part's xdist groups heaviest first by recorded weights
  - 1d42f56818e5: Share one adapter-spec build per run across the spec's builds
  - 658b1a43aa62: Test on a phone that the options list and the popover say each name once
  - 027e6c345291: Point the reading shell's clearance sentence to the touch exception in Screens
  - 4f5fb3a49de9: Say an option's name once in the options list and the letter popover
  - 6780c0b5ac21: Integrate fix/phone-side-arrows-and-option-repeat-20261106: adapter
  - 737d74a4283f: Integrate perf/slow-test-modules-20261106: core
  - 85c4d9580e2c: Merge remote-tracking branch 'origin/main' into fix/decision-figure-follow-ups-20261106
  - 19af8f6d5322: Open a decision figure's tab where a link leads into it
  - c87b0712a355: Resolve a decision option's short name once in the core
  - 3a7df59cc88c: Integrate fix/fixture-found-layout-faults-20261106: adapter
  - 4e2e98d6bf4a: Integrate feature/screen-layout-for-decks-20261106: core
  - 933517ea843f: Say that a letter in the decision rows is a control apart from its mark key
  - f009b4f04260: Name an option by its letter and short name, and open its letter in the rows
  - b4e5a65a0e8e: Merge remote-tracking branch 'origin/main' into feature/decision-figure-on-phones-20261106
  - 66e1cb1bd687: Draw the decision matrix as rows of letters on a narrow figure, with the chapter's sections as tabs
  - ae42a34686f2: Test decision figures on emulated phones at 360 and 390 px
  - 6325ead99472: Fit every bless band control in one row of one square size
  - 2d9f4114796a: Test the bless band at 360 and 390 px with the notices shown
  - a95a292845ca: Build the example deck through the core's command, and read the winner in a decision figure's reader state
  - b8f0589e1691: Build and walk an example deck of two decision chapters in obs's spec
  - f46491f43c2c: Show an answered chapter's verdict read-only, so the answered artifact is the decision record
  - 629f1dd39eb3: Bless, decline, ask or pick another option from the top band, and send the verdicts at once
  - 171e147c1fe9: Walk to the previous or next chapter with a horizontal swipe on touch
  - a33b3d0e69cf: Integrate chore/derived-test-lists-20261106: adapter
  - d64c42b86622: Merge remote-tracking branch 'origin/main' into feature/pugh-decision-figure-20261106
  - 0e3365f9e95d: Show a decision as lettered options, a changeable matrix, a checklist and what-if tabs
  - 23ffcf7cac19: Merge remote-tracking branch 'origin/main' into feature/pugh-decision-figure-20261106
  - 2d7e41927cd3: Keep a decision figure clear of the chapter controls, whole on its page, one review item
  - cc910a2bf9e2: Merge remote-tracking branch 'origin/main' into feature/pugh-decision-figure-20261106
  - 9400a4f5d4bd: Say the chosen option's name in a clause, and hold a cut criterion name in its tooltip
  - a1584d9f8702: Draw a decision figure in the page: bottom line, matrix, check, phone width
  - e2ac561e33e8: Carry ctrl's Pugh engine unchanged, checked against ctrl's test vectors
  - e5162137012b: Integrate fix/after-interim-removal-20261106: core
  - e87dfac496b5: Sweep each width of the coverage check in its own test
  - bd432b20e249: Name only current commands and paths in the README, AGENTS.md and the specs
  - a046b908e08d: Describe obs-html and the one-call build in the adapter's CLI and configuration notes
  - 778e8d148576: Build only obs's spec Document once per run
  - 4f118148a9f1: Hold the adapter and the core to their own output instead of the interim adapter
  - 8d75b0c26e27: Merge remote-tracking branch 'origin/main' into fix/no-test-can-hang-the-suite-20261106
  - f28f83d2edd9: Recover the html adapter's page pools from a crashed or unanswering browser
  - 906df7ce90dc: Give every test its tier's timeout, a measured multiple of the tier's slowest test
  - 12bb1c8dc995: Integrate perf/spec-built-once-per-run-20261106: core
  - 3a8feed21215: Split the long paragraphs left after the vault-settings and timing changes
  - 397e7008c837: Merge remote-tracking branch 'origin/main' into docs/spec-paragraphs-within-the-limit-20261106
  - aade73eed247: Split the html adapter's spec paragraphs to the long-paragraph limit
  - 5f10ed4d904e: Integrate fix/one-call-build-refuses-output-inside-the-vault-20261106: core
  - b4ad71eddd88: Integrate fix/export-pdf-carries-the-source-zip-20261106: adapter
  - ce7f70ebac2b: Integrate feature/long-paragraph-warnings-20261106: core
  - 3afc07863b2f: Merge remote-tracking branch 'origin/main' into fix/adapter-bordered-tags-20261106
  - 806d6a00d779: Parity table: artifact.borderedTags is the same as the interim's
  - fb2f8cdb1332: obs-html encloses paragraphs of bordered tag kinds in one shared titled card
  - bcaa80e07a84: obs-html settings accept artifact.borderedTags with the interim's default and limits
  - 59beac561732: Integrate perf/suite-headroom-20261106: adapter
  - 37866fe525c3: Integrate feature/adapter-applies-declared-style-20261106: adapter
  - ddbbefb8e677: Integrate chore/parity-audit-before-removing-interim-20261106: core
  - d19fc695dd15: Integrate fix/sankey-fence-checked-at-build-20261106: core
  - 681a4a1a943e: Integrate perf/suite-headroom-20261106: adapter
  - 491d1eb73005: Integrate fix/spec-vault-self-contained-20261106: adapter
  - 314cd1dae8b7: Test that the installed core draws Mermaid and PlantUML offline
  - 9501d9672ded: Integrate feature/style-as-declared-dependency-20261105: core
  - e1a6a701b58b: Integrate feature/figure-descriptor-data-shapes-20261105: core
  - 6c00af41bd69: Load the packaged maths library in the equations Node test
  - f110febaffae: Merge remote-tracking branch 'origin/main' into chore/adapter-ships-its-browser-assets-20261106
  - 021455cc1a45: Test that the installed obs-html wheel renders without the repository tree
  - 65949fb40d0f: Ship the adapter's browser assets as package data built from their lockfiles
  - 5a3d32989c6c: Integrate perf/suite-back-under-90s-20261106: core
  - b689f8eafe4f: Print render.py's limited-function warning through errors.warn
  - b41b82c419c5: Print the Document's diagnostics only when obs-html runs directly
  - d45acbce4dd7: Integrate fix/titles-and-labels-as-nodes-20261106: core
  - 1d885262d80e: Integrate feature/source-archive-refers-to-generator-20261106: adapter
  - 3601ebcff23c: State that --print-chapter cannot show labels the artifact computes at runtime
  - 9528a9a86210: Guard that every adapter message is raised or warned through errors.py
  - 2b82df2dd338: Name a figure-style warning's note below the vault root
  - bf68e9b70bb7: Integrate fix/sankey-label-counts-its-rows-20261106: adapter
  - ae9aedc0d366: Integrate feature/adapter-source-archive-and-snippets-20261106: adapter
  - f22ab755774e: Integrate feature/parallel-coordinates-20261105: adapter
  - c96d779a18ae: Integrate fix/figure-references-complete-20261106: core line
  - fc74782720e4: Integrate fix/authored-svg-styles-stay-in-their-figure-20261106: adapter line
  - 232d7f408e11: Select a Sankey node's drill-down exactly as its label counts
  - f78ecd8c2547: Test a Sankey node whose own records narrow its drill-down
  - e2b13dd84bd8: Integrate feature/equation-figures-live-20261105: adapter line
  - 439aaffe0ac9: Integrate fix/heading-link-labels-and-command-output-markup-20261106: adapter line
  - bc8b8fcf0c83: Merge remote-tracking branch 'origin/main' into fix/startup-test-stable-under-load-20261106
  - a2b9b2804563: Time the spec artifact's startup from its own marks, budgeted against same-run load
  - d2ecf9aaecb9: Integrate feature/equation-figures-core-20261105: core line
  - 9968c333b22b: Integrate fix/every-drill-down-matches-its-count-20261106: core line
  - 8b07b0452f9d: obs-html prints a chapter of a built artifact
  - ac0644d2b1e5: Integrate perf/coverage-sweep-without-repeats-20261106: adapter tests
  - 9091c020ae18: Merge remote-tracking branch 'origin/main' into feature/diagram-fences-20261105
  - 943cf2351ec7: Show diagram figures in the one figure frame
  - dc45d1daca4b: Merge remote-tracking branch 'origin/main' into feature/one-figure-class-20261105
  - 43c17de1708c: Declare a figure kind's library need through the feature registry
  - 03c7f2a7bba3: Give figure kinds with view options the tables' options menu
  - 1b902785236f: Merge remote-tracking branch 'origin/main' into feature/one-figure-class-20261105
  - 6a04da5eec12: Frame every figure kind in one figure frame from a kind registry
  - 3d42e4d30f3d: Emit every figure as one figures node of a kind, inline or from a source file
  - 362182e3a2dc: Restate obs's output-format sentences without naming HTML
  - 72248836f2ba: Split cover metadata and reviewed copies by owner
  - d434dfcd94bc: Integrate docs/html-spec-is-a-reference-20261105: adapter line
  - e332b0436efb: Merge remote-tracking branch 'origin/main' into feature/core-validates-cover-metadata-20261106
  - 2e68bb60f43f: Validate the manifest's cover metadata in the core
  - e9d388356629: Integrate chore/browser-deps-as-suite-setup-20261106: core line
  - 176671d95a9d: Integrate fix/clipboard-test-stable-under-load-20261106: adapter tests
  - 4e41c76301d9: Integrate fix/every-adapter-error-names-place-and-remedy-20261106: adapter line
  - 32d4f1e8c606: Let reader-facing text name the document number field
  - 811488e7b1a9: Merge remote-tracking branch 'origin/main' into fix/generic-document-number-field-20261105
  - 520681120714: Fail when a core schema or the HTML adapter names a vendor in a field
  - 6347727ee463: Name the manifest's document number generically
  - 60dabfe5f1f6: Integrate feature/adapter-one-selection-rule-set-20261105: adapter line
  - c1234d7fa2eb: Merge remote-tracking branch 'origin/main' into fix/property-editor-projection-per-spec-20261106
  - 92d2bf74b3ed: Merge remote-tracking branch 'origin/main' into fix/property-editor-projection-per-spec-20261106
  - 16b8c25c0244: obs-html renders a core-built property editor projection
  - 523da0ac0712: Integrate feature/field-nodes-for-every-record-20261106: every record carries field nodes for its string values
  - a72d03f1925c: Integrate fix/hashed-deny-list-repo-wide-20261106: the deny list holds salted hashes and covers the repository
  - 6c892390ea9c: The attachment download belongs to the downloads feature
  - e5b9e193e4f3: obs-html offers the light and the evidence edition with --embed-attachments
  - 6dd3c56ba9fc: Integrate feature/only-used-features-ship-20261105: clipboard and download remedies on use
  - 1a4abca25e06: Merge remote-tracking branch 'origin/main' into fix/block-nodes-never-inside-paragraphs-20261105
  - eeb933794e8b: Merge remote-tracking branch 'origin/main' into fix/block-nodes-never-inside-paragraphs-20261105
  - 359b2f2fef9d: Place the adapter fixture Document's note embed beside its paragraphs
  - 476be7256c7e: Merge remote-tracking branch 'origin/main' into fix/block-nodes-never-inside-paragraphs-20261105
  - 322bd0974bf2: Remove the adapter's paragraph split now that the core places no block node in a paragraph
  - 96a79bc1130f: Split a paragraph around each block node so none is a paragraph's child
  - 30f1bdf3e093: Integrate fix/hidden-manifest-lines-20261105: Obsidian comments hide manifest lines and never render
  - d317eae1b4c0: Integrate feature/card-bodies-from-nodes-20261105: card bodies render from the core's nodes
  - 2f5a9ded1ae6: Integrate fix/adapter-writes-valid-html-20261105: the adapter writes valid HTML, checked on every artifact
  - 703b89e84efc: Integrate feature/command-authorization-through-adapter-20261105: the core runs command fences under explicit authorization
  - b9701bccbd2a: Integrate perf/every-check-in-the-gate-20261105: the suite rebuilds every adapter fixture with the current core
  - 0a45d8c77d0c: Integrate feature/one-row-top-band-20261105: one top row; the title page shows its type once
  - d74488c28140: Integrate perf/every-check-in-the-gate-20261105: non-interim checks join the suite; tests stay offline
  - 0e56d8e52167: Merge remote-tracking branch 'origin/main' into feature/registers-from-node-20261105
  - 7893c89f5288: Drop Base-level members from the adapter's Base schema; rebuild the stale fixture Documents
  - 0e988d57675a: Read membership only through the core's rows; a view's members order and label them
  - dce0641727db: Render a registers node from its attrs: each view's rows are the core's, for every record type
  - 6effff19df1c: Render a core-built callout whose body holds a list, a wikilink and a nested callout
  - bdcc3ffe709d: Drop the callout syntax-extension registry: the core sends callouts without an extensions marker
  - 706fef25a06c: Integrate feature/structural-nodes-rendered-20261105: the adapter renders every structural node type
  - f3b6a5040674: Test that the spec artifact shows its first chapter within a second
  - 27a82c0807c7: Artifact startup runs in 50 ms slices and numbers pages once
  - 5a1f65df74fa: Dark is a near-black page with light grey text
  - 3e42e65aa960: html and body paint the appearance's background and text colour
  - a137a4448285: The root's color-scheme alone follows the chosen appearance
  - 314e34de7dc4: Add the artifact-viewer fixture and appearance regression tests
  - b5cf12613256: Batch the parity gate's browser checks
  - 0d52d25127cd: Build obs's spec and the shared fixture artifacts once per run
  - 76aa469c60ca: Run the complete suite in parallel workers
  - e1f07bf376b0: Describe one repository with an adapter folder in README and AGENTS
  - 8fc7d20a5c30: Read the core's selection conformance fixture from the adapter's runner
  - cfaf4374c945: Render an unknown Document node type as its text with one warning
  - 7559fdf68624: Name the adapter's presentation capability artifact-presentation
  - 4311d42e1f38: Make the HTML adapter a uv workspace member registered by the root adapters.json
  - 6650ca9b05d8: Rename the interim adapter to obs_html_interim and obs-html-interim
  - 09cd0f2539a4: Integrate refactor/report-becomes-artifact-20261105: the rendered output is the artifact; the Document stays the core's JSON
  - 62f20d9a9db6: Integrate fix/no-control-covered-20261105: no control is covered by another element's pointer area, checked at four widths in both preview frames
  - 5bfad3515b04: Integrate feature/render-references-registers-properties-extensions-20261105: references, callout syntax extensions and property editors render as in the interim adapter, with the remaining DOM contracts moved
  - 49bed48ae2f3: Integrate fix/reader-regressions-in-preview-20261105: Home and the chapter chooser are no longer covered by the arrows, filtering is not a change, canaries say what they observed, and a parity gate against the interim reference
  - 60c2699714ed: Integrate feature/render-cards-counts-quantities-20261105: cards and metrics, count queries and quantities render as in the interim adapter, never counting ignored notes
  - 16f2f7f94904: Integrate feature/render-callouts-embeds-attachments-20261105: callouts, embeds and attachments render as in the interim adapter; the title page's running header is centered
  - 52c192b76136: Integrate chore/project-identity-in-se-toml-20261105: se.toml names the project commit identity
  - a73bcc3d1f0c: Integrate feature/unlisted-chapters-and-home-links-20261105: unlisted chapters render outside Contents and stay reachable by link
  - 1e141cc1b695: Integrate fix/no-local-paths-in-command-output-20261105: command output and reports carry no paths of the build machine
  - 8365d9b9f8a8: Integrate feature/three-icon-notice-center-20261105: one notice center with at most three severity icons and count pills
  - 0a18c3486abf: Integrate feature/base-tables-from-records-20261105: Base tables from the core's note records, with ignored notes never selected
  - 87cc1ff33a9e: Integrate feature/pdf-inspection-tools-20261105: obs-html-inspect renders, crops, reads text and vector paths of PDF pages and annotates rasters
  - cb12b794317e: Integrate feature/limited-functionality-notice-20261105: startup canaries and a Limited functionality notice for restricted hosts
  - 9a12b1621244: Integrate feature/link-by-chapter-id-20261105: link wikilinks and embeds to the chapter the core names
  - 9507d8ba5be3: Integrate feature/attachment-replacement-extension-20261105: a trusted extension that replaces an attachment and its dependent records in one revision-checked transaction
  - 6ab5690faf2c: Integrate feature/report-verification-harness-20261105: a Node DOM harness that loads a report, activates chapters, mounts tables and reports page geometry
  - 5898c31f3fd8: Integrate feature/deterministic-svg-figure-export-20261105: export each figure as a byte-stable SVG through the CLI
  - 1f674696c56c: Integrate refactor/html-presentation-assets-20261105: the interactive report from the Document, with styles, icons, figures, comments and browser tests
  - d2a7a7411197: Integrate docs/one-owner-for-sync-command-20261105: the README owns the module sync command
  - 3667d949b625: Integrate docs/suite-needs-module-sync-20261105: name the module sync before the suite and in the missing-core error
  - cb44163b2c6a: Integrate refactor/html-rendering-adapter-20261105: render the JSON Document through the obs-html CLI
  - d4b547b85929: Allow the fleet's session and GitHub tools without prompts
  - f1ae365854df: Merge chore/authored-prose-opt-in-20261105: authored prose protection
  - 19ff87b9e297: Merge chore/create-obs-html-repository-20261105: core pin and smoke adapter
  - 2a9aef17131c: Initial skeleton
- **field-report**: every closed work issue has a field report: kept (23 checked)

### Metrics

1318 runs: 24 from the landing pull requests, 1333 from the local metrics file, each run once.

```text
Metrics: 1318 runs
Top spenders by wall time:
  work_tickets.py integrate: 27 runs, 11728.5 s wall, 105 GitHub calls, 0 refused, 0 s waiting
  work_tickets.py file: 41 runs, 3102.7 s wall, 858 GitHub calls, 1 refused, 0 s waiting
  work_tickets.py suite: 15 runs, 1664.7 s wall, 0 GitHub calls, 0 refused, 0 s waiting
  se_start.py check: 31 runs, 784.2 s wall, 253 GitHub calls, 0 refused, 0 s waiting
  se_start.py status: 59 runs, 600.1 s wall, 0 GitHub calls, 0 refused, 0 s waiting
  work_tickets.py stop-check: 441 runs, 553.0 s wall, 45 GitHub calls, 0 refused, 0 s waiting
  work_tickets.py sync: 46 runs, 470.2 s wall, 0 GitHub calls, 0 refused, 0 s waiting
  work_tickets.py deliver: 20 runs, 407.5 s wall, 65 GitHub calls, 0 refused, 0 s waiting
  work_tickets.py push: 9 runs, 400.7 s wall, 8 GitHub calls, 0 refused, 0 s waiting
  se_start.py start-components: 21 runs, 338.4 s wall, 0 GitHub calls, 0 refused, 0 s waiting
Top spenders by GitHub calls:
  work_tickets.py file: 41 runs, 3102.7 s wall, 858 GitHub calls, 1 refused, 0 s waiting
  work_tickets.py queue: 25 runs, 287.3 s wall, 471 GitHub calls, 0 refused, 0 s waiting
  se_start.py check: 31 runs, 784.2 s wall, 253 GitHub calls, 0 refused, 0 s waiting
  work_tickets.py integrate: 27 runs, 11728.5 s wall, 105 GitHub calls, 0 refused, 0 s waiting
  work_tickets.py backlog file: 3 runs, 219.6 s wall, 86 GitHub calls, 0 refused, 0 s waiting
  work_tickets.py start: 2 runs, 90.2 s wall, 67 GitHub calls, 0 refused, 0 s waiting
  work_tickets.py deliver: 20 runs, 407.5 s wall, 65 GitHub calls, 0 refused, 0 s waiting
  work_tickets.py paused: 63 runs, 248.4 s wall, 63 GitHub calls, 0 refused, 0 s waiting
  work_tickets.py ready: 1 runs, 24.2 s wall, 45 GitHub calls, 0 refused, 0 s waiting
  work_tickets.py stop-check: 441 runs, 553.0 s wall, 45 GitHub calls, 0 refused, 0 s waiting
Overruns: 77
  2026-11-16T11:00:17Z work_tickets.py suite: suite 297.3 s over its budget 120 s
  2026-11-16T11:01:57Z work_tickets.py intake: wall time 8.9 s over its budget 5 s
  2026-11-20T13:23:42Z se_start.py status: wall time 1.2 s over its budget 1 s
  2026-11-20T13:24:39Z se_start.py status: wall time 1.3 s over its budget 1 s
  2026-11-20T13:24:40Z se_start.py status: wall time 1.7 s over its budget 1 s
  2026-11-20T13:26:03Z work_tickets.py paused: wall time 16.6 s over its budget 5 s
  2026-11-20T13:32:54Z work_tickets.py suite: suite 301.0 s over its budget 120 s
  2026-11-20T13:40:41Z work_tickets.py suite: suite 306.1 s over its budget 120 s
  2026-11-20T13:43:15Z se_start.py status: wall time 2.1 s over its budget 1 s
  2026-11-20T13:44:53Z work_tickets.py paused: wall time 5.3 s over its budget 5 s
  2026-11-20T13:48:17Z work_tickets.py paused: wall time 16.4 s over its budget 5 s
  2026-11-20T14:04:44Z se_start.py status: wall time 1.1 s over its budget 1 s
  2026-11-20T14:26:22Z se_start.py status: wall time 1.2 s over its budget 1 s
  2026-11-20T14:29:19Z work_tickets.py paused: wall time 5.7 s over its budget 5 s
  2026-11-20T14:33:15Z work_tickets.py paused: wall time 7.2 s over its budget 5 s
  2026-11-20T14:33:46Z work_tickets.py paused: wall time 5.1 s over its budget 5 s
  2026-11-20T14:37:03Z work_tickets.py intake: wall time 6.4 s over its budget 5 s
  2026-11-20T14:54:08Z work_tickets.py status: wall time 15.4 s over its budget 5 s
  2026-11-20T14:56:57Z work_tickets.py intake: wall time 5.8 s over its budget 5 s
  2026-11-20T15:10:43Z work_tickets.py paused: wall time 5.7 s over its budget 5 s
  2026-11-20T16:45:06Z work_tickets.py queue: wall time 5.6 s over its budget 5 s
  2026-11-23T07:47:27Z work_tickets.py suite: suite 304.5 s over its budget 240 s
  2026-11-23T08:15:44Z work_tickets.py suite: suite 304.4 s over its budget 240 s
  2026-11-23T08:33:39Z se_start.py status: wall time 1.7 s over its budget 1 s
  2026-11-23T09:16:12Z work_tickets.py integrate #30: suite 504.7 s over its budget 480 s
  2026-11-23T10:03:23Z se_start.py status: wall time 1.2 s over its budget 1 s
  2026-11-23T10:12:37Z se_start.py status: wall time 2.3 s over its budget 1 s
  2026-11-23T11:04:37Z work_tickets.py integrate #33: suite 509.2 s over its budget 480 s
  2026-11-23T12:47:26Z work_tickets.py integrate #34: suite 519.5 s over its budget 480 s
  2026-11-23T13:12:01Z work_tickets.py integrate #32: suite 517.8 s over its budget 480 s
  2026-11-24T06:51:56Z work_tickets.py queue: wall time 8.1 s over its budget 5 s
  2026-11-24T07:14:50Z se_start.py status: wall time 1.2 s over its budget 1 s
  2026-11-24T07:43:13Z se_start.py status: wall time 1.2 s over its budget 1 s
  2026-11-24T09:12:59Z se_start.py status: wall time 2.2 s over its budget 1 s
  2026-11-24T09:22:14Z work_tickets.py queue: wall time 12.3 s over its budget 5 s
  2026-11-24T09:28:17Z work_tickets.py queue: wall time 12.0 s over its budget 5 s
  2026-11-24T09:32:09Z se_start.py status: wall time 1.8 s over its budget 1 s
  2026-11-24T09:32:42Z work_tickets.py queue: wall time 10.9 s over its budget 5 s
  2026-11-24T09:38:06Z work_tickets.py paused: wall time 5.0 s over its budget 5 s
  2026-11-24T09:38:12Z work_tickets.py queue: wall time 10.1 s over its budget 5 s
  2026-11-24T09:53:49Z se_start.py status: wall time 2.1 s over its budget 1 s
  2026-11-24T09:55:50Z work_tickets.py queue: wall time 11.0 s over its budget 5 s
  2026-11-24T09:56:07Z work_tickets.py queue: wall time 11.0 s over its budget 5 s
  2026-11-24T12:03:43Z se_start.py status: wall time 1.4 s over its budget 1 s
  2026-11-24T12:03:44Z se_start.py status: wall time 1.2 s over its budget 1 s
  2026-11-24T12:04:21Z work_tickets.py queue: wall time 10.0 s over its budget 5 s
  2026-11-24T12:40:10Z work_tickets.py queue: wall time 29.5 s over its budget 5 s
  2026-11-24T13:06:11Z work_tickets.py queue: wall time 8.2 s over its budget 5 s
  2026-11-24T13:22:30Z work_tickets.py queue: wall time 9.5 s over its budget 5 s
  2026-11-24T13:38:12Z work_tickets.py paused: wall time 22.1 s over its budget 5 s
  2026-11-24T13:38:46Z work_tickets.py queue: wall time 8.3 s over its budget 5 s
  2026-11-24T13:54:32Z work_tickets.py paused: wall time 8.0 s over its budget 5 s
  2026-11-24T13:55:04Z work_tickets.py queue: wall time 10.0 s over its budget 5 s
  2026-11-24T14:11:00Z work_tickets.py paused: wall time 10.6 s over its budget 5 s
  2026-11-24T14:20:55Z work_tickets.py intake: wall time 6.1 s over its budget 5 s
  2026-11-24T14:25:03Z work_tickets.py integrate #69: suite 615.0 s over its budget 480 s
  2026-11-24T14:45:35Z work_tickets.py integrate #67: suite 570.1 s over its budget 480 s
  2026-11-24T14:46:26Z se_start.py status: wall time 1.2 s over its budget 1 s
  2026-11-24T14:53:07Z work_tickets.py queue: wall time 7.1 s over its budget 5 s
  2026-11-24T20:00:36Z work_tickets.py integrate #76: suite 569.3 s over its budget 480 s
  2026-11-25T08:10:15Z se_start.py status: wall time 105.5 s over its budget 10 s
  2026-11-25T08:16:51Z se_start.py status: wall time 119.1 s over its budget 10 s
  2026-11-25T08:20:57Z se_start.py status: wall time 30.3 s over its budget 10 s
  2026-11-25T08:21:59Z work_tickets.py queue: wall time 6.1 s over its budget 5 s
  2026-11-25T08:25:50Z se_start.py status: wall time 30.5 s over its budget 10 s
  2026-11-25T08:25:51Z se_start.py status: wall time 30.3 s over its budget 10 s
  2026-11-25T08:35:24Z work_tickets.py queue: wall time 5.4 s over its budget 5 s
  2026-11-25T08:57:22Z work_tickets.py queue: wall time 7.4 s over its budget 5 s
  2026-11-25T09:02:59Z work_tickets.py queue: wall time 11.1 s over its budget 5 s
  2026-11-25T09:36:50Z se_start.py status: wall time 46.6 s over its budget 10 s
  2026-11-25T09:42:19Z se_start.py status: wall time 38.7 s over its budget 10 s
  2026-11-25T09:49:27Z se_start.py status: wall time 33.3 s over its budget 10 s
  2026-11-25T10:31:41Z se_start.py status: wall time 40.5 s over its budget 10 s
  2026-11-25T10:33:00Z work_tickets.py queue: wall time 24.5 s over its budget 5 s
  2026-11-25T10:46:24Z work_tickets.py queue: wall time 25.7 s over its budget 5 s
  2026-11-25T10:46:25Z se_start.py status: wall time 80.0 s over its budget 10 s
  2026-11-25T10:49:00Z work_tickets.py queue: wall time 29.2 s over its budget 5 s
```

### Breaking releases beyond a pin

`se_modules.py breaking` over the project's component tree, as collect ran it; what to do about a finding is the person's decision.

The check failed: se.toml: [modules] is [components] since se 8: rename each [modules.<name>] to [components.<name>] and drop its url, as a component is found by its name (docs/modules.md "Modules")

### Ad hoc components to promote

None.

### Ad hoc scripts to promote

None.

### The field reports' answers to the standing questions

#### What came back from real use since the last retro?

- #58: The real `obs-components install obs-html-style-generic` against GitHub installed v1.0.0, and a build applied it; without it, the build failed with the named remedy, as designed.
- #67: The real `obs-document --adapter obs-html` builds of both worked-example folders succeeded and printed only the usual provenance warning for a build outside a Git checkout.
- #69: The real cloud run: the container's browsers are Chrome 158, newer than the pinned Playwright's; only running the suite there showed it.
- #76: The person saw body text left of its headings in kern retro #56's decision deck; the cause was the section toggle placed before the heading text.

#### Which scripts did the AI write that a machine could own?

- #67: A scratch script built a machine folder (`components/obs-html` symlink, `components.json`, `style_component.install_into`) to run `obs-document --adapter obs-html` by hand, as test/conftest.py does. A test helper could expose it as a command, for example `uv run python test/conftest_machine.py <folder>`.
- #69: Comparing a browser binary's version with Playwright's `browsers.json` revision, done by hand twice; `conftest.pinned_browser` now owns it.
- #76: Two ad hoc Playwright scripts in the scratchpad measured left edges and took before/after screenshots of a built deck; `deck_look.py` in SE could take a `--compare <ref>` that builds a deck at two obs-html revisions and shoots both.

#### Anything worth porting to other projects, or so bad we remove it?

- #58: The fake Git door test (`Host(core.Git)` serving local trees to `install_with_requirements`) is a cheap way for any component to prove that installing it installs what it requires; other adapters and styles with requirements could take it over.
- #69: Port: pin the browser tests to Playwright's revision in obs core (ticket above) and in every repository whose tests pick the newest installed browser.

#### Has the process gone stale?

- #58: `[modules]` vs `[components]`: SE's start refuses obs-html's `se.toml`, but its remedy cannot be followed (ticket above), so kern's core never started in this session and every GitHub step ran by hand.
- #67: The SE start report said SE cannot start, because `se.toml` still has `[modules.se]` (renamed to `[components]` in se 8). `work_tickets.py identity` and `sync` still ran. Renaming the table is out of this package's scope.
- #76: The SE start reported `se.toml` uses `[modules]`, which SE 15 refuses; work_tickets.py still ran. A ticket for SE to migrate se.toml's `[modules.se]` to `[components]` belongs to SE, not this branch.

#### What would have stopped this from being produced at all?

- #69: A test that asserts the tests' browser is the revision Playwright pins; it existed as the opposite ("newest installed").
- #76: A layout test of heading edges, now added, would have caught the toggle pushing text right when the toggle was introduced.

#### What did the shell do that a command could have done? Name it.

- #58: Writing the issue's `issue_read` answer to a file for `intake --issue-body`, which kern's relay does when a core serves the checkout (`intake --issue`).
- #67: The flake-at-base comparison: a worktree at base, the failing browser files run there, and `comm` of the two FAILED lists. `work_tickets.py` could own this as a `flake-at-base --files ...` command.
- #69: Writing the GitHub tools' issue answer to a file for `intake --issue-body`: kern's relay was meant to do this, but `intake --issue` refused for lack of gh instead of reading the relay.
- #76: Building a deck from a vault folder with a branch's obs-html (`python -m obs.document --source … --document …` then `obs-html doc.json out.html`) could be one `deck.py build --adapter <checkout>` option.

#### Did anything local earn promotion upstream?

- #69: The pinned-revision lookup (`pinned_browser`) belongs in obs's `test/suite.py` (ticket above).

#### For each failed check, what rule would have caught it?

- #58: The public check refused the first commit message for naming a tracker number (`obs#895`); the rule "commit messages carry no tracker numbers" was known and only checked at commit time; reworded with `--amend` before any push.
- #67: Nine contract tests failed at first: features registry CASES, parity row, every-capability fixture, review-item counts and structural styles order. Each names its own remedy. A worker checklist entry, "a new capability touches adapter.json, CAPABILITIES, features.md, the document and features vaults, test_features CASES and REVIEW_ITEMS", would have caught them before the first run.
- #69: The 7 full-Chromium failures after the first fix: a check that every pool's engine is a pinned revision would have shown them before the complete suite.
- #76: None: the new test failed before the fix by design, and passed after.

#### What goes well, and what makes it go well?

- #58: Adopting a reviewed branch: #56's description was a complete design, so the work was the pin, one regression test and the report.
- #67: The committed-fixture workflow (`build_documents.py` rebuilt by the core) and the gates with precise remedies made the missing pieces quick to find.
- #69: Reproducing on one file (about 5 s), as SE's comment named, and then swapping `PLAYWRIGHT_BROWSERS_PATH` isolated the cause in minutes.
- #76: Measuring element edges in a real build first named the cause (the toggle) within minutes, instead of reading CSS for padding rules.

#### What goes badly, each with its moment in the log?

- #58: Kern did not serve the checkout: `se_relay.py next: no core serves /home/user/obs-html`, then `intake --issue 58` failed with "needs the GitHub CLI (gh), which is installed but not signed in", so intake ran by hand from the issue's tool answer. No `SE_KERN=off` was set.
- #67: The complete suite shows 48 browser failures in this container. All of them also fail at base, on Chromium's `focus-without-user-activation` permissions-policy error, so the suite cannot be green here.
- #69: The first complete run took 8 min only to show the full-Chromium set failing on the same cause (suite-1248.log: `7 failed, 2004 passed`); checking which executable every pool launches would have found it before.
- #76: I ran `git stash` in the checkout while the suite ran, to build at main; it stashed nothing because the tree was clean, and a worktree was the right tool, which I then used.

#### What do the thoughts say that the actions do not?

None.

#### Start, stop, keep, more, less.

- #58: Start: a start check that SE's own remedy for `se.toml` can be followed. Stop: none. Keep: adopting branches with their design as the description. More: tests through the core's own code behind its doors. Less: none.
- #67: Start: list every registry a new capability touches in AGENTS.md. Stop: nothing. Keep: fixture vaults copied from the core's worked example, checked against it by a test. More: base comparisons for browser failures. Less: nothing.
- #69: Start: check every browser the tests launch, not only the one named in the issue. Stop: None. Keep: one-file reproduction first. More: version checks of host binaries. Less: complete-suite runs before the focused set passes.
- #76: Start: measure the built page before reading CSS. Stop: None. Keep: regression test before the fix. More: worktrees for builds at another revision. Less: None.

#### Which rule, prompt or tool made each bad output, and what change stops it?

- #58: SE's start (`se_start.py`) refuses `[modules]` and stops the core; the change is in the ticket above, target SE's `scripts/se_modules.py` and `scripts/se_start.py`.
- #69: The Stop hook asked three times to re-author the commits as Claude; the worker's commit identity rule overrides it, so it was not followed. Change: the cloud host's commit-signature hook should honour se.toml's `identity` (target: the host's Stop hook configuration).

### Planning misses

What the field reports did not deliver:

- #5: **Piece 2, metadata cards, following, kind filter, front matter card, chevron removal:** the issue's Step 2 waits for obs's release of obs#872 and obs-html's core pin moving to it, as Requirements say; the issue stays open for it. Next: once the pin moves, a worker adds a metadata card per block with fields (read from the Document's `fields`/`effective`), the front matter card first, scroll following, the kind filter, and removes the chevron, its table and the metadata-only auto-open rule; `targetPlace` in `comments.js` already gives a block its place and path for those cards.
- #11: **Requirement 3 and Acceptance 2, `v0.1.1` tagged:** landing steps, not a worker's. Per SE's comment, the version stays 0.1.0 on this branch, and `integrate` bumps it to the next patch (0.1.2: main d2e365d, #1's landing, already carries 0.1.1 in `se.toml`) and the release workflow tags `v0.1.2` on the landing commit. Next step: the integrator lands this branch and checks `git ls-remote origin refs/tags/v0.1.2`.
- #11: **Requirement 4, the closing comment names the commit:** the integrator's closing comment of #11 names the landing commit, so obs#871 can name it in its `Moved:` line.
- #32: **`test_live_web_browser.py` (14 tests) stays on the real browser.** Its tests rest on the browser's own network rules: a `Link` header CORS does not expose (`link-hidden`), a cross-origin 302 that a `redirect: "error"` fetch refuses, credentials left out with a cookie set, `Content-Security-Policy: sandbox allow-scripts` blocking storage, and `connect-src` refusing the origin with a `securitypolicyviolation`. The fake neither computes these nor has a recording of them, and the issue rules out hand-written refusals. It would also add time: the tracker artifact runs about 1.5× slower on the fake (`test_live_rows_browser.py` 6.10 s on Chromium, 9.3 s on the fake, same artifact), against the no-added-time rule. Next step for SE: decide whether to (a) add network expectations to the door (a served-page state kind with response headers, recording what Chromium exposes, refuses and fires) and then move the file, or (b) reclassify it as hot. Its row in the note says why it stays.
- #32: **Nine collected tests of `test_comments_browser.py` stay on the real browser, after the merge of main `192be94`.** They open a fixture whose paged chapter holds an image figure: `document.json`, `figures.json`, `figure-references.json` (`test_every_review_item_of_a_paged_figure_fixture_is_a_block_of_its_chapter` ×3, `test_the_bar_shows_the_resolved_model_and_a_reviewed_copy_shows_the_same_states`, `test_a_selection_across_blocks_targets_the_block_it_starts_in`, `test_a_readers_resolve_of_anothers_comment_is_their_own_state_entry_and_only_own_bodies_edit`, `test_a_reopened_reviewed_copy_paints_a_comment_on_its_quote` ×2, `test_a_copy_saved_by_3_9_0_reopens_with_each_highlight_on_its_quote`). They passed on the fake before the merge. Since layout-logic's logical-margins stand-in, `pages.js:397` computes a figure's chrome with real block margins against the door's 24 px default page content, so the page stops with "Figure caption cannot fit the configured paper area". main's own fake does the same on `document.json`. A recording cannot answer it: the keys pagination measures (`html:1 > body:1 > div:3 > section:1 > div:1`, the figures' keys) belong to its measuring pages, which are gone when Chromium is probed. I recorded three states and replayed them for six passes, and the state still did not open, so the attempt is not kept. Next step for SE: decide the door's default geometry for a paged page (for example, a `.paper-content` default of the viewport's height), or a recorder that probes during pagination; then these tests move as they are.
- #32: **`test_comments_browser.py::test_a_cards_click_scrolls_its_block_into_view_and_scrolling_marks_the_cards_on_screen` stays on the real browser** (not hot: since hot-tests-record a hot test names the recordings of its pages, and no state records this page). It was split out of `test_each_block_with_fields_has_a_card_in_order_with_its_path_and_its_click_jumps_and_highlights`. Which cards are on screen after a scroll depends on block rects relative to the scroll box at each scroll position, and a recording answers one box per element and step.
- #32: **No added suite time is not met** (Suite time above: +5.8 s on average before the merge, +17.4 s once after it). The fake runs the table-heavy pages slower than the headless shell: CPU profiles of `test_live_rows_browser.py` put 38% of the host's time in the door's default box (`rendered()` in `fake-browser.cjs`), which recomputes the cascade each time the runtime's pagination and column measurement change the DOM. Holding happy-dom's weakly cached styles (c012b49) cut its misses to 501 in 19,070 reads, but not the time. Next step for SE: decide whether `test_live_rows_browser.py` and `test_live_connector_browser.py` go back to Chromium until the fake's default box is cheaper (a measure that reads only `display` up the ancestors from a per-DOM-change cache), or whether the time is accepted.
- #33: **Requirement 2, "and record":** the named exceptions carry the hot mark but write no recording of their own.
- #33: What a logic test replays is the layout of the states it opens. These are listed in `expectations.yaml`, and the door's hot recorder (`test_door_recordings_browser.py`) records them with `--record`.
- #33: An exception measures layout of its own and asserts it. No logic test replays it.
- #33: Next step: making each hot test record (its own states, or its own answers checked against the recording) is the design's package 6, `hot-tests-record`. That package can take these 35 tests with it.
- #34: **Requirement 1, "and record", for two files:** `test_chapter_sweep_browser.py` and `test_library_doors_browser.py` carry the hot mark but name no recording (RECORDS_NOTHING in `test/structure/test_browser_door.py`).
- #34: The sweep opens every chapter of 20 fixture Documents at two viewports in its own child process. That process must stay separate so it can stop a page that locks, so the one Chromium never visits those pages, and `--record` skips the sweep.
- #34: Recording them as door states would need 40 states, each with every chapter as a step. That would add their conformance to every landing.
- #34: The library doors' pages hold a door alone and no artifact. Their subject is the real library, which their own suite already holds the fakes to.
- #34: **Next step:** if SE wants the swept pages recorded, add one state per fixture Document and viewport, opening every chapter, for `hot-tests-on-change` to run only when stale. The library doors need a decision on whether a page without an artifact is a door state.
- #34: **Suite time:** +6.9 s against the person's rule that no suite time is added; see Suite time. Removing it means dropping new states' conformance, the check requirement 4 asks for, so it is SE's call: fewer states (the narrow variants `columns-narrow`, `bottom-lines-narrow`, `features-cards-phone`), or a faster fake open.
- #34: **Requirement 3 in the complete suite:** the group and the one full Chromium hold only under `--record`.
- #34: Without it, hot tests keep their per-file groups and pools, the headless shell's included.
- #34: The suite runs serially (`uv run pytest -q`, CI's `uv run pytest`), so the group changes nothing there.
- #34: Moving some 200 hot tests onto full Chromium in every run is "the pools reduced to the one instance", which the design gives to package 7, `hot-tests-on-change`.
- #34: **Next step:** `hot-tests-on-change` maps the pools as `RECORD_POOLS` does for every run, or runs hot tests only when a recording is stale.

### Refused deliveries and declined reviews

None.

### Collector caveats

Do not treat the three rule-check counts above as confirmed process failures without checking the collector. The work-issue check includes release PRs #73 and #79, which are not work landings. The outside-PR check excludes merge and exact-squash commits, but this repository lands by fast-forward, so it counts integration commits from PRs as outside-PR commits. For #40, the collector selects a failed `check` run immediately before merge; an earlier run succeeded and a later run succeeded after merge, so the exact required-check run still needs review.

## 2. Table of what happened

<!-- timeline: The timeline in chapters of about six hours, then per step what went well, what it cost and whether a machine could do it; collect fills what the record says, the judge the rest. -->

Chapters of up to 6 hours, by when each work issue came back (its landing, else its close).

| chapter | from | to | steps |
|---|---|---|---|
| 1 | 2026-11-22T16:27:31Z | 2026-11-22T22:17:53Z | #1, #11, #7, #2, #15, #4, #5, #17, #22, #3, #42, #35, #29 |
| 2 | 2026-11-22T23:12:41Z | 2026-11-22T23:12:41Z | #31 |
| 3 | 2026-11-23T09:35:59Z | 2026-11-23T13:30:31Z | #30, #38, #33, #58, #34, #32 |
| 4 | 2026-11-24T14:44:28Z | 2026-11-24T20:18:14Z | #69, #67, #76 |

| step | chapter | what went well | what it cost | can a machine do it |
|---|---|---|---|---|
| #1 unchanged-output-stands-alone | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 422.1 s | No repeated script or command recorded. |
| #11 block-records-from-obs | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 409.8 s | No repeated script or command recorded. |
| #7 name-is-obs-html | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 402.6 s | No repeated script or command recorded. |
| #2 links-stay-inside-repository | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 418.7 s | No repeated script or command recorded. |
| #15 pugh-browser-test-flakes | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 402.7 s | No repeated script or command recorded. |
| #4 drop-stale-commit-allow-entries | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 418.4 s | No repeated script or command recorded. |
| #5 one-bar-comments-and-fields | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 411.5 s | No repeated script or command recorded. |
| #17 tests-never-wait-on-time | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 400.3 s | No repeated script or command recorded. |
| #22 browser-as-io-door | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 421.4 s | No repeated script or command recorded. |
| #3 own-spec-build | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 422.2 s | No repeated script or command recorded. |
| #42 own-spec-reason-rewritten | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 417.5 s | No repeated script or command recorded. |
| #35 metadata-cards-in-the-bar | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 409 s | No repeated script or command recorded. |
| #29 fake-browser-door | 1 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 440.4 s | No repeated script or command recorded. |
| #31 browser-door-recorder | 2 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 449.4 s | No repeated script or command recorded. |
| #30 more-logic-to-fake-browser | 3 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 504.7 s | No repeated script or command recorded. |
| #38 dom-tier-on-fake-browser | 3 | No retro observation in the report. | landed; 0 refused, 0 escalated, suite 476 s | No repeated script or command recorded. |
| #33 layout-logic-to-fake-browser | 3 | No retro observation in the report. | landed; 0 refused, 1 escalated, suite 509.2 s | No repeated script or command recorded. |
| #58 generic-style-component | 3 | Adopting a reviewed branch: #56's description was a complete design, so the work was the pin, one regression test and the report. | landed; 0 refused, 0 escalated, suite 473.1 s | Writing the issue's `issue_read` answer to a file for `intake --issue-body`, which kern's relay does when a core serves the checkout (`intake --issue`). |
| #34 hot-tests-record | 3 | No retro observation in the report. | landed; 0 refused, 1 escalated, suite 519.5 s | No repeated script or command recorded. |
| #32 viewer-logic-to-fake-browser | 3 | No retro observation in the report. | landed; 0 refused, 1 escalated, suite 517.8 s | No repeated script or command recorded. |
| #69 cloud-browser-runs-the-suite | 4 | Reproducing on one file (about 5 s), as SE's comment named, and then swapping `PLAYWRIGHT_BROWSERS_PATH` isolated the cause in minutes. | landed; 0 refused, 0 escalated, suite 615 s | Comparing a browser binary's version with Playwright's `browsers.json` revision, done by hand twice; `conftest.pinned_browser` now owns it.; Writing the GitHub tools' issue answer to a file for `intake --issue-body`: kern's relay was meant to do this, but `intake --issue` refused for lack of gh instead of reading the relay. |
| #67 present-templates-capability | 4 | The committed-fixture workflow (`build_documents.py` rebuilt by the core) and the gates with precise remedies made the missing pieces quick to find. | landed; 0 refused, 0 escalated, suite 570.1 s | A scratch script built a machine folder (`components/obs-html` symlink, `components.json`, `style_component.install_into`) to run `obs-document --adapter obs-html` by hand, as test/conftest.py does. A test helper could expose it as a command, for example `uv run python test/conftest_machine.py <folder>`.; The flake-at-base comparison: a worktree at base, the failing browser files run there, and `comm` of the two FAILED lists. `work_tickets.py` could own this as a `flake-at-base --files ...` command. |
| #76 body-aligns-with-headings | 4 | Measuring element edges in a real build first named the cause (the toggle) within minutes, instead of reading CSS for padding rules. | landed; 0 refused, 0 escalated, suite 569.3 s | Two ad hoc Playwright scripts in the scratchpad measured left edges and took before/after screenshots of a built deck; `deck_look.py` in SE could take a `--compare <ref>` that builds a deck at two obs-html revisions and shoots both.; Building a deck from a vault folder with a branch's obs-html (`python -m obs.document --source … --document …` then `obs-html doc.json out.html`) could be one `deck.py build --adapter <checkout>` option. |

## 3. The standing questions

<!-- matrix: The matrix: each standing question against each chapter, a cell naming what answers it there; collect fills the field reports' answers, the judge the rest. -->

| question | 1 (2026-11-22 16:27) | 2 (2026-11-22 23:12) | 3 (2026-11-23 09:35) | 4 (2026-11-24 14:44) |
|---|---|---|---|---|
| What came back from real use since the last retro? | No report answer | No report answer | #58 | #69, #67, #76 |
| Which scripts did the AI write that a machine could own? | No report answer | No report answer | No report answer | #69, #67, #76 |
| Anything worth porting to other projects, or so bad we remove it? | No report answer | No report answer | #58 | #69 |
| Has the process gone stale? | No report answer | No report answer | #58 | #67, #76 |
| What would have stopped this from being produced at all? | No report answer | No report answer | No report answer | #69, #76 |
| What did the shell do that a command could have done? Name it. | No report answer | No report answer | #58 | #69, #67, #76 |
| Did anything local earn promotion upstream? | No report answer | No report answer | No report answer | #69 |
| For each failed check, what rule would have caught it? | No report answer | No report answer | #58 | #69, #67, #76 |
| What goes well, and what makes it go well? | No report answer | No report answer | #58 | #69, #67, #76 |
| What goes badly, each with its moment in the log? | No report answer | No report answer | #58 | #69, #67, #76 |
| What do the thoughts say that the actions do not? | No report answer | No report answer | No report answer | No report answer |
| Start, stop, keep, more, less. | No report answer | No report answer | #58 | #69, #67, #76 |
| Which rule, prompt or tool made each bad output, and what change stops it? | No report answer | No report answer | #58 | #69 |

## Answers to the standing questions

<!-- answers: The retro's answer to each standing question over the whole window, one `### <question>` each; "None" where nothing applies. -->

### What came back from real use since the last retro?

The field reports for #58, #69, #67 and #76 record real-run feedback. #58 found a mismatch between the local style config and the component model; #69 isolated a Playwright/browser-version mismatch by reproducing one file and changing `PLAYWRIGHT_BROWSERS_PATH`; #67 found missing capability coverage through the committed-fixture workflow and precise gate remedies; #76 found the heading/body alignment cause by measuring a built artifact. No new user feedback was requested for this retro.

### Which scripts did the AI write that a machine could own?

The repeated manual operation was writing GitHub issue-tool answers to a file for `intake --issue-body` (#58 and #69); kern's relay or intake should own that path. The other reported scripts were one-off candidates: browser revision checking (#69, now `conftest.pinned_browser`), a machine-folder fixture helper and `flake-at-base --files ...` (#67), and two rendered-deck measurement scripts (#76).

### Anything worth porting to other projects, or so bad we remove it?

No behavior is identified for removal. The #69 report says the pinned-revision lookup belongs in obs's `test/suite.py`; this is an upstream destination, not evidence that the change has already landed there.

### Has the process gone stale?

The #58 report says SE startup rejected the legacy `[modules]` section and stopped the core. This run's start report independently found `[modules.se]` in this repository's `se.toml`, while current SE expects `[components]`. Treat it as a repository setting to update, not as evidence that the whole component workflow is stale. The retro collector's rule-check output also needs its fast-forward/release-PR assumptions corrected before its rates are trusted.

### What would have stopped this from being produced at all?

A new-capability checklist in the worker guidance would have caught #67's missing registry/fixture updates before the first run. For #69, a startup preflight comparing every browser executable with Playwright's pinned revision would have exposed the environment mismatch before the full suite. For #76, measuring the built artifact was the effective early check; the report suggests automating the two-revision deck comparison.

### What did the shell do that a command could have done? Name it.

Candidates named by the reports: make `intake --issue-body` consume the relay's answer; add `work_tickets.py flake-at-base --files ...`; expose machine-folder setup as a test helper command; add `deck_look.py --compare <ref>`; and let `deck.py build` accept `--adapter <checkout>`. These are suggestions from individual reports; only the browser check is already implemented locally.

### Did anything local earn promotion upstream?

The #69 report names obs's `test/suite.py` as the home for the pinned-revision lookup. It does not show another project's adoption or prove the upstream change is complete.

### For each failed check, what rule would have caught it?

The #58 public check rejected the first commit message for naming a tracker number; the no-tracker-numbers rule was checked only at commit time, then the message was amended before push. #67 had nine contract-test failures at first; the report proposes a worker checklist entry for the registries and fixtures a new capability touches. #69's first full run took about eight minutes before seven full-Chromium failures exposed the browser-version mismatch; a check of every pool's executable would have caught it earlier. #76's new test failed before the fix by design and passed after. The collector's #40 failure has conflicting runs and is not judged here as a confirmed violation.

### What goes well, and what makes it go well?

All 23 closed work issues landed with field reports, with no duplicates or refused deliveries. The latest reports show effective diagnosis from focused reproductions (#69), committed fixtures and precise gate remedies (#67), and measuring the actual artifact before changing CSS (#76). A reviewed design made #58 a small pin-and-test change.

### What goes badly, each with its moment in the log?

The suite time rose from roughly 400–440 seconds in chapter 1 to 504–615 seconds in later chapters; seven of 23 measured suites exceeded the 480-second limit, with the latest at 615 seconds (#69). The three escalations are recorded on #32, #33 and #34. #67's 48 browser failures also reproduce at base on Chromium's `focus-without-user-activation` permissions-policy error, so they are not attributed to the change. This run's startup report says the `se.toml` component section is obsolete and kern did not load; those are startup blockers, not retro findings about landed work.

### What do the thoughts say that the actions do not?

None. The reports record no direct thought/action mismatch.

### Start, stop, keep, more, less.

Start: a preflight that checks every browser pool against Playwright's pinned revision, and a checklist for capability registries. Stop: hand-building the same machine folder or diagnosing the browser path by hand when a command can own it. Keep: adopting branches with their design in the description, committed fixtures and focused reproductions. More: tests through the core's own doors and measurements on the built page. Less: complete-suite runs before focused browser tests pass.

### Which rule, prompt or tool made each bad output, and what change stops it?

The #58 startup failure came from SE's start scripts rejecting the old `[modules]` config; its report names `se_modules.py` and `se_start.py` as the fix location. This run also found `se.toml` still using `[modules.se]`; update that repository setting to `[components.se]` and verify current startup. Kern's missing binary is a separate bootstrap condition. The #69 Stop hook's request to re-author commits conflicted with the repository's commit-identity rule; that host hook is outside this repository.

## 4. Classes and homes

One open class is a repository setting: `se.toml` still declares the SE component under `[modules.se]`, while current SE expects `[components]`. The fix is to move the declaration to the current section and verify startup. Its status is open; kern's missing binary remains a separate bootstrap condition.

Home order, strongest first: check, refusal, gate, prefill, checklist line, command, setting, sentence. A class's `home_kind` is the first of them that holds; its `home` is the file the fix changes, its `mark` a text the fix leaves there, which the tree check looks for.

## 5. The person decides

The person blessed both questions:

- **decision-01 — Bless.** “Obviously, you update the SE component declaration, and the fact that it doesn't solve another problem is not a downside of that solution. That solution solves one of the problems. You don't need to present everything you want to do as questions to me.” This accepts the `se.toml` migration as work: move the declaration to `[components.se]` and verify startup. The unplaced kern binary stays a separate bootstrap condition, not a downside of this fix. Filing the work issue waits for #1827.
- **Anything else? — Bless.** “Nothing else.” This adds no finding or other change to the draft.

<!-- se:retro-judge -->
## Judgment

The judge writes the person's field feedback into step 1, fills what steps 3 and 4 leave open, answers every standing question, fills `findings`, `classes` and `went_well` in the block below, then runs `retro.py file 80 --draft <this file>`, which refuses a step or a question left open: a finding has `title` (five words or more), `body`, `class` (a class's `name`), `home` (the file it changes), `controversial` (true where it changes a rule, trades one metric for another, the judge is unsure, or it recurred after an earlier fix) with its `why`, and optionally `check` (a rule check: work-issue, check, outside-pr, field-report); a class has `name`, `cause`, `fix`, `home` and `home_kind` (one of: check, refusal, gate, prefill, checklist line, command, setting, sentence), and optionally `status`, `pattern`, `limits`, `mark`; `went_well` lists what went well. Step 6 is the person's, in the session. This part is not posted.
<!-- se:retro-judge:end -->

<!-- se:retro-yaml -->
```yaml
{
  "version": 1,
  "window": {
    "retro": 80,
    "since": null,
    "since_retro": null,
    "until": "2026-11-25T10:49:36Z",
    "start": "history"
  },
  "sizes": {
    "closed": 23,
    "landed": 23,
    "duplicates": 0,
    "escalated": 3
  },
  "issues": [
    {
      "number": 1,
      "title": "unchanged-output-stands-alone",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 422.1,
      "landing_pull": 10,
      "report_pull": 8,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-22T16:27:31Z"
    },
    {
      "number": 2,
      "title": "links-stay-inside-repository",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 418.7,
      "landing_pull": 20,
      "report_pull": 9,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-22T17:43:18Z"
    },
    {
      "number": 3,
      "title": "own-spec-build",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 422.2,
      "landing_pull": 44,
      "report_pull": 41,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-22T20:39:07Z"
    },
    {
      "number": 4,
      "title": "drop-stale-commit-allow-entries",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 418.4,
      "landing_pull": 23,
      "report_pull": 6,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-22T18:13:29Z"
    },
    {
      "number": 5,
      "title": "one-bar-comments-and-fields",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 411.5,
      "landing_pull": 24,
      "report_pull": 16,
      "retro": {},
      "not_delivered": [
        "**Piece 2, metadata cards, following, kind filter, front matter card, chevron removal:** the issue's Step 2 waits for obs's release of obs#872 and obs-html's core pin moving to it, as Requirements say; the issue stays open for it. Next: once the pin moves, a worker adds a metadata card per block with fields (read from the Document's `fields`/`effective`), the front matter card first, scroll following, the kind filter, and removes the chevron, its table and the metadata-only auto-open rule; `targetPlace` in `comments.js` already gives a block its place and path for those cards."
      ],
      "at": "2026-11-22T18:28:36Z"
    },
    {
      "number": 7,
      "title": "name-is-obs-html",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 402.6,
      "landing_pull": 18,
      "report_pull": 13,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-22T17:20:54Z"
    },
    {
      "number": 11,
      "title": "block-records-from-obs",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 409.8,
      "landing_pull": 14,
      "report_pull": 12,
      "retro": {},
      "not_delivered": [
        "**Requirement 3 and Acceptance 2, `v0.1.1` tagged:** landing steps, not a worker's. Per SE's comment, the version stays 0.1.0 on this branch, and `integrate` bumps it to the next patch (0.1.2: main d2e365d, #1's landing, already carries 0.1.1 in `se.toml`) and the release workflow tags `v0.1.2` on the landing commit. Next step: the integrator lands this branch and checks `git ls-remote origin refs/tags/v0.1.2`.",
        "**Requirement 4, the closing comment names the commit:** the integrator's closing comment of #11 names the landing commit, so obs#871 can name it in its `Moved:` line."
      ],
      "at": "2026-11-22T17:05:36Z"
    },
    {
      "number": 15,
      "title": "pugh-browser-test-flakes",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 402.7,
      "landing_pull": 21,
      "report_pull": 19,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-22T17:58:17Z"
    },
    {
      "number": 17,
      "title": "tests-never-wait-on-time",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 400.3,
      "landing_pull": 26,
      "report_pull": 25,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-22T18:54:45Z"
    },
    {
      "number": 22,
      "title": "browser-as-io-door",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 421.4,
      "landing_pull": 28,
      "report_pull": 27,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-22T19:36:11Z"
    },
    {
      "number": 29,
      "title": "fake-browser-door",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 440.4,
      "landing_pull": 49,
      "report_pull": 48,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-22T22:17:53Z"
    },
    {
      "number": 30,
      "title": "more-logic-to-fake-browser",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 504.7,
      "landing_pull": 53,
      "report_pull": 52,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-23T09:35:59Z"
    },
    {
      "number": 31,
      "title": "browser-door-recorder",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 449.4,
      "landing_pull": 51,
      "report_pull": 50,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-22T23:12:41Z"
    },
    {
      "number": 32,
      "title": "viewer-logic-to-fake-browser",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 1,
      "suite_seconds": 517.8,
      "landing_pull": 65,
      "report_pull": 64,
      "retro": {},
      "not_delivered": [
        "**`test_live_web_browser.py` (14 tests) stays on the real browser.** Its tests rest on the browser's own network rules: a `Link` header CORS does not expose (`link-hidden`), a cross-origin 302 that a `redirect: \"error\"` fetch refuses, credentials left out with a cookie set, `Content-Security-Policy: sandbox allow-scripts` blocking storage, and `connect-src` refusing the origin with a `securitypolicyviolation`. The fake neither computes these nor has a recording of them, and the issue rules out hand-written refusals. It would also add time: the tracker artifact runs about 1.5× slower on the fake (`test_live_rows_browser.py` 6.10 s on Chromium, 9.3 s on the fake, same artifact), against the no-added-time rule. Next step for SE: decide whether to (a) add network expectations to the door (a served-page state kind with response headers, recording what Chromium exposes, refuses and fires) and then move the file, or (b) reclassify it as hot. Its row in the note says why it stays.",
        "**Nine collected tests of `test_comments_browser.py` stay on the real browser, after the merge of main `192be94`.** They open a fixture whose paged chapter holds an image figure: `document.json`, `figures.json`, `figure-references.json` (`test_every_review_item_of_a_paged_figure_fixture_is_a_block_of_its_chapter` ×3, `test_the_bar_shows_the_resolved_model_and_a_reviewed_copy_shows_the_same_states`, `test_a_selection_across_blocks_targets_the_block_it_starts_in`, `test_a_readers_resolve_of_anothers_comment_is_their_own_state_entry_and_only_own_bodies_edit`, `test_a_reopened_reviewed_copy_paints_a_comment_on_its_quote` ×2, `test_a_copy_saved_by_3_9_0_reopens_with_each_highlight_on_its_quote`). They passed on the fake before the merge. Since layout-logic's logical-margins stand-in, `pages.js:397` computes a figure's chrome with real block margins against the door's 24 px default page content, so the page stops with \"Figure caption cannot fit the configured paper area\". main's own fake does the same on `document.json`. A recording cannot answer it: the keys pagination measures (`html:1 > body:1 > div:3 > section:1 > div:1`, the figures' keys) belong to its measuring pages, which are gone when Chromium is probed. I recorded three states and replayed them for six passes, and the state still did not open, so the attempt is not kept. Next step for SE: decide the door's default geometry for a paged page (for example, a `.paper-content` default of the viewport's height), or a recorder that probes during pagination; then these tests move as they are.",
        "**`test_comments_browser.py::test_a_cards_click_scrolls_its_block_into_view_and_scrolling_marks_the_cards_on_screen` stays on the real browser** (not hot: since hot-tests-record a hot test names the recordings of its pages, and no state records this page). It was split out of `test_each_block_with_fields_has_a_card_in_order_with_its_path_and_its_click_jumps_and_highlights`. Which cards are on screen after a scroll depends on block rects relative to the scroll box at each scroll position, and a recording answers one box per element and step.",
        "**No added suite time is not met** (Suite time above: +5.8 s on average before the merge, +17.4 s once after it). The fake runs the table-heavy pages slower than the headless shell: CPU profiles of `test_live_rows_browser.py` put 38% of the host's time in the door's default box (`rendered()` in `fake-browser.cjs`), which recomputes the cascade each time the runtime's pagination and column measurement change the DOM. Holding happy-dom's weakly cached styles (c012b49) cut its misses to 501 in 19,070 reads, but not the time. Next step for SE: decide whether `test_live_rows_browser.py` and `test_live_connector_browser.py` go back to Chromium until the fake's default box is cheaper (a measure that reads only `display` up the ancestors from a per-DOM-change cache), or whether the time is accepted."
      ],
      "at": "2026-11-23T13:30:31Z"
    },
    {
      "number": 33,
      "title": "layout-logic-to-fake-browser",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 1,
      "suite_seconds": 509.2,
      "landing_pull": 59,
      "report_pull": 57,
      "retro": {},
      "not_delivered": [
        "**Requirement 2, \"and record\":** the named exceptions carry the hot mark but write no recording of their own.",
        "What a logic test replays is the layout of the states it opens. These are listed in `expectations.yaml`, and the door's hot recorder (`test_door_recordings_browser.py`) records them with `--record`.",
        "An exception measures layout of its own and asserts it. No logic test replays it.",
        "Next step: making each hot test record (its own states, or its own answers checked against the recording) is the design's package 6, `hot-tests-record`. That package can take these 35 tests with it."
      ],
      "at": "2026-11-23T11:23:03Z"
    },
    {
      "number": 34,
      "title": "hot-tests-record",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 1,
      "suite_seconds": 519.5,
      "landing_pull": 63,
      "report_pull": 62,
      "retro": {},
      "not_delivered": [
        "**Requirement 1, \"and record\", for two files:** `test_chapter_sweep_browser.py` and `test_library_doors_browser.py` carry the hot mark but name no recording (RECORDS_NOTHING in `test/structure/test_browser_door.py`).",
        "The sweep opens every chapter of 20 fixture Documents at two viewports in its own child process. That process must stay separate so it can stop a page that locks, so the one Chromium never visits those pages, and `--record` skips the sweep.",
        "Recording them as door states would need 40 states, each with every chapter as a step. That would add their conformance to every landing.",
        "The library doors' pages hold a door alone and no artifact. Their subject is the real library, which their own suite already holds the fakes to.",
        "**Next step:** if SE wants the swept pages recorded, add one state per fixture Document and viewport, opening every chapter, for `hot-tests-on-change` to run only when stale. The library doors need a decision on whether a page without an artifact is a door state.",
        "**Suite time:** +6.9 s against the person's rule that no suite time is added; see Suite time. Removing it means dropping new states' conformance, the check requirement 4 asks for, so it is SE's call: fewer states (the narrow variants `columns-narrow`, `bottom-lines-narrow`, `features-cards-phone`), or a faster fake open.",
        "**Requirement 3 in the complete suite:** the group and the one full Chromium hold only under `--record`.",
        "Without it, hot tests keep their per-file groups and pools, the headless shell's included.",
        "The suite runs serially (`uv run pytest -q`, CI's `uv run pytest`), so the group changes nothing there.",
        "Moving some 200 hot tests onto full Chromium in every run is \"the pools reduced to the one instance\", which the design gives to package 7, `hot-tests-on-change`.",
        "**Next step:** `hot-tests-on-change` maps the pools as `RECORD_POOLS` does for every run, or runs hot tests only when a recording is stale."
      ],
      "at": "2026-11-23T13:06:04Z"
    },
    {
      "number": 35,
      "title": "metadata-cards-in-the-bar",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 409.0,
      "landing_pull": 47,
      "report_pull": 46,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-22T21:34:59Z"
    },
    {
      "number": 38,
      "title": "dom-tier-on-fake-browser",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 476.0,
      "landing_pull": 55,
      "report_pull": 54,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-23T09:58:56Z"
    },
    {
      "number": 42,
      "title": "own-spec-reason-rewritten",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 417.5,
      "landing_pull": 45,
      "report_pull": 43,
      "retro": {},
      "not_delivered": [],
      "at": "2026-11-22T20:54:57Z"
    },
    {
      "number": 58,
      "title": "generic-style-component",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 473.1,
      "landing_pull": 61,
      "report_pull": 56,
      "retro": {
        "real_use": "The real `obs-components install obs-html-style-generic` against GitHub installed v1.0.0, and a build applied it; without it, the build failed with the named remedy, as designed.",
        "port_or_remove": "The fake Git door test (`Host(core.Git)` serving local trees to `install_with_requirements`) is a cheap way for any component to prove that installing it installs what it requires; other adapters and styles with requirements could take it over.",
        "stale_process": "`[modules]` vs `[components]`: SE's start refuses obs-html's `se.toml`, but its remedy cannot be followed (ticket above), so kern's core never started in this session and every GitHub step ran by hand.",
        "shell_command": "Writing the issue's `issue_read` answer to a file for `intake --issue-body`, which kern's relay does when a core serves the checkout (`intake --issue`).",
        "failed_checks": "The public check refused the first commit message for naming a tracker number (`obs#895`); the rule \"commit messages carry no tracker numbers\" was known and only checked at commit time; reworded with `--amend` before any push.",
        "goes_well": "Adopting a reviewed branch: #56's description was a complete design, so the work was the pin, one regression test and the report.",
        "goes_badly": "Kern did not serve the checkout: `se_relay.py next: no core serves /home/user/obs-html`, then `intake --issue 58` failed with \"needs the GitHub CLI (gh), which is installed but not signed in\", so intake ran by hand from the issue's tool answer. No `SE_KERN=off` was set.",
        "start_stop": "Start: a start check that SE's own remedy for `se.toml` can be followed. Stop: none. Keep: adopting branches with their design as the description. More: tests through the core's own code behind its doors. Less: none.",
        "bad_output_cause": "SE's start (`se_start.py`) refuses `[modules]` and stops the core; the change is in the ticket above, target SE's `scripts/se_modules.py` and `scripts/se_start.py`."
      },
      "not_delivered": [],
      "at": "2026-11-23T12:46:56Z"
    },
    {
      "number": 67,
      "title": "present-templates-capability",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 570.1,
      "landing_pull": 72,
      "report_pull": 68,
      "retro": {
        "real_use": "The real `obs-document --adapter obs-html` builds of both worked-example folders succeeded and printed only the usual provenance warning for a build outside a Git checkout.",
        "machine_scripts": "A scratch script built a machine folder (`components/obs-html` symlink, `components.json`, `style_component.install_into`) to run `obs-document --adapter obs-html` by hand, as test/conftest.py does. A test helper could expose it as a command, for example `uv run python test/conftest_machine.py <folder>`.",
        "stale_process": "The SE start report said SE cannot start, because `se.toml` still has `[modules.se]` (renamed to `[components]` in se 8). `work_tickets.py identity` and `sync` still ran. Renaming the table is out of this package's scope.",
        "shell_command": "The flake-at-base comparison: a worktree at base, the failing browser files run there, and `comm` of the two FAILED lists. `work_tickets.py` could own this as a `flake-at-base --files ...` command.",
        "failed_checks": "Nine contract tests failed at first: features registry CASES, parity row, every-capability fixture, review-item counts and structural styles order. Each names its own remedy. A worker checklist entry, \"a new capability touches adapter.json, CAPABILITIES, features.md, the document and features vaults, test_features CASES and REVIEW_ITEMS\", would have caught them before the first run.",
        "goes_well": "The committed-fixture workflow (`build_documents.py` rebuilt by the core) and the gates with precise remedies made the missing pieces quick to find.",
        "goes_badly": "The complete suite shows 48 browser failures in this container. All of them also fail at base, on Chromium's `focus-without-user-activation` permissions-policy error, so the suite cannot be green here.",
        "start_stop": "Start: list every registry a new capability touches in AGENTS.md. Stop: nothing. Keep: fixture vaults copied from the core's worked example, checked against it by a test. More: base comparisons for browser failures. Less: nothing."
      },
      "not_delivered": [],
      "at": "2026-11-24T15:04:46Z"
    },
    {
      "number": 69,
      "title": "cloud-browser-runs-the-suite",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 615.0,
      "landing_pull": 71,
      "report_pull": 70,
      "retro": {
        "real_use": "The real cloud run: the container's browsers are Chrome 158, newer than the pinned Playwright's; only running the suite there showed it.",
        "machine_scripts": "Comparing a browser binary's version with Playwright's `browsers.json` revision, done by hand twice; `conftest.pinned_browser` now owns it.",
        "port_or_remove": "Port: pin the browser tests to Playwright's revision in obs core (ticket above) and in every repository whose tests pick the newest installed browser.",
        "not_produced": "A test that asserts the tests' browser is the revision Playwright pins; it existed as the opposite (\"newest installed\").",
        "shell_command": "Writing the GitHub tools' issue answer to a file for `intake --issue-body`: kern's relay was meant to do this, but `intake --issue` refused for lack of gh instead of reading the relay.",
        "promote_upstream": "The pinned-revision lookup (`pinned_browser`) belongs in obs's `test/suite.py` (ticket above).",
        "failed_checks": "The 7 full-Chromium failures after the first fix: a check that every pool's engine is a pinned revision would have shown them before the complete suite.",
        "goes_well": "Reproducing on one file (about 5 s), as SE's comment named, and then swapping `PLAYWRIGHT_BROWSERS_PATH` isolated the cause in minutes.",
        "goes_badly": "The first complete run took 8 min only to show the full-Chromium set failing on the same cause (suite-1248.log: `7 failed, 2004 passed`); checking which executable every pool launches would have found it before.",
        "start_stop": "Start: check every browser the tests launch, not only the one named in the issue. Stop: None. Keep: one-file reproduction first. More: version checks of host binaries. Less: complete-suite runs before the focused set passes.",
        "bad_output_cause": "The Stop hook asked three times to re-author the commits as Claude; the worker's commit identity rule overrides it, so it was not followed. Change: the cloud host's commit-signature hook should honour se.toml's `identity` (target: the host's Stop hook configuration)."
      },
      "not_delivered": [],
      "at": "2026-11-24T14:44:28Z"
    },
    {
      "number": 76,
      "title": "body-aligns-with-headings",
      "state_reason": "completed",
      "duplicate": false,
      "landed": true,
      "refused": 0,
      "escalations": 0,
      "suite_seconds": 569.3,
      "landing_pull": 78,
      "report_pull": 77,
      "retro": {
        "real_use": "The person saw body text left of its headings in kern retro #56's decision deck; the cause was the section toggle placed before the heading text.",
        "machine_scripts": "Two ad hoc Playwright scripts in the scratchpad measured left edges and took before/after screenshots of a built deck; `deck_look.py` in SE could take a `--compare <ref>` that builds a deck at two obs-html revisions and shoots both.",
        "stale_process": "The SE start reported `se.toml` uses `[modules]`, which SE 15 refuses; work_tickets.py still ran. A ticket for SE to migrate se.toml's `[modules.se]` to `[components]` belongs to SE, not this branch.",
        "not_produced": "A layout test of heading edges, now added, would have caught the toggle pushing text right when the toggle was introduced.",
        "shell_command": "Building a deck from a vault folder with a branch's obs-html (`python -m obs.document --source … --document …` then `obs-html doc.json out.html`) could be one `deck.py build --adapter <checkout>` option.",
        "failed_checks": "None: the new test failed before the fix by design, and passed after.",
        "goes_well": "Measuring element edges in a real build first named the cause (the toggle) within minutes, instead of reading CSS for padding rules.",
        "goes_badly": "I ran `git stash` in the checkout while the suite ran, to build at main; it stashed nothing because the tree was clean, and a worktree was the right tool, which I then used.",
        "start_stop": "Start: measure the built page before reading CSS. Stop: None. Keep: regression test before the fix. More: worktrees for builds at another revision. Less: None."
      },
      "not_delivered": [],
      "at": "2026-11-24T20:18:14Z"
    }
  ],
  "chapters": [
    {
      "chapter": 1,
      "start": "2026-11-22T16:27:31Z",
      "end": "2026-11-22T22:17:53Z",
      "issues": [
        1,
        11,
        7,
        2,
        15,
        4,
        5,
        17,
        22,
        3,
        42,
        35,
        29
      ]
    },
    {
      "chapter": 2,
      "start": "2026-11-22T23:12:41Z",
      "end": "2026-11-22T23:12:41Z",
      "issues": [
        31
      ]
    },
    {
      "chapter": 3,
      "start": "2026-11-23T09:35:59Z",
      "end": "2026-11-23T13:30:31Z",
      "issues": [
        30,
        38,
        33,
        58,
        34,
        32
      ]
    },
    {
      "chapter": 4,
      "start": "2026-11-24T14:44:28Z",
      "end": "2026-11-24T20:18:14Z",
      "issues": [
        69,
        67,
        76
      ]
    }
  ],
  "rule_checks": [
    {
      "name": "work-issue",
      "rule": "every landing pull request names a work issue that was open when it merged",
      "checked": 26,
      "broken": [
        {
          "item": "#79",
          "what": "names no work issue (Fixes|Refs <issue url>)"
        },
        {
          "item": "#73",
          "what": "names no work issue (Fixes|Refs <issue url>)"
        }
      ],
      "kept": false
    },
    {
      "name": "check",
      "rule": "the check `check` passed on every landing pull request's head in its last run before the merge",
      "checked": 26,
      "broken": [
        {
          "item": "#40",
          "what": "check failure"
        }
      ],
      "kept": false
    },
    {
      "name": "outside-pr",
      "rule": "no commit reached the integration branch outside a pull request",
      "checked": 324,
      "broken": [
        {
          "item": "b3f3d7bd34ef",
          "what": "Set up se: the project's settings in se.toml, se's pin in se.lock and se's release workflow"
        },
        {
          "item": "9de9da56c710",
          "what": "Stand the HTML adapter alone: pin a core release, its own CI and release"
        },
        {
          "item": "66f62f8193a1",
          "what": "Integrate styles-by-name: `obs.style: <name>` names an installed style component, and obs-html stops fetching styles, so no committed document names where a style lives."
        },
        {
          "item": "d699458a802f",
          "what": "Integrate plugin-versions-recorded: Every Document carries the name, kind, version and commit of each component that builds it, every artifact and source-archive build record holds them"
        },
        {
          "item": "937785c86832",
          "what": "Integrate plugin-command: `obs-components` finds every component repository under the owner (the account or organization) of each remote of the checkout, lists their tagged releases with installed and newest versions"
        },
        {
          "item": "64d593ed3914",
          "what": "Integrate authored-block-ids: Make authored block IDs distinguishable from generated IDs without changing existing IDs or link targets."
        },
        {
          "item": "79397d9b7f15",
          "what": "Integrate feature/style-cover-template-20261120: Allow a style module to provide an optional cover template rendered with document values, while preserving the built-in cover for styles that do not provide one."
        },
        {
          "item": "7296a3929c3c",
          "what": "Integrate zero-marks-show-zero: Every place obs shows a matrix mark shows 0 as \"0\", so a mark reads as the number it is."
        },
        {
          "item": "77f081787725",
          "what": "Integrate fix/empty-title-and-provenance-public-20261120"
        },
        {
          "item": "53dfce5d8239",
          "what": "Integrate plugins-found-on-remotes: The design notes describe one mechanism for every adapter and style, called plugins: each plugin is its own tagged repository"
        },
        {
          "item": "57f122a3a9dc",
          "what": "Integrate screenshot-a-chapter: One documented command line saves a chapter of a built artifact as a desktop's or a phone's screenshot."
        },
        {
          "item": "9524f90cc51d",
          "what": "Integrate leads-under-their-links: In a bottom line's list of children's leads, each child's title stands alone on its line, with its lead on the next."
        },
        {
          "item": "5275157d4019",
          "what": "Integrate provenance-check-upkeep: The note says a key twice breaks the comment island's shape, and the planted path stays allowed when its line moves."
        },
        {
          "item": "8b53cbbf3dd2",
          "what": "Integrate comments-come-back: The extraction prints one call that brings a reviewer's comments back into the vault."
        },
        {
          "item": "7b1232f3aa82",
          "what": "Integrate bottom-lines-percolate: A chapter's bottom line is a `[!bluf]` callout that the reader sees first, under the chapter title"
        },
        {
          "item": "96f075433f4c",
          "what": "Integrate unify-neutral-main: One neutral tree is shared by every copy of obs, with no account names and documentation linking owners instead of issue numbers"
        },
        {
          "item": "6a5043210bd7",
          "what": "Integrate detail-selection-comments: A reader comments on text selected in a row's expanded note detail, a `details: columns` row body too, as before 9 Nov"
        },
        {
          "item": "45edcfb9fc80",
          "what": "Integrate embeds-show-the-block: An embed of a block or a section shows that block or section in place, as Obsidian does"
        },
        {
          "item": "a5099a2fdc42",
          "what": "Integrate obs-recorded-gaps: Each gap obs workers recorded on 17 Nov is decided: the notes say what the page does"
        },
        {
          "item": "fd83a51f8bc8",
          "what": "Integrate dom-contract-runs-every-check: The DOM contract's default run reaches every verify step, verifyPages and then verifyComments"
        },
        {
          "item": "6c795e1e4659",
          "what": "Integrate obs-adopts-generic-runme: Obs runs from a clean machine through the same two RUNME files as SE"
        },
        {
          "item": "99048fa6253d",
          "what": "Integrate table-rows-one-line: With `artifact.tableRowsOneLine` on, as packaged"
        },
        {
          "item": "64902ea15342",
          "what": "Integrate theme-choice-in-settings: On a page that carries local themes, the Settings bar offers a Theme select below Appearance"
        },
        {
          "item": "9628e69b0d74",
          "what": "Integrate local-theme-rules: A local theme may hold a `style.css` of its own, its fonts, spacing, rules and logo"
        },
        {
          "item": "d44cea8395df",
          "what": "Integrate local-themes-folder: A page built on a machine that holds local themes carries their colours beside Default and opens in that machine's start theme"
        },
        {
          "item": "fcfc89db3724",
          "what": "Integrate starting-appearance-setting: Every page obs-html builds opens in System appearance, which follows the reader's operating-system theme"
        },
        {
          "item": "64e6743da974",
          "what": "Integrate metadata-caret-source-link: Every page of an HTML artifact shows the faint chevron, whose table ends with a `Source file` row"
        },
        {
          "item": "5f320e3eb4ba",
          "what": "Integrate feat/table-live-web-20261116: A table with a live source can also read current values from a public web endpoint"
        },
        {
          "item": "98d4d91160f2",
          "what": "Integrate feat/table-live-rows-20261116: In Claude's artifact viewer, a table with a live source reads what changed since the page was made"
        },
        {
          "item": "e37d24003c30",
          "what": "Integrate check-exceptions-by-digest: An author can add an exception to obs's build checks, the provenance check first"
        },
        {
          "item": "a60263ed5b24",
          "what": "Integrate feat/table-live-source-20261116: A table can say where newer values of its rows come from, and obs checks that statement against the rows it built."
        },
        {
          "item": "dad8340509d3",
          "what": "Integrate unchanged-output-check: A worker can show with one command which of obs's reference pages a change leaves byte for byte as they were on main"
        },
        {
          "item": "f6a7f076a3a2",
          "what": "Integrate adapter-spec-builds-clean: The HTML adapter's own specification builds without a provenance warning, and stays so."
        },
        {
          "item": "f5cd54ac6568",
          "what": "Integrate compare-two-builds: A worker can compare two builds of an artifact with one command that says whether they are identical and"
        },
        {
          "item": "b579344ffba0",
          "what": "Integrate failed-send-plain-words: When a reader's Send fails, or sending is not available on the page, the notice center says so in plain words"
        },
        {
          "item": "00510f1edce2",
          "what": "Integrate passing-line-ships-opt-in: A page built without the setting for Send's passing line is again what it was before that line was added"
        },
        {
          "item": "feeee1e0ac31",
          "what": "Integrate sent-line-below-bar: After Send, obs can confirm it with a short plain line under the top bar that fades after a few seconds"
        },
        {
          "item": "d38cf4fe3d9b",
          "what": "Integrate figure-column-table-notes: The design notes state three rules that obs-html's code already follows, for figures"
        },
        {
          "item": "189dd182a1d9",
          "what": "Integrate pdf-links-without-local-paths: Links in a PDF that obs prints no longer hold a full path of the machine that built it."
        },
        {
          "item": "44f985de5167",
          "what": "Integrate source-date-epoch: With the standard `SOURCE_DATE_EPOCH` variable set"
        },
        {
          "item": "bf6524eab8bf",
          "what": "Integrate action-icon-rules-at-build: A page whose table action icon breaks the schema's rules for its unavailable reason fails to build"
        },
        {
          "item": "a567340612df",
          "what": "Integrate schema-pattern-parity: Obs-html checks a table definition's text patterns the way the page does."
        },
        {
          "item": "9d64f019cbfc",
          "what": "Integrate build-refuses-what-page-refuses: A build refuses what the page's script refuses in a table beyond the schema, unless the check needs other notes"
        },
        {
          "item": "1145c7bbe767",
          "what": "Integrate search-skips-hidden-fields: In a table view that hides fields from its opened rows, a plain search word no longer finds a row by a hidden field."
        },
        {
          "item": "87522c92aa6b",
          "what": "Integrate fix/table-view-options-checked-at-build-20261116: A build that contains a view option the schema refuses fails with the core's one error form, naming the note"
        },
        {
          "item": "ef3e257f9bf2",
          "what": "Integrate feat/table-detail-shows-chosen-fields-20261116: A table view can say which fields an opened row shows."
        },
        {
          "item": "91b56d5d275c",
          "what": "Integrate fix/reopened-comment-highlight-lands-on-its-quote-20261116: A reopened reviewed copy paints every comment's highlight exactly on the text the comment quotes."
        },
        {
          "item": "79175c1df7cc",
          "what": "Integrate feat/two-column-blocks-20261116: Build the `|||` two-column block that obs's input model already specifies"
        },
        {
          "item": "1f234295dae3",
          "what": "Integrate fix/table-headers-carry-no-sort-instructions-20261116: Column headers carry no instruction text."
        },
        {
          "item": "b8da0ba4b4d7",
          "what": "Integrate feat/register-exceptions-first-20261116: A table view can declare which of its rows pass."
        },
        {
          "item": "de2e1958ba2a",
          "what": "Integrate feat/timeline-figure-kind-20261116: Add a `timeline` figure kind that draws dated note records as a lane timeline inside the house figure frame."
        },
        {
          "item": "b2c857332dde",
          "what": "Integrate feat/register-empty-declared-groups-20261116: A grouped register can list its expected group values in `obsHtml.groupOrder`"
        },
        {
          "item": "5c78016e1dee",
          "what": "Integrate chore/neutral-home-20261116: General problem: the same tree may live on more than one Git host, so no tracked file should name where it lives."
        },
        {
          "item": "bec8aca2c541",
          "what": "Integrate test/verdict-print-parity-and-artifact-bytes-20261114: The printed verdict that landed today is held to what the reader's page shows, in full, by one browser test."
        },
        {
          "item": "d7f15e517265",
          "what": "Integrate feat/pugh-verdict-as-text-20261114: Obs prints the computed verdict of every decision in a Document as text and as JSON, without a reader's page"
        },
        {
          "item": "68da20c091a0",
          "what": "Integrate feat/page-shell-limited-host-and-provenance-check-20261114: Two things for pages obs builds"
        },
        {
          "item": "add73ecf3b56",
          "what": "Integrate feat/pugh-engine-computes-the-verdict-20261114: Obs's `pugh` fence computes its decision instead of only drawing it"
        },
        {
          "item": "0590f575fa7c",
          "what": "Integrate feat/first-chapter-second-checked-on-ci-20261113: Obs promises that a document's first chapter shows within one second."
        },
        {
          "item": "3ce2b24e577a",
          "what": "Integrate fix/first-chapter-test-not-runner-bound-20261113: `adapters/html/test/test_startup_browser.py:test_the_spec_artifact_shows_its_first_chapter_within_a_second` fails..."
        },
        {
          "item": "9aaf8661923d",
          "what": "Integrate chore/pins-current-se-5-26-and-js-yaml-20261113: Keep obs's pins current and complete."
        },
        {
          "item": "8fb4a662396a",
          "what": "Integrate chore/vendored-libraries-pass-size-rule-20261113: Two vendored minified JavaScript libraries in obs are over SE's 200 KB file-size rule."
        },
        {
          "item": "151a290014f5",
          "what": "Integrate chore/relock-se-5-25-20261113: Obs pins SE 5.3.0, and SE has moved to 5.25.0 in two days."
        },
        {
          "item": "9616226b2205",
          "what": "Integrate docs/layout-names-measurement-scripts-20261112: Name test/measure/ as the place of measurement scripts and move the library cost..."
        },
        {
          "item": "1d5cb9dae8a8",
          "what": "Integrate perf/load-libraries-on-first-use-20261111: Record the library cost measurement and why libraries stay evaluated at opening"
        },
        {
          "item": "4f7d7ff76c7c",
          "what": "Bound the locked-page sweep by the page's own opening time"
        },
        {
          "item": "18fd8e4a6c07",
          "what": "Put the tests that print a PDF in Chromium in the browser tier"
        },
        {
          "item": "fcb85e143966",
          "what": "Put the tests that build a whole Document or package in a build tier, and warn of a test far slower than its tier"
        },
        {
          "item": "149984aaecb4",
          "what": "Build every test artifact with the library fakes, the named set with the real ones"
        },
        {
          "item": "2b6276ec93e2",
          "what": "Give each library door a fake held to the door's contract"
        },
        {
          "item": "1759cf51c5a5",
          "what": "Reach Plotly, math.js and pdf-lib each through one door"
        },
        {
          "item": "4cdb02ff8953",
          "what": "Give the complete suite headroom under its time limit"
        },
        {
          "item": "60b998c11386",
          "what": "Merge remote-tracking branch 'origin/main' into fix/no-dead-download-links-in-claude-app-20261111"
        },
        {
          "item": "575bc026a1db",
          "what": "Save every file offer through the host's save path, so none is dead in Claude's artifact viewer"
        },
        {
          "item": "807966602260",
          "what": "Have the two-reader export test answer the other reader's reply"
        },
        {
          "item": "029ea0830cd0",
          "what": "Import several returned comment files in one call"
        },
        {
          "item": "aa6664fb6d6a",
          "what": "Export a reviewed copy as one comments file per author"
        },
        {
          "item": "955e8bc5cc54",
          "what": "Hold comment entries to their file's names, times to milliseconds, Delete to own comments"
        },
        {
          "item": "022cd068c62a",
          "what": "Merge remote-tracking branch 'origin/main' into feat/comment-abstract-target-and-state-entries-20261109"
        },
        {
          "item": "be4307e1e201",
          "what": "Comments: list state entries and abstract targets in the extracted text"
        },
        {
          "item": "0f715ee512ee",
          "what": "Comments: target the manifest abstract, record resolves as state entries"
        },
        {
          "item": "d405c1539a76",
          "what": "Comments: the core writes a returned copy's overlay file"
        },
        {
          "item": "7c867e67cfa5",
          "what": "HTML adapter tests: check the native thread fixtures in two core calls"
        },
        {
          "item": "be4741f55b8d",
          "what": "HTML adapter: a selection targets the block it starts in"
        },
        {
          "item": "bce528f40704",
          "what": "HTML adapter: comments and reviews through the core's model"
        },
        {
          "item": "ea4c73d6ef04",
          "what": "Give every block node a stable id"
        },
        {
          "item": "bd998e76af14",
          "what": "Deal CI's shards by committed group weights, heaviest first"
        },
        {
          "item": "03453595dd2d",
          "what": "Draw a first page when a pool's browser launches"
        },
        {
          "item": "c8cb91181a61",
          "what": "Run CI's suite in two shards"
        },
        {
          "item": "796cc46a2a67",
          "what": "Bound a page's release with a watchdog, not a polled evaluation"
        },
        {
          "item": "a136912cf2d0",
          "what": "Keep one sweep child per test process"
        },
        {
          "item": "27aa89e68b4f",
          "what": "Close a pooled page that does not answer while it is released"
        },
        {
          "item": "d979d9437d0f",
          "what": "Sweep each viewport in a child of its own, the phone at device scale 1"
        },
        {
          "item": "c5e3dd3cf15b",
          "what": "Sweep every chapter at phone width too"
        },
        {
          "item": "37119aba1a34",
          "what": "Let the plot legend correction converge"
        },
        {
          "item": "38d0ccfc0d6b",
          "what": "Test that the plot legend correction converges"
        },
        {
          "item": "bb8326a4bbbc",
          "what": "Switch transitions off under reduced motion instead of shortening them"
        },
        {
          "item": "cc575476bae1",
          "what": "Sweep every chapter of every fixture artifact, with and without reduced motion"
        },
        {
          "item": "8b0a6217ff10",
          "what": "Ship each feature's share of base.css only with that feature"
        },
        {
          "item": "4308c65e1576",
          "what": "Ship the reader's Base-table code only with the tables feature"
        },
        {
          "item": "bfbc497d78cc",
          "what": "Remove unused runtime exports, unreachable style rules and an unused alias"
        },
        {
          "item": "73a66f912025",
          "what": "Ship each runtime script, style and data island only where the Document uses it"
        },
        {
          "item": "18824b41f921",
          "what": "Decisions carry a success criterion per option and a Proposed winner box"
        },
        {
          "item": "666945610bd1",
          "what": "Bless and Decline take the review's acceptance and rejection colours"
        },
        {
          "item": "22fe1b73b13a",
          "what": "Screens drop the top band's chapter counter"
        },
        {
          "item": "ac7bbd9de78a",
          "what": "Launch each page pool's browser before the first test that needs it times anything"
        },
        {
          "item": "e599d490e389",
          "what": "Prepare the test workflow with the suite's own setup"
        },
        {
          "item": "8a1fc459bf47",
          "what": "Decision chapters read as Potential solutions, then Details"
        },
        {
          "item": "5163a47bec31",
          "what": "A print draws from a copy of the reader's state and never writes it"
        },
        {
          "item": "5afbeee926ab",
          "what": "Phone width: both decision tabs fit 360 px, the grid a block per option"
        },
        {
          "item": "47fe2b9a4ab0",
          "what": "Pareto tab: the options over the criteria, drawn by the engine's plotSvg"
        },
        {
          "item": "d26c678667c9",
          "what": "Merge origin/main"
        },
        {
          "item": "738ee023afc3",
          "what": "Sensitivity tab: the what-if prose becomes a grid of tie weights"
        },
        {
          "item": "0d2768f1ddeb",
          "what": "Integrate feature/decision-figure-layout-20261106: adapter"
        },
        {
          "item": "0b77f6d29c2f",
          "what": "Screens leave Home when a cleared filter or the screens view brings chapters back; the walk tests read the screens walk"
        },
        {
          "item": "ff25018fdf39",
          "what": "Test that only screens drop Home: scrolling and paged artifacts open on it"
        },
        {
          "item": "b3f4ebc2d5dd",
          "what": "None of the above: Pick offers it beside the letters, it needs a comment, and the answers file records option none"
        },
        {
          "item": "4d778314bc27",
          "what": "Verdicts toggle: the active key or pick, chosen again, clears to pending; pick, picked and obs-bless-change for the figure"
        },
        {
          "item": "a48025d4a976",
          "what": "A verdict never walks: the chapter stays after a bless or a confirmed comment"
        },
        {
          "item": "bd446eb220b6",
          "what": "Screens open on the first chapter: no title screen, Home goes to chapter 1"
        },
        {
          "item": "180ed8ba099c",
          "what": "Record each passed test's tier and time per suite run"
        },
        {
          "item": "02a4a19134b7",
          "what": "Deal each part's xdist groups heaviest first by recorded weights"
        },
        {
          "item": "1d42f56818e5",
          "what": "Share one adapter-spec build per run across the spec's builds"
        },
        {
          "item": "658b1a43aa62",
          "what": "Test on a phone that the options list and the popover say each name once"
        },
        {
          "item": "027e6c345291",
          "what": "Point the reading shell's clearance sentence to the touch exception in Screens"
        },
        {
          "item": "4f5fb3a49de9",
          "what": "Say an option's name once in the options list and the letter popover"
        },
        {
          "item": "6780c0b5ac21",
          "what": "Integrate fix/phone-side-arrows-and-option-repeat-20261106: adapter"
        },
        {
          "item": "737d74a4283f",
          "what": "Integrate perf/slow-test-modules-20261106: core"
        },
        {
          "item": "85c4d9580e2c",
          "what": "Merge remote-tracking branch 'origin/main' into fix/decision-figure-follow-ups-20261106"
        },
        {
          "item": "19af8f6d5322",
          "what": "Open a decision figure's tab where a link leads into it"
        },
        {
          "item": "c87b0712a355",
          "what": "Resolve a decision option's short name once in the core"
        },
        {
          "item": "3a7df59cc88c",
          "what": "Integrate fix/fixture-found-layout-faults-20261106: adapter"
        },
        {
          "item": "4e2e98d6bf4a",
          "what": "Integrate feature/screen-layout-for-decks-20261106: core"
        },
        {
          "item": "933517ea843f",
          "what": "Say that a letter in the decision rows is a control apart from its mark key"
        },
        {
          "item": "f009b4f04260",
          "what": "Name an option by its letter and short name, and open its letter in the rows"
        },
        {
          "item": "b4e5a65a0e8e",
          "what": "Merge remote-tracking branch 'origin/main' into feature/decision-figure-on-phones-20261106"
        },
        {
          "item": "66e1cb1bd687",
          "what": "Draw the decision matrix as rows of letters on a narrow figure, with the chapter's sections as tabs"
        },
        {
          "item": "ae42a34686f2",
          "what": "Test decision figures on emulated phones at 360 and 390 px"
        },
        {
          "item": "6325ead99472",
          "what": "Fit every bless band control in one row of one square size"
        },
        {
          "item": "2d9f4114796a",
          "what": "Test the bless band at 360 and 390 px with the notices shown"
        },
        {
          "item": "a95a292845ca",
          "what": "Build the example deck through the core's command, and read the winner in a decision figure's reader state"
        },
        {
          "item": "b8f0589e1691",
          "what": "Build and walk an example deck of two decision chapters in obs's spec"
        },
        {
          "item": "f46491f43c2c",
          "what": "Show an answered chapter's verdict read-only, so the answered artifact is the decision record"
        },
        {
          "item": "629f1dd39eb3",
          "what": "Bless, decline, ask or pick another option from the top band, and send the verdicts at once"
        },
        {
          "item": "171e147c1fe9",
          "what": "Walk to the previous or next chapter with a horizontal swipe on touch"
        },
        {
          "item": "a33b3d0e69cf",
          "what": "Integrate chore/derived-test-lists-20261106: adapter"
        },
        {
          "item": "d64c42b86622",
          "what": "Merge remote-tracking branch 'origin/main' into feature/pugh-decision-figure-20261106"
        },
        {
          "item": "0e3365f9e95d",
          "what": "Show a decision as lettered options, a changeable matrix, a checklist and what-if tabs"
        },
        {
          "item": "23ffcf7cac19",
          "what": "Merge remote-tracking branch 'origin/main' into feature/pugh-decision-figure-20261106"
        },
        {
          "item": "2d7e41927cd3",
          "what": "Keep a decision figure clear of the chapter controls, whole on its page, one review item"
        },
        {
          "item": "cc910a2bf9e2",
          "what": "Merge remote-tracking branch 'origin/main' into feature/pugh-decision-figure-20261106"
        },
        {
          "item": "9400a4f5d4bd",
          "what": "Say the chosen option's name in a clause, and hold a cut criterion name in its tooltip"
        },
        {
          "item": "a1584d9f8702",
          "what": "Draw a decision figure in the page: bottom line, matrix, check, phone width"
        },
        {
          "item": "e2ac561e33e8",
          "what": "Carry ctrl's Pugh engine unchanged, checked against ctrl's test vectors"
        },
        {
          "item": "e5162137012b",
          "what": "Integrate fix/after-interim-removal-20261106: core"
        },
        {
          "item": "e87dfac496b5",
          "what": "Sweep each width of the coverage check in its own test"
        },
        {
          "item": "bd432b20e249",
          "what": "Name only current commands and paths in the README, AGENTS.md and the specs"
        },
        {
          "item": "a046b908e08d",
          "what": "Describe obs-html and the one-call build in the adapter's CLI and configuration notes"
        },
        {
          "item": "778e8d148576",
          "what": "Build only obs's spec Document once per run"
        },
        {
          "item": "4f118148a9f1",
          "what": "Hold the adapter and the core to their own output instead of the interim adapter"
        },
        {
          "item": "8d75b0c26e27",
          "what": "Merge remote-tracking branch 'origin/main' into fix/no-test-can-hang-the-suite-20261106"
        },
        {
          "item": "f28f83d2edd9",
          "what": "Recover the html adapter's page pools from a crashed or unanswering browser"
        },
        {
          "item": "906df7ce90dc",
          "what": "Give every test its tier's timeout, a measured multiple of the tier's slowest test"
        },
        {
          "item": "12bb1c8dc995",
          "what": "Integrate perf/spec-built-once-per-run-20261106: core"
        },
        {
          "item": "3a8feed21215",
          "what": "Split the long paragraphs left after the vault-settings and timing changes"
        },
        {
          "item": "397e7008c837",
          "what": "Merge remote-tracking branch 'origin/main' into docs/spec-paragraphs-within-the-limit-20261106"
        },
        {
          "item": "aade73eed247",
          "what": "Split the html adapter's spec paragraphs to the long-paragraph limit"
        },
        {
          "item": "5f10ed4d904e",
          "what": "Integrate fix/one-call-build-refuses-output-inside-the-vault-20261106: core"
        },
        {
          "item": "b4ad71eddd88",
          "what": "Integrate fix/export-pdf-carries-the-source-zip-20261106: adapter"
        },
        {
          "item": "ce7f70ebac2b",
          "what": "Integrate feature/long-paragraph-warnings-20261106: core"
        },
        {
          "item": "3afc07863b2f",
          "what": "Merge remote-tracking branch 'origin/main' into fix/adapter-bordered-tags-20261106"
        },
        {
          "item": "806d6a00d779",
          "what": "Parity table: artifact.borderedTags is the same as the interim's"
        },
        {
          "item": "fb2f8cdb1332",
          "what": "obs-html encloses paragraphs of bordered tag kinds in one shared titled card"
        },
        {
          "item": "bcaa80e07a84",
          "what": "obs-html settings accept artifact.borderedTags with the interim's default and limits"
        },
        {
          "item": "59beac561732",
          "what": "Integrate perf/suite-headroom-20261106: adapter"
        },
        {
          "item": "37866fe525c3",
          "what": "Integrate feature/adapter-applies-declared-style-20261106: adapter"
        },
        {
          "item": "ddbbefb8e677",
          "what": "Integrate chore/parity-audit-before-removing-interim-20261106: core"
        },
        {
          "item": "d19fc695dd15",
          "what": "Integrate fix/sankey-fence-checked-at-build-20261106: core"
        },
        {
          "item": "681a4a1a943e",
          "what": "Integrate perf/suite-headroom-20261106: adapter"
        },
        {
          "item": "491d1eb73005",
          "what": "Integrate fix/spec-vault-self-contained-20261106: adapter"
        },
        {
          "item": "314cd1dae8b7",
          "what": "Test that the installed core draws Mermaid and PlantUML offline"
        },
        {
          "item": "9501d9672ded",
          "what": "Integrate feature/style-as-declared-dependency-20261105: core"
        },
        {
          "item": "e1a6a701b58b",
          "what": "Integrate feature/figure-descriptor-data-shapes-20261105: core"
        },
        {
          "item": "6c00af41bd69",
          "what": "Load the packaged maths library in the equations Node test"
        },
        {
          "item": "f110febaffae",
          "what": "Merge remote-tracking branch 'origin/main' into chore/adapter-ships-its-browser-assets-20261106"
        },
        {
          "item": "021455cc1a45",
          "what": "Test that the installed obs-html wheel renders without the repository tree"
        },
        {
          "item": "65949fb40d0f",
          "what": "Ship the adapter's browser assets as package data built from their lockfiles"
        },
        {
          "item": "5a3d32989c6c",
          "what": "Integrate perf/suite-back-under-90s-20261106: core"
        },
        {
          "item": "b689f8eafe4f",
          "what": "Print render.py's limited-function warning through errors.warn"
        },
        {
          "item": "b41b82c419c5",
          "what": "Print the Document's diagnostics only when obs-html runs directly"
        },
        {
          "item": "d45acbce4dd7",
          "what": "Integrate fix/titles-and-labels-as-nodes-20261106: core"
        },
        {
          "item": "1d885262d80e",
          "what": "Integrate feature/source-archive-refers-to-generator-20261106: adapter"
        },
        {
          "item": "3601ebcff23c",
          "what": "State that --print-chapter cannot show labels the artifact computes at runtime"
        },
        {
          "item": "9528a9a86210",
          "what": "Guard that every adapter message is raised or warned through errors.py"
        },
        {
          "item": "2b82df2dd338",
          "what": "Name a figure-style warning's note below the vault root"
        },
        {
          "item": "bf68e9b70bb7",
          "what": "Integrate fix/sankey-label-counts-its-rows-20261106: adapter"
        },
        {
          "item": "ae9aedc0d366",
          "what": "Integrate feature/adapter-source-archive-and-snippets-20261106: adapter"
        },
        {
          "item": "f22ab755774e",
          "what": "Integrate feature/parallel-coordinates-20261105: adapter"
        },
        {
          "item": "c96d779a18ae",
          "what": "Integrate fix/figure-references-complete-20261106: core line"
        },
        {
          "item": "fc74782720e4",
          "what": "Integrate fix/authored-svg-styles-stay-in-their-figure-20261106: adapter line"
        },
        {
          "item": "232d7f408e11",
          "what": "Select a Sankey node's drill-down exactly as its label counts"
        },
        {
          "item": "f78ecd8c2547",
          "what": "Test a Sankey node whose own records narrow its drill-down"
        },
        {
          "item": "e2b13dd84bd8",
          "what": "Integrate feature/equation-figures-live-20261105: adapter line"
        },
        {
          "item": "439aaffe0ac9",
          "what": "Integrate fix/heading-link-labels-and-command-output-markup-20261106: adapter line"
        },
        {
          "item": "bc8b8fcf0c83",
          "what": "Merge remote-tracking branch 'origin/main' into fix/startup-test-stable-under-load-20261106"
        },
        {
          "item": "a2b9b2804563",
          "what": "Time the spec artifact's startup from its own marks, budgeted against same-run load"
        },
        {
          "item": "d2ecf9aaecb9",
          "what": "Integrate feature/equation-figures-core-20261105: core line"
        },
        {
          "item": "9968c333b22b",
          "what": "Integrate fix/every-drill-down-matches-its-count-20261106: core line"
        },
        {
          "item": "8b07b0452f9d",
          "what": "obs-html prints a chapter of a built artifact"
        },
        {
          "item": "ac0644d2b1e5",
          "what": "Integrate perf/coverage-sweep-without-repeats-20261106: adapter tests"
        },
        {
          "item": "9091c020ae18",
          "what": "Merge remote-tracking branch 'origin/main' into feature/diagram-fences-20261105"
        },
        {
          "item": "943cf2351ec7",
          "what": "Show diagram figures in the one figure frame"
        },
        {
          "item": "dc45d1daca4b",
          "what": "Merge remote-tracking branch 'origin/main' into feature/one-figure-class-20261105"
        },
        {
          "item": "43c17de1708c",
          "what": "Declare a figure kind's library need through the feature registry"
        },
        {
          "item": "03c7f2a7bba3",
          "what": "Give figure kinds with view options the tables' options menu"
        },
        {
          "item": "1b902785236f",
          "what": "Merge remote-tracking branch 'origin/main' into feature/one-figure-class-20261105"
        },
        {
          "item": "6a04da5eec12",
          "what": "Frame every figure kind in one figure frame from a kind registry"
        },
        {
          "item": "3d42e4d30f3d",
          "what": "Emit every figure as one figures node of a kind, inline or from a source file"
        },
        {
          "item": "362182e3a2dc",
          "what": "Restate obs's output-format sentences without naming HTML"
        },
        {
          "item": "72248836f2ba",
          "what": "Split cover metadata and reviewed copies by owner"
        },
        {
          "item": "d434dfcd94bc",
          "what": "Integrate docs/html-spec-is-a-reference-20261105: adapter line"
        },
        {
          "item": "e332b0436efb",
          "what": "Merge remote-tracking branch 'origin/main' into feature/core-validates-cover-metadata-20261106"
        },
        {
          "item": "2e68bb60f43f",
          "what": "Validate the manifest's cover metadata in the core"
        },
        {
          "item": "e9d388356629",
          "what": "Integrate chore/browser-deps-as-suite-setup-20261106: core line"
        },
        {
          "item": "176671d95a9d",
          "what": "Integrate fix/clipboard-test-stable-under-load-20261106: adapter tests"
        },
        {
          "item": "4e41c76301d9",
          "what": "Integrate fix/every-adapter-error-names-place-and-remedy-20261106: adapter line"
        },
        {
          "item": "32d4f1e8c606",
          "what": "Let reader-facing text name the document number field"
        },
        {
          "item": "811488e7b1a9",
          "what": "Merge remote-tracking branch 'origin/main' into fix/generic-document-number-field-20261105"
        },
        {
          "item": "520681120714",
          "what": "Fail when a core schema or the HTML adapter names a vendor in a field"
        },
        {
          "item": "6347727ee463",
          "what": "Name the manifest's document number generically"
        },
        {
          "item": "60dabfe5f1f6",
          "what": "Integrate feature/adapter-one-selection-rule-set-20261105: adapter line"
        },
        {
          "item": "c1234d7fa2eb",
          "what": "Merge remote-tracking branch 'origin/main' into fix/property-editor-projection-per-spec-20261106"
        },
        {
          "item": "92d2bf74b3ed",
          "what": "Merge remote-tracking branch 'origin/main' into fix/property-editor-projection-per-spec-20261106"
        },
        {
          "item": "16b8c25c0244",
          "what": "obs-html renders a core-built property editor projection"
        },
        {
          "item": "523da0ac0712",
          "what": "Integrate feature/field-nodes-for-every-record-20261106: every record carries field nodes for its string values"
        },
        {
          "item": "a72d03f1925c",
          "what": "Integrate fix/hashed-deny-list-repo-wide-20261106: the deny list holds salted hashes and covers the repository"
        },
        {
          "item": "6c892390ea9c",
          "what": "The attachment download belongs to the downloads feature"
        },
        {
          "item": "e5b9e193e4f3",
          "what": "obs-html offers the light and the evidence edition with --embed-attachments"
        },
        {
          "item": "6dd3c56ba9fc",
          "what": "Integrate feature/only-used-features-ship-20261105: clipboard and download remedies on use"
        },
        {
          "item": "1a4abca25e06",
          "what": "Merge remote-tracking branch 'origin/main' into fix/block-nodes-never-inside-paragraphs-20261105"
        },
        {
          "item": "eeb933794e8b",
          "what": "Merge remote-tracking branch 'origin/main' into fix/block-nodes-never-inside-paragraphs-20261105"
        },
        {
          "item": "359b2f2fef9d",
          "what": "Place the adapter fixture Document's note embed beside its paragraphs"
        },
        {
          "item": "476be7256c7e",
          "what": "Merge remote-tracking branch 'origin/main' into fix/block-nodes-never-inside-paragraphs-20261105"
        },
        {
          "item": "322bd0974bf2",
          "what": "Remove the adapter's paragraph split now that the core places no block node in a paragraph"
        },
        {
          "item": "96a79bc1130f",
          "what": "Split a paragraph around each block node so none is a paragraph's child"
        },
        {
          "item": "30f1bdf3e093",
          "what": "Integrate fix/hidden-manifest-lines-20261105: Obsidian comments hide manifest lines and never render"
        },
        {
          "item": "d317eae1b4c0",
          "what": "Integrate feature/card-bodies-from-nodes-20261105: card bodies render from the core's nodes"
        },
        {
          "item": "2f5a9ded1ae6",
          "what": "Integrate fix/adapter-writes-valid-html-20261105: the adapter writes valid HTML, checked on every artifact"
        },
        {
          "item": "703b89e84efc",
          "what": "Integrate feature/command-authorization-through-adapter-20261105: the core runs command fences under explicit authorization"
        },
        {
          "item": "b9701bccbd2a",
          "what": "Integrate perf/every-check-in-the-gate-20261105: the suite rebuilds every adapter fixture with the current core"
        },
        {
          "item": "0a45d8c77d0c",
          "what": "Integrate feature/one-row-top-band-20261105: one top row; the title page shows its type once"
        },
        {
          "item": "d74488c28140",
          "what": "Integrate perf/every-check-in-the-gate-20261105: non-interim checks join the suite; tests stay offline"
        },
        {
          "item": "0e56d8e52167",
          "what": "Merge remote-tracking branch 'origin/main' into feature/registers-from-node-20261105"
        },
        {
          "item": "7893c89f5288",
          "what": "Drop Base-level members from the adapter's Base schema; rebuild the stale fixture Documents"
        },
        {
          "item": "0e988d57675a",
          "what": "Read membership only through the core's rows; a view's members order and label them"
        },
        {
          "item": "dce0641727db",
          "what": "Render a registers node from its attrs: each view's rows are the core's, for every record type"
        },
        {
          "item": "6effff19df1c",
          "what": "Render a core-built callout whose body holds a list, a wikilink and a nested callout"
        },
        {
          "item": "bdcc3ffe709d",
          "what": "Drop the callout syntax-extension registry: the core sends callouts without an extensions marker"
        },
        {
          "item": "706fef25a06c",
          "what": "Integrate feature/structural-nodes-rendered-20261105: the adapter renders every structural node type"
        },
        {
          "item": "f3b6a5040674",
          "what": "Test that the spec artifact shows its first chapter within a second"
        },
        {
          "item": "27a82c0807c7",
          "what": "Artifact startup runs in 50 ms slices and numbers pages once"
        },
        {
          "item": "5a1f65df74fa",
          "what": "Dark is a near-black page with light grey text"
        },
        {
          "item": "3e42e65aa960",
          "what": "html and body paint the appearance's background and text colour"
        },
        {
          "item": "a137a4448285",
          "what": "The root's color-scheme alone follows the chosen appearance"
        },
        {
          "item": "314e34de7dc4",
          "what": "Add the artifact-viewer fixture and appearance regression tests"
        },
        {
          "item": "b5cf12613256",
          "what": "Batch the parity gate's browser checks"
        },
        {
          "item": "0d52d25127cd",
          "what": "Build obs's spec and the shared fixture artifacts once per run"
        },
        {
          "item": "76aa469c60ca",
          "what": "Run the complete suite in parallel workers"
        },
        {
          "item": "e1f07bf376b0",
          "what": "Describe one repository with an adapter folder in README and AGENTS"
        },
        {
          "item": "8fc7d20a5c30",
          "what": "Read the core's selection conformance fixture from the adapter's runner"
        },
        {
          "item": "cfaf4374c945",
          "what": "Render an unknown Document node type as its text with one warning"
        },
        {
          "item": "7559fdf68624",
          "what": "Name the adapter's presentation capability artifact-presentation"
        },
        {
          "item": "4311d42e1f38",
          "what": "Make the HTML adapter a uv workspace member registered by the root adapters.json"
        },
        {
          "item": "6650ca9b05d8",
          "what": "Rename the interim adapter to obs_html_interim and obs-html-interim"
        },
        {
          "item": "09cd0f2539a4",
          "what": "Integrate refactor/report-becomes-artifact-20261105: the rendered output is the artifact; the Document stays the core's JSON"
        },
        {
          "item": "62f20d9a9db6",
          "what": "Integrate fix/no-control-covered-20261105: no control is covered by another element's pointer area, checked at four widths in both preview frames"
        },
        {
          "item": "5bfad3515b04",
          "what": "Integrate feature/render-references-registers-properties-extensions-20261105: references, callout syntax extensions and property editors render as in the interim adapter, with the remaining DOM contracts moved"
        },
        {
          "item": "49bed48ae2f3",
          "what": "Integrate fix/reader-regressions-in-preview-20261105: Home and the chapter chooser are no longer covered by the arrows, filtering is not a change, canaries say what they observed, and a parity gate against the interim reference"
        },
        {
          "item": "60c2699714ed",
          "what": "Integrate feature/render-cards-counts-quantities-20261105: cards and metrics, count queries and quantities render as in the interim adapter, never counting ignored notes"
        },
        {
          "item": "16f2f7f94904",
          "what": "Integrate feature/render-callouts-embeds-attachments-20261105: callouts, embeds and attachments render as in the interim adapter; the title page's running header is centered"
        },
        {
          "item": "52c192b76136",
          "what": "Integrate chore/project-identity-in-se-toml-20261105: se.toml names the project commit identity"
        },
        {
          "item": "a73bcc3d1f0c",
          "what": "Integrate feature/unlisted-chapters-and-home-links-20261105: unlisted chapters render outside Contents and stay reachable by link"
        },
        {
          "item": "1e141cc1b695",
          "what": "Integrate fix/no-local-paths-in-command-output-20261105: command output and reports carry no paths of the build machine"
        },
        {
          "item": "8365d9b9f8a8",
          "what": "Integrate feature/three-icon-notice-center-20261105: one notice center with at most three severity icons and count pills"
        },
        {
          "item": "0a18c3486abf",
          "what": "Integrate feature/base-tables-from-records-20261105: Base tables from the core's note records, with ignored notes never selected"
        },
        {
          "item": "87cc1ff33a9e",
          "what": "Integrate feature/pdf-inspection-tools-20261105: obs-html-inspect renders, crops, reads text and vector paths of PDF pages and annotates rasters"
        },
        {
          "item": "cb12b794317e",
          "what": "Integrate feature/limited-functionality-notice-20261105: startup canaries and a Limited functionality notice for restricted hosts"
        },
        {
          "item": "9a12b1621244",
          "what": "Integrate feature/link-by-chapter-id-20261105: link wikilinks and embeds to the chapter the core names"
        },
        {
          "item": "9507d8ba5be3",
          "what": "Integrate feature/attachment-replacement-extension-20261105: a trusted extension that replaces an attachment and its dependent records in one revision-checked transaction"
        },
        {
          "item": "6ab5690faf2c",
          "what": "Integrate feature/report-verification-harness-20261105: a Node DOM harness that loads a report, activates chapters, mounts tables and reports page geometry"
        },
        {
          "item": "5898c31f3fd8",
          "what": "Integrate feature/deterministic-svg-figure-export-20261105: export each figure as a byte-stable SVG through the CLI"
        },
        {
          "item": "1f674696c56c",
          "what": "Integrate refactor/html-presentation-assets-20261105: the interactive report from the Document, with styles, icons, figures, comments and browser tests"
        },
        {
          "item": "d2a7a7411197",
          "what": "Integrate docs/one-owner-for-sync-command-20261105: the README owns the module sync command"
        },
        {
          "item": "3667d949b625",
          "what": "Integrate docs/suite-needs-module-sync-20261105: name the module sync before the suite and in the missing-core error"
        },
        {
          "item": "cb44163b2c6a",
          "what": "Integrate refactor/html-rendering-adapter-20261105: render the JSON Document through the obs-html CLI"
        },
        {
          "item": "d4b547b85929",
          "what": "Allow the fleet's session and GitHub tools without prompts"
        },
        {
          "item": "f1ae365854df",
          "what": "Merge chore/authored-prose-opt-in-20261105: authored prose protection"
        },
        {
          "item": "19ff87b9e297",
          "what": "Merge chore/create-obs-html-repository-20261105: core pin and smoke adapter"
        },
        {
          "item": "2a9aef17131c",
          "what": "Initial skeleton"
        }
      ],
      "kept": false
    },
    {
      "name": "field-report",
      "rule": "every closed work issue has a field report",
      "checked": 23,
      "broken": [],
      "kept": true
    }
  ],
  "metrics": {
    "landings": 24,
    "local": 1333,
    "runs": 1318
  },
  "adhoc": [],
  "scripts": [],
  "previous": null,
  "findings": [
    {
      "title": "Update the SE component declaration to the current schema",
      "body": "The current startup report found `se.toml` still declares the SE component under `[modules.se]`, while current SE expects `[components]`. Move the declaration to `[components.se]` and verify startup. The report separately says kern's binary was not placed; this is a distinct bootstrap condition.",
      "class": "Legacy SE component section",
      "home": "se.toml",
      "controversial": false
    }
  ],
  "classes": [
    {
      "name": "Legacy SE component section",
      "cause": "The project config declares the SE component under `[modules.se]`, which current SE no longer reads.",
      "fix": "Move the declaration to `[components.se]` and verify the current startup path finds the component.",
      "home": "se.toml",
      "home_kind": "setting",
      "status": "Blessed; filing waits for #1827"
    }
  ],
  "went_well": [
    "All 23 closed work issues landed with field reports, with no duplicates or refused deliveries.",
    "Focused reproduction isolated the Playwright/browser mismatch in #69.",
    "Committed fixtures and precise gate remedies made capability gaps quick to find in #67.",
    "Measuring the built page identified the alignment cause before changing CSS in #76.",
    "A reviewed design let #58 stay a small pin-and-test change."
  ]
}
```
