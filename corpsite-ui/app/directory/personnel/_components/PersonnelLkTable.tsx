"use client";

import * as React from "react";
import Link from "next/link";

import { buildPersonalCardHref } from "@/lib/employeeCardNav";
import { downloadIntakePdfByApplicationId } from "@/app/intake/_lib/intakePdfOpen.client";
import { downloadPersonCardPdf } from "../_lib/personCardPdfOpen.client";
import type { PersonnelLkRegistryItem } from "../_lib/personnelLkApi.client";
import {
  formatPersonnelLkRate,
  personnelLkRecordKindLabel,
  personnelLkStatusLabel,
} from "../_lib/personnelLkLabels";

type Props = {
  items: PersonnelLkRegistryItem[];
  loading: boolean;
  registryReturnHref: string;
  onOpenApplicant: (applicationId: number) => void;
  showBulkSelect?: boolean;
  selectedEmployeeIds?: Set<number>;
  onToggleEmployee?: (employeeId: number) => void;
  onToggleSelectAllPage?: () => void;
  allPageEmployeesSelected?: boolean;
  somePageEmployeesSelected?: boolean;
};

const actionClass =
  "rounded-md border border-zinc-200 bg-zinc-100 px-2.5 py-1 text-[12px] leading-4 text-zinc-900 transition hover:bg-zinc-200 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-50 dark:hover:bg-zinc-700";

export default function PersonnelLkTable({
  items,
  loading,
  registryReturnHref,
  onOpenApplicant,
  showBulkSelect = false,
  selectedEmployeeIds = new Set(),
  onToggleEmployee,
  onToggleSelectAllPage,
  allPageEmployeesSelected = false,
  somePageEmployeesSelected = false,
}: Props) {
  const [pdfLoadingId, setPdfLoadingId] = React.useState<number | null>(null);
  const [pdfError, setPdfError] = React.useState<{ applicationId: number; message: string } | null>(null);
  const [personPdfLoadingId, setPersonPdfLoadingId] = React.useState<number | null>(null);
  const [personPdfError, setPersonPdfError] = React.useState<{ personId: number; message: string } | null>(null);
  const colSpan = showBulkSelect ? 7 : 6;

  async function downloadPdf(applicationId: number) {
    if (pdfLoadingId != null) return;
    setPdfLoadingId(applicationId);
    setPdfError(null);
    const result = await downloadIntakePdfByApplicationId(applicationId);
    setPdfLoadingId(null);
    if (!result.ok) setPdfError({ applicationId, message: result.error });
  }

  async function downloadPersonPdf(personId: number) {
    if (personPdfLoadingId != null) return;
    setPersonPdfLoadingId(personId);
    setPersonPdfError(null);
    const result = await downloadPersonCardPdf(personId);
    setPersonPdfLoadingId(null);
    if (!result.ok) setPersonPdfError({ personId, message: result.error });
  }

  return (
    <div
      className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800"
      data-testid="personnel-lk-table"
    >
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr className="bg-zinc-100 text-left dark:bg-zinc-900">
              {showBulkSelect ? (
                <th className="w-10 px-3 py-2">
                  <input
                    type="checkbox"
                    checked={allPageEmployeesSelected}
                    ref={(node) => {
                      if (node) node.indeterminate = somePageEmployeesSelected && !allPageEmployeesSelected;
                    }}
                    onChange={() => onToggleSelectAllPage?.()}
                    aria-label="Выбрать всех сотрудников на странице"
                    data-testid="personnel-lk-select-all"
                  />
                </th>
              ) : null}
              <th className="min-w-[260px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                ФИО
              </th>
              <th className="min-w-[140px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                ИИН
              </th>
              <th className="w-[140px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Тип
              </th>
              <th className="w-[100px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Ставка
              </th>
              <th className="min-w-[180px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Статус
              </th>
              <th className="min-w-[180px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Действие
              </th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={colSpan} className="px-3 py-8 text-center text-sm text-zinc-500">
                  {loading ? "Загрузка…" : "Записи не найдены."}
                </td>
              </tr>
            ) : (
              items.map((item) => {
                const isSelectableEmployee =
                  showBulkSelect && item.record_kind === "employee" && item.employee_id != null;
                const employeeId = item.employee_id ?? null;

                return (
                  <tr
                    key={`${item.record_kind}-${item.person_id}`}
                    data-testid={`personnel-lk-row-${item.record_kind}-${item.person_id}`}
                  >
                    {showBulkSelect ? (
                      <td className="px-3 py-1.5">
                        {isSelectableEmployee && employeeId != null ? (
                          <input
                            type="checkbox"
                            checked={selectedEmployeeIds.has(employeeId)}
                            onChange={() => onToggleEmployee?.(employeeId)}
                            aria-label={`Выбрать ${item.fio || "сотрудника"}`}
                            data-testid={`personnel-lk-select-employee-${employeeId}`}
                          />
                        ) : null}
                      </td>
                    ) : null}
                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-900 dark:text-zinc-50">
                      {item.fio || "—"}
                    </td>
                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                      {item.iin || "—"}
                    </td>
                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                      {personnelLkRecordKindLabel(item.record_kind)}
                    </td>
                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                      {formatPersonnelLkRate(item.rate)}
                    </td>
                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                      {personnelLkStatusLabel(item)}
                    </td>
                    <td className="px-3 py-1.5">
                      {item.record_kind === "employee" ? (
                        <div className="flex flex-wrap items-start gap-2">
                        {Number.isSafeInteger(item.person_id) && item.person_id > 0 ? <button
                          type="button"
                          disabled={personPdfLoadingId != null}
                          onClick={() => void downloadPersonPdf(item.person_id)}
                          className={actionClass}
                          data-testid={`personnel-lk-pdf-person-${item.person_id}`}
                        >
                          {personPdfLoadingId === item.person_id ? "Формирование…" : "PDF"}
                        </button> : null}
                        <Link
                          href={buildPersonalCardHref(
                            { personId: item.person_id },
                            { returnTo: registryReturnHref },
                          )}
                          className={actionClass}
                          data-testid={`personnel-lk-open-card-${item.person_id}`}
                        >
                          Открыть
                        </Link>
                        {personPdfError?.personId === item.person_id ? <p className="basis-full text-xs text-red-600" role="alert" data-testid={`personnel-lk-pdf-person-error-${item.person_id}`}>{personPdfError.message}</p> : null}
                        </div>
                      ) : item.record_kind === "applicant" && item.active_application_id != null ? (
                        <div className="flex flex-wrap items-start gap-2">
                        <button
                          type="button"
                          disabled={pdfLoadingId != null}
                          onClick={() => void downloadPdf(item.active_application_id!)}
                          className={actionClass}
                          data-testid={`personnel-lk-pdf-application-${item.active_application_id}`}
                        >
                          {pdfLoadingId === item.active_application_id ? "Формирование…" : "PDF"}
                        </button>
                        <button
                          type="button"
                          onClick={() => onOpenApplicant(item.active_application_id!)}
                          className={actionClass}
                          data-testid={`personnel-lk-open-application-${item.active_application_id}`}
                        >
                          Открыть
                        </button>
                        {pdfError?.applicationId === item.active_application_id ? (
                          <p className="basis-full text-xs text-red-600" role="alert" data-testid={`personnel-lk-pdf-error-${item.active_application_id}`}>
                            {pdfError.message}
                          </p>
                        ) : null}
                        </div>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
