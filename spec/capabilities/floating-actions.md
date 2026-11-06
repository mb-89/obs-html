---
kind: adapter-behavior
capability:
  id: floating-actions
  summary: Expose trusted actions from an authored floating-content view.
  authoring: Declare a supported action identifier in the trusted runtime mapping.
  dependsOn: ["trusted-actions", "canonical-references"]
  source: "[[input-model#Trusted floating-content actions]]"
---

The register presents the owning metadata as the capability reference.
