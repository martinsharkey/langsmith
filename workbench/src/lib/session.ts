// Server-side sessions. The browser holds only an opaque, random session id in an HttpOnly cookie; tokens stay on
// the server (AD-55). This in-memory store suits one replica. For more than one replica, back it with Valkey
// (docs/status.md).

import { randomBytes } from "node:crypto";

export const SESSION_COOKIE = "wb_session";
export const LOGIN_COOKIE = "wb_login";

export interface Session {
  userId: string;
  userName: string;
  accessToken: string;
  refreshToken?: string;
  idToken?: string;
  accessTokenExpiresAt: number; // epoch seconds
  expiresAt: number; // epoch seconds
}

const globalStore = globalThis as unknown as { __wbSessions?: Map<string, Session> };
const sessions: Map<string, Session> = (globalStore.__wbSessions ??= new Map());

export function now(): number {
  return Math.floor(Date.now() / 1000);
}

export function createSession(session: Session): string {
  const id = randomBytes(32).toString("base64url");
  sessions.set(id, session);
  return id;
}

export function getSession(id: string | undefined): Session | undefined {
  if (!id) return undefined;
  const session = sessions.get(id);
  if (!session) return undefined;
  if (session.expiresAt <= now()) {
    sessions.delete(id);
    return undefined;
  }
  return session;
}

/** Removes every expired session, with its tokens, whether or not it is read again. Returns how many it removed. */
export function sweepExpiredSessions(): number {
  const cutoff = now();
  let removed = 0;
  for (const [id, session] of sessions) {
    if (session.expiresAt <= cutoff) {
      sessions.delete(id);
      removed += 1;
    }
  }
  return removed;
}

// One sweep timer per process. `unref` lets the process exit without waiting for it.
const SWEEP_INTERVAL_MS = 60_000;
const sweeper = globalThis as unknown as { __wbSessionSweep?: ReturnType<typeof setInterval> };
sweeper.__wbSessionSweep ??= setInterval(sweepExpiredSessions, SWEEP_INTERVAL_MS);
sweeper.__wbSessionSweep.unref?.();

export function updateSession(id: string, patch: Partial<Session>): void {
  const session = sessions.get(id);
  if (session) sessions.set(id, { ...session, ...patch });
}

export function deleteSession(id: string | undefined): Session | undefined {
  if (!id) return undefined;
  const session = sessions.get(id);
  sessions.delete(id);
  return session;
}

export function cookieOptions(publicUrl: string, maxAgeSeconds: number) {
  return {
    httpOnly: true,
    secure: publicUrl.startsWith("https://"),
    sameSite: "lax" as const,
    path: "/",
    maxAge: maxAgeSeconds,
  };
}
