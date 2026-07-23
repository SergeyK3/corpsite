"use client";

import * as React from "react";

import PersonnelDayDateField from "@/lib/PersonnelDayDateField";
import EmploymentTenureSummary, { useEmploymentTenureCalculation } from "./EmploymentTenureSummary";
import {
  emptyIntakeEmploymentBiographyEntry,
  employmentBiographyCellValue,
  ensureEmploymentBiographyRecordId,
  formatIntakeEmploymentPeriodCell,
  INTAKE_EMPLOYMENT_BIOGRAPHY_SHOW_TENURE_COLUMN,
  INTAKE_EMPLOYMENT_TENURE_OVERLAP_HINT,
  isIntakeEmploymentCurrent,
  sortIntakeEmploymentBiographyRows,
  type IntakeEmploymentBiographyEntry,
} from "../_lib/intakeEmploymentBiography";
import { formatTenureDisplay } from "../_lib/employmentTenureFormat";
import type { EmploymentTenureRecordResult } from "../_lib/employmentTenureApi.client";

type Props = {
  items: IntakeEmploymentBiographyEntry[];
  onChange: (items: IntakeEmploymentBiographyEntry[]) => void;
  readOnly?: boolean;
};

function updateItemAt(
  items: IntakeEmploymentBiographyEntry[],
  index: number,
  patch: Partial<IntakeEmploymentBiographyEntry>,
): IntakeEmploymentBiographyEntry[] {
  const next = [...items];
  next[index] = { ...next[index], ...patch };
  return next;
}

function EmploymentRowEditor({
  item,
  index,
  readOnly,
  onPatch,
}: {
  item: IntakeEmploymentBiographyEntry;
  index: number;
  readOnly?: boolean;
  onPatch: (patch: Partial<IntakeEmploymentBiographyEntry>) => void;
}) {
  const currentlyEmployed = isIntakeEmploymentCurrent(item);

  return (
    <div
      className="grid gap-3 border-t border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40 sm:grid-cols-2"
      data-testid={`intake-employment-editor-${index}`}
    >
      <label className="block sm:col-span-2">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Организация</span>
        <input
          type="text"
          value={item.organization}
          readOnly={readOnly}
          data-testid={`intake-employment-organization-${index}`}
          onChange={(event) => onPatch({ organization: event.target.value })}
          className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm read-only:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:read-only:bg-zinc-900"
        />
      </label>
      <label className="block sm:col-span-2">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Должность</span>
        <input
          type="text"
          value={item.position}
          readOnly={readOnly}
          data-testid={`intake-employment-position-${index}`}
          onChange={(event) => onPatch({ position: event.target.value })}
          className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm read-only:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:read-only:bg-zinc-900"
        />
      </label>
      <PersonnelDayDateField
        label="Дата начала"
        value={item.year_from}
        onChange={(value) => onPatch({ year_from: value })}
        readOnly={readOnly}
        testId={`intake-employment-year-from-${index}`}
        mode="document"
      />
      <PersonnelDayDateField
        label="Дата окончания"
        value={item.year_to}
        onChange={(value) => onPatch({ year_to: value })}
        readOnly={readOnly || currentlyEmployed}
        testId={`intake-employment-year-to-${index}`}
        mode="document"
      />
      {!readOnly ? (
        <label className="flex items-center gap-2 sm:col-span-2">
          <input
            type="checkbox"
            checked={currentlyEmployed}
            data-testid={`intake-employment-current-${index}`}
            onChange={(event) => {
              onPatch({ year_to: event.target.checked ? "" : item.year_to });
            }}
          />
          <span className="text-sm text-zinc-700 dark:text-zinc-300">Работает по настоящее время</span>
        </label>
      ) : null}
      <label className="block sm:col-span-2">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Причина увольнения</span>
        <input
          type="text"
          value={item.reason_for_leaving}
          readOnly={readOnly}
          data-testid={`intake-employment-reason-${index}`}
          onChange={(event) => onPatch({ reason_for_leaving: event.target.value })}
          className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm read-only:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:read-only:bg-zinc-900"
        />
      </label>
    </div>
  );
}

function RowActionsMenu({
  index,
  readOnly,
  onEdit,
  onDelete,
}: {
  index: number;
  readOnly?: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [open, setOpen] = React.useState(false);
  const menuRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    function onDocumentClick(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocumentClick);
    return () => document.removeEventListener("mousedown", onDocumentClick);
  }, [open]);

  if (readOnly) return null;

  return (
    <div className="relative inline-flex" ref={menuRef}>
      <button
        type="button"
        aria-label="Действия"
        aria-haspopup="menu"
        aria-expanded={open}
        data-testid={`intake-employment-actions-${index}`}
        className="rounded-lg border border-zinc-300 px-2 py-1 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        onClick={() => setOpen((value) => !value)}
      >
        ⋮
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 min-w-36 rounded-lg border border-zinc-200 bg-white py-1 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
          data-testid={`intake-employment-actions-menu-${index}`}
        >
          <button
            type="button"
            role="menuitem"
            className="block w-full px-3 py-1.5 text-left text-sm hover:bg-zinc-50 dark:hover:bg-zinc-900"
            data-testid={`intake-employment-row-edit-${index}`}
            onClick={() => {
              setOpen(false);
              onEdit();
            }}
          >
            Редактировать
          </button>
          <button
            type="button"
            role="menuitem"
            className="block w-full px-3 py-1.5 text-left text-sm text-red-700 hover:bg-red-50 dark:text-red-300 dark:hover:bg-red-950/40"
            data-testid={`intake-employment-row-delete-${index}`}
            onClick={() => {
              setOpen(false);
              onDelete();
            }}
          >
            Удалить
          </button>
        </div>
      ) : null}
    </div>
  );
}

function TenureCell({
  recordId,
  row,
}: {
  recordId: string;
  row: EmploymentTenureRecordResult;
}) {
  if (!row.included || row.days === null) {
    return (
      <span className="text-amber-700 dark:text-amber-300" title={row.warning ?? undefined}>
        {row.warning ? "—" : "—"}
      </span>
    );
  }

  return (
    <span
      className={row.overlaps_other ? "underline decoration-dotted underline-offset-2" : undefined}
      title={row.overlaps_other ? INTAKE_EMPLOYMENT_TENURE_OVERLAP_HINT : undefined}
      data-testid={`intake-employment-tenure-${recordId}`}
    >
      {formatTenureDisplay(row.days)}
    </span>
  );
}

export default function IntakeEmploymentBiographyTable({ items, onChange, readOnly = false }: Props) {
  const [expandedIndex, setExpandedIndex] = React.useState<number | null>(null);
  const rows = React.useMemo(() => sortIntakeEmploymentBiographyRows(items), [items]);
  const { calculation, loading, error } = useEmploymentTenureCalculation(items);
  const tenureByRecordId = React.useMemo(() => {
    const map = new Map<string, EmploymentTenureRecordResult>();
    calculation?.records.forEach((row) => map.set(row.record_id, row));
    return map;
  }, [calculation]);

  function patchRow(index: number, patch: Partial<IntakeEmploymentBiographyEntry>) {
    onChange(updateItemAt(items, index, patch));
  }

  function handleDelete(index: number) {
    const organization = items[index]?.organization?.trim() || "эту запись";
    if (!window.confirm(`Удалить место работы «${organization}»?`)) return;
    onChange(items.filter((_, itemIndex) => itemIndex !== index));
    setExpandedIndex((current) => (current === index ? null : current));
  }

  function handleAdd() {
    const nextItems = [...items, emptyIntakeEmploymentBiographyEntry()];
    onChange(nextItems);
    setExpandedIndex(nextItems.length - 1);
  }

  function toggleExpand(index: number) {
    setExpandedIndex((current) => (current === index ? null : index));
  }

  return (
    <div className="space-y-4" data-testid="intake-employment-biography-table">
      <EmploymentTenureSummary
        items={items}
        calculation={calculation}
        loading={loading}
        error={error}
      />

      {items.length === 0 ? (
        <p className="text-sm text-zinc-500" data-testid="intake-employment-empty">
          Записей пока нет.
        </p>
      ) : (
        <>
          <div className="hidden md:block" data-testid="intake-employment-desktop-view">
            <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
              <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
                <thead className="bg-zinc-50 dark:bg-zinc-900/60">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Период работы
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Организация
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Должность
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Причина увольнения
                    </th>
                    {INTAKE_EMPLOYMENT_BIOGRAPHY_SHOW_TENURE_COLUMN ? (
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        Стаж
                      </th>
                    ) : null}
                    <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      Действие
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ item, index }) => {
                    const recordId = ensureEmploymentBiographyRecordId(item, index);
                    const tenureRow = tenureByRecordId.get(recordId);
                    return (
                    <React.Fragment key={`desktop-${recordId}`}>
                      <tr
                        className="border-b border-zinc-200 dark:border-zinc-800"
                        data-testid={`intake-employment-row-${index}`}
                      >
                        <td className="whitespace-nowrap px-3 py-2 align-top text-sm">
                          {formatIntakeEmploymentPeriodCell(item.year_from, item.year_to)}
                        </td>
                        <td className="px-3 py-2 align-top text-sm">
                          {employmentBiographyCellValue(item.organization)}
                        </td>
                        <td className="px-3 py-2 align-top text-sm">
                          {employmentBiographyCellValue(item.position)}
                        </td>
                        <td className="px-3 py-2 align-top text-sm">
                          {employmentBiographyCellValue(item.reason_for_leaving)}
                        </td>
                        {INTAKE_EMPLOYMENT_BIOGRAPHY_SHOW_TENURE_COLUMN ? (
                          <td className="px-3 py-2 align-top text-sm">
                            {tenureRow ? (
                              <TenureCell recordId={recordId} row={tenureRow} />
                            ) : (
                              "—"
                            )}
                          </td>
                        ) : null}
                        <td className="px-3 py-2 align-top text-right">
                          <RowActionsMenu
                            index={index}
                            readOnly={readOnly}
                            onEdit={() => toggleExpand(index)}
                            onDelete={() => handleDelete(index)}
                          />
                        </td>
                      </tr>
                      {expandedIndex === index ? (
                        <tr data-testid={`intake-employment-expanded-${index}`}>
                          <td
                            colSpan={INTAKE_EMPLOYMENT_BIOGRAPHY_SHOW_TENURE_COLUMN ? 6 : 5}
                            className="p-0"
                          >
                            <EmploymentRowEditor
                              item={item}
                              index={index}
                              readOnly={readOnly}
                              onPatch={(patch) => patchRow(index, patch)}
                            />
                          </td>
                        </tr>
                      ) : null}
                    </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="space-y-3 md:hidden" data-testid="intake-employment-mobile-view">
            {rows.map(({ item, index }) => {
              const recordId = ensureEmploymentBiographyRecordId(item, index);
              const tenureRow = tenureByRecordId.get(recordId);
              return (
              <div
                key={`mobile-${recordId}`}
                className="rounded-xl border border-zinc-200 dark:border-zinc-800"
                data-testid={`intake-employment-card-${index}`}
              >
                <div className="space-y-2 p-3">
                  <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                    {employmentBiographyCellValue(item.organization)}
                  </div>
                  <div className="text-sm text-zinc-600 dark:text-zinc-400">
                    {employmentBiographyCellValue(item.position)}
                  </div>
                  <div className="text-sm text-zinc-600 dark:text-zinc-400">
                    {formatIntakeEmploymentPeriodCell(item.year_from, item.year_to)}
                  </div>
                  {INTAKE_EMPLOYMENT_BIOGRAPHY_SHOW_TENURE_COLUMN ? (
                    <div className="text-sm text-zinc-600 dark:text-zinc-400">
                      Стаж:{" "}
                      {tenureRow ? (
                        <TenureCell recordId={recordId} row={tenureRow} />
                      ) : (
                        "—"
                      )}
                    </div>
                  ) : null}
                  <div className="text-sm text-zinc-600 dark:text-zinc-400">
                    {employmentBiographyCellValue(item.reason_for_leaving)}
                  </div>
                  <div className="flex justify-end">
                    <RowActionsMenu
                      index={index}
                      readOnly={readOnly}
                      onEdit={() => toggleExpand(index)}
                      onDelete={() => handleDelete(index)}
                    />
                  </div>
                </div>
                {expandedIndex === index ? (
                  <EmploymentRowEditor
                    item={item}
                    index={index}
                    readOnly={readOnly}
                    onPatch={(patch) => patchRow(index, patch)}
                  />
                ) : null}
              </div>
              );
            })}
          </div>
        </>
      )}

      {!readOnly ? (
        <button
          type="button"
          className="rounded-lg border border-dashed border-zinc-300 px-4 py-2 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300"
          data-testid="intake-employment-add-button"
          onClick={handleAdd}
        >
          Добавить место работы
        </button>
      ) : null}
    </div>
  );
}
