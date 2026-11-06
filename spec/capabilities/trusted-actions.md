---
kind: adapter-behavior
capability:
  id: trusted-actions
  summary: Invoke declared trusted runtime actions against canonical source state.
  authoring: Register a trusted action bundle through the explicit runtime boundary.
  dependsOn: ["markdown-frontmatter", "canonical-references"]
  source: "[[input-model#Trusted runtime and canonical replacement]]"
---

The register presents the owning metadata as the capability reference.

## Registration

The bundle `--trusted-runtime-bundle ID=PATH` selects registers once, with
`obsArtifact.registerApplication({id, actions})`: `id` is the selected ID, and `actions` is an
array of actions, each with an `id`, the file types it `accept`s, its `help` and its `handle`.
`actions` may be empty: a bundle that registers only extensions, such as an
[[capabilities/answers|answers]] sink, is trusted for them and adds no action. A registration
without an `actions` array, or under another ID, fails the opening and names
`obsArtifact.registerApplication`.

## Adapter extensions

obs's input model owns where an adapter documents its trusted extensions and how it names their
namespace (Core and adapter namespaces, Adapter extensions). This adapter's namespace is `obsHtml`
(for obs-html), so its extensions are `obsHtml.<area>`, for example `obsHtml.attachments`.

obs-html's [[capabilities/attachment-replacement|attachment replacement]] note is the example to
follow; [[capabilities/answers|answers]] (`obsHtml.answers`) is the second extension.
