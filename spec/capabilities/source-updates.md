---
kind: adapter-behavior
capability:
  id: source-updates
  summary: Project current canonical source after a trusted update.
  authoring: Use the trusted update flow with declared canonical source identifiers.
  dependsOn: ["trusted-actions", "source-archive"]
  source: "[[input-model#Current source projection after a trusted update]]"
---

The register presents the owning metadata as the capability reference.
