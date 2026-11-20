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

test("upstream set-cookie is not returned to the browser", () => {
  const out = responseHeaders(new Headers({ "set-cookie": "a=b", "content-type": "text/event-stream" }));
  assert.equal(out.get("set-cookie"), null);
  assert.equal(out.get("content-type"), "text/event-stream");
});
