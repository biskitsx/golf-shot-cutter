"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

/**
 * Subscribes to /api/proxy/sessions/{id}/events (SSE). On every event, invalidates
 * the matching session detail query so TanStack Query refetches.
 */
export function useRealtimeInvalidation(sessionId: string | null) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!sessionId) return;
    const url = `/api/proxy/sessions/${sessionId}/events`;
    const es = new EventSource(url, { withCredentials: true });
    es.onmessage = () => {
      qc.invalidateQueries({ queryKey: ["sessions", sessionId] });
      qc.invalidateQueries({ queryKey: ["sessions"] });
    };
    es.onerror = () => {
      // Best-effort: backend may close the stream; React effect will re-run on next mount.
    };
    return () => {
      es.close();
    };
  }, [sessionId, qc]);
}
