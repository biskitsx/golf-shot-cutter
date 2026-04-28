"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { type ChangeEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUploadVideoMutation } from "../hooks/useUploadVideoMutation";

export function UploadDropzone() {
  const t = useTranslations();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [preRoll, setPreRoll] = useState(2);
  const [postRoll, setPostRoll] = useState(5);
  const [progress, setProgress] = useState(0);
  const upload = useUploadVideoMutation();

  function onPick(e: ChangeEvent<HTMLInputElement>) {
    setFile(e.target.files?.[0] ?? null);
  }

  async function onUpload() {
    if (!file) return;
    const sessionId = await upload.mutateAsync({
      file,
      preRollSeconds: preRoll,
      postRollSeconds: postRoll,
      onProgress: setProgress,
    });
    router.push(`/sessions/${sessionId}`);
  }

  return (
    <div className="space-y-4">
      <label className="block cursor-pointer rounded-lg border-2 border-dashed border-zinc-300 p-12 text-center hover:bg-white">
        <input
          type="file"
          accept="video/*"
          className="hidden"
          onChange={onPick}
        />
        <p className="text-sm">{file?.name ?? t("upload.drop")}</p>
      </label>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <Label>{t("upload.preRoll")}</Label>
          <Input
            type="number"
            min={0}
            step={0.5}
            value={preRoll}
            onChange={(e) => setPreRoll(Number(e.target.value))}
          />
        </div>
        <div className="space-y-1">
          <Label>{t("upload.postRoll")}</Label>
          <Input
            type="number"
            min={0}
            step={0.5}
            value={postRoll}
            onChange={(e) => setPostRoll(Number(e.target.value))}
          />
        </div>
      </div>
      <Button disabled={!file || upload.isPending} onClick={onUpload}>
        {upload.isPending
          ? t("upload.uploading", { percent: progress })
          : t("upload.title")}
      </Button>
    </div>
  );
}
