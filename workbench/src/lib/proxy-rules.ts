// Pure rules for the Agent Server proxy, kept separate so they can be unit-tested without Next.js.

/** Agent Server paths the browser may reach through the workbench. Everything else is refused. */
const ALLOWED_PREFIXES = ["threads", "runs", "assistants", "info", "store"];

export function isAllowedPath(segments: string[]): boolean {
  if (segments.length === 0) return false;
  if (segments.some((s) => s === "" || s === "." || s === ".." || s.includes("/") || s.includes("\\"))) return false;
  return ALLOWED_PREFIXES.includes(segments[0]);
}

/** A state-changing request must come from the workbench's own origin (CSRF defence). */
export function isSameOrigin(method: string, originHeader: string | null, publicUrl: string): boolean {
  if (method === "GET" || method === "HEAD") return true;
  if (!originHeader) return false;
  try {
    return new URL(originHeader).origin === new URL(publicUrl).origin;
  } catch {
    return false;
  }
}

/** Request headers forwarded to Agent Server. Cookies and any caller-supplied Authorization are never forwarded. */
const FORWARDED_REQUEST_HEADERS = ["accept", "content-type", "last-event-id", "cache-control"];

export function forwardHeaders(incoming: Headers, accessToken: string): Headers {
  const out = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = incoming.get(name);
    if (value) out.set(name, value);
  }
  out.set("authorization", `Bearer ${accessToken}`);
  return out;
}

const RETURNED_RESPONSE_HEADERS = ["content-type", "cache-control", "content-location", "location"];

export function responseHeaders(upstream: Headers): Headers {
  const out = new Headers();
  for (const name of RETURNED_RESPONSE_HEADERS) {
    const value = upstream.get(name);
    if (value) out.set(name, value);
  }
  out.set("x-accel-buffering", "no");
  return out;
}
