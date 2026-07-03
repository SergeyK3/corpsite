// FILE: corpsite-ui/app/directory/employees/_components/EmployeeDrawer.tsx
"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";

import { apiAuthMe } from "@/lib/api";
import { isPrivilegedOperator } from "@/lib/adminNav";
import { EmployeeImportCardSection } from "../../personnel/_components/EmployeeImportCardSection";
import type { EmployeeDetails } from "../_lib/types";
import {
  getEmployee,
  getEmployees,
  getPositions,
  mapApiErrorToMessage,
  transferEmployee,
  updateEmployee,
} from "../_lib/api.client";
import { employeeStatusMeta } from "../_lib/employeeStatus";
import EmployeeStatusBadge from "./EmployeeStatusBadge";
import EmployeeTransferDrawer from "./EmployeeTransferDrawer";
import EmployeeAccountSections from "./EmployeeAccountSections";
import EmployeeProfessionalProfile from "./EmployeeProfessionalProfile";
import type { EmployeeTransferFormValues } from "./EmployeeTransferForm";

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
  onSaved?: () => void;
  refreshToken?: number;
  /** Полный справочник из parent (как в Create); drawer догружает при необходимости. */
  positionCatalogOptions?: PositionOption[];
  /** Management-facing read-only view — no edit/transfer/account actions. */
  readOnly?: boolean;
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

function employeeOrgUnitId(details: EmployeeDetails | null | undefined): number | null {
  if (!details) return null;

  const fromOrgUnit = Number((details as any)?.org_unit?.unit_id ?? (details as any)?.orgUnit?.unit_id ?? 0);
  if (Number.isFinite(fromOrgUnit) && fromOrgUnit > 0) return Math.trunc(fromOrgUnit);

  const fromTopLevel = Number((details as any)?.org_unit_id ?? (details as any)?.unit_id ?? 0);
  if (Number.isFinite(fromTopLevel) && fromTopLevel > 0) return Math.trunc(fromTopLevel);

  const fromDepartment = Number((details as any)?.department?.id ?? 0);
  if (Number.isFinite(fromDepartment) && fromDepartment > 0) return Math.trunc(fromDepartment);

  return null;
}

function buildEditValues(details: EmployeeDetails): EditValues {
  return {
    full_name: String((details as any)?.fio ?? (details as any)?.full_name ?? "").trim(),
    employment_rate: String((details as any)?.employment_rate ?? (details as any)?.rate ?? "1"),
    date_from: toIsoDate((details as any)?.date_from ?? (details as any)?.dateFrom),
    position_id: positionIdOf(details),
  };
}

function employeePositionId(item: {
  position?: { id?: number | null } | null;
  position_id?: number | null;
}): number {
  const fromNested = Number(item?.position?.id ?? 0);
  if (Number.isFinite(fromNested) && fromNested > 0) return fromNested;

  const fromFlat = Number(item?.position_id ?? 0);
  return Number.isFinite(fromFlat) && fromFlat > 0 ? fromFlat : 0;
}

function positionOptionsFromEmployees(items: unknown[]): PositionOption[] {
  const byId = new Map<number, string>();

  for (const item of items) {
    const row = item as {
      position?: { id?: number | null; name?: string | null } | null;
      position_id?: number | null;
    };
    const id = employeePositionId(row);
    if (id <= 0) continue;

    const label = String(row?.position?.name ?? `#${id}`).trim() || `#${id}`;
    byId.set(id, label);
  }

  return [...byId.entries()]
    .map(([id, label]) => ({ id, label }))
    .sort((a, b) => a.label.localeCompare(b.label, "ru"));
}

function mergePositionOptions(...groups: PositionOption[][]): PositionOption[] {
  const byId = new Map<number, string>();
  for (const group of groups) {
    for (const opt of group) {
      if (Number.isFinite(opt.id) && opt.id > 0) {
        byId.set(opt.id, opt.label);
      }
    }
  }
  return [...byId.entries()]
    .map(([id, label]) => ({ id, label }))
    .sort((a, b) => a.label.localeCompare(b.label, "ru"));
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
  onSaved,
  refreshToken = 0,
  positionCatalogOptions = [],
  readOnly = false,
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
  const [allPositionOptions, setAllPositionOptions] = useState<PositionOption[]>([]);
  const [unitPositionIds, setUnitPositionIds] = useState<Set<number> | null>(null);
  const [showAllPositions, setShowAllPositions] = useState(false);
  const [positionsLoading, setPositionsLoading] = useState(false);
  const [positionsOrgUnitHint, setPositionsOrgUnitHint] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [transferOpen, setTransferOpen] = useState(false);
  const [transferSaving, setTransferSaving] = useState(false);
  const [transferError, setTransferError] = useState<string | null>(null);
  const [eventsRefreshToken, setEventsRefreshToken] = useState(0);
  const [privilegedOperator, setPrivilegedOperator] = useState(false);

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
    if (!open) {
      setPrivilegedOperator(false);
      return;
    }

    let cancelled = false;
    void apiAuthMe()
      .then((me) => {
        if (!cancelled) setPrivilegedOperator(isPrivilegedOperator(me));
      })
      .catch(() => {
        if (!cancelled) setPrivilegedOperator(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open]);

  const accountAllowRoleEdit = readOnly ? privilegedOperator : true;

  useEffect(() => {
    if (!open || !employeeId) {
      setDetails(null);
      setError(null);
      setMode("view");
      setSaveError(null);
      setTransferOpen(false);
      setTransferError(null);
      setPositionsOrgUnitHint(null);
      setAllPositionOptions([]);
      setUnitPositionIds(null);
      setShowAllPositions(false);
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
    setPositionsOrgUnitHint(null);
    setShowAllPositions(false);
    setAllPositionOptions([]);
    setUnitPositionIds(null);
    setPositionsLoading(true);

    const orgUnitId = employeeOrgUnitId(details);

    try {
      let unitIds = new Set<number>();
      let unitOptionsFromEmployees: PositionOption[] = [];

      if (orgUnitId != null) {
        try {
          const employeesRes = await getEmployees({
            status: "all",
            org_unit_id: orgUnitId,
            include_children: false,
            limit: 200,
            offset: 0,
          });
          unitOptionsFromEmployees = positionOptionsFromEmployees(employeesRes?.items ?? []);
          unitIds = new Set(unitOptionsFromEmployees.map((p) => p.id));
          setUnitPositionIds(unitIds);
          setPositionsOrgUnitHint(null);
        } catch {
          setUnitPositionIds(new Set());
          setShowAllPositions(true);
          setPositionsOrgUnitHint(
            "Не удалось загрузить должности отделения — показан полный справочник"
          );
        }
      } else {
        setUnitPositionIds(null);
        setPositionsOrgUnitHint("Отделение не определено — показан полный справочник должностей");
      }

      let catalogOptions: PositionOption[] = [...positionCatalogOptions];

      if (catalogOptions.length === 0) {
        try {
          const rawPositions = await getPositions({ limit: 1000, offset: 0 });
          catalogOptions = normalizePositionOptions(rawPositions);
        } catch {
          catalogOptions = [];
        }
      }

      const mergedCatalog = mergePositionOptions(catalogOptions, unitOptionsFromEmployees);
      setAllPositionOptions(mergedCatalog);

      if (
        orgUnitId != null &&
        unitIds.size > 0 &&
        mergedCatalog.length > 0 &&
        mergedCatalog.length <= unitIds.size
      ) {
        setShowAllPositions(true);
        setPositionsOrgUnitHint(
          "Полный справочник недоступен — показаны должности, найденные в отделении"
        );
      }
    } catch {
      setAllPositionOptions([]);
      setUnitPositionIds(null);
    } finally {
      setPositionsLoading(false);
    }
  }

  function handleCancelEdit() {
    setMode("view");
    setSaveError(null);
    setPositionsOrgUnitHint(null);
    setShowAllPositions(false);
    if (details) setEditValues(buildEditValues(details));
  }

  async function handleSaveEdit() {
    if (!employeeId || !details) return;

    setSaving(true);
    setSaveError(null);

    try {
      const updated = await updateEmployee(employeeId, {
        full_name: editValues.full_name.trim(),
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

  function handleOpenTransfer() {
    if (!details || !isActive(details)) return;
    setTransferError(null);
    setTransferOpen(true);
  }

  function handleCloseTransfer() {
    if (transferSaving) return;
    setTransferOpen(false);
    setTransferError(null);
  }

  async function handleTransferSubmit(values: EmployeeTransferFormValues) {
    if (!employeeId || !details) return;

    setTransferSaving(true);
    setTransferError(null);

    try {
      const toOrgUnitId = Number(values.to_org_unit_id);
      if (!Number.isFinite(toOrgUnitId) || toOrgUnitId < 1) {
        setTransferError("Выберите целевое отделение.");
        setTransferSaving(false);
        return;
      }

      const payload: Parameters<typeof transferEmployee>[1] = {
        to_org_unit_id: toOrgUnitId,
        effective_date: values.effective_date,
      };

      const toPositionId = Number(values.to_position_id);
      if (Number.isFinite(toPositionId) && toPositionId > 0) {
        payload.to_position_id = toPositionId;
      }

      const orderRef = values.order_ref.trim();
      if (orderRef) payload.order_ref = orderRef;

      const comment = values.comment.trim();
      if (comment) payload.comment = comment;

      const result = await transferEmployee(employeeId, payload);

      setDetails(result.item);
      setTransferOpen(false);
      setEventsRefreshToken((t) => t + 1);
      onSaved?.();
    } catch (e) {
      setTransferError(mapApiErrorToMessage(e));
    } finally {
      setTransferSaving(false);
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

  const canEdit = !readOnly && Boolean(details && isActive(details));

  const editOrgUnitId = employeeOrgUnitId(details);
  const unitPositionCount = unitPositionIds?.size ?? 0;
  const hasUnitPositionMatches = unitPositionIds !== null && unitPositionCount > 0;
  const canExpandPositionCatalog =
    editOrgUnitId != null &&
    hasUnitPositionMatches &&
    !showAllPositions &&
    allPositionOptions.length > unitPositionCount;
  const canCollapsePositionCatalog =
    editOrgUnitId != null && hasUnitPositionMatches && showAllPositions && allPositionOptions.length > unitPositionCount;

  const positionSelectOptions = (() => {
    const currentId = Number(editValues.position_id || positionIdOf(details));

    let baseOptions: PositionOption[];
    if (showAllPositions || editOrgUnitId == null) {
      baseOptions = allPositionOptions;
    } else if (unitPositionIds === null) {
      baseOptions = allPositionOptions;
    } else if (unitPositionIds.size === 0) {
      baseOptions = [];
    } else {
      baseOptions = allPositionOptions.filter((p) => unitPositionIds.has(p.id));
    }

    const hasCurrent = baseOptions.some((p) => p.id === currentId);
    if (Number.isFinite(currentId) && currentId > 0 && !hasCurrent && positionName !== "—") {
      return [{ id: currentId, label: positionName }, ...baseOptions];
    }
    return baseOptions;
  })();

  const editableFieldClass =
    "mt-1 w-full rounded-lg border border-blue-300 dark:border-blue-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-200 dark:focus:ring-blue-900/40 disabled:opacity-60";
  const editableCardClass =
    "rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50/40 dark:bg-blue-950/20 p-4";
  const readOnlyCardClass =
    "rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4";

  function handleBackdropClick() {
    if (transferOpen) {
      handleCloseTransfer();
      return;
    }
    if (mode === "edit") {
      handleCancelEdit();
      return;
    }
    onClose();
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
                  disabled={saving}
                >
                  {saving ? "Сохранение..." : "Сохранить"}
                </button>
              </>
            ) : (
              <>
                {canEdit ? (
                  <>
                    <button
                      type="button"
                      onClick={() => void handleEnterEdit()}
                      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
                    >
                      Изменить
                    </button>
                    <button
                      type="button"
                      onClick={handleOpenTransfer}
                      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
                    >
                      Перевести
                    </button>
                  </>
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
                    </div>
                    <p className="mt-3 text-xs text-zinc-600 dark:text-zinc-400">
                      Должность, ставку и дату приёма можно изменить только через кадровое событие.
                    </p>
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
              ) : (
                <SectionBlock title="Отделение">
                  <div className={readOnlyCardClass}>
                    <div className="text-xs text-zinc-600 dark:text-zinc-400">Текущее отделение</div>
                    <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{orgUnitDisplay}</div>
                  </div>
                </SectionBlock>
              )}

              {mode === "view" && employeeId && !readOnly ? (
                <EmployeeProfessionalProfile employeeId={employeeId} />
              ) : null}

              {mode === "view" && employeeId ? (
                <EmployeeImportCardSection
                  id="access"
                  title="Доступ"
                  description="Учётная запись Corpsite и каналы уведомлений. Управление доступом — отдельно от кадрового контура."
                >
                  <EmployeeAccountSections
                    employeeId={employeeId}
                    refreshToken={eventsRefreshToken}
                    readOnly={readOnly}
                    allowRoleEdit={accountAllowRoleEdit}
                    embedded
                    showEvents={false}
                  />
                </EmployeeImportCardSection>
              ) : null}
            </div>
          ) : loading ? (
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Загрузка данных...</div>
          ) : null}
        </div>
      </div>

      <EmployeeTransferDrawer
        open={transferOpen}
        details={details}
        saving={transferSaving}
        error={transferError}
        onClose={handleCloseTransfer}
        onSubmit={handleTransferSubmit}
      />
    </div>
  );
}
