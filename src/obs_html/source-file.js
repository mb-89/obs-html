/* Source file row (features.py, source-file): the last row of each note's front matter card in the
   Comments bar names the vault path of the note, after its fields (artifact-ui.md, Comments bar;
   cli.md, Source file links). It reads each note's sourceFilePath and sourceFileHref from the data
   island; the bar asks it for the value of each card it shows (bars/comments.js), in a list a saved
   copy holds empty (data-transient-content): a link that opens in a new tab where the build knew
   where the vault lies from the page, plain text elsewhere, and none for a note without a path. */
(() => {
  const data = JSON.parse(document.querySelector("[data-artifact-data]").textContent);
  const notes = new Map(data.notes.map(note => [note.slug, note]));
  globalThis.obsSourceFile = {
    value: slug => {
      const note = notes.get(slug);
      if (!note?.sourceFilePath) return null;
      if (!note.sourceFileHref) return document.createTextNode(note.sourceFilePath);
      const link = document.createElement("a");
      link.href = note.sourceFileHref;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = note.sourceFilePath;
      return link;
    },
  };
})();
