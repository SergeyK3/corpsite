"use client";

import * as React from "react";

import { apiCreateTelegramBindCode } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import type { APIError, MeInfo, TelegramBindCodeResponse } from "@/lib/types";

const TGBIND_CONFLICT_HINT =
  "Код привязки уже создан. Если вы его потеряли, дождитесь истечения (до 30 минут) или обратитесь к администратору.";

type Props = {
  me: MeInfo | null;
  loading?: boolean;
  onRefresh: () => Promise<void>;
};

function isTelegramBound(me: MeInfo | null): boolean {
  return me?.telegram_bound === true;
}

function formatTelegramUsername(value: string | null | undefined): string | null {
  const raw = String(value ?? "").trim();
  if (!raw) return null;
  return raw.startsWith("@") ? raw : `@${raw}`;
}

function formatExpiresAt(value: string): string {
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function extractErrorCode(err: APIError): string {
  const direct = String(err?.code ?? "").trim();
  if (direct) return direct;

  const details = err?.details;
  if (!details || typeof details !== "object") return "";

  const root = details as Record<string, unknown>;
  if (typeof root.code === "string" && root.code.trim()) return root.code.trim();

  const nested = root.detail;
  if (nested && typeof nested === "object") {
    const code = (nested as Record<string, unknown>).code;
    if (typeof code === "string" && code.trim()) return code.trim();
  }

  return "";
}

function mapBindError(err: unknown): string {
  const e = err as APIError;
  const code = extractErrorCode(e);
  if (Number(e?.status ?? 0) === 409 && code === "TGBIND_CONFLICT_CODE_EXISTS") {
    return TGBIND_CONFLICT_HINT;
  }
  return formatThrownError(err);
}

async function copyText(value: string): Promise<boolean> {
  const text = String(value ?? "").trim();
  if (!text) return false;

  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // fallback below
  }

  try {
    const el = document.createElement("textarea");
    el.value = text;
    el.setAttribute("readonly", "true");
    el.style.position = "fixed";
    el.style.left = "-9999px";
    document.body.appendChild(el);
    el.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(el);
    return ok;
  } catch {
    return false;
  }
}

export default function TelegramBindPanel({ me, loading = false, onRefresh }: Props) {
  const [activeCode, setActiveCode] = React.useState<TelegramBindCodeResponse | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [refreshing, setRefreshing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [copyHint, setCopyHint] = React.useState<string | null>(null);

  const bound = isTelegramBound(me);
  const telegramUsername = formatTelegramUsername(me?.telegram_username);

  React.useEffect(() => {
    if (bound) {
      setActiveCode(null);
    }
  }, [bound]);

  async function onCreateCode() {
    setCreating(true);
    setError(null);
    setCopyHint(null);

    try {
      const body = await apiCreateTelegramBindCode();
      setActiveCode(body);
    } catch (e) {
      setError(mapBindError(e));
    } finally {
      setCreating(false);
    }
  }

  async function onRefreshClick() {
    setRefreshing(true);
    setError(null);
    setCopyHint(null);

    try {
      await onRefresh();
    } catch (e) {
      setError(formatThrownError(e));
    } finally {
      setRefreshing(false);
    }
  }

  async function onCopyCode() {
    if (!activeCode?.code) return;
    const ok = await copyText(activeCode.code);
    setCopyHint(ok ? "Код скопирован" : "Не удалось скопировать код");
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4 text-sm text-zinc-600 dark:text-zinc-400">
        Загрузка статуса Telegram…
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-5 space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Telegram</h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Привязка нужна для уведомлений о задачах в Telegram-боте.
        </p>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
          {error}
        </div>
      ) : null}

      {bound ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-emerald-200 dark:border-emerald-900/55 bg-emerald-50 dark:bg-emerald-950/30 px-4 py-3 text-sm text-emerald-900 dark:text-emerald-100">
            <div className="font-medium">Telegram подключён</div>
            {telegramUsername ? (
              <div className="mt-1 text-emerald-800 dark:text-emerald-200">{telegramUsername}</div>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => void onRefreshClick()}
            disabled={refreshing}
            className="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-60"
          >
            {refreshing ? "Обновление…" : "Обновить статус"}
          </button>
        </div>
      ) : activeCode ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-4 py-3">
            <div className="text-xs text-zinc-600 dark:text-zinc-400">Код привязки</div>
            <div className="mt-2 font-mono text-xl tracking-wide text-zinc-900 dark:text-zinc-50">
              {activeCode.code}
            </div>
            <div className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
              Действует до: {formatExpiresAt(activeCode.expires_at)}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void onCopyCode()}
              className="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-100 dark:hover:bg-zinc-800"
            >
              Скопировать код
            </button>
            <button
              type="button"
              onClick={() => void onCreateCode()}
              disabled={creating}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-60"
            >
              {creating ? "Создание…" : "Создать новый код"}
            </button>
            <button
              type="button"
              onClick={() => void onRefreshClick()}
              disabled={refreshing}
              className="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-60"
            >
              {refreshing ? "Обновление…" : "Обновить статус"}
            </button>
          </div>

          {copyHint ? <div className="text-sm text-zinc-600 dark:text-zinc-400">{copyHint}</div> : null}

          <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900/60 px-4 py-3 text-sm text-zinc-800 dark:text-zinc-200">
            <div className="font-medium">Инструкция</div>
            <ol className="mt-2 list-decimal space-y-1 pl-5">
              <li>Откройте Telegram-бот Corpsite.</li>
              <li>
                Отправьте команду: <span className="font-mono">/bind {activeCode.code}</span>
              </li>
              <li>После успешной привязки нажмите «Обновить статус».</li>
            </ol>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-4 py-3 text-sm text-zinc-800 dark:text-zinc-200">
            Telegram не подключён. Получите код и выполните привязку в боте.
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void onCreateCode()}
              disabled={creating}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-60"
            >
              {creating ? "Создание…" : "Получить код"}
            </button>
            <button
              type="button"
              onClick={() => void onRefreshClick()}
              disabled={refreshing}
              className="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-60"
            >
              {refreshing ? "Обновление…" : "Обновить статус"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
