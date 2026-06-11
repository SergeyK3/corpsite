// FILE: corpsite-ui/app/directory/employees/_components/EmployeeDrawer.tsx
"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
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

function userStatusLabel(active: boolean | null | undefined): string {
  if (active === true) return "Активен";
  if (active === false) return "Неактивен";
  return "—";
}

function resolveTelegramLabel(user: Record<string, unknown> | null | undefined): string {
  if (!user) return "Telegram не привязан";

  const username = user.telegram_username ?? user.telegramUsername;
  if (username != null && String(username).trim()) {
    const s = String(username).trim();
    return s.startsWith("@") ? s : `@${s}`;
  }

  const id = user.telegram_id ?? user.telegramId;
  if (id != null && String(id).trim()) return String(id).trim();

  return "Telegram не привязан";
}

function SectionBlock({
  title,
  children,
  className = "",
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={className}>
      <h3 className="mb-3 text-sm font-medium text-zinc-900 dark:text-zinc-50">{title}</h3>
      {children}
    </section>
  );
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

  const displayFio =
    (details as any)?.fio ??
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
  const telegramLabel = resolveTelegramLabel(linkedUser as Record<string, unknown> | null);

  const positionSelectOptions = (() => {
    const currentId = Number(editValues.position_id || positionIdOf(details));
    const hasCurrent = positionOptions.some((p) => p.id === currentId);
    if (Number.isFinite(currentId) && currentId > 0 && !hasCurrent && positionName !== "—") {
      return [{ id: currentId, label: positionName }, ...positionOptions];
    }
    return positionOptions;
  })();

  const editableFieldClass =
    "mt-1 w-full rounded-lg border border-blue-300 dark:border-blue-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-200 dark:focus:ring-blue-900/40 disabled:opacity-60";
  const editableCardClass =
    "rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50/40 dark:bg-blue-950/20 p-4";
  const readOnlyCardClass =
    "rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4";

  function handleBackdropClick() {
    if (mode === "edit") {
      handleCancelEdit();
      return;
    }
    onClose();
  }

  function renderOrgUnitCorrectionStub() {
    return (
      <div className="mt-4 rounded-lg border border-amber-200 dark:border-amber-900/50 bg-amber-50/60 dark:bg-amber-950/20 p-3">
        <p className="text-xs leading-relaxed text-amber-900 dark:text-amber-200/90">
          Используйте это действие только если отделение было указано неверно при импорте или первичном
          заполнении. Это не кадровый перевод.
        </p>
        <button
          type="button"
          disabled
          title="Функция будет доступна в следующем этапе HR"
          className="mt-3 rounded-lg border border-amber-300 dark:border-amber-800 bg-white/70 dark:bg-zinc-900/60 px-3 py-2 text-sm text-zinc-700 dark:text-zinc-300 opacity-70 cursor-not-allowed"
        >
          Исправить ошибочное отделение
        </button>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-zinc-600/35 dark:bg-black/50 backdrop-blur-sm" onClick={handleBackdropClick} />
      <div className="relative ml-auto flex h-full w-full max-w-[860px] flex-col border-l border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-2xl">
        <div
          className={[
            "flex items-start justify-between gap-4 border-b px-6 py-5",
            mode === "edit"
              ? "border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/20"
              : "border-zinc-200 dark:border-zinc-800",
          ].join(" ")}
        >
          <div className="min-w-0">
            {mode === "edit" ? (
              <>
                <h2 className="text-2xl font-semibold leading-tight text-zinc-900 dark:text-zinc-50">
                  Редактирование сотрудника
                </h2>
                <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                  {displayFio}
                  {details ? ` · Таб. № ${tabNo}` : ""}
                </p>
              </>
            ) : (
              <>
                <h2 className="truncate text-2xl font-semibold leading-tight text-zinc-900 dark:text-zinc-50">
                  {displayFio}
                </h2>
                <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{details ? `Таб. № ${tabNo}` : ""}</p>
              </>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {mode === "edit" ? (
              <>
                <button
                  type="button"
                  className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-60"
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
              </>
            ) : (
              <>
                {canEdit ? (
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
              </>
            )}
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
            <div className="space-y-6">
              {mode === "edit" ? (
                <SectionBlock title="Изменяемые данные">
                  <div className="rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50/30 dark:bg-blue-950/10 p-4">
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <div className={editableCardClass}>
                        <label htmlFor="employee-drawer-full-name" className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                          ФИО
                        </label>
                        <input
                          id="employee-drawer-full-name"
                          value={editValues.full_name}
                          onChange={(e) => setEditValues((prev) => ({ ...prev, full_name: e.target.value }))}
                          className={editableFieldClass}
                          placeholder="ФИО сотрудника"
                          autoComplete="off"
                          spellCheck={false}
                        />
                      </div>

                      <div className={editableCardClass}>
                        <label htmlFor="employee-drawer-position" className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                          Должность
                        </label>
                        <select
                          id="employee-drawer-position"
                          value={editValues.position_id}
                          onChange={(e) => setEditValues((prev) => ({ ...prev, position_id: e.target.value }))}
                          disabled={positionsLoading}
                          className={editableFieldClass}
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
                      </div>

                      <div className={editableCardClass}>
                        <label htmlFor="employee-drawer-rate" className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                          Ставка
                        </label>
                        <input
                          id="employee-drawer-rate"
                          type="number"
                          min="0.01"
                          max="2"
                          step="0.01"
                          value={editValues.employment_rate}
                          onChange={(e) => setEditValues((prev) => ({ ...prev, employment_rate: e.target.value }))}
                          className={editableFieldClass}
                        />
                      </div>

                      <div className={editableCardClass}>
                        <label htmlFor="employee-drawer-date-from" className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                          Дата приёма
                        </label>
                        <input
                          id="employee-drawer-date-from"
                          type="date"
                          value={editValues.date_from}
                          onChange={(e) => setEditValues((prev) => ({ ...prev, date_from: e.target.value }))}
                          className={editableFieldClass}
                        />
                      </div>
                    </div>
                  </div>
                </SectionBlock>
              ) : (
                <SectionBlock title="Основные данные">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <div className={readOnlyCardClass}>
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Статус</div>
                      <div className="mt-1">
                        <EmployeeStatusBadge item={details} />
                      </div>
                    </div>

                    <div className={readOnlyCardClass}>
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Должность</div>
                      <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{positionName}</div>
                    </div>

                    <div className={readOnlyCardClass}>
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Ставка</div>
                      <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{String(rate)}</div>
                    </div>

                    <div className={readOnlyCardClass}>
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Дата приёма</div>
                      <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{dateFrom}</div>
                    </div>

                    <div className={readOnlyCardClass}>
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Дата по</div>
                      <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{dateTo}</div>
                    </div>
                  </div>
                </SectionBlock>
              )}

              {mode === "edit" ? (
                <SectionBlock title="Данные только для просмотра">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <div className={readOnlyCardClass}>
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Статус</div>
                      <div className="mt-1">
                        <EmployeeStatusBadge item={details} />
                      </div>
                    </div>

                    <div className={readOnlyCardClass}>
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Отделение</div>
                      <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{orgUnitDisplay}</div>
                    </div>

                    <div className={readOnlyCardClass}>
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Дата по</div>
                      <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{dateTo}</div>
                    </div>
                  </div>
                </SectionBlock>
              ) : (
                <SectionBlock title="Отделение">
                  <div className={readOnlyCardClass}>
                    <div className="text-xs text-zinc-600 dark:text-zinc-400">Текущее отделение</div>
                    <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{orgUnitDisplay}</div>
                    {renderOrgUnitCorrectionStub()}
                  </div>
                </SectionBlock>
              )}

              <SectionBlock title="Учётная запись Corpsite">
                <div className={readOnlyCardClass}>
                  {linkedUser ? (
                    <div className="space-y-1 text-sm text-zinc-900 dark:text-zinc-50">
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
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
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
              </SectionBlock>

              <SectionBlock title="Telegram">
                <div className={readOnlyCardClass}>
                  <div className="text-sm text-zinc-900 dark:text-zinc-50">{telegramLabel}</div>
                </div>
              </SectionBlock>
            </div>
          ) : loading ? (
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Загрузка данных...</div>
          ) : null}
        </div>

        {mode === "view" && details && isActive(details) ? (
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
