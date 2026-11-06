---
kind: adapter-behavior
capability:
  id: source-archive
  summary: Include reproducible source material in an authored artifact.
  authoring: Request source embedding through the explicit build option and declared inputs.
  dependsOn: ["manifest", "attachments"]
  source: "[[input-model#Optional reproduction archive]]"
---

The register presents the owning metadata as the capability reference.
