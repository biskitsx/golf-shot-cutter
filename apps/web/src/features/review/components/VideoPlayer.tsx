"use client";

export function VideoPlayer({ src }: { src: string | null }) {
  if (!src) {
    return <div className="aspect-video w-full rounded-md bg-zinc-200" />;
  }
  return (
    <video
      src={src}
      controls
      className="aspect-video w-full rounded-md bg-black"
    >
      <track kind="captions" />
    </video>
  );
}
