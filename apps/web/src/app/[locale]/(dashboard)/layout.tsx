import type { ReactNode } from "react";

import { SiteHeader } from "@/components/site-header";
import { AuthGate } from "@/features/auth/components/AuthGate";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate>
      <div className="min-h-screen bg-zinc-50">
        <SiteHeader />
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      </div>
    </AuthGate>
  );
}
