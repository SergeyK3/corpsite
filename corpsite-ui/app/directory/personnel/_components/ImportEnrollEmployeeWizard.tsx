"use client";

import * as React from "react";
import Link from "next/link";

import OrgScopeFilter from "@/components/OrgScopeFilter";
import OrgUnitScopeFilter from "@/components/OrgUnitScopeFilter";
import { buildEmployeeCardHref } from "@/lib/employeeCardNav";
import {
  OPEN_HR_DOSSIER_CTA,
  WORKING_QUICK_VIEW_MODE,
} from "@/lib/personnelCardTerminology";
import { fetchDepartmentGroups, type DepartmentGroupRow } from "@/lib/orgScope";
import {
  isOrgUnitAllowedForGroup,
  isPositionAllowedInOptions,
  type PersonnelOrderPositionSelectGroup,
  type TaskOrgFilterOption,
} from "@/lib/taskOrgFilters";
import { useOrgUnitScopeOptions } from "@/lib/useOrgUnitScopeOptions";
import { usePersonnelOrderPositionOptions } from "@/lib/usePersonnelOrderPositionOptions";
import { findOrgGroupIdForUnit } from "@/lib/userCreateOrgScope";
import { getOrgUnitsTree } from "@/app/directory/org-units/_lib/api.client";
import {
  EnrollEmployeeConflictError,
  enrollEmployeeFromNormalizedRecord,
  getNormalizedRecord,
  mapImportApiError,
  patchNormalizedRecordEmployeeBinding,
  type EnrollEmployeeRequestBody,
  type EnrollEmployeeResponse,
  type NormalizedRecord,
} from "../_lib/importApi.client";
import { displayNormalizedRecordIin } from "../_lib/normalizedRecordIin";
import EnrollmentCompletionPanel from "./EnrollmentCompletionPanel";

type Props = {
  record: NormalizedRecord;
  batchFileName?: string;
  canEnroll?: boolean;
  onReviewed: (record: NormalizedRecord) => void;
  onToast: (message: string, kind?: "success" | "error") => void;
};

type FieldErrors = {
  orgGroup?: string;
  orgUnit?: string;
  position?: string;
  dateFrom?: string;
  employmentRate?: string;
  confirm?: string;
};

const ENROLL_WIZARD_BASE_PATH = "/directory/personnel/import";

const IMPORT_POSITION_NOT_IN_CATALOG_WARNING =
  "Должность из импорта не найдена в справочнике должностей. Создайте должность в справочнике или выберите корректную существующую должность вручную.";

function normalizePositionName(name: string): string {
  return name.trim().toLowerCase();
}

function findPositionByImportHint(
  hint: string,
  options: readonly TaskOrgFilterOption[],
): TaskOrgFilterOption | undefined {
  const normalized = normalizePositionName(hint);
  if (!normalized) return undefined;
  return options.find((p) => normalizePositionName(p.label) === normalized);
}

function renderPositionSelectOptions(groups: readonly PersonnelOrderPositionSelectGroup[]) {
  if (groups.length === 0) return null;

  return groups.map((group) => (
    <optgroup key={group.key} label={group.label}>
      {group.items.map((position) => (
        <option key={position.id} value={String(position.id)}>
          {position.label}
        </option>
      ))}
    </optgroup>
  ));
}

export function isValidOptionalIsoDate(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return true;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!Number.isFinite(year) || month < 1 || month > 12 || day < 1 || day > 31) return false;
  const parsed = new Date(`${trimmed}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return false;
  return (
    parsed.getFullYear() === year &&
    parsed.getMonth() + 1 === month &&
    parsed.getDate() === day
  );
}

function formatDisplayDate(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "Не указана";
  const [year, month, day] = trimmed.split("-");
  if (!year || !month || !day) return trimmed;
  return `${day}.${month}.${year}`;
}

function buildEnrollPayload(args: {
  fullName: string;
  orgUnitId: number;
  positionId: number;
  dateFrom: string;
  employmentRate: string;
}): EnrollEmployeeRequestBody {
  const body: EnrollEmployeeRequestBody = {
    dry_run: false,
    full_name: args.fullName.trim(),
    org_unit_id: args.orgUnitId,
    position_id: args.positionId,
    employment_rate: Number(args.employmentRate) || 1,
    link_same_iin_in_batch: true,
  };
  const trimmedDate = args.dateFrom.trim();
  if (trimmedDate) {
    body.date_from = trimmedDate;
  }
  return body;
}

function EnrollConfirmModal({
  open,
  loading,
  summary,
  onClose,
  onConfirm,
}: {
  open: boolean;
  loading: boolean;
  summary: {
    fullName: string;
    iin: string;
    orgGroupLabel: string;
    orgUnitLabel: string;
    positionLabel: string;
    dateFromLabel: string;
    employmentRate: string;
    linkedCount: number | null;
  };
  onClose: () => void;
  onConfirm: () => void;
}) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !loading) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, loading, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4"
      data-testid="enroll-wizard-confirm-modal"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="enroll-wizard-confirm-title"
        className="w-full max-w-lg rounded-xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-950"
      >
        <h4
          id="enroll-wizard-confirm-title"
          className="text-base font-semibold text-zinc-900 dark:text-zinc-100"
        >
          Подтверждение зачисления
        </h4>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Проверьте данные перед добавлением сотрудника в персонал.
        </p>

        <dl className="mt-4 space-y-2 text-sm text-zinc-700 dark:text-zinc-300">
          <div className="flex gap-2">
            <dt className="min-w-[10rem] text-zinc-500">ФИО</dt>
            <dd>{summary.fullName || "—"}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="min-w-[10rem] text-zinc-500">ИИН</dt>
            <dd className="font-mono">{summary.iin}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="min-w-[10rem] text-zinc-500">Группа подразделений</dt>
            <dd data-testid="enroll-wizard-summary-org-group">{summary.orgGroupLabel}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="min-w-[10rem] text-zinc-500">Подразделение</dt>
            <dd data-testid="enroll-wizard-summary-org-unit">{summary.orgUnitLabel}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="min-w-[10rem] text-zinc-500">Должность</dt>
            <dd data-testid="enroll-wizard-summary-position">{summary.positionLabel}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="min-w-[10rem] text-zinc-500">Дата приёма</dt>
            <dd data-testid="enroll-wizard-summary-date-from">{summary.dateFromLabel}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="min-w-[10rem] text-zinc-500">Ставка</dt>
            <dd data-testid="enroll-wizard-summary-rate">{summary.employmentRate}</dd>
          </div>
          {summary.linkedCount != null ? (
            <div className="flex gap-2">
              <dt className="min-w-[10rem] text-zinc-500">Привязка записей</dt>
              <dd data-testid="enroll-wizard-summary-linked-count">
                {summary.linkedCount} (same batch + same IIN)
              </dd>
            </div>
          ) : null}
        </dl>

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            disabled={loading}
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
          >
            Отмена
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={onConfirm}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Создание…" : "Подтвердить и создать"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ImportEnrollEmployeeWizard({
  record,
  batchFileName,
  canEnroll = true,
  onReviewed,
  onToast,
}: Props) {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [dryRunResult, setDryRunResult] = React.useState<EnrollEmployeeResponse | null>(null);
  const [conflictResult, setConflictResult] = React.useState<EnrollEmployeeResponse | null>(null);
  const [successEmployeeId, setSuccessEmployeeId] = React.useState<number | null>(null);
  const [successEnrollResult, setSuccessEnrollResult] = React.useState<EnrollEmployeeResponse | null>(null);
  const [fullName, setFullName] = React.useState(record.full_name || "");
  const [orgGroupId, setOrgGroupId] = React.useState<number | null>(null);
  const [orgUnitId, setOrgUnitId] = React.useState<number | null>(null);
  const [positionId, setPositionId] = React.useState<number | null>(null);
  const [dateFrom, setDateFrom] = React.useState("");
  const [employmentRate, setEmploymentRate] = React.useState("1");
  const [confirmChecked, setConfirmChecked] = React.useState(false);
  const [fieldErrors, setFieldErrors] = React.useState<FieldErrors>({});
  const [confirmModalOpen, setConfirmModalOpen] = React.useState(false);
  const [positionValidationMessage, setPositionValidationMessage] = React.useState<string | null>(null);
  const [departmentGroups, setDepartmentGroups] = React.useState<DepartmentGroupRow[]>([]);
  const placementPrefillStartedRef = React.useRef(false);

  const {
    options: orgUnitSelectOptions,
    catalogOptions: orgUnitCatalogOptions,
    loading: orgUnitsLoading,
    error: orgUnitsError,
  } = useOrgUnitScopeOptions(orgGroupId);

  const {
    positionGroups,
    allOptions: positionOptions,
    scopedOptions,
    loading: positionsLoading,
  } = usePersonnelOrderPositionOptions({
    enabled: true,
    orgUnitId,
    orgGroupId,
  });

  React.useEffect(() => {
    setError(null);
    setDryRunResult(null);
    setConflictResult(null);
    setSuccessEmployeeId(null);
    setSuccessEnrollResult(null);
    setFullName(record.full_name || "");
    setOrgGroupId(null);
    setOrgUnitId(null);
    setPositionId(null);
    setFieldErrors({});
    setPositionValidationMessage(null);
    setDateFrom("");
    setEmploymentRate("1");
    setConfirmChecked(false);
    setConfirmModalOpen(false);
    placementPrefillStartedRef.current = false;
  }, [record.record_id]);

  React.useEffect(() => {
    let cancelled = false;
    void fetchDepartmentGroups()
      .then((rows) => {
        if (!cancelled) setDepartmentGroups(rows);
      })
      .catch(() => {
        if (!cancelled) setDepartmentGroups([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    if (orgUnitId == null || orgUnitCatalogOptions.length === 0) return;
    if (isOrgUnitAllowedForGroup(orgUnitId, orgGroupId ?? undefined, orgUnitCatalogOptions)) return;
    setOrgUnitId(null);
    setPositionId(null);
  }, [orgGroupId, orgUnitId, orgUnitCatalogOptions]);

  React.useEffect(() => {
    if (positionId == null || positionsLoading) return;
    if (isPositionAllowedInOptions(positionId, positionOptions)) return;
    setPositionId(null);
  }, [positionId, positionOptions, positionsLoading]);

  const importPositionHint = dryRunResult?.preview?.position_hint?.value?.trim() ?? "";
  const importPositionMatch = React.useMemo(() => {
    if (!importPositionHint || positionOptions.length === 0) return undefined;
    return findPositionByImportHint(importPositionHint, positionOptions);
  }, [importPositionHint, positionOptions]);
  const showImportPositionNotFoundWarning =
    Boolean(importPositionHint) && positionOptions.length > 0 && !importPositionMatch;

  React.useEffect(() => {
    if (!importPositionHint || positionOptions.length === 0 || positionId != null) return;
    const match = findPositionByImportHint(importPositionHint, positionOptions);
    if (match) {
      setPositionId(match.id);
    }
  }, [importPositionHint, positionOptions, positionId]);

  React.useEffect(() => {
    const hintUnitId = dryRunResult?.preview?.org_unit_hint?.org_unit_id;
    if (!hintUnitId || orgUnitId != null || placementPrefillStartedRef.current) return;

    placementPrefillStartedRef.current = true;
    let cancelled = false;

    void (async () => {
      try {
        const tree = await getOrgUnitsTree({ include_inactive: false });
        if (cancelled) return;
        const groupId = findOrgGroupIdForUnit(tree.items ?? [], hintUnitId);
        if (groupId != null) {
          setOrgGroupId(groupId);
        }
      } catch {
        // Prefill is best-effort; user can select manually.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [dryRunResult, orgUnitId]);

  React.useEffect(() => {
    const hintUnitId = dryRunResult?.preview?.org_unit_hint?.org_unit_id;
    if (!hintUnitId || orgUnitId != null || orgUnitCatalogOptions.length === 0) return;
    if (!isOrgUnitAllowedForGroup(hintUnitId, orgGroupId ?? undefined, orgUnitCatalogOptions)) return;
    setOrgUnitId(hintUnitId);
  }, [dryRunResult, orgUnitId, orgGroupId, orgUnitCatalogOptions]);

  function handleOrgGroupChange(nextGroupId: number | null) {
    if (orgUnitId != null || positionId != null) {
      setPositionValidationMessage("Выбранные подразделение и должность сброшены — выберите заново для новой группы");
    } else {
      setPositionValidationMessage(null);
    }
    setFieldErrors((prev) => ({
      ...prev,
      orgGroup: undefined,
      orgUnit: undefined,
      position: undefined,
    }));
    setOrgGroupId(nextGroupId);
    setOrgUnitId(null);
    setPositionId(null);
  }

  function handleOrgUnitChange(nextOrgUnitId: number | null) {
    if (positionId != null) {
      setPositionValidationMessage("Выбранная должность сброшена — выберите должность для нового подразделения");
    } else {
      setPositionValidationMessage(null);
    }
    setFieldErrors((prev) => ({
      ...prev,
      orgUnit: undefined,
      position: undefined,
    }));
    setOrgUnitId(nextOrgUnitId);
    setPositionId(null);
  }

  function positionSelectPlaceholder(): string {
    if (orgUnitId == null) return "Сначала выберите подразделение";
    if (positionsLoading) return "Загрузка должностей…";
    if (positionOptions.length === 0) return "Нет доступных должностей";
    return "Выберите должность";
  }

  const positionSelectDisabled =
    orgUnitId == null || positionsLoading || positionOptions.length === 0;

  const orgGroupLabel =
    departmentGroups.find((g) => g.group_id === orgGroupId)?.group_name?.trim() || "—";
  const orgUnitLabel =
    orgUnitCatalogOptions
      .find((o) => o.unit_id === orgUnitId)
      ?.name.replace(/^—\s*/g, "")
      .trim() || "—";
  const positionLabel =
    positionOptions.find((p) => p.id === positionId)?.label?.trim() || "—";

  function validateForm(): FieldErrors {
    const errors: FieldErrors = {};

    if (orgGroupId == null) {
      errors.orgGroup = "Выберите группу подразделений";
    }
    if (orgUnitId == null) {
      errors.orgUnit = "Выберите подразделение";
    } else if (
      orgUnitCatalogOptions.length > 0 &&
      !isOrgUnitAllowedForGroup(orgUnitId, orgGroupId ?? undefined, orgUnitCatalogOptions)
    ) {
      errors.orgUnit = "Подразделение не относится к выбранной группе";
    }
    if (positionId == null || positionId < 1) {
      errors.position = "Выберите должность";
    } else if (!isPositionAllowedInOptions(positionId, positionOptions)) {
      errors.position = "Выберите должность";
    }

    if (!isValidOptionalIsoDate(dateFrom)) {
      errors.dateFrom = "Укажите корректную дату приёма";
    }

    const rate = Number(employmentRate);
    if (!Number.isFinite(rate) || rate < 0.01 || rate > 2) {
      errors.employmentRate = "Ставка должна быть от 0,01 до 2";
    }

    if (!confirmChecked) {
      errors.confirm = "Подтвердите добавление сотрудника в персонал";
    }

    return errors;
  }

  function attemptOpenConfirmModal() {
    const errors = validateForm();
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      setConfirmModalOpen(false);
      return;
    }
    setFieldErrors({});
    setError(null);
    setConfirmModalOpen(true);
  }

  async function runDryRun() {
    setLoading(true);
    setError(null);
    setConflictResult(null);
    try {
      const result = await enrollEmployeeFromNormalizedRecord(record.record_id, {
        dry_run: true,
        full_name: fullName.trim() || undefined,
      });
      setDryRunResult(result);
    } catch (e) {
      if (e instanceof EnrollEmployeeConflictError) {
        setConflictResult(e.payload);
        setDryRunResult(null);
      } else {
        setError(mapImportApiError(e));
      }
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    if (!canEnroll) return;
    void runDryRun();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [record.record_id, canEnroll]);

  async function handleExecute() {
    const orgId = orgUnitId ?? 0;
    const posId = positionId ?? 0;
    if (!Number.isInteger(orgId) || orgId < 1) {
      setError("Выберите подразделение");
      setConfirmModalOpen(false);
      return;
    }
    if (!Number.isInteger(posId) || posId < 1) {
      setError("Выберите должность");
      setConfirmModalOpen(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await enrollEmployeeFromNormalizedRecord(
        record.record_id,
        buildEnrollPayload({
          fullName,
          orgUnitId: orgId,
          positionId: posId,
          dateFrom,
          employmentRate,
        }),
      );
      setSuccessEmployeeId(result.employee_id ?? null);
      setSuccessEnrollResult(result);
      setConfirmModalOpen(false);
      const updated = await getNormalizedRecord(record.record_id);
      onReviewed(updated);
      onToast("Сотрудник создан и записи привязаны", "success");
    } catch (e) {
      if (e instanceof EnrollEmployeeConflictError) {
        setConflictResult(e.payload);
        setConfirmModalOpen(false);
      } else {
        setError(mapImportApiError(e));
      }
    } finally {
      setLoading(false);
    }
  }

  async function linkExistingEmployee(employeeId: number) {
    setLoading(true);
    setError(null);
    try {
      const updated = await patchNormalizedRecordEmployeeBinding(record.record_id, employeeId);
      onReviewed(updated);
      onToast(`Запись привязана к сотруднику #${employeeId}`, "success");
      setConflictResult(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setLoading(false);
    }
  }

  if (!canEnroll) return null;

  const iin = displayNormalizedRecordIin(record);
  const bindingReason = record.employee_binding?.reason ?? "";
  const showWizard =
    !record.employee_id &&
    record.review_status !== "promoted" &&
    record.review_status !== "superseded" &&
    iin.length === 12 &&
    (record.employee_binding?.status === "unbound" ||
      bindingReason.includes("не найден"));

  if (!showWizard && !successEmployeeId) return null;

  if (successEmployeeId && successEnrollResult) {
    return (
      <EnrollmentCompletionPanel
        employeeId={successEmployeeId}
        enrollResult={successEnrollResult}
        record={record}
        batchFileName={batchFileName}
      />
    );
  }

  if (conflictResult?.conflict) {
    const conflict = conflictResult.conflict;
    const primary =
      conflict.candidates?.[0] ??
      (conflict.existing_employee_id
        ? {
            employee_id: conflict.existing_employee_id,
            full_name: conflict.existing_employee_name,
            org_unit_name: conflict.existing_org_unit_name,
            position_name: conflict.existing_position_name,
          }
        : null);

    return (
      <section className="space-y-3 rounded-lg border border-orange-200 bg-orange-50/70 p-4 dark:border-orange-900 dark:bg-orange-950/30">
        <h3 className="text-sm font-semibold text-orange-900 dark:text-orange-100">
          ИИН уже в справочнике
        </h3>
        <p className="text-sm text-orange-800 dark:text-orange-200">{conflict.message}</p>
        {primary ? (
          <div className="rounded-lg border border-orange-200 bg-white/80 px-3 py-2 text-sm dark:border-orange-800 dark:bg-zinc-950">
            <div className="font-medium">{primary.full_name || "—"}</div>
            <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              Employee #{primary.employee_id}
              {primary.org_unit_name ? ` · ${primary.org_unit_name}` : ""}
              {primary.position_name ? ` · ${primary.position_name}` : ""}
            </div>
          </div>
        ) : null}
        {conflict.code === "IIN_ALREADY_EXISTS" && primary?.employee_id ? (
          <div className="flex flex-wrap gap-2">
            <Link
              href={buildEmployeeCardHref(primary.employee_id)}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              {OPEN_HR_DOSSIER_CTA}
            </Link>
            <Link
              href={`/directory/staff?employeeId=${primary.employee_id}`}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            >
              {WORKING_QUICK_VIEW_MODE}
            </Link>
            <button
              type="button"
              disabled={loading}
              onClick={() => linkExistingEmployee(primary.employee_id!)}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              Привязать запись
            </button>
          </div>
        ) : (
          <p className="text-xs text-zinc-600 dark:text-zinc-400">
            Используйте ручную привязку по ID или обратитесь к администратору.
          </p>
        )}
      </section>
    );
  }

  return (
    <>
      <section
        className="space-y-4 rounded-lg border border-blue-200 bg-blue-50/40 p-4 dark:border-blue-900 dark:bg-blue-950/20"
        data-testid="enroll-wizard-main"
      >
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Добавить в персонал</h3>
          <p className="mt-1 text-xs text-zinc-500">
            Добавление сотрудника в персонал из записи импорта. Укажите размещение и подтвердите создание.
          </p>
        </div>

        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div>
        ) : null}

        <div className="space-y-3 text-sm">
          <label className="grid gap-1">
            <span className="text-xs font-medium text-zinc-500">ФИО *</span>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
          <label className="grid gap-1">
            <span className="text-xs font-medium text-zinc-500">ИИН</span>
            <input
              value={iin}
              readOnly
              className="rounded-lg border border-zinc-200 bg-zinc-100 px-3 py-2 font-mono dark:border-zinc-800 dark:bg-zinc-900"
            />
          </label>

          <div className="space-y-3" data-testid="enroll-wizard-org-placement">
            <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Размещение в организации
            </div>
            <div data-testid="enroll-wizard-org-scope-cascade">
              <OrgScopeFilter
                basePath={ENROLL_WIZARD_BASE_PATH}
                label="Группа подразделений *"
                value={orgGroupId}
                onChange={handleOrgGroupChange}
              />
              {fieldErrors.orgGroup ? (
                <p
                  className="mt-1 text-xs text-red-600 dark:text-red-400"
                  data-testid="enroll-wizard-error-org-group"
                >
                  {fieldErrors.orgGroup}
                </p>
              ) : null}
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <OrgUnitScopeFilter
                    basePath={ENROLL_WIZARD_BASE_PATH}
                    label="Подразделение *"
                    allLabel="Выберите подразделение"
                    orgGroupId={orgGroupId}
                    value={orgUnitId}
                    unitOptions={orgUnitSelectOptions}
                    unitsLoading={orgUnitsLoading}
                    unitsError={orgUnitsError}
                    onChange={handleOrgUnitChange}
                  />
                  {fieldErrors.orgUnit ? (
                    <p
                      className="mt-1 text-xs text-red-600 dark:text-red-400"
                      data-testid="enroll-wizard-error-org-unit"
                    >
                      {fieldErrors.orgUnit}
                    </p>
                  ) : null}
                  {dryRunResult?.preview?.org_unit_hint?.value ? (
                    <span className="mt-1 block text-xs text-blue-600 dark:text-blue-400">
                      Из импорта: {dryRunResult.preview.org_unit_hint.value}
                    </span>
                  ) : null}
                </div>
                <label className="grid gap-1">
                  <span className="text-xs font-medium text-zinc-500">Должность *</span>
                  <select
                    data-testid="enroll-wizard-position-select"
                    value={positionId != null ? String(positionId) : ""}
                    onChange={(e) => {
                      const parsed = e.target.value ? Number(e.target.value) : null;
                      setPositionId(
                        parsed != null && Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : null,
                      );
                      setPositionValidationMessage(null);
                      setFieldErrors((prev) => ({ ...prev, position: undefined }));
                    }}
                    disabled={positionSelectDisabled}
                    className="rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    <option value="">{positionSelectPlaceholder()}</option>
                    {renderPositionSelectOptions(positionGroups)}
                  </select>
                  {fieldErrors.position ? (
                    <span
                      className="text-xs text-red-600 dark:text-red-400"
                      data-testid="enroll-wizard-error-position"
                    >
                      {fieldErrors.position}
                    </span>
                  ) : null}
                  {scopedOptions.length > 0 ? (
                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                      Используются в подразделении: {scopedOptions.map((p) => p.label).join(", ")}
                    </span>
                  ) : null}
                  {showImportPositionNotFoundWarning ? (
                    <span className="text-xs text-amber-700 dark:text-amber-300">
                      {IMPORT_POSITION_NOT_IN_CATALOG_WARNING}
                    </span>
                  ) : null}
                  {importPositionMatch && positionId === importPositionMatch.id ? (
                    <span className="text-xs text-green-700 dark:text-green-300">
                      Совпадение с импортом: {importPositionMatch.label}
                    </span>
                  ) : null}
                  {positionValidationMessage ? (
                    <span className="text-xs text-amber-700 dark:text-amber-300">{positionValidationMessage}</span>
                  ) : null}
                  {orgUnitId != null ? (
                    <Link
                      href="/directory/positions"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300"
                    >
                      Справочник должностей
                    </Link>
                  ) : null}
                  {dryRunResult?.preview?.position_hint?.value ? (
                    <span className="text-xs text-blue-600 dark:text-blue-400">
                      Из импорта: {dryRunResult.preview.position_hint.value}
                    </span>
                  ) : null}
                </label>
              </div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1">
              <span className="text-xs font-medium text-zinc-500">Дата приёма</span>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setFieldErrors((prev) => ({ ...prev, dateFrom: undefined }));
                }}
                className="rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
                data-testid="enroll-wizard-date-from"
              />
              {fieldErrors.dateFrom ? (
                <span
                  className="text-xs text-red-600 dark:text-red-400"
                  data-testid="enroll-wizard-error-date-from"
                >
                  {fieldErrors.dateFrom}
                </span>
              ) : (
                <span className="text-xs text-zinc-500 dark:text-zinc-400">
                  Необязательно. Фактическая дата приёма может быть зафиксирована позже приказом HIRE.
                </span>
              )}
            </label>
            <label className="grid gap-1">
              <span className="text-xs font-medium text-zinc-500">Ставка</span>
              <input
                type="number"
                min="0.01"
                max="2"
                step="0.01"
                value={employmentRate}
                onChange={(e) => {
                  setEmploymentRate(e.target.value);
                  setFieldErrors((prev) => ({ ...prev, employmentRate: undefined }));
                }}
                className="rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
                data-testid="enroll-wizard-employment-rate"
              />
              {fieldErrors.employmentRate ? (
                <span
                  className="text-xs text-red-600 dark:text-red-400"
                  data-testid="enroll-wizard-error-employment-rate"
                >
                  {fieldErrors.employmentRate}
                </span>
              ) : null}
            </label>
          </div>

          {dryRunResult ? (
            <div
              className="rounded-lg border border-zinc-200 bg-white/80 px-3 py-2 text-xs dark:border-zinc-800 dark:bg-zinc-950"
              data-testid="enroll-wizard-linked-info"
            >
              <div>✓ ИИН валиден</div>
              <div>✓ Сотрудник с таким ИИН не найден</div>
              <div data-testid="enroll-wizard-linked-count">
                Будет привязано записей: {dryRunResult.linked_records_count} (same batch + same IIN)
              </div>
              {dryRunResult.warnings.map((w) => (
                <div key={w} className="text-amber-700 dark:text-amber-300">
                  ⚠ {w}
                </div>
              ))}
            </div>
          ) : null}

          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={confirmChecked}
              onChange={(e) => {
                setConfirmChecked(e.target.checked);
                setFieldErrors((prev) => ({ ...prev, confirm: undefined }));
              }}
              className="mt-1"
              data-testid="enroll-wizard-confirm-checkbox"
            />
            <span>Добавить сотрудника в справочник персонала</span>
          </label>
          {fieldErrors.confirm ? (
            <p className="text-xs text-red-600 dark:text-red-400" data-testid="enroll-wizard-error-confirm">
              {fieldErrors.confirm}
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={loading}
              onClick={attemptOpenConfirmModal}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              data-testid="enroll-wizard-submit"
            >
              Создать и привязать
            </button>
          </div>
        </div>
      </section>

      <EnrollConfirmModal
        open={confirmModalOpen}
        loading={loading}
        summary={{
          fullName,
          iin,
          orgGroupLabel,
          orgUnitLabel,
          positionLabel,
          dateFromLabel: formatDisplayDate(dateFrom),
          employmentRate,
          linkedCount: dryRunResult?.linked_records_count ?? null,
        }}
        onClose={() => {
          if (!loading) setConfirmModalOpen(false);
        }}
        onConfirm={() => void handleExecute()}
      />
    </>
  );
}
