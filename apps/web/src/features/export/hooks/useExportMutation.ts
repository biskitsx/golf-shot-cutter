"use client";

import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface ExportResp {
  data: { exportId: string; signedDownloadUrl: string };
}

export function useExportMutation() {
  return useMutation({
    mutationFn: async (sessionId: string) => {
      const r = await api.post<ExportResp>(`/sessions/${sessionId}/export`);
      return r.data.data;
    },
  });
}
