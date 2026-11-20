import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { loadConfig } from "@/lib/config.ts";
import { beginLogin } from "@/lib/oidc.ts";
import { LOGIN_COOKIE, cookieOptions } from "@/lib/session.ts";

export const dynamic = "force-dynamic";

export async function GET() {
  const { url, login } = await beginLogin();
  const jar = await cookies();
  jar.set(LOGIN_COOKIE, JSON.stringify(login), cookieOptions(loadConfig().publicUrl, 600));
  return NextResponse.redirect(url);
}
