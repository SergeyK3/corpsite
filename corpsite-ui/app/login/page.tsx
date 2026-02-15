// FILE: corpsite-ui/app/login/page.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { apiAuthLogin } from "@/lib/api";

const LAST_LOGIN_KEY = "corpsite.lastLogin";

function normalizeLogin(v: string): string {
  return (v || "").trim().toLowerCase();
}

export default function LoginPage() {
  const router = useRouter();

  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const passwordRef = useRef<HTMLInputElement | null>(null);
  const saveTimerRef = useRef<number | null>(null);

  // Load last login
  useEffect(() => {
    try {
      const saved = localStorage.getItem(LAST_LOGIN_KEY);
      if (saved) {
        setLogin(saved);
        setTimeout(() => passwordRef.current?.focus(), 0);
      }
    } catch {
      // ignore
    }
  }, []);

  // Persist last login (debounced)
  useEffect(() => {
    try {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = window.setTimeout(() => {
        localStorage.setItem(LAST_LOGIN_KEY, normalizeLogin(login));
      }, 250);
    } catch {
      // ignore
    }
    return () => {
      try {
        if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
      } catch {
        // ignore
      }
    };
  }, [login]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);

    const l = normalizeLogin(login);
    const p = (password ?? "").toString();

    if (!l) {
      setBusy(false);
      setError("Введите логин.");
      return;
    }
    if (!p) {
      setBusy(false);
      setError("Введите пароль.");
      return;
    }

    try {
      // backend auth
      await apiAuthLogin({ login: l, password: p });

      // store last login for convenience
      try {
        localStorage.setItem(LAST_LOGIN_KEY, l);
      } catch {
        // ignore
      }

      router.replace("/");
    } catch (e: any) {
      const msg =
        String(e?.details?.detail ?? e?.message ?? "Не удалось выполнить вход").trim() ||
        "Не удалось выполнить вход";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-0px)] flex items-center justify-center px-4">
      <div className="w-full max-w-md rounded-2xl border bg-white p-6 shadow-sm">
        <div className="mb-6">
          <h1 className="text-xl font-semibold">Вход</h1>
          <p className="mt-1 text-sm text-muted-foreground">Введите свой логин и пароль.</p>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="login" className="text-sm font-medium">
              Логин
            </label>
            <input
              id="login"
              name="login"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              autoComplete="username"
              placeholder="Введите логин"
              className="w-full rounded-xl border px-3 py-2 outline-none focus:ring-2 focus:ring-black/10"
              disabled={busy}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium">
              Пароль
            </label>

            <div className="relative">
              <input
                ref={passwordRef}
                id="password"
                name="password"
                type={showPwd ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="Введите пароль"
                className="w-full rounded-xl border px-3 py-2 pr-12 outline-none focus:ring-2 focus:ring-black/10"
                disabled={busy}
              />

              <button
                type="button"
                onClick={() => setShowPwd((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg border px-2 py-1 text-xs hover:bg-black/5 disabled:opacity-60"
                disabled={busy}
                aria-label={showPwd ? "Скрыть пароль" : "Показать пароль"}
                title={showPwd ? "Скрыть пароль" : "Показать пароль"}
              >
                {showPwd ? "🙈" : "👁"}
              </button>
            </div>
          </div>

          {error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          <button
            type="submit"
            className="w-full rounded-xl bg-black px-3 py-2 text-white disabled:opacity-60"
            disabled={busy}
          >
            {busy ? "Входим..." : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
}
