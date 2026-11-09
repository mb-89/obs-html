// The one mapping between the core's comments (obs input-model, Comments and reviews) and the threads
// the Comments bar shows (spec/input-model.md, Comments and the core model). A thread is a root
// comment with its replies nested by inReplyTo, its body as text and mediaType, its state as status;
// a decision is the core's decision as it is, and a target the core's target.
(() => {
    "use strict";

    const VERSION = 1;
    const fail = (message) => { throw new Error(message); };
    const canonical = (target) => JSON.stringify(Object.keys(target).sort().map((key) => [key, target[key]]));
    const sameTarget = (first, second) => canonical(first) === canonical(second);
    const order = (first, second) => Date.parse(first.created) - Date.parse(second.created) ||
        (first.id < second.id ? -1 : first.id > second.id ? 1 : 0);

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
            const {body, state, inReplyTo: _answered, ...rest} = comment;
            threads.set(comment.id, {...rest, mediaType: body.mediaType, text: body.text, status: state, replies: []});
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
        return {files: [...(model.files || [])], annotations, decisions: model.decisions.map((decision) => ({...decision}))};
    };

    const toCore = (data) => {
        const comments = [];
        const flatten = (node, answered) => {
            const {replies, mediaType, text, status, ...rest} = node;
            comments.push({...rest, body: {mediaType, text}, state: status,
                ...(answered === undefined ? {} : {inReplyTo: answered})});
            replies.forEach((reply) => flatten(reply, node.id));
        };
        data.annotations.forEach((annotation) => flatten(annotation));
        return {version: VERSION, files: [...data.files], comments: comments.sort(order),
            decisions: data.decisions.map((decision) => ({...decision})).sort(order)};
    };

    // A target's review state: the reviewer's decision on it, or without one the aggregate, as
    // obs.comments.review_state computes it; the shared conformance fixture holds the two together.
    const reviewState = (decisions, target, reviewer) => {
        const states = new Set(decisions.filter((decision) => sameTarget(decision.target, target) &&
            (reviewer === undefined || reviewer === null || decision.reviewer === reviewer))
            .map((decision) => decision.state));
        return ["rejected", "accepted"].find((state) => states.has(state)) || "waiting";
    };

    globalThis.obsCommentModel = {VERSION, fromCore, toCore, reviewState, sameTarget};
})();
