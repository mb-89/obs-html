// Canary of Interactive plots (features.py, plotting), which asks the library's door (plotly-door.js): the plotting library loads after the canaries,
// from the HTML itself or, where configured, from its CDN, so a plot reports a failure on use.
globalThis.obsCapabilities.canary({
    key: "plotting", feature: "Interactive plots",
    blocks: "the plotting library, so plots show their static form or a notice",
    remedy: "Open the HTML file directly in a browser with network access, or build it with the plotting library embedded.",
    probe: ({view}) => (view.obsPlotly?.available()
        ? {allowed: true, observation: "the plotting library is loaded"}
        : {allowed: undefined, observation: "the plotting library loads after the canaries; a plot tries it on use"}),
});
