import assert from "node:assert/strict";
import { test } from "node:test";

import { forwardHeaders, isAllowedPath, isSameOrigin, responseHeaders } from "./proxy-rules.ts";

test("only Agent Server resource paths are proxied", () => {
  assert.equal(isAllowedPath(["threads", "abc", "runs", "stream"]), true);
  assert.equal(isAllowedPath(["assistants", "search"]), true);
  assert.equal(isAllowedPath([]), false);
  assert.equal(isAllowedPath(["metrics"]), false);
  assert.equal(isAllowedPath(["threads", "..", "internal"]), false);
  assert.equal(isAllowedPath(["mcp"]), false);
});

test("state-changing requests must come from the workbench origin", () => {
  const self = "https://workbench.site.example";
  assert.equal(isSameOrigin("GET", null, self), true);
  assert.equal(isSameOrigin("POST", self, self), true);
  assert.equal(isSameOrigin("POST", null, self), false);
  assert.equal(isSameOrigin("POST", "https://evil.example", self), false);
  assert.equal(isSameOrigin("DELETE", "not a url", self), false);
});

test("cookies and caller authorization are never forwarded", () => {
  const incoming = new Headers({
    cookie: "wb_session=secret",
    authorization: "Bearer attacker",
    "content-type": "application/json",
    "x-forwarded-for": "10.0.0.1",
  });
  const out = forwardHeaders(incoming, "user-token");
  assert.equal(out.get("authorization"), "Bearer user-token");
  assert.equal(out.get("cookie"), null);
  assert.equal(out.get("x-forwarded-for"), null);
  assert.equal(out.get("content-type"), "application/json");
});

const AGENT = "http://agent-server.internal:2024";

test("upstream set-cookie is not returned to the browser", () => {
  const out = responseHeaders(new Headers({ "set-cookie": "a=b", "content-type": "text/event-stream" }), AGENT);
  assert.equal(out.get("set-cookie"), null);
  assert.equal(out.get("content-type"), "text/event-stream");
});

test("the internal Agent Server address never reaches the browser", () => {
  const out = responseHeaders(
    new Headers({
      "content-location": `${AGENT}/threads/t1/runs/r1`,
      location: `${AGENT}/threads/t1/runs/r1?x=1`,
    }),
    AGENT,
  );
  // Content-Location stays a path on Agent Server's API, which the SDK resolves against its own base (/api/agent).
  assert.equal(out.get("content-location"), "/threads/t1/runs/r1");
  // Location is followed by the browser, so it points at the workbench's proxy route.
  assert.equal(out.get("location"), "/api/agent/threads/t1/runs/r1?x=1");
  for (const value of [...out.values()]) assert.doesNotMatch(value, /agent-server\.internal/);
});

test("relative locations are kept and locations on another host are dropped", () => {
  const relative = responseHeaders(new Headers({ "content-location": "/threads/t1/runs/r1" }), AGENT);
  assert.equal(relative.get("content-location"), "/threads/t1/runs/r1");
  const elsewhere = responseHeaders(new Headers({ location: "https://elsewhere.example/x" }), AGENT);
  assert.equal(elsewhere.get("location"), null);
});
