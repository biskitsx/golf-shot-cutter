"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { useLogoutMutation } from "@/features/auth/hooks/useLogoutMutation";

export function SiteHeader() {
  const t = useTranslations();
  const logout = useLogoutMutation();

  return (
    <header className="border-b border-zinc-200 bg-white">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link href="/sessions" className="font-semibold">
          {t("common.appName")}
        </Link>
        <div className="flex items-center gap-3">
          <Link
            href="/upload"
            className="text-sm text-zinc-700 hover:underline"
          >
            {t("upload.title")}
          </Link>
          <Button
            variant="outline"
            onClick={() => {
              logout.mutate(undefined, {
                onSuccess: () => {
                  window.location.href = "/login";
                },
              });
            }}
          >
            {t("common.logOut")}
          </Button>
        </div>
      </div>
    </header>
  );
}
