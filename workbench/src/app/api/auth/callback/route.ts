import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { loadConfig } from "@/lib/config.ts";
import { type LoginState, completeLogin } from "@/lib/oidc.ts";
import { LOGIN_COOKIE, SESSION_COOKIE, cookieOptions, createSession } from "@/lib/session.ts";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const cfg = loadConfig();
  const jar = await cookies();
  const raw = jar.get(LOGIN_COOKIE)?.value;
  jar.delete(LOGIN_COOKIE);
  if (!raw) return NextResponse.redirect(`${cfg.publicUrl}/api/auth/login`);
  try {
    const login = JSON.parse(raw) as LoginState;
    // Rebuild the callback URL on the public origin: behind a gateway the request's own host is internal.
    const incoming = new URL(request.url);
    const current = new URL(`${cfg.publicUrl}/api/auth/callback${incoming.search}`);
    const session = await completeLogin(current, login);
    jar.set(SESSION_COOKIE, createSession(session), cookieOptions(cfg.publicUrl, cfg.sessionTtlSeconds));
    return NextResponse.redirect(cfg.publicUrl);
  } catch {
    return new NextResponse("Sign-in failed. Close this tab and try again.", { status: 401 });
  }
}
