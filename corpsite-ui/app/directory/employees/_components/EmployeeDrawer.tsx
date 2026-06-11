// FILE: corpsite-ui/app/directory/employees/_components/EmployeeDrawer.tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import type { EmployeeDetails } from "../_lib/types";
import { getEmployee, getPositions, mapApiErrorToMessage, updateEmployee } from "../_lib/api.client";
import { employeeStatusMeta } from "../_lib/employeeStatus";
import EmployeeStatusBadge from "./EmployeeStatusBadge";

type PositionOption = {
  id: number;
  label: string;
};

type EditValues = {
  full_name: string;
  employment_rate: string;
  date_from: string;
  position_id: string;
};

type Props = {
  employeeId: string | null;
  open: boolean;
  onClose: () => void;
  onTerminate: (details: EmployeeDetails) => void;
  onCreateUser?: (details: EmployeeDetails) => void;
  onSaved?: () => void;
  refreshToken?: number;
};

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const dt = new Date(v);
  if (Number.isNaN(dt.getTime())) return String(v);
  return dt.toLocaleDateString("ru-RU");
}

function toIsoDate(v: string | null | undefined): string {
  if (!v) return "";
  const s = String(v).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const dt = new Date(s);
  if (Number.isNaN(dt.getTime())) return "";
  return dt.toISOString().slice(0, 10);
}

function isActive(d: EmployeeDetails): boolean {
  return employeeStatusMeta(d).active;
}

function positionIdOf(details: EmployeeDetails | null): string {
  const id = Number((details as any)?.position?.id ?? 0);
  return Number.isFinite(id) && id > 0 ? String(id) : "";
}

function buildEditValues(details: EmployeeDetails): EditValues {
  return {
    full_name: String((details as any)?.fio ?? (details as any)?.full_name ?? "").trim(),
    employment_rate: String((details as any)?.employment_rate ?? (details as any)?.rate ?? "1"),
    date_from: toIsoDate((details as any)?.date_from ?? (details as any)?.dateFrom),
    position_id: positionIdOf(details),
  };
}

function normalizePositionOptions(raw: unknown): PositionOption[] {
  const items = Array.isArray(raw)
    ? raw
    : raw && typeof raw === "object" && Array.isArray((raw as any).items)
      ? (raw as any).items
      : [];

  return items
    .map((p: any) => {
      const id = Number(p?.position_id ?? p?.id ?? 0);
      const label = String(p?.name ?? `#${id}`).trim();
      return { id, label } as PositionOption;
    })
    .filter((p: PositionOption) => Number.isFinite(p.id) && p.id > 0)
    .sort((a: PositionOption, b: PositionOption) => a.label.localeCompare(b.label, "ru"));
}

export default function EmployeeDrawer({
  employeeId,
  open,
  onClose,
  onTerminate,
  onCreateUser,
  onSaved,
  refreshToken = 0,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [details, setDetails] = useState<EmployeeDetails | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [editValues, setEditValues] = useState<EditValues>({
    full_name: "",
    employment_rate: "1",
    date_from: "",
    position_id: "",
  });
  const [positionOptions, setPositionOptions] = useState<PositionOption[]>([]);
  const [positionsLoading, setPositionsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const loadDetails = useCallback(async () => {
    if (!employeeId) {
      setDetails(null);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const d = await getEmployee(employeeId);
      setDetails(d);
    } catch (e) {
      setDetails(null);
      setError(mapApiErrorToMessage(e));
    } finally {
      setLoading(false);
    }
  }, [employeeId]);

  useEffect(() => {
    if (!open || !employeeId) {
      setDetails(null);
      setError(null);
      setMode("view");
      setSaveError(null);
      return;
    }

    void loadDetails();
  }, [employeeId, open, refreshToken, loadDetails]);

  useEffect(() => {
    if (mode !== "edit" || !details) return;
    setEditValues(buildEditValues(details));
    setSaveError(null);
  }, [mode, details]);

  async function handleEnterEdit() {
    if (!details || !isActive(details)) return;

    setMode("edit");
    setSaveError(null);
    setEditValues(buildEditValues(details));
    setPositionsLoading(true);

    try {
      const raw = await getPositions({ limit: 500, offset: 0 });
      setPositionOptions(normalizePositionOptions(raw));
    } catch {
      setPositionOptions([]);
    } finally {
      setPositionsLoading(false);
    }
  }

  function handleCancelEdit() {
    setMode("view");
    setSaveError(null);
    if (details) setEditValues(buildEditValues(details));
  }

  async function handleSaveEdit() {
    if (!employeeId || !details) return;

    setSaving(true);
    setSaveError(null);

    try {
      const updated = await updateEmployee(employeeId, {
        full_name: editValues.full_name.trim(),
        employment_rate: Number(editValues.employment_rate),
        date_from: editValues.date_from || null,
        position_id: Number(editValues.position_id),
      });

      setDetails(updated);
      setMode("view");
      onSaved?.();
    } catch (e) {
      setSaveError(mapApiErrorToMessage(e));
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  const fio =
    mode === "edit"
      ? editValues.full_name || (loading ? "Загрузка..." : "Сотрудник")
      : (details as any)?.fio ??
        (details as any)?.full_name ??
        (details as any)?.fullName ??
        (loading ? "Загрузка..." : "Сотрудник");

  const tabNo = details
    ? (details as any)?.id ?? (details as any)?.employee_id ?? employeeId
    : "";

  const orgUnitName =
    (details as any)?.org_unit?.name ??
    (details as any)?.orgUnit?.name ??
    (details as any)?.org_unit_name ??
    (details as any)?.orgUnitName ??
    null;

  const departmentName =
    (details as any)?.department?.name ??
    (details as any)?.department_name ??
    (details as any)?.departmentName ??
    null;

  const orgUnitDisplay = orgUnitName ?? departmentName ?? "—";

  const positionName =
    (details as any)?.position?.name ??
    (details as any)?.position_name ??
    (details as any)?.positionName ??
    "—";

  const rate = (details as any)?.employment_rate ?? (details as any)?.rate ?? "—";
  const dateFrom = fmtDate((details as any)?.date_from ?? (details as any)?.dateFrom);
  const dateTo = fmtDate((details as any)?.date_to ?? (details as any)?.dateTo);

  const linkedUser = (details as any)?.user ?? null;
  const canEdit = Boolean(details && isActive(details));

  const positionSelectOptions = (() => {
    const currentId = Number(editValues.position_id || positionIdOf(details));
    const hasCurrent = positionOptions.some((p) => p.id === currentId);
    if (Number.isFinite(currentId) && currentId > 0 && !hasCurrent && positionName !== "—") {
      return [{ id: currentId, label: positionName }, ...positionOptions];
    }
    return positionOptions;
  })();

  function userStatusLabel(active: boolean | null | undefined): string {
    if (active === true) return "Активен";
    if (active === false) return "Неактивен";
    return "—";
  }

  function telegramAccessLabel(user: Record<string, unknown> | null | undefined): string | null {
    if (!user) return null;

    const hasUsername = "telegram_username" in user || "telegramUsername" in user;
    const hasId = "telegram_id" in user || "telegramId" in user;
    if (!hasUsername && !hasId) return null;

    const username = user.telegram_username ?? user.telegramUsername;
    if (username != null && String(username).trim()) {
      const s = String(username).trim();
      return s.startsWith("@") ? s : `@${s}`;
    }

    const id = user.telegram_id ?? user.telegramId;
    if (id != null && String(id).trim()) return String(id).trim();

    return "—";
  }

  const telegramAccess = linkedUser
    ? telegramAccessLabel(linkedUser as Record<string, unknown>)
    : null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-zinc-600/35 dark:bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative ml-auto flex h-full w-full max-w-[860px] flex-col border-l border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 px-6 py-5">
          <div className="min-w-0">
            {mode === "edit" ? (
              <input
                value={editValues.full_name}
                onChange={(e) => setEditValues((prev) => ({ ...prev, full_name: e.target.value }))}
                className="w-full rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-2xl font-semibold text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
                placeholder="ФИО"
                autoComplete="off"
                spellCheck={false}
              />
            ) : (
              <h2 className="truncate text-2xl font-semibold leading-tight text-zinc-900 dark:text-zinc-50">{fio}</h2>
            )}
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{details ? `Таб. № ${tabNo}` : ""}</p>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {mode === "view" && canEdit ? (
              <button
                type="button"
                onClick={() => void handleEnterEdit()}
                className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
              >
                Изменить
              </button>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Закрыть
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {error ? (
            <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
              {error}
            </div>
          ) : null}

          {saveError ? (
            <div className="mb-4 rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
              {saveError}
            </div>
          ) : null}

          {details ? (
            <div className="space-y-5">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Статус</div>
                  <div className="mt-1">
                    <EmployeeStatusBadge item={details} />
                  </div>
                </div>

                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Отделение</div>
                  <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{orgUnitDisplay}</div>
                </div>

                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Должность</div>
                  {mode === "edit" ? (
                    <select
                      value={editValues.position_id}
                      onChange={(e) => setEditValues((prev) => ({ ...prev, position_id: e.target.value }))}
                      disabled={positionsLoading}
                      className="mt-1 w-full rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400 disabled:opacity-60"
                    >
                      <option value="">
                        {positionsLoading ? "Загрузка должностей…" : "Выберите должность"}
                      </option>
                      {positionSelectOptions.map((opt) => (
                        <option key={opt.id} value={String(opt.id)}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{positionName}</div>
                  )}
                </div>

                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Ставка</div>
                  {mode === "edit" ? (
                    <input
                      type="number"
                      min="0.01"
                      max="2"
                      step="0.01"
                      value={editValues.employment_rate}
                      onChange={(e) => setEditValues((prev) => ({ ...prev, employment_rate: e.target.value }))}
                      className="mt-1 w-full rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
                    />
                  ) : (
                    <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{String(rate)}</div>
                  )}
                </div>

                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Дата приёма</div>
                  {mode === "edit" ? (
                    <input
                      type="date"
                      value={editValues.date_from}
                      onChange={(e) => setEditValues((prev) => ({ ...prev, date_from: e.target.value }))}
                      className="mt-1 w-full rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
                    />
                  ) : (
                    <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{dateFrom}</div>
                  )}
                </div>

                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Дата по</div>
                  <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{dateTo}</div>
                </div>
              </div>

              {mode === "view" ? (
                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Период работы</div>
                  <div className="mt-2 text-sm text-zinc-900 dark:text-zinc-50">
                    {dateFrom} — {dateTo}
                  </div>
                </div>
              ) : null}

              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                <div className="text-xs text-zinc-600 dark:text-zinc-400">Учётная запись Corpsite</div>
                {linkedUser ? (
                  <div className="mt-2 space-y-1 text-sm text-zinc-900 dark:text-zinc-50">
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">Логин: </span>
                      {linkedUser.login ?? "—"}
                    </div>
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">Роль доступа: </span>
                      {linkedUser.role_name ?? linkedUser.role_id ?? "—"}
                    </div>
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">Статус доступа: </span>
                      {userStatusLabel(linkedUser.is_active)}
                    </div>
                    {telegramAccess != null ? (
                      <div>
                        <span className="text-zinc-600 dark:text-zinc-400">Telegram: </span>
                        {telegramAccess}
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="space-y-1">
                      <div className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
                        Доступ к Corpsite не создан
                      </div>
                      <div className="text-sm text-zinc-700 dark:text-zinc-300">
                        Создайте доступ, если сотрудник должен входить в систему или получать задачи.
                      </div>
                    </div>
                    {onCreateUser && mode === "view" ? (
                      <button
                        type="button"
                        onClick={() => onCreateUser(details)}
                        className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500"
                      >
                        Создать доступ к Corpsite
                      </button>
                    ) : null}
                  </div>
                )}
              </div>
            </div>
          ) : loading ? (
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Загрузка данных...</div>
          ) : null}
        </div>

        {mode === "edit" ? (
          <div className="flex items-center justify-end gap-3 border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
            <button
              type="button"
              className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
              onClick={handleCancelEdit}
              disabled={saving}
            >
              Отмена
            </button>
            <button
              type="button"
              className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
              onClick={() => void handleSaveEdit()}
              disabled={saving || positionsLoading}
            >
              {saving ? "Сохранение..." : "Сохранить"}
            </button>
          </div>
        ) : details && isActive(details) ? (
          <div className="border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
            <button
              type="button"
              className="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white/50 dark:bg-zinc-900/50 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
              onClick={() => onTerminate(details)}
            >
              Завершить работу
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
