"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { useExportMutation } from "../hooks/useExportMutation";

export function ExportButton({
  sessionId,
  disabled,
}: {
  sessionId: string;
  disabled?: boolean;
}) {
  const t = useTranslations("review");
  const { mutate, isPending, data } = useExportMutation();

  if (data?.signedDownloadUrl) {
    return (
      <a
        href={data.signedDownloadUrl}
        className="inline-flex h-10 items-center justify-center rounded-md border border-zinc-300 bg-white px-4 text-sm font-medium hover:bg-zinc-50"
        download
      >
        ⬇ {t("export")}
      </a>
    );
  }

  return (
    <Button disabled={disabled || isPending} onClick={() => mutate(sessionId)}>
      {isPending ? "…" : t("export")}
    </Button>
  );
}
