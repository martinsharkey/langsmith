// OpenID Connect against Keycloak with the certified `openid-client` library: authorization code flow with a
// confidential client and PKCE, performed entirely on the server.

import * as client from "openid-client";

import { loadConfig } from "./config.ts";
import { type Session, getSession, now, updateSession } from "./session.ts";

let cached: Promise<client.Configuration> | undefined;

export function oidc(): Promise<client.Configuration> {
  if (!cached) {
    const cfg = loadConfig();
    const issuer = new URL(cfg.oidcIssuer);
    // Plain HTTP is accepted only for a local issuer during development and tests.
    const local = issuer.protocol === "http:" && ["localhost", "127.0.0.1"].includes(issuer.hostname);
    cached = client
      .discovery(issuer, cfg.oidcClientId, cfg.oidcClientSecret, undefined, local ? { execute: [client.allowInsecureRequests] } : undefined)
      .catch((error) => {
        cached = undefined;
        throw error;
      });
  }
  return cached;
}

export function redirectUri(): string {
  return `${loadConfig().publicUrl}/api/auth/callback`;
}

export interface LoginState {
  state: string;
  codeVerifier: string;
}

export async function beginLogin(): Promise<{ url: URL; login: LoginState }> {
  const config = await oidc();
  const codeVerifier = client.randomPKCECodeVerifier();
  const state = client.randomState();
  const url = client.buildAuthorizationUrl(config, {
    redirect_uri: redirectUri(),
    scope: "openid profile email",
    code_challenge: await client.calculatePKCECodeChallenge(codeVerifier),
    code_challenge_method: "S256",
    state,
  });
  return { url, login: { state, codeVerifier } };
}

export async function completeLogin(currentUrl: URL, login: LoginState): Promise<Session> {
  const config = await oidc();
  const tokens = await client.authorizationCodeGrant(config, currentUrl, {
    pkceCodeVerifier: login.codeVerifier,
    expectedState: login.state,
  });
  const claims = tokens.claims();
  if (!claims?.sub) throw new Error("ID token has no subject");
  const cfg = loadConfig();
  return {
    userId: claims.sub,
    userName: String(claims.preferred_username ?? claims.name ?? claims.sub),
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    idToken: tokens.id_token,
    accessTokenExpiresAt: now() + (tokens.expiresIn() ?? 60),
    expiresAt: now() + cfg.sessionTtlSeconds,
  };
}

// At most one refresh in flight per session. The browser sends parallel requests (stream, state, polling); with
// refresh-token rotation, a second refresh with the same refresh token would fail and sign the user out.
const globalRefreshes = globalThis as unknown as { __wbRefreshes?: Map<string, Promise<string | undefined>> };
const refreshes: Map<string, Promise<string | undefined>> = (globalRefreshes.__wbRefreshes ??= new Map());

async function refresh(sessionId: string, refreshToken: string): Promise<string | undefined> {
  try {
    const tokens = await client.refreshTokenGrant(await oidc(), refreshToken);
    updateSession(sessionId, {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token ?? refreshToken,
      accessTokenExpiresAt: now() + (tokens.expiresIn() ?? 60),
    });
    return tokens.access_token;
  } catch {
    return undefined;
  }
}

/** Returns a valid access token for the session, refreshing it when it is about to expire. */
export async function accessTokenFor(sessionId: string): Promise<string | undefined> {
  const session = getSession(sessionId);
  if (!session) return undefined;
  if (session.accessTokenExpiresAt - now() > 30) return session.accessToken;
  if (!session.refreshToken) return undefined;
  let pending = refreshes.get(sessionId);
  if (!pending) {
    pending = refresh(sessionId, session.refreshToken).finally(() => refreshes.delete(sessionId));
    refreshes.set(sessionId, pending);
  }
  return pending;
}

/** Revokes the session's refresh token at Keycloak on sign-out (RFC 7009), so it cannot be used again. */
export async function revokeTokens(session: Pick<Session, "refreshToken"> | undefined): Promise<void> {
  if (!session?.refreshToken) return;
  try {
    await client.tokenRevocation(await oidc(), session.refreshToken, { token_type_hint: "refresh_token" });
  } catch (error) {
    // Sign-out continues; the token still expires with the Keycloak session.
    console.warn("Refresh token revocation failed", error instanceof Error ? error.message : error);
  }
}

export async function logoutUrl(idToken: string | undefined): Promise<URL> {
  const cfg = loadConfig();
  const config = await oidc();
  return client.buildEndSessionUrl(config, {
    post_logout_redirect_uri: cfg.publicUrl,
    ...(idToken ? { id_token_hint: idToken } : {}),
  });
}
