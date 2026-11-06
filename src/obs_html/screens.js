/* Screens (features.py, screens; artifact-ui.md, Screens): an artifact that opens in screens shows
   the manifest's title in the top band, between the breadcrumbs and the frontmatter chevron.
   screens.css lays the screen out. */
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
})();
