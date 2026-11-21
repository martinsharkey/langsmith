import assert from "node:assert/strict";
import { test } from "node:test";

import { decisionsFor, reviewsOf } from "./decisions.ts";

// The batched interrupt value LangChain's HumanInTheLoopMiddleware raises: one action request per gated call, and
// a review config per tool naming the decisions it allows.
const interrupt = {
  value: {
    action_requests: [
      { name: "publish_document", args: { title: "Alpha", body: "One" } },
      { name: "publish_document", args: { title: "Beta", body: "Two" } },
      { name: "send_notice", args: { to: "team" } },
    ],
    review_configs: [
      { action_name: "publish_document", allowed_decisions: ["approve", "edit", "reject", "respond"] },
      { action_name: "send_notice", allowed_decisions: ["approve", "reject"] },
    ],
  },
};

test("each action request is reviewed on its own, with the decisions its tool allows", () => {
  const reviews = reviewsOf(interrupt);
  assert.equal(reviews.length, 3);
  assert.deepEqual(reviews[1].action.args, { title: "Beta", body: "Two" });
  assert.deepEqual(reviews[0].allowed, ["approve", "edit", "reject"]);
  assert.deepEqual(reviews[2].allowed, ["approve", "reject"]);
  assert.deepEqual(reviewsOf(undefined), []);
});

test("nothing is sent until every action has a decision", () => {
  const reviews = reviewsOf(interrupt);
  assert.equal(decisionsFor(reviews, []), null);
  assert.equal(decisionsFor(reviews, [{ type: "approve" }, undefined, { type: "approve" }]), null);
});

test("decisions are sent in request order, so one action can be approved and another rejected", () => {
  const reviews = reviewsOf(interrupt);
  const decisions = decisionsFor(reviews, [
    { type: "approve" },
    { type: "reject", message: "Not this one" },
    { type: "approve" },
  ]);
  assert.deepEqual(decisions, [
    { type: "approve" },
    { type: "reject", message: "Not this one" },
    { type: "approve" },
  ]);
});

test("an edit sends the changed arguments for the same tool", () => {
  const reviews = reviewsOf(interrupt);
  const decisions = decisionsFor(reviews, [
    { type: "edit", argsText: '{"title": "Alpha (edited)", "body": "One"}' },
    { type: "reject", message: "No" },
    { type: "approve" },
  ]);
  assert.deepEqual(decisions?.[0], {
    type: "edit",
    edited_action: { name: "publish_document", args: { title: "Alpha (edited)", body: "One" } },
  });
});

test("an edit with arguments that are not a JSON object, or on a tool that does not allow edits, is not sent", () => {
  const reviews = reviewsOf(interrupt);
  assert.equal(decisionsFor(reviews, [{ type: "edit", argsText: "not json" }, { type: "approve" }, { type: "approve" }]), null);
  assert.equal(decisionsFor(reviews, [{ type: "edit", argsText: "[1]" }, { type: "approve" }, { type: "approve" }]), null);
  assert.equal(
    decisionsFor(reviews, [{ type: "approve" }, { type: "approve" }, { type: "edit", argsText: '{"to": "all"}' }]),
    null,
  );
});
