// Content Security Policy for the workbench's pages, following the Next.js guide "How to set a Content Security
// Policy (CSP) for your Next.js application" (nonces, through Proxy). Next.js reads the nonce from the request's
// CSP header and applies it to its own scripts, so no script runs inline without it.

import { randomBytes } from "node:crypto";

export function newNonce(): string {
  return randomBytes(16).toString("base64");
}

export function contentSecurityPolicy(nonce: string, development: boolean): string {
  return [
    "default-src 'self'",
    // React needs eval in development only, for its error overlays.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
}
