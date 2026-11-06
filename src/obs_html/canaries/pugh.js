// Canary of Decision figures (features.py, pugh): ctrl's decision engine is embedded in the HTML and
// loads after the canaries, so a decision figure reports a failure on use.
globalThis.obsCapabilities.canary({
    key: "pugh", feature: "Decision figures",
    blocks: "the embedded decision engine, so decision figures show a notice instead of their decision",
    remedy: "Open the HTML file directly in a browser that runs its scripts.",
    probe: ({view}) => (view.obsPughEngine
        ? {allowed: true, observation: "the decision engine is loaded"}
        : {allowed: undefined, observation: "the decision engine loads after the canaries; a decision figure tries it on use"}),
});
