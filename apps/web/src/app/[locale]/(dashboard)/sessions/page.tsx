"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { SessionCard } from "@/features/sessions/components/SessionCard";
import { useSessionsQuery } from "@/features/sessions/hooks/useSessionsQuery";

export default function SessionsPage() {
  const t = useTranslations();
  const { data, isLoading } = useSessionsQuery();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("sessions.title")}</h1>
        <Link href="/upload">
          <Button>{t("sessions.newSession")}</Button>
        </Link>
      </div>
      {isLoading && (
        <p className="text-sm text-zinc-600">{t("common.loading")}</p>
      )}
      {data && data.length === 0 && (
        <p className="text-sm text-zinc-600">{t("sessions.empty")}</p>
      )}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {data?.map((s) => (
          <SessionCard key={s.id} session={s} />
        ))}
      </div>
    </div>
  );
}
