// FILE: corpsite-ui/app/directory/working-contacts/_components/WorkingContactsDrawer.tsx
"use client";

import * as React from "react";

type WorkingContactItem = {
  id?: number;
  user_id?: number | null;
  full_name?: string | null;
  login?: string | null;
  phone?: string | null;
  telegram_username?: string | null;
  role_name?: string | null;
  role_name_ru?: string | null;
  unit_name?: string | null;
  unit_name_ru?: string | null;
  is_active?: boolean | null;
};

type WorkingContactsDrawerProps = {
  open: boolean;
  item: WorkingContactItem | null;
  onClose: () => void;
};

function textOrDash(value?: string | null): string {
  return String(value ?? "").trim() || "—";
}

function displayTelegram(item: WorkingContactItem | null): string {
  const raw = String(item?.telegram_username ?? "").trim();
  if (!raw) return "—";
  return raw.startsWith("@") ? raw : `@${raw}`;
}

function displayRole(item: WorkingContactItem | null): string {
  return textOrDash(item?.role_name_ru ?? item?.role_name);
}

function displayUnit(item: WorkingContactItem | null): string {
  return textOrDash(item?.unit_name_ru ?? item?.unit_name);
}

function InfoBlock({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
      <div className="text-[11px] uppercase tracking-[0.08em] text-zinc-500">{label}</div>
      <div className="mt-2 text-sm text-zinc-100">{value}</div>
    </div>
  );
}

export default function WorkingContactsDrawer({
  open,
  item,
  onClose,
}: WorkingContactsDrawerProps) {
  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && open) onClose();
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />

      <div className="relative ml-auto flex h-full w-full max-w-[760px] flex-col border-l border-zinc-800 bg-[#050816] shadow-2xl">
        <div className="flex items-start justify-between border-b border-zinc-800 px-6 py-5">
          <div>
            <h2 className="text-2xl font-semibold leading-tight text-zinc-100">
              {textOrDash(item?.full_name)}
            </h2>
            <p className="mt-1 text-sm text-zinc-400">Рабочий контакт</p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
          >
            Закрыть
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
            <div className="flex flex-wrap gap-2">
              <span
                className={[
                  "inline-flex rounded-full border px-2.5 py-1 text-xs font-medium",
                  item?.is_active
                    ? "border-emerald-800 bg-emerald-950/30 text-emerald-300"
                    : "border-zinc-700 bg-zinc-900/40 text-zinc-400",
                ].join(" ")}
              >
                {item?.is_active ? "Активный" : "Неактивный"}
              </span>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <InfoBlock label="ID" value={item?.id ?? item?.user_id ?? "—"} />
              <InfoBlock label="Логин" value={textOrDash(item?.login)} />
              <InfoBlock label="Телефон" value={textOrDash(item?.phone)} />
              <InfoBlock label="Telegram" value={displayTelegram(item)} />
              <InfoBlock label="Роль" value={displayRole(item)} />
              <InfoBlock label="Отделение" value={displayUnit(item)} />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-zinc-800 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}