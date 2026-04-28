"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { use } from "react";

import { Button } from "@/components/ui/button";
import { ExportButton } from "@/features/export/components/ExportButton";
import { useRealtimeInvalidation } from "@/features/realtime/hooks/useRealtimeInvalidation";
import { ReviewTimeline } from "@/features/review/components/ReviewTimeline";
import { VideoPlayer } from "@/features/review/components/VideoPlayer";
import { SessionStatusBadge } from "@/features/sessions/components/SessionStatusBadge";
import { useSessionQuery } from "@/features/sessions/hooks/useSessionQuery";
import { useStartProcessingMutation } from "@/features/sessions/hooks/useStartProcessingMutation";
import { ShotSidebarItem } from "@/features/shots/components/ShotSidebarItem";
import { useAddManualShotMutation } from "@/features/shots/hooks/useAddManualShotMutation";

export default function SessionDetailPage({
  params,
}: {
  params: Promise<{ id: string; locale: string }>;
}) {
  const { id } = use(params);
  const t = useTranslations("review");
  const qc = useQueryClient();
  const { data, isLoading } = useSessionQuery(id);
  const add = useAddManualShotMutation();
  const startProcessing = useStartProcessingMutation();
  useRealtimeInvalidation(id);

  if (isLoading || !data) {
    return <p className="text-sm text-zinc-600">…</p>;
  }

  const { session, shots } = data;
  const processingDisabled =
    startProcessing.isPending || session.status === "processing";

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <div className="flex items-center gap-2">
            <SessionStatusBadge status={session.status} />
            <Button
              variant="outline"
              disabled={processingDisabled}
              onClick={() => startProcessing.mutate(id)}
            >
              {startProcessing.isPending ? "…" : t("process")}
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                qc.invalidateQueries({ queryKey: ["sessions", id] });
              }}
            >
              {t("refresh")}
            </Button>
          </div>
        </div>
        <VideoPlayer src={null /* signed GET URL retrieval is Plan 6 */} />
        <ReviewTimeline
          shots={shots}
          duration={session.durationSeconds || 60}
        />
        <ExportButton sessionId={id} disabled={session.status !== "ready"} />
      </div>
      <aside className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">Shots</h2>
          <Button
            variant="outline"
            disabled={add.isPending || session.status !== "ready"}
            onClick={() => {
              const last = shots[shots.length - 1];
              const t_impact = (last ? last.tEnd : 0) + 5;
              add.mutate({
                sessionId: id,
                tImpact: t_impact,
                tStart: Math.max(0, t_impact - 2),
                tEnd: t_impact + 5,
              });
            }}
          >
            {t("addShot")}
          </Button>
        </div>
        {shots.length === 0 ? (
          <p className="text-sm text-zinc-600">{t("noShots")}</p>
        ) : (
          shots.map((s) => (
            <ShotSidebarItem key={s.id} shot={s} sessionId={id} />
          ))
        )}
      </aside>
    </div>
  );
}
