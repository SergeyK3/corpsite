"use client";

import * as React from "react";

import { listPlatformRoleCatalog, type PlatformRoleOption } from "@/lib/platformRoleCatalog";

export type UserRoleEditFormValues = {
  role_id: string;
};

type UserRoleEditFormProps = {
  login: string;
  currentRoleLabel: string;
  currentRoleId: number | null | undefined;
  saving?: boolean;
  error?: string | null;
  onCancel: () => void;
  onSubmit: (roleId: number) => Promise<void> | void;
};

function formatRoleOption(opt: PlatformRoleOption): string {
  return opt.code ? `${opt.label} (${opt.code})` : opt.label;
}

export default function UserRoleEditForm({
  login,
  currentRoleLabel,
  currentRoleId,
  saving = false,
  error = null,
  onCancel,
  onSubmit,
}: UserRoleEditFormProps) {
  const [roleOptions, setRoleOptions] = React.useState<PlatformRoleOption[]>([]);
  const [rolesLoading, setRolesLoading] = React.useState(true);
  const [rolesError, setRolesError] = React.useState<string | null>(null);
  const [selectedRoleId, setSelectedRoleId] = React.useState(
    currentRoleId != null ? String(currentRoleId) : "",
  );

  React.useEffect(() => {
    setSelectedRoleId(currentRoleId != null ? String(currentRoleId) : "");
  }, [currentRoleId, login]);

  React.useEffect(() => {
    let cancelled = false;
    setRolesLoading(true);
    setRolesError(null);

    void (async () => {
      try {
        const rows = await listPlatformRoleCatalog();
        if (cancelled) return;
        setRoleOptions(rows);
      } catch (e: unknown) {
        if (cancelled) return;
        setRoleOptions([]);
        setRolesError(e instanceof Error ? e.message : "Не удалось загрузить справочник ролей.");
      } finally {
        if (!cancelled) setRolesLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [login]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const nextRoleId = Number(selectedRoleId);
    if (!Number.isFinite(nextRoleId) || nextRoleId < 1) return;
    await onSubmit(nextRoleId);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50"
    >
      <div className="flex items-start justify-between border-b border-zinc-200 dark:border-zinc-800 px-6 py-5">
        <div>
          <h2 className="text-2xl font-semibold leading-tight text-zinc-900 dark:text-zinc-50">
            Изменить роль Corpsite
          </h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Логин: <span className="font-medium text-zinc-900 dark:text-zinc-50">{login || "—"}</span>
          </p>
        </div>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
        >
          Закрыть
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="space-y-4">
          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="text-xs text-zinc-500">Текущая роль Corpsite</div>
            <div className="mt-1 text-sm font-medium text-zinc-900 dark:text-zinc-50">
              {currentRoleLabel || "—"}
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="user-role-edit-select" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Новая роль Corpsite
            </label>
            <select
              id="user-role-edit-select"
              value={selectedRoleId}
              onChange={(e) => setSelectedRoleId(e.target.value)}
              disabled={rolesLoading || saving}
              className="h-10 rounded-lg border border-zinc-200 bg-white px-3 text-sm text-zinc-900 outline-none disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              required
            >
              <option value="">{rolesLoading ? "Загрузка ролей…" : "Выберите роль"}</option>
              {roleOptions.map((opt) => (
                <option key={opt.id} value={String(opt.id)}>
                  {formatRoleOption(opt)}
                </option>
              ))}
            </select>
            {rolesError ? <p className="text-xs text-red-600 dark:text-red-400">{rolesError}</p> : null}
            {error ? <p className="text-xs text-red-600 dark:text-red-400">{error}</p> : null}
          </div>
        </div>
      </div>

      <div className="flex gap-2 border-t border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <button
          type="submit"
          disabled={saving || rolesLoading || !selectedRoleId}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? "Сохранение…" : "Сохранить"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm text-zinc-800 transition hover:bg-zinc-50 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200"
        >
          Отмена
        </button>
      </div>
    </form>
  );
}
