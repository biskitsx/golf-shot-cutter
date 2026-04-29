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
import { useRawVideoUrlQuery } from "@/features/sessions/hooks/useRawVideoUrlQuery";
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
  const rawUrl = useRawVideoUrlQuery(id);
  const add = useAddManualShotMutation();
  const startProcessing = useStartProcessingMutation();
  useRealtimeInvalidation(id);

  if (isLoading || !data) {
    return <p className="text-sm text-muted-foreground">…</p>;
  }

  const { session, shots } = data;
  const processingDisabled =
    startProcessing.isPending || session.status === "processing";

  return (
    <div className="space-y-6">
      {/* Header */}
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

      {/* Main video + timeline */}
      <div className="space-y-4">
        <VideoPlayer src={rawUrl.data?.url ?? null} />
        <ReviewTimeline
          shots={shots}
          duration={session.durationSeconds || 60}
        />
        <ExportButton sessionId={id} disabled={session.status !== "ready"} />
      </div>

      {/* Shots grid */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            Shots{" "}
            <span className="text-sm font-normal text-muted-foreground">
              ({shots.length})
            </span>
          </h2>
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
          <p className="text-sm text-muted-foreground">{t("noShots")}</p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {shots.map((s) => (
              <ShotSidebarItem key={s.id} shot={s} sessionId={id} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
