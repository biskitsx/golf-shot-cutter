# Plan 5 — Next.js Frontend (`apps/web`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Build `apps/web` — a Next.js 16 (App Router) frontend that lets a user log in, upload a raw golf video, watch processing progress over SSE, review the auto-detected shots on a timeline (drag handles to fine-tune in/out points, add/delete shots manually), and export the result as a ZIP. After this plan, the full system is browser-usable end-to-end.

**Spec adherence — non-negotiable:**
- Next.js 16 App Router + TypeScript strict
- Tailwind CSS v4 + shadcn/ui primitives (Button, Card, Dialog, etc.)
- **TanStack Query global config:** `staleTime: Infinity`, `gcTime: 30min`, `retry: 1`, `refetchOnWindowFocus: false`. NEVER override per-feature with `staleTime: 0` / `refetchOnWindowFocus: true` / `refetchOnMount: "always"`. Freshness comes from mutation `invalidateQueries(...)` + SSE invalidation only.
- **Components NEVER call axios/fetch directly** — every network call goes through a hook in `features/<scope>/hooks/`.
- Auth via JWT httpOnly cookies (set by `apps/api`); no frontend auth lib.
- All user-facing strings via `next-intl` (Thai default, English fallback).
- Linting: biome (no eslint).
- **No-new-tests rule for `apps/web`:** existing test commands still verify, but don't add new vitest/RTL/Playwright suites in this plan. Verification is build + typecheck + lint + dev-server smoke.

**Architecture target:**

```
apps/web/
  package.json
  next.config.ts
  tsconfig.json
  biome.json
  postcss.config.mjs
  tailwind.config.ts
  project.json                     # Nx project
  Dockerfile
  src/
    app/
      [locale]/
        layout.tsx                  # html shell + Providers + i18n
        page.tsx                    # → redirect to /sessions
        login/page.tsx
        (dashboard)/
          layout.tsx                # auth gate + nav header
          sessions/
            page.tsx                # list
            [id]/page.tsx           # review timeline
          upload/page.tsx
      api/
        proxy/[...path]/route.ts    # forwards /api/* to apps/api with cookies
      providers.tsx                 # QueryClientProvider + NextIntlClientProvider
      globals.css                   # Tailwind layers
    features/
      auth/
        components/LoginForm.tsx
        hooks/useLoginMutation.ts
        hooks/useLogoutMutation.ts
        hooks/useMeQuery.ts
      sessions/
        components/SessionCard.tsx
        components/SessionStatusBadge.tsx
        hooks/useSessionsQuery.ts
        hooks/useSessionQuery.ts
        hooks/useCreateSessionMutation.ts
        hooks/useStartProcessingMutation.ts
      shots/
        components/ShotSidebarItem.tsx
        components/ShotMarker.tsx
        components/DragHandle.tsx
        hooks/useUpdateShotBoundaryMutation.ts
        hooks/useAddManualShotMutation.ts
        hooks/useDeleteShotMutation.ts
      upload/
        components/UploadDropzone.tsx
        hooks/useSignedUploadUrl.ts
        hooks/useUploadVideoMutation.ts
      review/
        components/ReviewTimeline.tsx
        components/VideoPlayer.tsx
        components/TimelineRuler.tsx
        hooks/usePlayerSync.ts
      export/
        components/ExportButton.tsx
        hooks/useExportMutation.ts
      realtime/
        hooks/useRealtimeInvalidation.ts
    lib/
      api-client.ts                 # axios + cookie credentials + 401 redirect
      query-client.ts               # global QueryClient config
      utils.ts                      # cn() + formatters
    i18n/
      config.ts                     # routing/locale config
      request.ts                    # next-intl request config
      messages/
        th.json
        en.json
    components/
      ui/                           # shadcn primitives (button.tsx, card.tsx, ...)
    types/                          # cross-feature view-model types (extends @golf/contracts)
```

**Tech stack:** Next.js 16, React 19, TypeScript 5.6, Tailwind v4, shadcn/ui, TanStack Query 5, axios, next-intl, biome.

**Pre-state:** HEAD `cb294bd` on `main`, tag `v0.4.0-worker`. 108 pytest + 3 vitest passing, 2 skipped.

---

## Task 1: Scaffold Next.js 16 + Tailwind v4 + biome + Nx project

**Files:**
- Create: `apps/web/package.json`, `next.config.ts`, `tsconfig.json`, `biome.json`, `postcss.config.mjs`, `tailwind.config.ts`, `project.json`, `app/globals.css`, `app/[locale]/page.tsx`, `app/[locale]/layout.tsx`
- Modify: root `pnpm-workspace.yaml` (add `apps/web`), root `nx.json` (no change needed; new project auto-discovered via project.json)

- [ ] **Step 1: Confirm pnpm workspace already lists `apps/web`**

Read `pnpm-workspace.yaml`. Should already include `apps/web` from Plan 1. If not, add.

- [ ] **Step 2: Create `apps/web/package.json`**

```json
{
  "name": "@golf/web",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "typecheck": "tsc --noEmit",
    "lint": "pnpm exec biome check src"
  },
  "dependencies": {
    "next": "16.0.0",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "@tanstack/react-query": "5.59.20",
    "axios": "1.7.7",
    "next-intl": "3.25.3",
    "zod": "3.23.8",
    "@golf/contracts": "workspace:*",
    "clsx": "2.1.1",
    "tailwind-merge": "2.5.4",
    "class-variance-authority": "0.7.0",
    "lucide-react": "0.453.0"
  },
  "devDependencies": {
    "@types/node": "22.9.0",
    "@types/react": "19.0.1",
    "@types/react-dom": "19.0.1",
    "typescript": "5.6.3",
    "tailwindcss": "4.0.0-beta.1",
    "@tailwindcss/postcss": "4.0.0-beta.1",
    "postcss": "8.4.49",
    "@biomejs/biome": "1.9.4"
  }
}
```

NOTE on versions: as of late 2026 these are reasonable picks for the Next.js 16 + React 19 + Tailwind v4 stack. If `pnpm install` reports any unresolvable version, pick the closest stable available and document. Tailwind v4 betas in particular evolve quickly; `4.0.0` GA may be available — use it if so.

- [ ] **Step 3: Create `apps/web/next.config.ts`**

```ts
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
};

export default withNextIntl(nextConfig);
```

- [ ] **Step 4: Create `apps/web/tsconfig.json`**

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "module": "esnext",
    "moduleResolution": "bundler",
    "jsx": "preserve",
    "incremental": true,
    "allowJs": true,
    "noEmit": true,
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./src/*"],
      "@golf/contracts": ["../../libs/contracts/src/index.ts"]
    }
  },
  "include": ["next-env.d.ts", "src/**/*", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 5: Create `apps/web/biome.json`**

```json
{
  "$schema": "../../node_modules/@biomejs/biome/configuration_schema.json",
  "extends": ["../../biome.json"],
  "files": {
    "ignore": [".next/**", "node_modules/**"]
  }
}
```

- [ ] **Step 6: Create `apps/web/tailwind.config.ts`**

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{ts,tsx,mdx}",
    "../../libs/ui/src/**/*.{ts,tsx}", // future shared UI lib (currently empty)
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 7: Create `apps/web/postcss.config.mjs`**

```js
export default {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
```

- [ ] **Step 8: Create `apps/web/src/app/globals.css`**

```css
@import "tailwindcss";

:root {
  --background: 0 0% 100%;
  --foreground: 240 10% 3.9%;
  --primary: 240 5.9% 10%;
  --muted: 240 4.8% 95.9%;
  --border: 240 5.9% 90%;
  --radius: 0.5rem;
}

@media (prefers-color-scheme: dark) {
  :root {
    --background: 240 10% 3.9%;
    --foreground: 0 0% 98%;
    --primary: 0 0% 98%;
    --muted: 240 3.7% 15.9%;
    --border: 240 3.7% 15.9%;
  }
}

body {
  background: hsl(var(--background));
  color: hsl(var(--foreground));
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", "Helvetica Neue", sans-serif;
}
```

- [ ] **Step 9: Create `apps/web/src/app/[locale]/layout.tsx`** (placeholder; Task 4 enriches)

```tsx
import "../globals.css";

import type { ReactNode } from "react";

export default function LocaleLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="th">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 10: Create `apps/web/src/app/[locale]/page.tsx`** (placeholder)

```tsx
export default function HomePage() {
  return (
    <main className="p-8">
      <h1 className="text-2xl font-semibold">golf-shot-cutter</h1>
      <p className="mt-2 text-sm opacity-60">Next.js scaffold OK. Plan 5 in progress.</p>
    </main>
  );
}
```

- [ ] **Step 11: Create `apps/web/project.json` (Nx)**

```json
{
  "name": "web",
  "$schema": "../../node_modules/nx/schemas/project-schema.json",
  "projectType": "application",
  "sourceRoot": "apps/web/src",
  "tags": ["type:app", "scope:web"],
  "targets": {
    "build": {
      "executor": "nx:run-commands",
      "options": { "command": "pnpm next build", "cwd": "apps/web" }
    },
    "serve": {
      "executor": "nx:run-commands",
      "options": { "command": "pnpm next dev --port 3000", "cwd": "apps/web" }
    },
    "lint": {
      "executor": "nx:run-commands",
      "options": { "command": "pnpm exec biome check apps/web/src" }
    },
    "typecheck": {
      "executor": "nx:run-commands",
      "options": { "command": "pnpm tsc --noEmit", "cwd": "apps/web" }
    },
    "test": {
      "executor": "nx:run-commands",
      "options": { "command": "echo 'web: no-new-tests rule applies'", "cwd": "apps/web" }
    }
  }
}
```

- [ ] **Step 12: Install + verify**

Run: `pnpm install`. Expected: `apps/web` deps installed, `@golf/contracts` linked from workspace.

Run: `pnpm nx typecheck web`. Expected: 0 errors.

Run: `pnpm nx build web`. Expected: build succeeds (Next.js may warn about missing i18n/middleware — fine for placeholder; Task 3 fixes).

If build fails because of missing `i18n/request.ts`, create a stub:
```ts
// apps/web/src/i18n/request.ts
import { getRequestConfig } from "next-intl/server";

export default getRequestConfig(async () => ({
  locale: "th",
  messages: {},
}));
```

(Task 3 replaces with real content.)

- [ ] **Step 13: Commit**

```bash
git add apps/web pnpm-lock.yaml
git commit -m "chore(web): scaffold Next.js 16 + Tailwind v4 + biome + Nx project"
```

---

## Task 2: Lib layer — api-client + query-client

**Files:**
- Create: `apps/web/src/lib/api-client.ts`
- Create: `apps/web/src/lib/query-client.ts`
- Create: `apps/web/src/lib/utils.ts`
- Create: `apps/web/src/app/providers.tsx`

- [ ] **Step 1: `lib/api-client.ts`**

```ts
import axios from "axios";

/**
 * All requests go through Next.js's `/api/proxy/*` route handler (Task 8),
 * which forwards to the FastAPI backend with cookies attached. This avoids
 * CORS pain in the browser and centralizes 401-redirect handling.
 */
export const api = axios.create({
  baseURL: "/api/proxy",
  withCredentials: true,
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (
      typeof window !== "undefined" &&
      error.response?.status === 401 &&
      !window.location.pathname.endsWith("/login")
    ) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);
```

- [ ] **Step 2: `lib/query-client.ts`**

```ts
import { QueryClient } from "@tanstack/react-query";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: Number.POSITIVE_INFINITY,
        gcTime: 1000 * 60 * 30,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  });
}
```

- [ ] **Step 3: `lib/utils.ts`**

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatSeconds(s: number): string {
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(1);
  return `${m}:${sec.padStart(4, "0")}`;
}
```

- [ ] **Step 4: `src/app/providers.tsx`**

```tsx
"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { makeQueryClient } from "@/lib/query-client";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => makeQueryClient());
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib apps/web/src/app/providers.tsx
git commit -m "feat(web): api-client + query-client + Providers wrapper"
```

---

## Task 3: i18n setup (next-intl, Thai default + English)

**Files:**
- Create: `apps/web/src/i18n/config.ts`, `request.ts`, `messages/th.json`, `messages/en.json`
- Create: `apps/web/src/middleware.ts`
- Modify: `apps/web/src/app/[locale]/layout.tsx` to use NextIntlClientProvider

- [ ] **Step 1: `src/i18n/config.ts`**

```ts
export const locales = ["th", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "th";
```

- [ ] **Step 2: `src/i18n/request.ts`**

```ts
import { getRequestConfig } from "next-intl/server";
import { notFound } from "next/navigation";

import { locales, type Locale } from "./config";

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale: Locale | undefined = locales.includes(requested as Locale)
    ? (requested as Locale)
    : undefined;
  if (!locale) notFound();
  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
```

- [ ] **Step 3: `src/i18n/messages/th.json`**

```json
{
  "common": {
    "appName": "Golf Shot Cutter",
    "logIn": "เข้าสู่ระบบ",
    "logOut": "ออกจากระบบ",
    "save": "บันทึก",
    "cancel": "ยกเลิก",
    "delete": "ลบ",
    "loading": "กำลังโหลด...",
    "error": "เกิดข้อผิดพลาด"
  },
  "auth": {
    "email": "อีเมล",
    "password": "รหัสผ่าน",
    "submit": "เข้าสู่ระบบ",
    "invalidCredentials": "อีเมลหรือรหัสผ่านไม่ถูกต้อง"
  },
  "sessions": {
    "title": "เซสชัน",
    "newSession": "เซสชันใหม่",
    "empty": "ยังไม่มีเซสชัน — เริ่มจากอัปโหลดวิดีโอ",
    "uploading": "กำลังอัปโหลด",
    "queued": "อยู่ในคิว",
    "processing": "กำลังประมวลผล",
    "ready": "พร้อม",
    "failed": "ล้มเหลว",
    "shotCount": "{count} ช็อต"
  },
  "upload": {
    "title": "อัปโหลดวิดีโอ",
    "drop": "ลากวิดีโอมาวางที่นี่ หรือคลิกเพื่อเลือกไฟล์",
    "uploading": "กำลังอัปโหลด {percent}%",
    "preRoll": "Pre-roll (วินาที)",
    "postRoll": "Post-roll (วินาที)"
  },
  "review": {
    "title": "ตรวจทานช็อต",
    "addShot": "เพิ่มช็อต",
    "deleteShot": "ลบช็อต",
    "noShots": "ไม่พบช็อต — ลองเพิ่มด้วยตัวเอง",
    "export": "Export ZIP"
  }
}
```

- [ ] **Step 4: `src/i18n/messages/en.json`**

```json
{
  "common": {
    "appName": "Golf Shot Cutter",
    "logIn": "Log in",
    "logOut": "Log out",
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "loading": "Loading...",
    "error": "Something went wrong"
  },
  "auth": {
    "email": "Email",
    "password": "Password",
    "submit": "Log in",
    "invalidCredentials": "Invalid email or password"
  },
  "sessions": {
    "title": "Sessions",
    "newSession": "New session",
    "empty": "No sessions yet — start by uploading a video",
    "uploading": "Uploading",
    "queued": "Queued",
    "processing": "Processing",
    "ready": "Ready",
    "failed": "Failed",
    "shotCount": "{count} shots"
  },
  "upload": {
    "title": "Upload video",
    "drop": "Drag a video here or click to choose a file",
    "uploading": "Uploading {percent}%",
    "preRoll": "Pre-roll (seconds)",
    "postRoll": "Post-roll (seconds)"
  },
  "review": {
    "title": "Review shots",
    "addShot": "Add shot",
    "deleteShot": "Delete shot",
    "noShots": "No shots detected — try adding one manually",
    "export": "Export ZIP"
  }
}
```

- [ ] **Step 5: `src/middleware.ts`**

```ts
import createMiddleware from "next-intl/middleware";

import { defaultLocale, locales } from "@/i18n/config";

export default createMiddleware({
  locales,
  defaultLocale,
  localePrefix: "as-needed",
});

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
```

- [ ] **Step 6: Update `src/app/[locale]/layout.tsx`**

```tsx
import "../globals.css";

import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import type { ReactNode } from "react";

import { Providers } from "../providers";

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 7: Verify build**

Run: `pnpm nx typecheck web && pnpm nx build web`
Expected: build succeeds; the placeholder page renders OK with i18n configured.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src
git commit -m "feat(web): next-intl setup with Thai/English messages + middleware"
```

---

## Task 4: Auth feature — login form + hooks

**Files:**
- Create: `apps/web/src/features/auth/hooks/useLoginMutation.ts`, `useLogoutMutation.ts`, `useMeQuery.ts`
- Create: `apps/web/src/features/auth/components/LoginForm.tsx`
- Create: `apps/web/src/app/[locale]/login/page.tsx`
- Create: `apps/web/src/components/ui/button.tsx`, `input.tsx`, `label.tsx`, `card.tsx` (minimal shadcn primitives — hand-written rather than shadcn-cli to keep the task self-contained)

- [ ] **Step 1: shadcn-style primitives** — create `components/ui/button.tsx`:

```tsx
import { cn } from "@/lib/utils";
import { type ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "default" | "outline" | "ghost" | "destructive";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const variantClass: Record<Variant, string> = {
  default: "bg-zinc-900 text-zinc-50 hover:bg-zinc-800",
  outline: "border border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50",
  ghost: "bg-transparent text-zinc-900 hover:bg-zinc-100",
  destructive: "bg-red-600 text-white hover:bg-red-700",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", ...rest }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium",
        "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900",
        "disabled:pointer-events-none disabled:opacity-50",
        variantClass[variant],
        className,
      )}
      {...rest}
    />
  ),
);
Button.displayName = "Button";
```

`components/ui/input.tsx`:
```tsx
import { cn } from "@/lib/utils";
import { type InputHTMLAttributes, forwardRef } from "react";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...rest }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm",
        "placeholder:text-zinc-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...rest}
    />
  ),
);
Input.displayName = "Input";
```

`components/ui/label.tsx`:
```tsx
import { cn } from "@/lib/utils";
import { type LabelHTMLAttributes } from "react";

export function Label({ className, ...rest }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={cn("text-sm font-medium leading-none", className)} {...rest} />
  );
}
```

`components/ui/card.tsx`:
```tsx
import { cn } from "@/lib/utils";
import { type HTMLAttributes } from "react";

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-lg border border-zinc-200 bg-white shadow-sm", className)}
      {...rest}
    />
  );
}

export function CardHeader({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col space-y-1.5 p-6", className)} {...rest} />;
}

export function CardTitle({ className, ...rest }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-xl font-semibold leading-none", className)} {...rest} />;
}

export function CardContent({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-6 pt-0", className)} {...rest} />;
}
```

- [ ] **Step 2: Auth hooks**

`features/auth/hooks/useLoginMutation.ts`:
```ts
"use client";

import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface LoginInput {
  email: string;
  password: string;
}

export function useLoginMutation() {
  return useMutation({
    mutationFn: async ({ email, password }: LoginInput) => {
      await api.post("/auth/login", { email, password });
    },
  });
}
```

`features/auth/hooks/useLogoutMutation.ts`:
```ts
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

export function useLogoutMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.post("/auth/logout");
    },
    onSuccess: () => {
      qc.clear();
    },
  });
}
```

`features/auth/hooks/useMeQuery.ts`:
```ts
"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface MeResponse {
  data: { userId: string };
}

export function useMeQuery() {
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      const r = await api.get<MeResponse>("/auth/me");
      return r.data.data;
    },
  });
}
```

- [ ] **Step 3: Login form component**

`features/auth/components/LoginForm.tsx`:
```tsx
"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

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
            <p className="text-sm text-red-600">{t("auth.invalidCredentials")}</p>
          )}
          <Button type="submit" disabled={isPending}>
            {isPending ? t("common.loading") : t("auth.submit")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Login page**

`src/app/[locale]/login/page.tsx`:
```tsx
import { LoginForm } from "@/features/auth/components/LoginForm";

export default function LoginPage() {
  return (
    <main className="min-h-screen bg-zinc-50 px-4">
      <LoginForm />
    </main>
  );
}
```

- [ ] **Step 5: Verify build + lint**

Run: `pnpm nx typecheck web && pnpm nx lint web && pnpm nx build web`. Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src
git commit -m "feat(web): auth feature (login form + hooks) + minimal shadcn primitives"
```

---

## Task 5: Dashboard layout + auth gate + nav

**Files:**
- Create: `apps/web/src/app/[locale]/(dashboard)/layout.tsx`
- Create: `apps/web/src/features/auth/components/AuthGate.tsx`
- Create: `apps/web/src/components/site-header.tsx`
- Modify: `apps/web/src/app/[locale]/page.tsx` to redirect to `/sessions`

- [ ] **Step 1: `features/auth/components/AuthGate.tsx`**

```tsx
"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

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
```

- [ ] **Step 2: `components/site-header.tsx`**

```tsx
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
          <Link href="/upload" className="text-sm text-zinc-700 hover:underline">
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
```

- [ ] **Step 3: `(dashboard)/layout.tsx`**

```tsx
import type { ReactNode } from "react";

import { SiteHeader } from "@/components/site-header";
import { AuthGate } from "@/features/auth/components/AuthGate";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate>
      <div className="min-h-screen bg-zinc-50">
        <SiteHeader />
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      </div>
    </AuthGate>
  );
}
```

- [ ] **Step 4: Update `[locale]/page.tsx` to redirect**

```tsx
import { redirect } from "next/navigation";

export default function HomePage() {
  redirect("/sessions");
}
```

- [ ] **Step 5: Verify + commit**

`pnpm nx build web && pnpm nx lint web && pnpm nx typecheck web` → all green.

```bash
git add apps/web/src
git commit -m "feat(web): dashboard layout + AuthGate + SiteHeader"
```

---

## Task 6: Sessions list + create

**Files:**
- Create: `apps/web/src/features/sessions/hooks/useSessionsQuery.ts`
- Create: `apps/web/src/features/sessions/hooks/useCreateSessionMutation.ts`
- Create: `apps/web/src/features/sessions/hooks/useStartProcessingMutation.ts`
- Create: `apps/web/src/features/sessions/hooks/useSessionQuery.ts`
- Create: `apps/web/src/features/sessions/components/SessionStatusBadge.tsx`
- Create: `apps/web/src/features/sessions/components/SessionCard.tsx`
- Create: `apps/web/src/app/[locale]/(dashboard)/sessions/page.tsx`

The list page shows existing sessions. The "New session" CTA links to `/upload`.

- [ ] **Step 1: Hooks**

`useSessionsQuery.ts`:
```ts
"use client";

import { useQuery } from "@tanstack/react-query";
import type { SessionDto } from "@golf/contracts";

import { api } from "@/lib/api-client";

interface ListResponse {
  data: SessionDto[];
}

export function useSessionsQuery() {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: async () => {
      const r = await api.get<ListResponse>("/sessions");
      return r.data.data;
    },
  });
}
```

`useSessionQuery.ts`:
```ts
"use client";

import { useQuery } from "@tanstack/react-query";
import type { SessionDto, ShotDto } from "@golf/contracts";

import { api } from "@/lib/api-client";

interface SessionDetailResponse {
  data: { session: SessionDto; shots: ShotDto[] };
}

export function useSessionQuery(sessionId: string) {
  return useQuery({
    queryKey: ["sessions", sessionId],
    queryFn: async () => {
      const r = await api.get<SessionDetailResponse>(`/sessions/${sessionId}`);
      return r.data.data;
    },
    enabled: Boolean(sessionId),
  });
}
```

`useCreateSessionMutation.ts`:
```ts
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface CreateInput {
  originalFilename: string;
  preRollSeconds?: number;
  postRollSeconds?: number;
}

interface CreateResponse {
  data: { sessionId: string; signedUploadUrl: string; expiresAt: string };
}

export function useCreateSessionMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateInput) => {
      const r = await api.post<CreateResponse>("/sessions", input);
      return r.data.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}
```

`useStartProcessingMutation.ts`:
```ts
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
```

- [ ] **Step 2: Components**

`SessionStatusBadge.tsx`:
```tsx
"use client";

import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";

const palette: Record<string, string> = {
  uploading: "bg-zinc-200 text-zinc-700",
  queued: "bg-amber-100 text-amber-800",
  processing: "bg-blue-100 text-blue-800",
  ready: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
};

export function SessionStatusBadge({ status }: { status: string }) {
  const t = useTranslations("sessions");
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
        palette[status] ?? "bg-zinc-100 text-zinc-700",
      )}
    >
      {t(status as never)}
    </span>
  );
}
```

`SessionCard.tsx`:
```tsx
"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";

import { Card } from "@/components/ui/card";
import type { SessionDto } from "@golf/contracts";

import { SessionStatusBadge } from "./SessionStatusBadge";

export function SessionCard({ session }: { session: SessionDto }) {
  const t = useTranslations("sessions");
  return (
    <Link href={`/sessions/${session.id}`} className="block">
      <Card className="p-4 hover:shadow-md">
        <div className="flex items-center justify-between">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{session.rawVideoKey}</p>
            <p className="mt-1 text-xs text-zinc-600">
              {t("shotCount", { count: session.shotCount })} ·{" "}
              {new Date(session.createdAt).toLocaleString()}
            </p>
          </div>
          <SessionStatusBadge status={session.status} />
        </div>
      </Card>
    </Link>
  );
}
```

- [ ] **Step 3: List page**

`(dashboard)/sessions/page.tsx`:
```tsx
"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { SessionCard } from "@/features/sessions/components/SessionCard";
import { useSessionsQuery } from "@/features/sessions/hooks/useSessionsQuery";

export default function SessionsPage() {
  const t = useTranslations();
  const { data, isLoading } = useSessionsQuery();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("sessions.title")}</h1>
        <Link href="/upload">
          <Button>{t("sessions.newSession")}</Button>
        </Link>
      </div>
      {isLoading && <p className="text-sm text-zinc-600">{t("common.loading")}</p>}
      {data && data.length === 0 && (
        <p className="text-sm text-zinc-600">{t("sessions.empty")}</p>
      )}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {data?.map((s) => <SessionCard key={s.id} session={s} />)}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify + commit**

`pnpm nx build web && pnpm nx typecheck web && pnpm nx lint web` → green.

```bash
git add apps/web/src
git commit -m "feat(web): sessions list page + hooks + SessionCard"
```

---

## Task 7: Upload feature (drop zone + signed PUT upload)

**Files:**
- Create: `apps/web/src/features/upload/hooks/useUploadVideoMutation.ts`
- Create: `apps/web/src/features/upload/components/UploadDropzone.tsx`
- Create: `apps/web/src/app/[locale]/(dashboard)/upload/page.tsx`

The upload flow:
1. User picks a file + (optional) pre/post-roll seconds
2. POST /sessions returns `{ sessionId, signedUploadUrl, expiresAt }`
3. Browser PUTs the file directly to R2 via the signed URL
4. POST /sessions/{id}/process to enqueue
5. Redirect to /sessions/{id}

- [ ] **Step 1: `features/upload/hooks/useUploadVideoMutation.ts`**

```ts
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
    mutationFn: async ({ file, preRollSeconds, postRollSeconds, onProgress }: UploadInput) => {
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
```

- [ ] **Step 2: `features/upload/components/UploadDropzone.tsx`**

```tsx
"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState, type ChangeEvent } from "react";

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
        <input type="file" accept="video/*" className="hidden" onChange={onPick} />
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
```

- [ ] **Step 3: `(dashboard)/upload/page.tsx`**

```tsx
import { useTranslations } from "next-intl";
import { getTranslations } from "next-intl/server";

import { UploadDropzone } from "@/features/upload/components/UploadDropzone";

export default async function UploadPage() {
  const t = await getTranslations();
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t("upload.title")}</h1>
      <UploadDropzone />
    </div>
  );
}
```

- [ ] **Step 4: Verify + commit**

`pnpm nx build web && pnpm nx typecheck web && pnpm nx lint web` → green.

```bash
git add apps/web/src
git commit -m "feat(web): upload page + signed-URL PUT mutation"
```

---

## Task 8: API proxy route handler

**Files:**
- Create: `apps/web/src/app/api/proxy/[...path]/route.ts`

The Next.js server-side proxy forwards browser requests at `/api/proxy/*` to the backend at `${API_URL}/*`, attaching cookies. This avoids CORS in the browser and keeps `apps/web` callable as a single origin.

- [ ] **Step 1: `route.ts`**

```ts
import type { NextRequest } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function forward(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const url = new URL(`${API_URL}/${path.join("/")}`);
  url.search = req.nextUrl.search;

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("connection");

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  const upstream = await fetch(url, init);
  const respHeaders = new Headers(upstream.headers);
  respHeaders.delete("content-encoding");
  respHeaders.delete("transfer-encoding");

  return new Response(upstream.body, {
    status: upstream.status,
    headers: respHeaders,
  });
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const PUT = forward;
export const DELETE = forward;
```

NOTE: this proxy works because the browser's Set-Cookie headers from the upstream API land on the same origin (Next.js serves them back unchanged). For production HTTPS, ensure the API sets `secure=True` on cookies (Plan 2 patch already does that for HTTPS schemes).

- [ ] **Step 2: Add `NEXT_PUBLIC_API_URL` to `.env.example`**

Edit root `.env.example` — add line near the bottom:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/api .env.example
git commit -m "feat(web): /api/proxy route handler forwarding to FastAPI"
```

---

## Task 9: Session detail + Review timeline + shots feature

**Files:**
- Create: `apps/web/src/features/shots/hooks/useUpdateShotBoundaryMutation.ts`, `useAddManualShotMutation.ts`, `useDeleteShotMutation.ts`
- Create: `apps/web/src/features/shots/components/ShotSidebarItem.tsx`
- Create: `apps/web/src/features/review/components/VideoPlayer.tsx`, `ReviewTimeline.tsx`, `TimelineRuler.tsx`
- Create: `apps/web/src/app/[locale]/(dashboard)/sessions/[id]/page.tsx`

Skipping fancy drag-handle UI for Plan 5 — use simple numeric inputs for in/out points. A drag-handle UX can land in Plan 6.

- [ ] **Step 1: Shot mutation hooks**

`useUpdateShotBoundaryMutation.ts`:
```ts
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface UpdateInput {
  sessionId: string;
  shotId: string;
  tStart: number;
  tEnd: number;
}

export function useUpdateShotBoundaryMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ sessionId, shotId, tStart, tEnd }: UpdateInput) => {
      await api.patch(`/sessions/${sessionId}/shots/${shotId}`, { tStart, tEnd });
    },
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ["sessions", vars.sessionId] }),
  });
}
```

`useAddManualShotMutation.ts`:
```ts
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface AddInput {
  sessionId: string;
  tImpact: number;
  tStart: number;
  tEnd: number;
}

export function useAddManualShotMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ sessionId, ...body }: AddInput) => {
      await api.post(`/sessions/${sessionId}/shots`, body);
    },
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ["sessions", vars.sessionId] }),
  });
}
```

`useDeleteShotMutation.ts`:
```ts
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api-client";

interface DeleteInput {
  sessionId: string;
  shotId: string;
}

export function useDeleteShotMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ sessionId, shotId }: DeleteInput) => {
      await api.delete(`/sessions/${sessionId}/shots/${shotId}`);
    },
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ["sessions", vars.sessionId] }),
  });
}
```

- [ ] **Step 2: `features/shots/components/ShotSidebarItem.tsx`**

```tsx
"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ShotDto } from "@golf/contracts";
import { formatSeconds } from "@/lib/utils";

import { useDeleteShotMutation } from "../hooks/useDeleteShotMutation";
import { useUpdateShotBoundaryMutation } from "../hooks/useUpdateShotBoundaryMutation";

export function ShotSidebarItem({
  shot,
  sessionId,
}: {
  shot: ShotDto;
  sessionId: string;
}) {
  const t = useTranslations("review");
  const update = useUpdateShotBoundaryMutation();
  const del = useDeleteShotMutation();
  const [tStart, setTStart] = useState(shot.tStart);
  const [tEnd, setTEnd] = useState(shot.tEnd);

  return (
    <div className="space-y-2 rounded-md border border-zinc-200 p-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">#{shot.index}</span>
        <span className="text-xs text-zinc-500">{shot.source}</span>
      </div>
      <p className="text-xs text-zinc-600">
        impact: {formatSeconds(shot.tImpact)} · conf:{" "}
        {(shot.confidence * 100).toFixed(0)}%
      </p>
      <div className="grid grid-cols-2 gap-2">
        <Input
          type="number"
          step={0.1}
          value={tStart}
          onChange={(e) => setTStart(Number(e.target.value))}
        />
        <Input
          type="number"
          step={0.1}
          value={tEnd}
          onChange={(e) => setTEnd(Number(e.target.value))}
        />
      </div>
      <div className="flex gap-2">
        <Button
          className="flex-1"
          variant="outline"
          disabled={
            (tStart === shot.tStart && tEnd === shot.tEnd) || update.isPending
          }
          onClick={() =>
            update.mutate({ sessionId, shotId: shot.id, tStart, tEnd })
          }
        >
          {update.isPending ? "…" : "Save"}
        </Button>
        <Button
          variant="destructive"
          disabled={del.isPending}
          onClick={() => del.mutate({ sessionId, shotId: shot.id })}
        >
          {t("deleteShot")}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: `features/review/components/VideoPlayer.tsx`** (basic HTML5 video)

```tsx
"use client";

export function VideoPlayer({ src }: { src: string | null }) {
  if (!src) {
    return (
      <div className="aspect-video w-full rounded-md bg-zinc-200" />
    );
  }
  return (
    <video src={src} controls className="aspect-video w-full rounded-md bg-black" />
  );
}
```

- [ ] **Step 4: `features/review/components/TimelineRuler.tsx`**

```tsx
import { formatSeconds } from "@/lib/utils";

export function TimelineRuler({ duration }: { duration: number }) {
  const ticks = Math.max(2, Math.ceil(duration / 30));
  const stops = Array.from({ length: ticks + 1 }, (_, i) =>
    Math.round((i * duration) / ticks),
  );
  return (
    <div className="relative h-6 w-full">
      <div className="absolute inset-x-0 top-1/2 h-px bg-zinc-300" />
      {stops.map((s) => (
        <span
          key={s}
          className="absolute top-0 -translate-x-1/2 text-[10px] text-zinc-500"
          style={{ left: `${(s / duration) * 100}%` }}
        >
          {formatSeconds(s)}
        </span>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: `features/review/components/ReviewTimeline.tsx`**

```tsx
"use client";

import type { ShotDto } from "@golf/contracts";

import { TimelineRuler } from "./TimelineRuler";

export function ReviewTimeline({
  shots,
  duration,
}: {
  shots: ShotDto[];
  duration: number;
}) {
  if (duration <= 0) {
    return <div className="text-sm text-zinc-600">…</div>;
  }
  return (
    <div className="space-y-2">
      <div className="relative h-10 rounded-md bg-zinc-100">
        {shots.map((s) => {
          const left = (s.tStart / duration) * 100;
          const width = ((s.tEnd - s.tStart) / duration) * 100;
          return (
            <div
              key={s.id}
              className="absolute top-1 bottom-1 rounded bg-emerald-500/70"
              style={{ left: `${left}%`, width: `${Math.max(0.5, width)}%` }}
              title={`#${s.index} ${s.tStart.toFixed(1)}–${s.tEnd.toFixed(1)}s`}
            />
          );
        })}
      </div>
      <TimelineRuler duration={duration} />
    </div>
  );
}
```

- [ ] **Step 6: `(dashboard)/sessions/[id]/page.tsx`**

```tsx
"use client";

import { useTranslations } from "next-intl";
import { use } from "react";

import { Button } from "@/components/ui/button";
import { ExportButton } from "@/features/export/components/ExportButton";
import { useSessionQuery } from "@/features/sessions/hooks/useSessionQuery";
import { SessionStatusBadge } from "@/features/sessions/components/SessionStatusBadge";
import { ShotSidebarItem } from "@/features/shots/components/ShotSidebarItem";
import { useAddManualShotMutation } from "@/features/shots/hooks/useAddManualShotMutation";
import { ReviewTimeline } from "@/features/review/components/ReviewTimeline";
import { VideoPlayer } from "@/features/review/components/VideoPlayer";
import { useRealtimeInvalidation } from "@/features/realtime/hooks/useRealtimeInvalidation";

export default function SessionDetailPage({
  params,
}: {
  params: Promise<{ id: string; locale: string }>;
}) {
  const { id } = use(params);
  const t = useTranslations("review");
  const { data, isLoading } = useSessionQuery(id);
  const add = useAddManualShotMutation();
  useRealtimeInvalidation(id);

  if (isLoading || !data) {
    return <p className="text-sm text-zinc-600">…</p>;
  }

  const { session, shots } = data;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <SessionStatusBadge status={session.status} />
        </div>
        <VideoPlayer src={null /* signed GET URL retrieval is Plan 6 */} />
        <ReviewTimeline shots={shots} duration={session.durationSeconds || 60} />
        <ExportButton sessionId={id} disabled={session.status !== "ready"} />
      </div>
      <aside className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">Shots</h2>
          <Button
            variant="outline"
            disabled={add.isPending || session.status !== "ready"}
            onClick={() => {
              const last = shots[shots.length - 1];
              const t_impact = (last ? last.tEnd : 0) + 5;
              add.mutate({
                sessionId: id,
                tImpact: t_impact,
                tStart: Math.max(0, t_impact - 2),
                tEnd: t_impact + 5,
              });
            }}
          >
            {t("addShot")}
          </Button>
        </div>
        {shots.length === 0 ? (
          <p className="text-sm text-zinc-600">{t("noShots")}</p>
        ) : (
          shots.map((s) => (
            <ShotSidebarItem key={s.id} shot={s} sessionId={id} />
          ))
        )}
      </aside>
    </div>
  );
}
```

- [ ] **Step 7: Verify + commit**

`pnpm nx build web && pnpm nx typecheck web && pnpm nx lint web` → green.

```bash
git add apps/web/src
git commit -m "feat(web): session detail + ReviewTimeline + ShotSidebarItem + shot mutations"
```

---

## Task 10: Export feature + SSE realtime invalidation

**Files:**
- Create: `apps/web/src/features/export/hooks/useExportMutation.ts`
- Create: `apps/web/src/features/export/components/ExportButton.tsx`
- Create: `apps/web/src/features/realtime/hooks/useRealtimeInvalidation.ts`

- [ ] **Step 1: Export hook**

`features/export/hooks/useExportMutation.ts`:
```ts
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
```

- [ ] **Step 2: Export button**

`features/export/components/ExportButton.tsx`:
```tsx
"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { useExportMutation } from "../hooks/useExportMutation";

export function ExportButton({
  sessionId,
  disabled,
}: {
  sessionId: string;
  disabled?: boolean;
}) {
  const t = useTranslations("review");
  const { mutate, isPending, data } = useExportMutation();

  if (data?.signedDownloadUrl) {
    return (
      <a
        href={data.signedDownloadUrl}
        className="inline-flex h-10 items-center justify-center rounded-md border border-zinc-300 bg-white px-4 text-sm font-medium hover:bg-zinc-50"
        download
      >
        ⬇ {t("export")}
      </a>
    );
  }

  return (
    <Button disabled={disabled || isPending} onClick={() => mutate(sessionId)}>
      {isPending ? "…" : t("export")}
    </Button>
  );
}
```

- [ ] **Step 3: Realtime invalidation hook**

`features/realtime/hooks/useRealtimeInvalidation.ts`:
```ts
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
```

NOTE: `EventSource` doesn't accept arbitrary headers, and `withCredentials: true` is supported. For the proxy route to forward the auth cookie correctly, the route handler in Task 8 already preserves cookies on `fetch`.

- [ ] **Step 4: Verify + commit**

`pnpm nx build web && pnpm nx typecheck web && pnpm nx lint web` → green.

```bash
git add apps/web/src
git commit -m "feat(web): export button + realtime SSE invalidation"
```

---

## Task 11: Dockerfile + docker-compose update

**Files:**
- Create: `apps/web/Dockerfile`
- Create: `apps/web/.dockerignore`
- Modify: `docker-compose.dev.yml` to add the web service (optional — local devs usually run `pnpm dev` directly)

- [ ] **Step 1: `apps/web/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS base
ENV PNPM_HOME=/usr/local/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

WORKDIR /app
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY libs/contracts ./libs/contracts
COPY apps/web/package.json ./apps/web/package.json

RUN pnpm install --frozen-lockfile --filter @golf/web... --filter @golf/contracts

COPY apps/web ./apps/web
RUN pnpm --filter @golf/web build

EXPOSE 3000
CMD ["pnpm", "--filter", "@golf/web", "start", "-p", "3000"]
```

- [ ] **Step 2: `apps/web/.dockerignore`**

```
**/node_modules
**/.next
**/.git
**/.env
**/.env.local
**/.nx
**/.pytest_cache
**/.ruff_cache
**/.venv
**/dist
**/coverage
docs
docker-compose.dev.yml
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/Dockerfile apps/web/.dockerignore
git commit -m "chore(web): minimal Dockerfile + .dockerignore"
```

---

## Task 12: Final verification + tag `v0.5.0-frontend`

- [ ] **Step 1: Build + typecheck + lint**

```
pnpm nx build web
pnpm nx typecheck web
pnpm nx lint web
```
All green.

- [ ] **Step 2: Full repo checks**

```
uv run pytest 2>&1 | tail -3                # 108 passed + 2 skipped (unchanged)
pnpm nx run-many -t test 2>&1 | tail -3     # contracts 3/3
pnpm exec biome check . 2>&1 | tail -2      # checked, no fixes
uv run ruff check . 2>&1 | tail -2          # checks passed
uv tool run pre-commit run --all-files 2>&1 | tail -5  # all pass
```

- [ ] **Step 3: Manual smoke (optional but recommended)**

In separate terminals:
1. `docker compose -f docker-compose.dev.yml up -d` (mongo + redis + minio).
2. `cp .env.example .env` and fill in.
3. API: `cd apps/api && uv run uvicorn app.main:app --port 8000 --reload`.
4. Worker: `cd apps/worker && uv run celery -A worker_app.main:celery_app worker --queues video,export --loglevel=INFO`.
5. Web: `cd apps/web && pnpm dev` → open `http://localhost:3000`.
6. Log in (`dev@local` / `dev`), upload a small mp4, watch SSE updates roll in, edit shots, export.

If any step fails, document and fix or escalate.

- [ ] **Step 4: Tag**

```bash
git tag v0.5.0-frontend
git log --oneline | head -15
```

---

## Done criteria

- `apps/web` is a Next.js 16 + Tailwind v4 app with biome lint, next-intl (Thai default + English), and TanStack Query (with the spec's exact global config).
- All network calls go through hooks in `features/<scope>/hooks/`; no direct axios/fetch in components.
- Auth via JWT cookies (login form → POST /auth/login; AuthGate redirects on 401).
- Sessions list + create + upload (signed-URL PUT direct to R2) + start processing.
- Session detail with ReviewTimeline, ShotSidebarItem (numeric in/out edit + delete), Add manual shot button, Export ZIP button, SSE realtime invalidation.
- Dockerfile present.
- All checks green; tag `v0.5.0-frontend` set.

## Carry-overs

- **Drag-handle UX** for shot in/out points (currently numeric inputs) → Plan 6 frontend polish.
- **VideoPlayer with signed-GET URL** for the raw video (currently empty) — needs a new `/sessions/:id/raw-url` endpoint OR tunneling via the proxy. Plan 6.
- **shadcn-cli integration** for richer UI primitives (Dialog, Toast, etc.) → Plan 6.
- **Real e2e tests with Playwright** (currently just build/lint smoke) → Plan 6 or production hardening.
- All Plan 2/4 carry-overs (IDOR, MediaPipe, idempotent worker, KEDA) still open.
