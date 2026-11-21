import assert from "node:assert/strict";
import { mock, test } from "node:test";

// openid-client is replaced, so no identity provider is needed: discovery returns a stand-in configuration and the
// grants are counted.
let refreshCalls = 0;
let refreshResult: () => Promise<unknown> = async () => ({});
const revoked: { token: string; hint?: string }[] = [];

mock.module("openid-client", {
  namedExports: {
    discovery: async () => ({ stand_in: true }),
    allowInsecureRequests: () => undefined,
    refreshTokenGrant: async () => {
      refreshCalls += 1;
      return refreshResult();
    },
    tokenRevocation: async (_config: unknown, token: string, parameters?: Record<string, string>) => {
      revoked.push({ token, hint: parameters?.token_type_hint });
    },
  },
});

process.env.AGENT_SERVER_URL = "http://agent.test";
process.env.WORKBENCH_PUBLIC_URL = "https://workbench.test";
process.env.OIDC_ISSUER = "https://idp.test/realms/test";
process.env.OIDC_CLIENT_SECRET = "test-only";

const { accessTokenFor, revokeTokens } = await import("./oidc.ts");
const { createSession, getSession, now } = await import("./session.ts");

function expiringSession() {
  return createSession({
    userId: "u",
    userName: "user",
    accessToken: "old-access",
    refreshToken: "old-refresh",
    accessTokenExpiresAt: now() + 5,
    expiresAt: now() + 3600,
  });
}

test("concurrent requests on one session share a single token refresh", async () => {
  refreshCalls = 0;
  refreshResult = async () => {
    await new Promise((resolve) => setTimeout(resolve, 20));
    return { access_token: "new-access", refresh_token: "new-refresh", expiresIn: () => 300 };
  };
  const id = expiringSession();
  const tokens = await Promise.all([accessTokenFor(id), accessTokenFor(id), accessTokenFor(id)]);
  assert.deepEqual(tokens, ["new-access", "new-access", "new-access"]);
  assert.equal(refreshCalls, 1);
  assert.equal(getSession(id)?.refreshToken, "new-refresh");
  assert.equal(await accessTokenFor(id), "new-access");
  assert.equal(refreshCalls, 1, "a fresh token is used without refreshing again");
});

test("a failed refresh signs the session out for every waiting request, and a later request may retry", async () => {
  refreshCalls = 0;
  refreshResult = async () => {
    throw new Error("invalid_grant");
  };
  const id = expiringSession();
  assert.deepEqual(await Promise.all([accessTokenFor(id), accessTokenFor(id)]), [undefined, undefined]);
  assert.equal(refreshCalls, 1);
  await accessTokenFor(id);
  assert.equal(refreshCalls, 2);
});

test("signing out revokes the refresh token at the identity provider", async () => {
  revoked.length = 0;
  await revokeTokens({ refreshToken: "to-revoke" });
  assert.deepEqual(revoked, [{ token: "to-revoke", hint: "refresh_token" }]);
  await revokeTokens(undefined);
  assert.equal(revoked.length, 1);
});
