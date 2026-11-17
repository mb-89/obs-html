---
kind: adapter-behavior
capability:
  id: live-data
  summary: Let a Base declare where newer values of its rows are read when the page opens, checked against the rows the build selected.
  authoring: Add obsHtml.liveSource to a Base, then run obs-html --check-rendered on the built page.
  dependsOn: ["bases", "registers"]
  source: "[[generic-tables#Current data]]"
---

# Live data

Reader: whoever declares, in a Base, where newer values of its rows come from, or changes how
obs-html checks such a declaration.

[[generic-tables#Current data]] owns the declaration, its refusals, the mapping rules and the
check; this note shows how to author one.

## Authoring

Add `obsHtml.liveSource` to the Base, in a `base` fence or a `.base` file. Each row is a note
whose path follows from its key, here `issues/widgets-12.md` for the item `{repo: widgets,
number: 12}`, and whose frontmatter holds the fields the declaration maps. A row carries no date,
by the owner's decision of 17 Nov 2026: the page compares a read item's values with its row's.

```yaml
obsHtml:
  liveSource:
    name: Example Tracker
    key: [repo, number]
    notePath: "issues/{repo}-{number}.md"
    fields:
      number: number
      state: {path: state, lowercase: true}
      labels: labels
      pullRequest: pull_request.url
    derive:
      status:
      - {where: [{field: labels, equals: planned}], keep: true}
      - {where: [{field: state, equals: closed}], value: Done}
      - {where: [{field: labels, equals: backlogged}], value: Backlog}
      - {where: [{field: labels, equals: needs-you}], value: Needs you}
      - {where: [{field: labels, equals: running}], value: Running}
      - {where: [{field: labels, equals: ready}], value: Next}
      - {keep: true}
    fillNew: {where: title}
    bodyPath: body
    exclude: [{field: pullRequest, exists: true}]
    changes:
    - provider: connector
      server: Example Tracker
      tool: list_issues
      rows: issues
      next: {cursor: pageInfo.endCursor, more: pageInfo.hasNextPage, input: after}
      maxPages: 3
      requests:
      - set: {repo: widgets}
        input: {owner: example-org, repo: widgets, since: "{since}", orderBy: UPDATED_AT, direction: ASC, perPage: 100}
    - provider: web
      next: link
      maxPages: 3
      fields: {labels: "labels[].name"}
      requests:
      - set: {repo: widgets}
        url: "https://api.example.test/repos/example-org/widgets/issues?state=all&since={since}&sort=updated&direction=asc&per_page=100"
```

## What a read sees

A read asks each request for the items changed since `{since}`: the page's generation timestamp
minus `lookbackHours` (default 1). The generation timestamp is the page's last content change, so
a page whose rows stay the same while its source is busy reads more items as time passes.

- Order each request oldest-first by update, as the example does: an item read twice keeps its last
  occurrence, the newest. A read that stops at `maxPages` then shows the older changes and says
  "showing the first <n> changes".
- Narrow a request, such as by labels, where a table shows few of its source's items.
- A read sees only items changed after `{since}`. Rows written longer than `lookbackHours` before
  their build, such as a rebuild from the source archive or notes harvested earlier, miss the
  changes of that interval until the item changes again; such a vault sets `lookbackHours` to the
  age its rows can reach.
- Where `SOURCE_DATE_EPOCH` fixes an earlier build time, a read starts earlier and returns more
  items, never fewer.

## Checking a declaration

The build refuses a declaration it can tell is wrong by its shape, at its field. Whether the
declaration fits the rows is told only in the page: after declaring a source, build the HTML and
run `obs-html --check-rendered` on it. A row whose key, note path or derived value the declaration
does not reproduce fails that check with one console error naming the table, the note, the check
and the field, and the table keeps its saved rows.

## Reading in Claude's artifact viewer

A connector route is read only in Claude's artifact viewer, through the viewer's own connection to
the source, after the reader allows it once with the button "Show current data" or in the
artifact's permissions; [[generic-tables#Reading]] owns the steps. The page carries no token and
reaches no other host: the viewer blocks every request a page makes itself.

Publish the page with exactly this declaration, one entry per connector route, `server` and `tool`
as the route names them:

```json
{"mcp": {"servers": [{"server": "Example Tracker", "tools": ["list_issues"]}]}}
```

`obs-html` prints it after "Generated ..." for a page that has a connector route. A viewer outside
the publisher's organization, an artifact opened top-level and a page opened from disk see the
saved rows; in the viewer the line under the table says "Newer updates cannot be shown here".

### A gap the source leaves

The connector's issue list carries no closed date and no close reason. An issue closed since the
page was made therefore shows as its `derive` says, `Done` in the example, even when it was closed
as not planned, until the next build.
