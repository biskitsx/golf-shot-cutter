"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLoginMutation } from "../hooks/useLoginMutation";

export function LoginForm() {
  const t = useTranslations();
  const router = useRouter();
  const { mutateAsync, isPending, isError } = useLoginMutation();

  const [email, setEmail] = useState("dev@local");
  const [password, setPassword] = useState("dev");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await mutateAsync({ email, password });
      router.push("/sessions");
    } catch {
      // surfaced via isError
    }
  }

  return (
    <Card className="mx-auto mt-24 w-full max-w-sm">
      <CardHeader>
        <CardTitle>{t("common.appName")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div className="space-y-1">
            <Label htmlFor="email">{t("auth.email")}</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="password">{t("auth.password")}</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {isError && (
            <p className="text-sm text-red-600">
              {t("auth.invalidCredentials")}
            </p>
          )}
          <Button type="submit" disabled={isPending}>
            {isPending ? t("common.loading") : t("auth.submit")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
