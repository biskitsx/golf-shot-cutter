"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

import { useExportMutation } from "../hooks/useExportMutation";

interface ApiErrorBody {
  error?: string;
  message?: string;
  detail?: unknown;
}

function readErrorMessage(err: unknown): string | null {
  if (!err || typeof err !== "object") return null;
  const e = err as { response?: { data?: ApiErrorBody; status?: number } };
  const body = e.response?.data;
  if (!body) return null;
  if (typeof body.message === "string" && body.message) return body.message;
  if (typeof body.detail === "string") return body.detail;
  if (typeof body.error === "string") return body.error;
  return null;
}

export function ExportButton({
  sessionId,
  disabled,
}: {
  sessionId: string;
  disabled?: boolean;
}) {
  const t = useTranslations("review");
  const { mutate, isPending, data, error, isError } = useExportMutation();

  return (
    <div className="space-y-2">
      {!data?.signedDownloadUrl && (
        <Button
          disabled={disabled || isPending}
          onClick={() => mutate(sessionId)}
          title={
            disabled ? "Session must be in READY status to export" : undefined
          }
        >
          {isPending ? "Preparing…" : t("export")}
        </Button>
      )}

      {data?.signedDownloadUrl && (
        <div className="flex flex-col gap-1">
          <div className="flex gap-2">
            <a
              href={data.signedDownloadUrl}
              className="inline-flex h-10 items-center justify-center rounded-md border border-zinc-300 bg-white px-4 text-sm font-medium hover:bg-zinc-50"
              download
            >
              ⬇ Download ZIP
            </a>
            <Button
              variant="ghost"
              onClick={() => mutate(sessionId)}
              disabled={isPending}
            >
              {isPending ? "…" : "Re-export"}
            </Button>
          </div>
          <p className="text-xs text-zinc-500">
            ZIP is being assembled by the worker — wait ~5–10s before clicking
            download. If the link 404s, retry in a few seconds.
          </p>
        </div>
      )}

      {isError && (
        <p className="text-xs text-red-600">
          Export request failed: {readErrorMessage(error) ?? "unknown error"}
        </p>
      )}
    </div>
  );
}
