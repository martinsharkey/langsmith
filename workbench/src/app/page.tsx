import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { Workbench } from "@/components/Workbench.tsx";
import { loadConfig } from "@/lib/config.ts";
import { SESSION_COOKIE, getSession } from "@/lib/session.ts";

export const dynamic = "force-dynamic";

export default async function Page() {
  const session = getSession((await cookies()).get(SESSION_COOKIE)?.value);
  if (!session) redirect("/api/auth/login");
  return <Workbench userName={session.userName} assistantId={loadConfig().assistantId} />;
}
