// Canary of Screens (features.py, screens): a chapter fits one screen only where the page has a
// viewport of its own; a host that shows the page in a frame of no size gives it none.
globalThis.obsCapabilities.canary({
    key: "screens", feature: "Screens",
    blocks: "a viewport of the page's own, so a chapter cannot fit one screen",
    remedy: "Open the HTML file directly in a browser to read it one screen per chapter.",
    probe({view}) {
        const {innerWidth: width, innerHeight: height} = view;
        return {allowed: width > 0 && height > 0, observation: `the page's viewport is ${width} × ${height} px`};
    },
});
