---
kind: adapter-behavior
capability:
  id: artifact-presentation
  summary: Set document-level layout and page presentation.
  authoring: Declare the document obsHtml presentation mapping in manifest frontmatter.
  dependsOn: ["manifest", "profiles"]
  source: "[[input-model#Artifact presentation profile]]"
---

The register presents the owning metadata as the capability reference.
