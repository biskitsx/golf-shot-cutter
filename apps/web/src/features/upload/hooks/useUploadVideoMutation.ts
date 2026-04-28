"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

import { api } from "@/lib/api-client";

interface UploadInput {
  file: File;
  preRollSeconds?: number;
  postRollSeconds?: number;
  onProgress?: (percent: number) => void;
}

interface CreateResp {
  data: { sessionId: string; signedUploadUrl: string };
}

export function useUploadVideoMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      file,
      preRollSeconds,
      postRollSeconds,
      onProgress,
    }: UploadInput) => {
      // 1. Reserve session and get signed URL.
      const created = await api.post<CreateResp>("/sessions", {
        originalFilename: file.name,
        preRollSeconds,
        postRollSeconds,
      });
      const { sessionId, signedUploadUrl } = created.data.data;

      // 2. PUT file directly to R2.
      await axios.put(signedUploadUrl, file, {
        headers: { "Content-Type": "video/mp4" },
        onUploadProgress: (e) => {
          if (e.total) onProgress?.(Math.round((100 * e.loaded) / e.total));
        },
      });

      // 3. Tell backend to start processing.
      await api.post(`/sessions/${sessionId}/process`);

      return sessionId;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}
