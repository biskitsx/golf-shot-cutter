"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

export function useStartProcessingMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (sessionId: string) => {
      await api.post(`/sessions/${sessionId}/process`);
    },
    onSuccess: (_d, sessionId) => {
      qc.invalidateQueries({ queryKey: ["sessions", sessionId] });
      qc.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}
