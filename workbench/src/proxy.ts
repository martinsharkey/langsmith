// Next.js Proxy (formerly middleware): a fresh CSP nonce for every page request. Next.js reads the nonce from the
// request's Content-Security-Policy header while rendering and adds it to its scripts. Pages are rendered per request
// (`dynamic = "force-dynamic"`), which nonces require.

import { type NextRequest, NextResponse } from "next/server";

import { contentSecurityPolicy, newNonce } from "./lib/csp.ts";

export function proxy(request: NextRequest) {
  const policy = contentSecurityPolicy(newNonce(), process.env.NODE_ENV === "development");
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("Content-Security-Policy", policy);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", policy);
  return response;
}

export const config = {
  matcher: [
    // Pages only: API routes (including the streaming agent proxy) and static assets are left alone.
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
