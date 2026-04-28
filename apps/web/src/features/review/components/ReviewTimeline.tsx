"use client";

import type { ShotDto } from "@golf/contracts";

import { TimelineRuler } from "./TimelineRuler";

export function ReviewTimeline({
  shots,
  duration,
}: {
  shots: ShotDto[];
  duration: number;
}) {
  if (duration <= 0) {
    return <div className="text-sm text-zinc-600">…</div>;
  }
  return (
    <div className="space-y-2">
      <div className="relative h-10 rounded-md bg-zinc-100">
        {shots.map((s) => {
          const left = (s.tStart / duration) * 100;
          const width = ((s.tEnd - s.tStart) / duration) * 100;
          return (
            <div
              key={s.id}
              className="absolute top-1 bottom-1 rounded bg-emerald-500/70"
              style={{ left: `${left}%`, width: `${Math.max(0.5, width)}%` }}
              title={`#${s.index} ${s.tStart.toFixed(1)}–${s.tEnd.toFixed(1)}s`}
            />
          );
        })}
      </div>
      <TimelineRuler duration={duration} />
    </div>
  );
}
