// Canary of Equation figures (features.py, equations): the maths library is embedded in the HTML
// and loads after the canaries, so an equation figure reports a failure on use.
globalThis.obsCapabilities.canary({
    key: "equations", feature: "Equation figures",
    blocks: "the embedded maths library, so equation figures show a notice instead of their plot",
    remedy: "Open the HTML file directly in a browser that runs its scripts.",
    probe: ({view}) => (view.math
        ? {allowed: true, observation: "the maths library is loaded"}
        : {allowed: undefined, observation: "the maths library loads after the canaries; an equation figure tries it on use"}),
});
