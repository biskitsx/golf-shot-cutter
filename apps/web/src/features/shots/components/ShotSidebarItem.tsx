"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatSeconds } from "@/lib/utils";
import type { ShotDto } from "@golf/contracts";

import { useDeleteShotMutation } from "../hooks/useDeleteShotMutation";
import { useUpdateShotBoundaryMutation } from "../hooks/useUpdateShotBoundaryMutation";

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
      <div className="flex gap-2">
        <Button
          className="flex-1"
          variant="outline"
          disabled={
            (tStart === shot.tStart && tEnd === shot.tEnd) || update.isPending
          }
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
