"use client";

import * as React from "react";

import {
  correctEmployee,
  getEmployee,
  mapApiErrorToMessage,
} from "../../employees/_lib/api.client";
import type { EmployeeDetails } from "../../employees/_lib/types";
import { getOrgUnitsTree } from "../../org-units/_lib/api.client";
import { fetchDepartmentGroups } from "@/lib/orgScope";
import {
  employeeOrgUnitLabel,
  employeePositionLabel,
  isActiveEmployee,
  isOperationallyEnrolled,
} from "@/lib/employeeOperationalAssignment";
import { findOrgGroupIdForUnit } from "@/lib/userCreateOrgScope";
import {
  getNormalizedRecord,
  listNormalizedRecords,
  mapImportApiError,
  type NormalizedRecord,
} from "../_lib/importApi.client";
import EmployeeAssignmentCorrectionDrawer, {
  type EmployeeAssignmentCorrectionFormValues,
} from "./EmployeeAssignmentCorrectionDrawer";
import ImportNormalizedRecordDrawer from "./ImportNormalizedRecordDrawer";

type Props = {
  employeeId: string;
  batchId?: number | null;
  rowId?: number | null;
  refreshToken?: number;
  onAssignmentChanged?: () => void;
};

function SummaryField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-0.5 text-sm font-medium text-zinc-900 dark:text-zinc-50">{value || "—"}</div>
    </div>
  );
}

function enrollmentStatusLabel(enrolled: boolean, active: boolean): string {
  if (!enrolled) return "Не зачислен";
  if (!active) return "Зачислен (неактивен)";
  return "Зачислен";
}

async function resolveEnrollRecord(args: {
  batchId: number;
  rowId?: number | null;
  employeeId: string;
}): Promise<NormalizedRecord | null> {
  const employeeNumId = Number(args.employeeId);
  const response = await listNormalizedRecords({
    batch_id: args.batchId,
    employee_id: Number.isFinite(employeeNumId) ? employeeNumId : undefined,
    limit: 50,
  });

  let items = response.items ?? [];
  if (args.rowId != null) {
    const byRow = items.filter((item) => item.row_id === args.rowId);
    if (byRow.length > 0) items = byRow;
  }

  if (items.length === 0) {
    const fallback = await listNormalizedRecords({ batch_id: args.batchId, limit: 200 });
    items = (fallback.items ?? []).filter((item) =>
      args.rowId != null ? item.row_id === args.rowId : item.employee_id === employeeNumId,
    );
  }

  const first = items[0];
  if (!first) return null;
  return getNormalizedRecord(first.record_id);
}

export default function EmployeeOperationalAssignmentSection({
  employeeId,
  batchId,
  rowId,
  refreshToken = 0,
  onAssignmentChanged,
}: Props) {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [details, setDetails] = React.useState<EmployeeDetails | null>(null);
  const [groupName, setGroupName] = React.useState("—");

  const [correctionOpen, setCorrectionOpen] = React.useState(false);
  const [correctionSaving, setCorrectionSaving] = React.useState(false);
  const [correctionError, setCorrectionError] = React.useState<string | null>(null);

  const [enrollDrawerOpen, setEnrollDrawerOpen] = React.useState(false);
  const [enrollRecord, setEnrollRecord] = React.useState<NormalizedRecord | null>(null);
  const [enrollLoading, setEnrollLoading] = React.useState(false);
  const [enrollError, setEnrollError] = React.useState<string | null>(null);
  const [enrollToast, setEnrollToast] = React.useState<string | null>(null);

  const loadAssignment = React.useCallback(async () => {
    if (!employeeId) {
      setDetails(null);
      setGroupName("—");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [employee, groups, tree] = await Promise.all([
        getEmployee(employeeId),
        fetchDepartmentGroups(),
        getOrgUnitsTree({ include_inactive: false }),
      ]);
      setDetails(employee);

      const orgUnitId = Number(employee.org_unit?.unit_id ?? 0);
      const groupId =
        Number.isFinite(orgUnitId) && orgUnitId > 0
          ? findOrgGroupIdForUnit(tree.items ?? [], orgUnitId)
          : null;
      const groupLabel =
        groupId != null
          ? groups.find((g) => g.group_id === groupId)?.group_name?.trim() || "—"
          : "—";
      setGroupName(groupLabel);
    } catch (e) {
      setDetails(null);
      setGroupName("—");
      setError(mapApiErrorToMessage(e));
    } finally {
      setLoading(false);
    }
  }, [employeeId]);

  React.useEffect(() => {
    void loadAssignment();
  }, [loadAssignment, refreshToken]);

  const enrolled = isOperationallyEnrolled(details);
  const active = isActiveEmployee(details);

  async function handleOpenEnrollDrawer() {
    if (!batchId) {
      setEnrollError("Не удалось определить batch для зачисления.");
      setEnrollDrawerOpen(true);
      return;
    }

    setEnrollLoading(true);
    setEnrollError(null);
    setEnrollToast(null);
    setEnrollDrawerOpen(true);

    try {
      const record = await resolveEnrollRecord({ batchId, rowId, employeeId });
      setEnrollRecord(record);
      if (!record) {
        setEnrollError("Не найдена normalized record для зачисления.");
      }
    } catch (e) {
      setEnrollRecord(null);
      setEnrollError(mapImportApiError(e, "Не удалось открыть workflow зачисления."));
    } finally {
      setEnrollLoading(false);
    }
  }

  function handleCloseEnrollDrawer() {
    setEnrollDrawerOpen(false);
    setEnrollRecord(null);
    setEnrollError(null);
  }

  function handleOpenCorrection() {
    if (!details || !enrolled) return;
    setCorrectionError(null);
    setCorrectionOpen(true);
  }

  function handleCloseCorrection() {
    if (correctionSaving) return;
    setCorrectionOpen(false);
    setCorrectionError(null);
  }

  async function handleCorrectionSubmit(values: EmployeeAssignmentCorrectionFormValues) {
    if (!employeeId || !details) return;

    setCorrectionSaving(true);
    setCorrectionError(null);
    try {
      const result = await correctEmployee(employeeId, {
        domain: "assignment",
        org_unit_id: values.org_unit_id,
        position_id: values.position_id ?? undefined,
        employment_rate: values.employment_rate,
        date_from: values.date_from,
        date_to: values.date_to,
        effective_date: values.effective_date,
        reason: values.reason,
        comment: values.comment,
      });
      setDetails(result.item);
      setCorrectionOpen(false);
      onAssignmentChanged?.();
      await loadAssignment();
    } catch (e) {
      setCorrectionError(mapApiErrorToMessage(e));
    } finally {
      setCorrectionSaving(false);
    }
  }

  if (loading) {
    return <div className="text-sm text-zinc-500">Загрузка организационного назначения…</div>;
  }

  if (error) {
    return <div className="text-sm text-red-600 dark:text-red-400">{error}</div>;
  }

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryField label="Группа отделений" value={groupName} />
        <SummaryField label="Отделение" value={employeeOrgUnitLabel(details)} />
        <SummaryField label="Кадровая должность" value={employeePositionLabel(details)} />
        <SummaryField
          label="Статус зачисления в Operational Directory"
          value={enrollmentStatusLabel(enrolled, active)}
        />
      </div>

      {!enrolled ? (
        <div className="mt-4 rounded-lg border border-amber-200/80 bg-amber-50/60 px-3 py-2.5 text-sm text-amber-950 dark:border-amber-900/60 dark:bg-amber-950/20 dark:text-amber-100">
          <span className="font-medium">Сотрудник ещё не зачислен</span>
          <span className="text-xs text-amber-900/90 dark:text-amber-100/90">
            {" "}
            — организационное назначение в Operational Directory не заполнено.
          </span>
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {enrolled ? (
          <button
            type="button"
            onClick={handleOpenCorrection}
            data-testid="assignment-correction-open"
            className="rounded border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            Исправить назначение
          </button>
        ) : null}
        {!enrolled ? (
          <button
            type="button"
            onClick={() => void handleOpenEnrollDrawer()}
            disabled={enrollLoading}
            className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {enrollLoading ? "Открытие…" : "Зачислить в Operational Directory"}
          </button>
        ) : null}
      </div>

      {enrollToast && !enrollDrawerOpen ? (
        <div className="mt-3 rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800 dark:border-green-900 dark:bg-green-950/30 dark:text-green-200">
          {enrollToast}
        </div>
      ) : null}

      <EmployeeAssignmentCorrectionDrawer
        open={correctionOpen}
        details={details}
        saving={correctionSaving}
        error={correctionError}
        onClose={handleCloseCorrection}
        onSubmit={handleCorrectionSubmit}
      />

      <ImportNormalizedRecordDrawer
        open={enrollDrawerOpen}
        record={enrollRecord}
        canEnrollEmployee
        onClose={handleCloseEnrollDrawer}
        onReviewed={(record) => {
          setEnrollRecord(record);
          handleCloseEnrollDrawer();
          onAssignmentChanged?.();
          void loadAssignment();
        }}
        onToast={(message, kind) => {
          setEnrollToast(message);
          if (kind === "success") {
            onAssignmentChanged?.();
            void loadAssignment();
          }
        }}
      />

      {enrollDrawerOpen && enrollError && !enrollRecord ? (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={handleCloseEnrollDrawer} />
          <div className="relative max-w-md rounded-xl border border-zinc-200 bg-white p-4 text-sm dark:border-zinc-800 dark:bg-zinc-950">
            <p className="text-red-600 dark:text-red-400">{enrollError}</p>
            <button
              type="button"
              className="mt-3 rounded border border-zinc-300 px-3 py-1.5 dark:border-zinc-700"
              onClick={handleCloseEnrollDrawer}
            >
              Закрыть
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
