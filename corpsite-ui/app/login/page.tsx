// FILE: corpsite-ui/app/login/page.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { apiAuthLogin, apiAuthMe, apiFetchJson } from "@/lib/api";
import { isAuthed, logout, setSessionLogin } from "@/lib/auth";

const LAST_LOGIN_KEY = "corpsite.lastLogin";

function normalizeLogin(v: string): string {
  return (v || "").trim().toLowerCase();
}

export default function LoginPage() {
  const router = useRouter();

  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [forgotPassword, setForgotPassword] = useState(false);
  const [recoveryRequested, setRecoveryRequested] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState("");
  const [recoveryPassword, setRecoveryPassword] = useState("");
  const [recoveryConfirmation, setRecoveryConfirmation] = useState("");
  const [showRecoveryPassword, setShowRecoveryPassword] = useState(false);
  const [showRecoveryConfirmation, setShowRecoveryConfirmation] = useState(false);
  const [recoveryMessage, setRecoveryMessage] = useState("");
  const [recoveryBusy, setRecoveryBusy] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const passwordRef = useRef<HTMLInputElement | null>(null);
  const saveTimerRef = useRef<number | null>(null);

  // If already authed with a valid token -> go home.
  // Stale tokens are ignored so the form stays usable.
  useEffect(() => {
    if (!isAuthed()) return;

    let cancelled = false;

    void (async () => {
      try {
        await apiAuthMe();
        if (!cancelled) router.replace("/");
      } catch {
        if (!cancelled) logout();
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [router]);

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
      await apiAuthLogin({ login: l, password: p });

      // store login for convenience / diagnostics
      try {
        localStorage.setItem(LAST_LOGIN_KEY, l);
      } catch {
        // ignore
      }
      setSessionLogin(l);

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

  async function requestTelegramRecovery() {
    setRecoveryBusy(true); setRecoveryMessage(""); setRecoveryRequested(true);
    try {
      await apiFetchJson<{ message: string }>("/auth/password-recovery/telegram/request", { method: "POST", body: { login: normalizeLogin(login) }, noAuth: true });
      setRecoveryMessage("Запрос принят. Если Telegram привязан к этой учётной записи, код придёт в Telegram. Проверьте телефон.");
    } catch { setRecoveryMessage("Не удалось связаться с сервером. Повторите попытку позже"); }
    finally { setRecoveryBusy(false); }
  }

  async function completeTelegramRecovery(e: React.FormEvent) {
    e.preventDefault(); setRecoveryBusy(true); setRecoveryMessage("");
    try {
      const result = await apiFetchJson<{ message: string }>("/auth/password-recovery/telegram/complete", { method: "POST", body: { login: normalizeLogin(login), code: recoveryCode, new_password: recoveryPassword, new_password_confirmation: recoveryConfirmation }, noAuth: true });
      setRecoveryMessage(result.message); setRecoveryCode(""); setRecoveryPassword(""); setRecoveryConfirmation("");
    } catch (err: any) { setRecoveryMessage(String(err?.details?.detail ?? "Не удалось изменить пароль.")); }
    finally { setRecoveryBusy(false); }
  }

  return (
    <div className="min-h-[calc(100vh-0px)] flex items-center justify-center px-4">
      <div className="w-full max-w-md rounded-2xl border bg-white dark:bg-zinc-950 p-6 shadow-sm">
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
                {showPwd ? "Скрыть" : "Показать"}
              </button>
            </div>
          </div>

          {error ? (
            <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-3 py-2 text-sm text-red-700 dark:text-red-300">
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
        <div className="mt-4 text-sm">
          <button type="button" className="text-blue-700 underline dark:text-blue-300" onClick={() => setForgotPassword((value) => !value)}>
            Забыли пароль?
          </button>
          {forgotPassword ? <div className="mt-2 space-y-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200" data-testid="telegram-password-recovery">
            <p>Если Telegram подключён, получите одноразовый код. Иначе обратитесь к системному администратору и сообщите свой логин.</p>
            <button type="button" className="rounded-xl border border-zinc-300 bg-white px-3 py-2 text-zinc-900 hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:hover:bg-zinc-800" disabled={recoveryBusy || !normalizeLogin(login)} onClick={() => void requestTelegramRecovery()}>Получить код в Telegram</button>
            {recoveryMessage ? <p role="status">{recoveryMessage}</p> : null}
            {recoveryRequested ? <form className="space-y-3" onSubmit={completeTelegramRecovery}>
              <div className="space-y-1">
                <label htmlFor="telegram-recovery-code" className="text-sm font-medium">Код из Telegram</label>
                <input id="telegram-recovery-code" name="telegram-recovery-code" autoComplete="one-time-code" aria-label="Код из Telegram" value={recoveryCode} onChange={(e) => setRecoveryCode(e.target.value)} inputMode="numeric" maxLength={8} placeholder="Введите код" required className="w-full rounded-xl border border-zinc-300 bg-white px-3 py-2 text-zinc-950 placeholder:text-zinc-500 outline-none focus:ring-2 focus:ring-black/10 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:placeholder:text-zinc-400" />
              </div>
              <div className="space-y-1">
                <label htmlFor="telegram-recovery-password" className="text-sm font-medium">Новый пароль</label>
                <div className="relative">
                  <input id="telegram-recovery-password" name="telegram-recovery-password" autoComplete="new-password" aria-label="Новый пароль" type={showRecoveryPassword ? "text" : "password"} value={recoveryPassword} onChange={(e) => setRecoveryPassword(e.target.value)} minLength={8} placeholder="Введите новый пароль" required className="w-full rounded-xl border border-zinc-300 bg-white px-3 py-2 pr-20 text-zinc-950 placeholder:text-zinc-500 outline-none focus:ring-2 focus:ring-black/10 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:placeholder:text-zinc-400" />
                  <button type="button" onClick={() => setShowRecoveryPassword((value) => !value)} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg border px-2 py-1 text-xs hover:bg-black/5 disabled:opacity-60" disabled={recoveryBusy} aria-label={showRecoveryPassword ? "Скрыть новый пароль" : "Показать новый пароль"}>{showRecoveryPassword ? "Скрыть" : "Показать"}</button>
                </div>
              </div>
              <div className="space-y-1">
                <label htmlFor="telegram-recovery-confirmation" className="text-sm font-medium">Подтверждение нового пароля</label>
                <div className="relative">
                  <input id="telegram-recovery-confirmation" name="telegram-recovery-confirmation" autoComplete="new-password" aria-label="Подтверждение нового пароля" type={showRecoveryConfirmation ? "text" : "password"} value={recoveryConfirmation} onChange={(e) => setRecoveryConfirmation(e.target.value)} minLength={8} placeholder="Повторите новый пароль" required className="w-full rounded-xl border border-zinc-300 bg-white px-3 py-2 pr-20 text-zinc-950 placeholder:text-zinc-500 outline-none focus:ring-2 focus:ring-black/10 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:placeholder:text-zinc-400" />
                  <button type="button" onClick={() => setShowRecoveryConfirmation((value) => !value)} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg border px-2 py-1 text-xs hover:bg-black/5 disabled:opacity-60" disabled={recoveryBusy} aria-label={showRecoveryConfirmation ? "Скрыть подтверждение нового пароля" : "Показать подтверждение нового пароля"}>{showRecoveryConfirmation ? "Скрыть" : "Показать"}</button>
                </div>
              </div>
              <button className="w-full rounded-xl border border-zinc-300 bg-white px-3 py-2 text-zinc-900 hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:hover:bg-zinc-800" disabled={recoveryBusy}>Установить новый пароль</button>
            </form> : null}
          </div> : null}
        </div>
      </div>
    </div>
  );
}
