// The one mapping between the core's comments (obs input-model, Comments and reviews) and the threads
// the Comments bar shows (spec/input-model.md, Comments and the core model). A thread is a root
// comment with its replies nested by inReplyTo, its body as text and mediaType; a decision, a
// state entry and the reader's names are the core's as they are, and a target the core's, but for
// the abstract's, which on the home page is the home page's chapter key. The review state
// (reviewState) and a comment's state (commentState) mirror their owners,
// obs.comments.review_state and obs.comments.comment_state.
(() => {
    "use strict";

    const VERSION = 1;
    // The home page's chapter key (render.py HOME), which no Document chapter may have.
    const HOME = "home";
    const fail = (message) => { throw new Error(message); };
    const canonical = (target) => JSON.stringify(Object.keys(target).sort().map((key) => [key, target[key]]));
    const sameTarget = (first, second) => canonical(first) === canonical(second);
    const compare = (first, second) => (first < second ? -1 : first > second ? 1 : 0);
    const order = (first, second) => Date.parse(first.created) - Date.parse(second.created) ||
        compare(first.id, second.id);
    const fromTarget = ({abstract, ...target}) => (abstract === true ? {chapter: HOME, ...target} : target);
    const toTarget = ({chapter, ...target}) => (chapter === HOME ? {abstract: true, ...target}
        : {...(chapter === undefined ? {} : {chapter}), ...target});
    const mapTargets = (entry, map) => ({...entry, ...(entry.target ? {target: map(entry.target)} : {}),
        ...(entry.batch ? {batch: {...entry.batch, items: entry.batch.items.map(map)}} : {})});

    const fromCore = (model) => {
        if (!model || model.version !== VERSION || !Array.isArray(model.comments) || !Array.isArray(model.decisions)) {
            fail(`the comment island is not version ${VERSION} of the core's comments`);
        }
        const threads = new Map();
        model.comments.forEach((comment) => {
            if (!comment || typeof comment.id !== "string" || typeof comment.body?.text !== "string" ||
                    !["open", "resolved"].includes(comment.state) || threads.has(comment.id)) {
                fail("the comment island holds an invalid comment");
            }
            const {body, inReplyTo: _answered, ...rest} = mapTargets(comment, fromTarget);
            threads.set(comment.id, {...rest, mediaType: body.mediaType, text: body.text, replies: []});
        });
        const annotations = [];
        model.comments.forEach((comment) => {
            if (comment.inReplyTo === undefined) annotations.push(threads.get(comment.id));
            else if (threads.has(comment.inReplyTo)) threads.get(comment.inReplyTo).replies.push(threads.get(comment.id));
            else fail(`the reply ${comment.id} answers no comment of the island`);
        });
        let reached = 0;
        const count = (node) => { reached += 1; node.replies.forEach(count); };
        annotations.forEach(count);
        if (reached !== threads.size) fail("the comment island holds a chain of replies that reaches no root");
        model.decisions.forEach((decision) => {
            if (!decision || typeof decision.id !== "string" || typeof decision.reviewer !== "string" ||
                    !decision.target || !["accepted", "rejected"].includes(decision.state)) {
                fail("the comment island holds an invalid decision");
            }
        });
        const states = model.states || [];
        if (!Array.isArray(states) || states.some((entry) => !entry || typeof entry.id !== "string" ||
                !threads.has(entry.target) || !["open", "resolved"].includes(entry.state))) {
            fail("the comment island holds an invalid state entry");
        }
        return {files: [...(model.files || [])], names: [...(model.names || [])], annotations,
            decisions: model.decisions.map((decision) => mapTargets(decision, fromTarget)),
            states: states.map((entry) => ({...entry}))};
    };

    const toCore = (data) => {
        const comments = [];
        const flatten = (node, answered) => {
            const {replies, mediaType, text, ...rest} = mapTargets(node, toTarget);
            comments.push({...rest, body: {mediaType, text}, ...(answered === undefined ? {} : {inReplyTo: answered})});
            replies.forEach((reply) => flatten(reply, node.id));
        };
        data.annotations.forEach((annotation) => flatten(annotation));
        return {version: VERSION, files: [...data.files], ...(data.names.length ? {names: [...data.names]} : {}),
            comments: comments.sort(order),
            decisions: data.decisions.map((decision) => mapTargets(decision, toTarget)).sort(order),
            states: data.states.map((entry) => ({...entry})).sort(order)};
    };

    // A target's review state: the reviewer's decision on it, or without one the aggregate. Its owner
    // is obs.comments.review_state; this mirrors it, and the shared fixture
    // test/fixtures/review-state-conformance.json holds the two together.
    const reviewState = (decisions, target, reviewer) => {
        const states = new Set(decisions.filter((decision) => sameTarget(decision.target, target) &&
            (reviewer === undefined || reviewer === null || decision.reviewer === reviewer))
            .map((decision) => decision.state));
        return ["rejected", "accepted"].find((state) => states.has(state)) || "waiting";
    };

    // A comment's state: its latest state entry's, of one time the one whose author, then id, sorts
    // first; without one the state it was created with. Its owner is obs.comments.comment_state, and
    // the same shared fixture holds the two together.
    const commentState = (comment, states) => {
        const entries = states.filter((entry) => entry.target === comment.id);
        if (!entries.length) return comment.state;
        const latest = Math.max(...entries.map((entry) => Date.parse(entry.created)));
        return entries.filter((entry) => Date.parse(entry.created) === latest)
            .sort((first, second) => compare(first.author, second.author) || compare(first.id, second.id))[0].state;
    };

    globalThis.obsCommentModel = {VERSION, fromCore, toCore, reviewState, commentState, sameTarget};
})();
