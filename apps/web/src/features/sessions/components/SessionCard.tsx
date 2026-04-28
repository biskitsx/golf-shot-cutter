"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";

import { Card } from "@/components/ui/card";
import type { SessionDto } from "@golf/contracts";

import { SessionStatusBadge } from "./SessionStatusBadge";

export function SessionCard({ session }: { session: SessionDto }) {
  const t = useTranslations("sessions");
  return (
    <Link href={`/sessions/${session.id}`} className="block">
      <Card className="p-4 hover:shadow-md">
        <div className="flex items-center justify-between">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">
              {session.rawVideoKey}
            </p>
            <p className="mt-1 text-xs text-zinc-600">
              {t("shotCount", { count: session.shotCount })} ·{" "}
              {new Date(session.createdAt).toLocaleString()}
            </p>
          </div>
          <SessionStatusBadge status={session.status} />
        </div>
      </Card>
    </Link>
  );
}
