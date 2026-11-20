import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { loadConfig } from "@/lib/config.ts";
import { logoutUrl } from "@/lib/oidc.ts";
import { isSameOrigin } from "@/lib/proxy-rules.ts";
import { SESSION_COOKIE, deleteSession } from "@/lib/session.ts";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const cfg = loadConfig();
  if (!isSameOrigin("POST", request.headers.get("origin"), cfg.publicUrl)) {
    return new NextResponse("Forbidden", { status: 403 });
  }
  const jar = await cookies();
  const session = deleteSession(jar.get(SESSION_COOKIE)?.value);
  jar.delete(SESSION_COOKIE);
  return NextResponse.redirect(await logoutUrl(session?.idToken), { status: 303 });
}
