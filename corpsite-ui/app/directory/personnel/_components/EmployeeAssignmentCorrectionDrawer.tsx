"use client";

import * as React from "react";

import OrgScopeFilter from "@/components/OrgScopeFilter";
import OrgUnitScopeFilter from "@/components/OrgUnitScopeFilter";
import { findOrgGroupIdForUnit } from "@/lib/userCreateOrgScope";
import { useOrgUnitScopeOptions } from "@/lib/useOrgUnitScopeOptions";
import { usePersonnelOrderPositionOptions } from "@/lib/usePersonnelOrderPositionOptions";
import { getOrgUnitsTree } from "../../org-units/_lib/api.client";
import type { EmployeeDetails } from "../../employees/_lib/types";

const CORRECTION_BASE_PATH = "/directory/personnel/employees/correction";

export type EmployeeAssignmentCorrectionFormValues = {
  full_name?: string;
  org_unit_id?: number;
  position_id?: number | null;
  employment_rate?: number;
  date_from?: string | null;
  date_to?: string | null;
  status?: "active" | "inactive";
  effective_date: string;
  reason: string;
  comment: string;
};

type Props = {
  open: boolean;
  details: EmployeeDetails | null;
  saving?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (values: EmployeeAssignmentCorrectionFormValues) => Promise<void> | void;
};

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function isoDateOrNull(value: string | null | undefined): string | null {
  const raw = String(value ?? "").trim();
  return raw || null;
}

function toInputDate(value: string | null | undefined): string {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  return raw.slice(0, 10);
}
function currentStatus(details: EmployeeDetails): "active" | "inactive" {
  return details.status === "inactive" || details.is_active === false ? "inactive" : "active";
}
function currentFullName(details: EmployeeDetails): string {
  const record = details as Record<string, unknown>;
  return String(record.fio ?? record.full_name ?? record.fullName ?? "").trim();
}

export default function EmployeeAssignmentCorrectionDrawer({
  open,
  details,
  saving = false,
  error = null,
  onClose,
  onSubmit,
}: Props) {
  const [orgGroupId, setOrgGroupId] = React.useState<number | null>(null);
  const [orgUnitId, setOrgUnitId] = React.useState<number | null>(null);
  const [positionId, setPositionId] = React.useState<number | null>(null);
  const [fullName, setFullName] = React.useState("");
  const [employmentRate, setEmploymentRate] = React.useState("1");
  const [dateFrom, setDateFrom] = React.useState("");
  const [dateTo, setDateTo] = React.useState("");
  const [status, setStatus] = React.useState<"active" | "inactive">("active");
  const [effectiveDate, setEffectiveDate] = React.useState(todayIsoDate());
  const [reason, setReason] = React.useState("");
  const [comment, setComment] = React.useState("");
  const [prefillDone, setPrefillDone] = React.useState(false);

  const {
    options: orgUnitSelectOptions,
    loading: orgUnitsLoading,
    error: orgUnitsError,
  } = useOrgUnitScopeOptions(orgGroupId);

  const { allOptions: positionOptions, loading: positionsLoading } = usePersonnelOrderPositionOptions({
    enabled: open,
    orgUnitId,
    orgGroupId,
  });

  React.useEffect(() => {
    if (!open || !details) {
      setPrefillDone(false);
      return;
    }

    let cancelled = false;

    (async () => {
      const orgUnit = Number(details.org_unit?.unit_id ?? 0);
      const position = Number(details.position?.id ?? 0);
      const rate = Number(details.rate ?? 1);
      const d = details as Record<string, unknown>;

      let groupId: number | null = null;
      if (Number.isFinite(orgUnit) && orgUnit > 0) {
        try {
          const tree = await getOrgUnitsTree({ include_inactive: false });
          groupId = findOrgGroupIdForUnit(tree.items ?? [], orgUnit);
        } catch {
          groupId = null;
        }
      }

      if (cancelled) return;

      setOrgGroupId(groupId);
      setOrgUnitId(Number.isFinite(orgUnit) && orgUnit > 0 ? orgUnit : null);
      setPositionId(Number.isFinite(position) && position > 0 ? position : null);
      setFullName(currentFullName(details));
      setEmploymentRate(Number.isFinite(rate) && rate > 0 ? String(rate) : "1");
      setDateFrom(toInputDate((d.date_from ?? d.dateFrom) as string | null | undefined));
      setDateTo(toInputDate((d.date_to ?? d.dateTo) as string | null | undefined));
      setStatus(currentStatus(details));
      setEffectiveDate(todayIsoDate());
      setReason("");
      setComment("");
      setPrefillDone(true);
    })();

    return () => {
      cancelled = true;
    };
  }, [open, details]);

  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && open && !saving) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, saving]);

  if (!open || !details) return null;

  return (
    <div className="fixed inset-0 z-[60] flex" data-testid="assignment-correction-drawer">
      <div
        className="absolute inset-0 bg-zinc-600/35 backdrop-blur-sm dark:bg-black/50"
        onClick={saving ? undefined : onClose}
      />
      <div className="relative ml-auto flex h-full w-full max-w-[720px] flex-col border-l border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Исправить ошибку в назначении</h2>
            <p className="mt-1 text-sm text-zinc-500">
              Используйте для исправления неверно внесённых данных. Новое назначение не создаётся; причина исправления сохраняется в истории.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700"
          >
            Закрыть
          </button>
        </div>

        <form
          className="flex flex-1 flex-col overflow-y-auto px-5 py-4"
          onSubmit={(e) => {
            e.preventDefault();
            const rate = Number(employmentRate);
            const currentOrgUnitId = Number(details.org_unit?.unit_id ?? 0);
            const currentPositionId = Number(details.position?.id ?? 0);
            const currentRate = Number(details.rate ?? 1);
            const detailRecord = details as Record<string, unknown>;
            const currentDateFrom = toInputDate(
              (detailRecord.date_from ?? detailRecord.dateFrom) as string | null | undefined,
            );
            const currentDateTo = toInputDate(
              (detailRecord.date_to ?? detailRecord.dateTo) as string | null | undefined,
            );
            const nextDateFrom = isoDateOrNull(dateFrom);
            const nextDateTo = isoDateOrNull(dateTo);
            void onSubmit({
              ...(fullName.trim() !== currentFullName(details) ? { full_name: fullName.trim() } : {}),
              ...(orgUnitId != null && orgUnitId !== currentOrgUnitId ? { org_unit_id: orgUnitId } : {}),
              ...(positionId !== currentPositionId ? { position_id: positionId } : {}),
              ...(Number.isFinite(rate) && rate > 0 && rate !== currentRate ? { employment_rate: rate } : {}),
              ...(nextDateFrom !== (currentDateFrom || null) ? { date_from: nextDateFrom } : {}),
              ...(nextDateTo !== (currentDateTo || null) ? { date_to: nextDateTo } : {}),
              ...(status === currentStatus(details) ? {} : { status }),
              effective_date: effectiveDate,
              reason: reason.trim(),
              comment: comment.trim(),
            });
          }}
        >
          {error ? (
            <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
              {error}
            </div>
          ) : null}

          {!prefillDone ? (
            <div className="text-sm text-zinc-500">Загрузка текущего назначения…</div>
          ) : (
            <div className="space-y-4">
              <label className="grid gap-1">
                <span className="text-xs font-medium text-zinc-500">{"ФИО *"}</span>
                <input
                  data-testid="assignment-correction-full-name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  required
                />
              </label>

              <div data-testid="assignment-correction-org-cascade">
                <OrgScopeFilter
                  basePath={CORRECTION_BASE_PATH}
                  label="Группа подразделений *"
                  value={orgGroupId}
                  onChange={(groupId) => {
                    setOrgGroupId(groupId);
                    setOrgUnitId(null);
                    setPositionId(null);
                  }}
                />
                <div className="mt-3">
                  <OrgUnitScopeFilter
                    basePath={CORRECTION_BASE_PATH}
                    label="Подразделение *"
                    allLabel="Выберите подразделение"
                    orgGroupId={orgGroupId}
                    value={orgUnitId}
                    unitOptions={orgUnitSelectOptions}
                    unitsLoading={orgUnitsLoading}
                    unitsError={orgUnitsError}
                    onChange={(unitId) => {
                      setOrgUnitId(unitId);
                      setPositionId(null);
                    }}
                  />
                </div>
              </div>

              <label className="grid gap-1">
                <span className="text-xs font-medium text-zinc-500">Должность *</span>
                <select
                  data-testid="assignment-correction-position"
                  value={positionId != null ? String(positionId) : ""}
                  onChange={(e) => {
                    const parsed = e.target.value ? Number(e.target.value) : null;
                    setPositionId(
                      parsed != null && Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : null,
                    );
                  }}
                  disabled={!orgUnitId || positionsLoading}
                  className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  required
                >
                  <option value="">{positionsLoading ? "Загрузка…" : "Выберите должность"}</option>
                  {positionOptions.map((option) => (
                    <option key={option.id} value={String(option.id)}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="grid gap-1">
                <span className="text-xs font-medium text-zinc-500">Статус *</span>
                <select
                  data-testid="assignment-correction-status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value === "inactive" ? "inactive" : "active")}
                  className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                >
                  <option value="active">{"\u0420\u0430\u0431\u043e\u0442\u0430\u0435\u0442"}</option>
                  <option value="inactive">{"\u041d\u0435 \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442"}</option>
                </select>
              </label>

              <label className="grid gap-1">
                <span className="text-xs font-medium text-zinc-500">Ставка *</span>
                <input
                  data-testid="assignment-correction-rate"
                  type="number"
                  min={0.01}
                  max={2}
                  step={0.01}
                  value={employmentRate}
                  onChange={(e) => setEmploymentRate(e.target.value)}
                  className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  required
                />
              </label>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="grid gap-1">
                  <span className="text-xs font-medium text-zinc-500">{"\u0414\u0430\u0442\u0430 \u043d\u0430\u0447\u0430\u043b\u0430"}</span>
                  <input
                    data-testid="assignment-correction-date-from"
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  />
                  <span className="text-xs text-zinc-500">{"\u041e\u0441\u0442\u0430\u0432\u044c\u0442\u0435 \u043f\u0443\u0441\u0442\u044b\u043c \u0434\u043b\u044f NULL"}</span>
                </label>
                <label className="grid gap-1">
                  <span className="text-xs font-medium text-zinc-500">{"\u0414\u0430\u0442\u0430 \u043e\u043a\u043e\u043d\u0447\u0430\u043d\u0438\u044f"}</span>
                  <input
                    data-testid="assignment-correction-date-to"
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  />
                  <span className="text-xs text-zinc-500">{"\u041e\u0441\u0442\u0430\u0432\u044c\u0442\u0435 \u043f\u0443\u0441\u0442\u044b\u043c \u0434\u043b\u044f NULL"}</span>
                </label>
              </div>

              <label className="grid gap-1">
                <span className="text-xs font-medium text-zinc-500">{"\u0414\u0430\u0442\u0430 \u043a\u043e\u0440\u0440\u0435\u043a\u0442\u0438\u0440\u043e\u0432\u043a\u0438 *"}</span>
                <input
                  data-testid="assignment-correction-effective-date"
                  type="date"
                  value={effectiveDate}
                  onChange={(e) => setEffectiveDate(e.target.value)}
                  className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  required
                />
              </label>

              <label className="grid gap-1">
                <span className="text-xs font-medium text-zinc-500">Причина *</span>
                <input
                  data-testid="assignment-correction-reason"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  required
                />
              </label>

              <label className="grid gap-1">
                <span className="text-xs font-medium text-zinc-500">{"\u041a\u043e\u043c\u043c\u0435\u043d\u0442\u0430\u0440\u0438\u0439 *"}</span>
                <textarea
                  data-testid="assignment-correction-comment"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows={3}
                  className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  required
                />
              </label>
            </div>
          )}

          <div className="mt-auto flex justify-end gap-2 border-t border-zinc-200 pt-4 dark:border-zinc-800">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={saving || !prefillDone || !fullName.trim()}
              data-testid="assignment-correction-submit"
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Сохранение…" : "Сохранить корректировку"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
