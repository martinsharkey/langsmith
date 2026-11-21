import assert from "node:assert/strict";
import { test } from "node:test";

import { isNotification } from "./messages.ts";

test("a message the user typed is shown even if it mentions task notifications", () => {
  assert.equal(isNotification({ content: "What does <task-notification> mean?", additional_kwargs: {} }), false);
  assert.equal(isNotification({ content: [{ type: "text", text: "<task-notification>" }] }), false);
});

test("a background task's report is recognised by its notification metadata", () => {
  // langchain-core's add_notification_metadata, as Deep Agents uses it for async subagent updates.
  assert.equal(isNotification({ content: "x", additional_kwargs: { lc_source: "async_subagent", lc_data: {} } }), true);
  // The older Deep Agents key, which it still writes.
  assert.equal(isNotification({ content: "x", additional_kwargs: { deepagents_notification: { task_id: "t" } } }), true);
});
