import assert from "node:assert/strict";
import { test } from "node:test";

import { contentSecurityPolicy, newNonce } from "./csp.ts";

function directive(policy: string, name: string): string {
  return policy.split(";").map((d) => d.trim()).find((d) => d.startsWith(`${name} `)) ?? "";
}

test("scripts run only with the request's nonce, never inline", () => {
  const policy = contentSecurityPolicy("abc123", false);
  const scripts = directive(policy, "script-src");
  assert.match(scripts, /'nonce-abc123'/);
  assert.match(scripts, /'strict-dynamic'/);
  assert.doesNotMatch(scripts, /unsafe-inline|unsafe-eval/);
  assert.equal(directive(policy, "frame-ancestors"), "frame-ancestors 'none'");
  assert.equal(directive(policy, "object-src"), "object-src 'none'");
});

test("eval is allowed only in development, where React needs it", () => {
  assert.match(directive(contentSecurityPolicy("n", true), "script-src"), /'unsafe-eval'/);
});

test("every request gets a different nonce", () => {
  assert.notEqual(newNonce(), newNonce());
  assert.ok(newNonce().length >= 22);
});
