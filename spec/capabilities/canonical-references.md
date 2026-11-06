---
kind: adapter-behavior
capability:
  id: canonical-references
  summary: Present canonical references through declared detail views.
  authoring: Declare reference fields in the supported table presentation mapping.
  dependsOn: ["references", "bases"]
  source: "[[input-model#Canonical reference presentation]]"
---

The register presents the owning metadata as the capability reference.
