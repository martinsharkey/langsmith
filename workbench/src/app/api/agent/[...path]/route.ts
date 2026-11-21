// Back end for front end (AD-55): the browser talks only to this route. It checks the session, attaches the user's
// access token and forwards to Agent Server, which validates the token again with its own custom auth (AD-57).

import { cookies } from "next/headers";

import { loadConfig } from "@/lib/config.ts";
import { accessTokenFor } from "@/lib/oidc.ts";
import { forwardHeaders, isAllowedPath, isSameOrigin, responseHeaders } from "@/lib/proxy-rules.ts";
import { SESSION_COOKIE } from "@/lib/session.ts";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type Context = { params: Promise<{ path: string[] }> };

async function handle(request: Request, context: Context): Promise<Response> {
  const cfg = loadConfig();
  const { path } = await context.params;
  if (!isAllowedPath(path)) return new Response("Not found", { status: 404 });
  if (!isSameOrigin(request.method, request.headers.get("origin"), cfg.publicUrl)) {
    return new Response("Forbidden", { status: 403 });
  }
  const sessionId = (await cookies()).get(SESSION_COOKIE)?.value;
  const token = sessionId ? await accessTokenFor(sessionId) : undefined;
  if (!token) return new Response("Sign-in required", { status: 401 });

  const target = new URL(`${cfg.agentServerUrl}/${path.map(encodeURIComponent).join("/")}`);
  target.search = new URL(request.url).search;
  const hasBody = !["GET", "HEAD"].includes(request.method);
  const upstream = await fetch(target, {
    method: request.method,
    headers: forwardHeaders(request.headers, token),
    body: hasBody ? request.body : undefined,
    // @ts-expect-error duplex is required by Node's fetch to stream a request body
    duplex: hasBody ? "half" : undefined,
    signal: request.signal,
    redirect: "manual",
    cache: "no-store",
  });
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders(upstream.headers, cfg.agentServerUrl) });
}

export { handle as GET, handle as POST, handle as PUT, handle as PATCH, handle as DELETE };
