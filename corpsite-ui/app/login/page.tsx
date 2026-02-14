// FILE: corpsite-ui/app/login/page.tsx
"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { apiAuthLogin } from "../../lib/api";
import { LOGIN_TO_USER_ID } from "../../lib/auth";

export default function LoginPage() {
  const router = useRouter();

  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const knownLogins = useMemo(() => {
    // Подсказки логинов (dev), но сам вход — через backend /auth/login.
    return Object.keys(LOGIN_TO_USER_ID)
      .filter((k) => k && k.trim().length > 0)
      .sort((a, b) => a.localeCompare(b));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;

    const l = (login ?? "").trim();
    const p = (password ?? "").trim();

    if (!l) {
      setError("Введите логин");
      return;
    }
    if (!p) {
      setError("Введите пароль");
      return;
    }

    setError("");
    setBusy(true);

    try {
      await apiAuthLogin({ login: l, password: p });
      router.push("/tasks");
    } catch (e: any) {
      const msg =
        e?.message ||
        e?.details?.detail ||
        e?.details?.message ||
        "Ошибка входа";
      setError(String(msg));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-md px-4 py-12">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
          <div className="text-xl font-semibold">Вход</div>
          <div className="mt-1 text-sm text-zinc-400">
            Авторизация через backend (/auth/login → JWT).
          </div>

          <form onSubmit={onSubmit} className="mt-6 space-y-3">
            <div>
              <div className="text-xs text-zinc-400">Логин</div>
              <input
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                placeholder="например: director@corp.local"
                autoComplete="username"
                className="mt-1 w-full rounded-xl border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-600"
              />
              {knownLogins.length > 0 ? (
                <div className="mt-2 text-xs text-zinc-500">
                  Быстрый выбор:&nbsp;
                  {knownLogins.map((l, idx) => (
                    <button
                      type="button"
                      key={l}
                      onClick={() => setLogin(l)}
                      className="underline decoration-zinc-700 hover:decoration-zinc-300"
                    >
                      {l}
                      {idx < knownLogins.length - 1 ? ", " : ""}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            <div>
              <div className="text-xs text-zinc-400">Пароль</div>
              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type="password"
                autoComplete="current-password"
                className="mt-1 w-full rounded-xl border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-600"
              />
            </div>

            {error ? (
              <div className="rounded-xl border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">
                {error}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-xl border border-zinc-800 bg-zinc-950/60 px-4 py-2 text-sm font-semibold hover:bg-zinc-900/70 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy ? "Вход..." : "Войти"}
            </button>

            <div className="text-xs text-zinc-500">
              <Link
                className="underline decoration-zinc-700 hover:decoration-zinc-300"
                href="/"
              >
                На главную
              </Link>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
