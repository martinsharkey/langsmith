import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

// Every page is rendered per request so it carries that request's CSP nonce (src/proxy.ts), the error pages too.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Innovox Workbench",
  description: "Hand tasks to agents, follow their work and approve their actions.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-GB">
      <body>{children}</body>
    </html>
  );
}
