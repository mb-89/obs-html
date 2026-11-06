document.documentElement.dataset.theme = READER_THEME;
document.documentElement.classList.toggle("paged-mode", READER_LAYOUT === "paged");
document.documentElement.classList.toggle("screens-mode", READER_LAYOUT === "screens");
