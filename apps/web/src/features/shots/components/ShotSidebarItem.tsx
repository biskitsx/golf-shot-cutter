"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatSeconds } from "@/lib/utils";
import type { ShotDto } from "@golf/contracts";

import { useDeleteShotMutation } from "../hooks/useDeleteShotMutation";
import { useUpdateShotBoundaryMutation } from "../hooks/useUpdateShotBoundaryMutation";

interface ApiErrorBody {
  error?: string;
  message?: string;
  detail?: unknown;
}

function readErrorMessage(err: unknown): string | null {
  if (!err || typeof err !== "object") return null;
  // axios-style error
  const e = err as { response?: { data?: ApiErrorBody } };
  const body = e.response?.data;
  if (!body) return null;
  if (typeof body.message === "string" && body.message) return body.message;
  if (typeof body.detail === "string") return body.detail;
  if (typeof body.error === "string") return body.error;
  return null;
}

export function ShotSidebarItem({
  shot,
  sessionId,
}: {
  shot: ShotDto;
  sessionId: string;
}) {
  const t = useTranslations("review");
  const update = useUpdateShotBoundaryMutation();
  const del = useDeleteShotMutation();
  const [tStart, setTStart] = useState(shot.tStart);
  const [tEnd, setTEnd] = useState(shot.tEnd);

  const dirty = tStart !== shot.tStart || tEnd !== shot.tEnd;
  // Domain invariant: t_start < t_impact < t_end. Mirror it client-side so user
  // sees the constraint before hitting the API.
  const localInvalid =
    tStart >= shot.tImpact || tEnd <= shot.tImpact || tEnd <= tStart;
  const serverError = update.isError ? readErrorMessage(update.error) : null;

  return (
    <div className="space-y-2 rounded-md border border-zinc-200 p-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">#{shot.index}</span>
        <span className="text-xs text-zinc-500">{shot.source}</span>
      </div>
      <p className="text-xs text-zinc-600">
        impact: {formatSeconds(shot.tImpact)} · conf:{" "}
        {(shot.confidence * 100).toFixed(0)}%
      </p>
      <div className="grid grid-cols-2 gap-2">
        <Input
          type="number"
          step={0.1}
          value={tStart}
          onChange={(e) => setTStart(Number(e.target.value))}
        />
        <Input
          type="number"
          step={0.1}
          value={tEnd}
          onChange={(e) => setTEnd(Number(e.target.value))}
        />
      </div>
      {(localInvalid || serverError) && (
        <p className="text-xs text-red-600">
          {localInvalid
            ? `tStart < impact (${shot.tImpact}) < tEnd is required`
            : serverError}
        </p>
      )}
      <div className="flex gap-2">
        <Button
          className="flex-1"
          variant="outline"
          disabled={!dirty || localInvalid || update.isPending}
          onClick={() =>
            update.mutate({ sessionId, shotId: shot.id, tStart, tEnd })
          }
        >
          {update.isPending ? "…" : "Save"}
        </Button>
        <Button
          variant="destructive"
          disabled={del.isPending}
          onClick={() => del.mutate({ sessionId, shotId: shot.id })}
        >
          {t("deleteShot")}
        </Button>
      </div>
    </div>
  );
}
