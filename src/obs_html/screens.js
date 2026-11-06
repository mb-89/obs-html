/* Screens (features.py, screens; artifact-ui.md, Screens): an artifact that opens in screens shows
   the manifest's title in the top band, between the breadcrumbs and the frontmatter chevron, and,
   first at the band's end, the active chapter's position on the chapters of the walk, "2 / 3";
   Home, which is not one of them, shows none. screens.css lays the screen out; pages.js prints it. */
(() => {
  const data = JSON.parse(document.querySelector("[data-artifact-data]").textContent);
  const band = document.querySelector("[data-top-band]");
  const title = document.createElement("span");
  title.className = "screens-title";
  title.dataset.screensTitle = "";
  title.dataset.transientView = "";
  title.textContent = title.title = data.document.title;
  title.hidden = !data.document.title;
  band.querySelector("[data-frontmatter-toggle]").before(title);
  const position = document.createElement("span");
  position.className = "screens-position";
  position.dataset.screensPosition = "";
  position.dataset.transientView = "";
  position.setAttribute("role", "status");
  position.hidden = true;
  band.querySelector("[data-top-band-end]").prepend(position);
  // The walk is obsArtifact's (artifact.js), which exists once its script has run: the first chapter
  // opens while it runs, so the position follows each change after the change's own task.
  const update = () => {
    const slug = document.querySelector("[data-active-chapter]").dataset.chapter;
    const walk = globalThis.obsArtifact.navigationChapters();
    const index = walk.findIndex(record => record.slug === slug);
    position.hidden = index < 0;
    position.textContent = `${index + 1} / ${walk.length}`;
    position.title = `Chapter ${index + 1} of ${walk.length}`;
    position.setAttribute("aria-label", position.title);
  };
  document.addEventListener("obs-chapter-change", () => queueMicrotask(update));
  document.addEventListener("obs-artifact-filter", () => queueMicrotask(update));
})();
