// Server-side configuration. Secrets arrive as environment variables from the deployment, never from the repository.

export interface Config {
  agentServerUrl: string;
  assistantId: string;
  publicUrl: string;
  oidcIssuer: string;
  oidcClientId: string;
  oidcClientSecret: string;
  sessionTtlSeconds: number;
}

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing environment variable ${name}`);
  return value;
}

export function loadConfig(): Config {
  return {
    agentServerUrl: required("AGENT_SERVER_URL").replace(/\/+$/, ""),
    assistantId: process.env.ASSISTANT_ID ?? "agent",
    publicUrl: required("WORKBENCH_PUBLIC_URL").replace(/\/+$/, ""),
    oidcIssuer: required("OIDC_ISSUER").replace(/\/+$/, ""),
    oidcClientId: process.env.OIDC_CLIENT_ID ?? "workbench",
    oidcClientSecret: required("OIDC_CLIENT_SECRET"),
    sessionTtlSeconds: Number(process.env.SESSION_TTL_SECONDS ?? 28800),
  };
}
