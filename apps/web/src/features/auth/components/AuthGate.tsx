"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { useMeQuery } from "../hooks/useMeQuery";

export function AuthGate({ children }: { children: ReactNode }) {
  const { data, isLoading, isError } = useMeQuery();
  const router = useRouter();

  useEffect(() => {
    if (isError) router.push("/login");
  }, [isError, router]);

  if (isLoading || isError || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-sm opacity-60">…</div>
      </div>
    );
  }

  return <>{children}</>;
}
