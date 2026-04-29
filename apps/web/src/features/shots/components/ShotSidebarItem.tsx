"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ShotWithClip } from "@/features/sessions/hooks/useSessionQuery";
import { formatSeconds } from "@/lib/utils";

import { useDeleteShotMutation } from "../hooks/useDeleteShotMutation";
import { useGetPoseClipMutation } from "../hooks/useGetPoseClipMutation";
import { useUpdateShotBoundaryMutation } from "../hooks/useUpdateShotBoundaryMutation";

interface ApiErrorBody {
  error?: string;
  message?: string;
  detail?: unknown;
}

function readErrorMessage(err: unknown): string | null {
  if (!err || typeof err !== "object") return null;
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
  shot: ShotWithClip;
  sessionId: string;
}) {
  const t = useTranslations("review");
  const update = useUpdateShotBoundaryMutation();
  const del = useDeleteShotMutation();
  const poseClip = useGetPoseClipMutation();
  const [tStart, setTStart] = useState(shot.tStart);
  const [tEnd, setTEnd] = useState(shot.tEnd);
  const [poseUrl, setPoseUrl] = useState<string | null>(null);
  const [showPose, setShowPose] = useState(false);

  const onTogglePose = () => {
    if (showPose) {
      setShowPose(false);
      return;
    }
    if (poseUrl) {
      setShowPose(true);
      return;
    }
    poseClip.mutate(
      { sessionId, shotId: shot.id },
      {
        onSuccess: (url) => {
          setPoseUrl(url);
          setShowPose(true);
        },
      },
    );
  };

  const videoSrc = showPose && poseUrl ? poseUrl : shot.clipUrl;

  const dirty = tStart !== shot.tStart || tEnd !== shot.tEnd;
  const localInvalid =
    tStart >= shot.tImpact || tEnd <= shot.tImpact || tEnd <= tStart;
  const serverError = update.isError ? readErrorMessage(update.error) : null;

  return (
    <div className="space-y-2 rounded-md border bg-card p-3 shadow-sm">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">#{shot.index}</span>
        <span className="text-xs text-muted-foreground">{shot.source}</span>
      </div>

      {videoSrc ? (
        <video
          key={videoSrc}
          src={videoSrc}
          controls
          preload="metadata"
          className="aspect-video w-full rounded-md bg-black"
        >
          <track kind="captions" />
        </video>
      ) : (
        <div className="flex aspect-video w-full items-center justify-center rounded-md bg-muted text-xs text-muted-foreground">
          ยังไม่มีคลิป (clip_key ว่าง)
        </div>
      )}

      {shot.clipUrl && (
        <Button
          variant="secondary"
          size="sm"
          className="w-full"
          disabled={poseClip.isPending}
          onClick={onTogglePose}
        >
          {poseClip.isPending
            ? "กำลังสร้าง pose overlay…"
            : showPose
              ? "ซ่อน pose"
              : poseUrl
                ? "แสดง pose"
                : "แสดง pose (สร้างครั้งแรก)"}
        </Button>
      )}

      <p className="text-xs text-muted-foreground">
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
