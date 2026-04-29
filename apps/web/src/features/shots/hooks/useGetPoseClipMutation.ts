"use client";

import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface Input {
  sessionId: string;
  shotId: string;
}

interface PoseClipResponse {
  data: { url: string; expiresAt: string };
}

export function useGetPoseClipMutation() {
  return useMutation({
    mutationFn: async ({ sessionId, shotId }: Input): Promise<string> => {
      const res = await api.post<PoseClipResponse>(
        `/sessions/${sessionId}/shots/${shotId}/pose-clip`,
      );
      return res.data.data.url;
    },
  });
}
