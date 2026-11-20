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

/** Returns a valid access token for the session, refreshing it when it is about to expire. */
export async function accessTokenFor(sessionId: string): Promise<string | undefined> {
  const session = getSession(sessionId);
  if (!session) return undefined;
  if (session.accessTokenExpiresAt - now() > 30) return session.accessToken;
  if (!session.refreshToken) return undefined;
  try {
    const tokens = await client.refreshTokenGrant(await oidc(), session.refreshToken);
    updateSession(sessionId, {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token ?? session.refreshToken,
      accessTokenExpiresAt: now() + (tokens.expiresIn() ?? 60),
    });
    return tokens.access_token;
  } catch {
    return undefined;
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
