/* Source file row (features.py, source-file): the frontmatter table's last row names the vault
   path of the note the page shows, after its fields (artifact-ui.md, Reading shell; cli.md, Source
   file links). It reads each note's sourceFilePath and sourceFileHref from the data island; on each
   chapter change it fills a tbody of its own, which a saved copy holds empty (data-transient-content),
   with one row for a note that has a path: a link that opens in a new tab where the build knew where
   the vault lies from the page, plain text elsewhere. It then shows the chevron; for a note without a
   path it leaves the tbody empty and the chevron as artifact.js set it. */
(() => {
  const data = JSON.parse(document.querySelector("[data-artifact-data]").textContent);
  const notes = new Map(data.notes.map(note => [note.slug, note]));
  const fields = document.querySelector("[data-frontmatter-body]");
  const toggle = document.querySelector("[data-frontmatter-toggle]");
  const own = () => {
    let body = fields.parentElement.querySelector("[data-source-file-body]");
    if (!body) {
      body = document.createElement("tbody");
      body.dataset.sourceFileBody = "";
      body.dataset.transientContent = "";
      fields.after(body);
    }
    return body;
  };
  const row = note => {
    const heading = document.createElement("th");
    heading.scope = "row";
    heading.textContent = "Source file";
    const cell = document.createElement("td");
    if (note.sourceFileHref) {
      const link = document.createElement("a");
      link.href = note.sourceFileHref;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = note.sourceFilePath;
      cell.append(link);
    } else {
      cell.textContent = note.sourceFilePath;
    }
    const line = document.createElement("tr");
    line.append(heading, cell);
    return line;
  };
  document.addEventListener("obs-chapter-change", ({detail}) => {
    if (!detail?.slug) return;  // An event that names no chapter leaves the row as it is.
    const note = notes.get(detail.slug);
    const body = own();
    if (!note?.sourceFilePath) {
      body.replaceChildren();
      return;
    }
    body.replaceChildren(row(note));
    toggle.hidden = false;
  });
})();
