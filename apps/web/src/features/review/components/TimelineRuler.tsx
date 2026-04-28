import { formatSeconds } from "@/lib/utils";

export function TimelineRuler({ duration }: { duration: number }) {
  const ticks = Math.max(2, Math.ceil(duration / 30));
  const stops = Array.from({ length: ticks + 1 }, (_, i) =>
    Math.round((i * duration) / ticks),
  );
  return (
    <div className="relative h-6 w-full">
      <div className="absolute inset-x-0 top-1/2 h-px bg-zinc-300" />
      {stops.map((s) => (
        <span
          key={s}
          className="absolute top-0 -translate-x-1/2 text-[10px] text-zinc-500"
          style={{ left: `${(s / duration) * 100}%` }}
        >
          {formatSeconds(s)}
        </span>
      ))}
    </div>
  );
}
