import assert from "node:assert/strict";
import { test } from "node:test";

import { createSession, getSession, now, sweepExpiredSessions } from "./session.ts";

function session(expiresAt: number) {
  return { userId: "u", userName: "user", accessToken: "a", refreshToken: "r", accessTokenExpiresAt: now() + 300, expiresAt };
}

test("the sweep removes expired sessions that are never read again, and keeps live ones", () => {
  sweepExpiredSessions();
  const expired = createSession(session(now() - 1));
  const live = createSession(session(now() + 600));
  assert.equal(sweepExpiredSessions(), 1);
  assert.equal(sweepExpiredSessions(), 0);
  assert.equal(getSession(expired), undefined);
  assert.ok(getSession(live));
});
