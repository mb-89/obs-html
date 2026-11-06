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

## Adapter extensions

obs's input model owns where an adapter documents its trusted extensions and how it names their
namespace (Core and adapter namespaces, Adapter extensions). This adapter's namespace is `obsHtml`
(for obs-html), so its extensions are `obsHtml.<area>`, for example `obsHtml.attachments`.

obs-html's [[capabilities/attachment-replacement|attachment replacement]] note is the example to
follow.
