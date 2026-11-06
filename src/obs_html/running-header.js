(() => {
    // The header lines as HTML, from the metadata's display HTML (render.py, _frontmatter_html):
    // values render from their field nodes, never from the authored strings.
    const escaped = value => {
        const span = document.createElement("span");
        span.textContent = value;
        return span.innerHTML;
    };
    const content = (metadataHtml, slug = "home", section = "") => [
        [metadataHtml["product.name"], metadataHtml["document type"]].filter(Boolean).join(" · "),
        slug === "home" ? metadataHtml.confidentiality || "" : escaped(section),
    ];
    const snapshot = (root, metadataHtml) => {
        root.querySelector("#running-header-script").dataset.headerMetadata = JSON.stringify(metadataHtml);
    };
    globalThis.obsRunningHeader = Object.freeze({content, snapshot});

    const metadataHtml = JSON.parse(document.querySelector("#running-header-script").dataset.headerMetadata);
    const opening = document.createElement("div");
    opening.className = "reader-opening";
    const header = document.createElement("header");
    header.className = "paper-header";
    content(metadataHtml).forEach(value => {
        const line = document.createElement("span");
        line.innerHTML = value;
        if (line.textContent.trim()) header.append(line);
    });
    const status = document.createElement("p");
    status.setAttribute("role", "status");
    status.setAttribute("aria-busy", "true");
    status.textContent = "Opening HTML…";
    opening.append(header, status);
    document.querySelector("[data-chapter-body]").replaceChildren(opening);
})();
