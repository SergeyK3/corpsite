"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import TelegramBindPanel from "@/components/TelegramBindPanel";
import { apiAuthMe } from "@/lib/api";
import { isAuthed, logout as authLogout } from "@/lib/auth";
import { formatThrownError } from "@/lib/i18n";
import type { MeInfo } from "@/lib/types";

function isUnauthorized(err: unknown): boolean {
  return Number((err as { status?: number })?.status ?? 0) === 401;
}

export default function ProfilePageClient() {
  const router = useRouter();
  const [me, setMe] = React.useState<MeInfo | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const loadMe = React.useCallback(async () => {
    const data = await apiAuthMe();
    setMe(data);
    return data;
  }, []);

  React.useEffect(() => {
    let alive = true;

    void (async () => {
      if (!isAuthed()) {
        router.replace("/login");
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const data = await loadMe();
        if (alive) setMe(data);
      } catch (e) {
        if (!alive) return;
        if (isUnauthorized(e)) {
          authLogout();
          router.replace("/login");
          return;
        }
        setError(formatThrownError(e));
        setMe(null);
      } finally {
        if (alive) setLoading(false);
      }
    })();

    return () => {
      alive = false;
    };
  }, [loadMe, router]);

  const roleTitle = String(me?.role_name_ru ?? me?.role_name ?? "").trim() || "Сотрудник";
  const login = String(me?.login ?? "").trim();

  return (
    <div className="mx-auto w-full max-w-2xl space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">Профиль</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Управление привязкой Telegram и параметрами аккаунта.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
          {error}
        </div>
      ) : null}

      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-5 space-y-2">
        <div className="text-xs text-zinc-600 dark:text-zinc-400">Аккаунт</div>
        <div className="text-sm text-zinc-900 dark:text-zinc-50">{login || "—"}</div>
        <div className="text-sm text-zinc-600 dark:text-zinc-400">{roleTitle}</div>
      </div>

      <TelegramBindPanel
        me={me}
        loading={loading}
        onRefresh={async () => {
          const data = await loadMe();
          setMe(data);
        }}
      />
    </div>
  );
}
