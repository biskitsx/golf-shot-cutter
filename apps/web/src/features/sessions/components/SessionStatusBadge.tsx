"use client";

import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";

const palette: Record<string, string> = {
  uploading: "bg-zinc-200 text-zinc-700",
  queued: "bg-amber-100 text-amber-800",
  processing: "bg-blue-100 text-blue-800",
  ready: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
};

export function SessionStatusBadge({ status }: { status: string }) {
  const t = useTranslations("sessions");
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
        palette[status] ?? "bg-zinc-100 text-zinc-700",
      )}
    >
      {t(status as never)}
    </span>
  );
}
