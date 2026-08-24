// FILE: corpsite-ui/app/directory/employees/_components/EmployeesTable.tsx
"use client";

import Link from "next/link";

import type { EmployeeListItem } from "../_lib/types";
import { buildEmployeeCardHref, buildPersonalCardHref } from "@/lib/employeeCardNav";
import {
  HR_DOSSIER_MISSING_EMPLOYEE_ID_TOOLTIP,
  OPEN_HR_DOSSIER_CTA,
  OPEN_PERSONAL_CARD_CTA,
} from "@/lib/personnelCardTerminology";
import EmployeeStatusBadge from "./EmployeeStatusBadge";
import {
  sortIndicator,
  type EmployeeSortColumn,
  type SortOrder,
} from "../_lib/employeeSort";

type Props = {
  items: EmployeeListItem[];
  total: number;
  limit: number;
  offset: number;
  loading: boolean;
  onOpenEmployee: (employee_id: string) => void;
  onChangePage: (nextOffset: number) => void;
  /** HR import journal: single «Открыть» link to /card. */
  showCard2Button?: boolean;
  /** Staff «Персонал»: one «Открыть» link straight to PPR personal card. */
  directPersonalCardNav?: boolean;
  /** Compact columns: ФИО, должность, отделение, статус, ставки, открыть. */
  managementView?: boolean;
  /** Sysadmin hard-delete on /directory/staff. */
  showAdminDelete?: boolean;
  deletingEmployeeId?: string | null;
  onDeleteEmployee?: (item: EmployeeListItem) => void;
  /** Staff «Персонал»: server-side sort via column headers. */
  sortable?: boolean;
  sortColumn?: EmployeeSortColumn | null;
  sortOrder?: SortOrder | null;
  onSortColumn?: (column: EmployeeSortColumn) => void;
};

function formatDate(d: string | null): string {
  if (!d) return "—";
  const dt = new Date(d);
  if (Number.isNaN(dt.getTime())) return d;
  return dt.toLocaleDateString("ru-RU");
}

function getEmployeeId(it: any): string {
  const v = it?.employee_id ?? it?.employeeId ?? it?.id;
  return v == null ? "" : String(v);
}

function getEmployeeFio(it: any): string {
  return it?.fio ?? it?.full_name ?? it?.fullName ?? it?.name ?? it?.title ?? "—";
}

function getDepartmentName(it: any): string {
  return it?.department_name ?? it?.departmentName ?? it?.department?.name ?? it?.org_unit?.name ?? "—";
}

function getPositionName(it: any): string {
  return it?.position_name ?? it?.positionName ?? it?.position?.name ?? it?.position?.title ?? "—";
}

const actionLinkClass =
  "rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2.5 py-1 text-[12px] leading-4 text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700";

const actionDisabledClass =
  "rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2.5 py-1 text-[12px] leading-4 text-zinc-900 dark:text-zinc-50 disabled:cursor-not-allowed disabled:opacity-50";

const actionDeleteClass =
  "rounded-md border border-red-200 dark:border-red-900/60 bg-red-50 dark:bg-red-950/40 px-2.5 py-1 text-[12px] leading-4 text-red-800 dark:text-red-200 transition hover:bg-red-100 dark:hover:bg-red-900/50 disabled:cursor-not-allowed disabled:opacity-50";

function getPersonId(it: any): number | null {
  const raw = it?.person_id ?? it?.personId;
  if (raw == null) return null;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function PersonalCardOpenAction({ item }: { item: any }) {
  const personId = getPersonId(item);
  const employeeId = getEmployeeId(item);

  if (personId != null) {
    return (
      <Link
        href={buildPersonalCardHref({ personId })}
        title={OPEN_PERSONAL_CARD_CTA}
        aria-label={OPEN_PERSONAL_CARD_CTA}
        className={actionLinkClass}
      >
        Открыть
      </Link>
    );
  }

  if (employeeId) {
    return (
      <Link
        href={buildEmployeeCardHref(employeeId)}
        title={OPEN_PERSONAL_CARD_CTA}
        aria-label={OPEN_PERSONAL_CARD_CTA}
        className={actionLinkClass}
      >
        Открыть
      </Link>
    );
  }

  return (
    <span title={HR_DOSSIER_MISSING_EMPLOYEE_ID_TOOLTIP} className="inline-flex">
      <button
        type="button"
        disabled
        aria-disabled="true"
        aria-label={HR_DOSSIER_MISSING_EMPLOYEE_ID_TOOLTIP}
        className={actionDisabledClass}
      >
        Открыть
      </button>
    </span>
  );
}

const sortableHeaderClass =
  "inline-flex items-center gap-1 rounded px-0.5 py-0.5 text-left transition hover:text-zinc-900 dark:hover:text-zinc-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/60";

function SortableHeader({
  label,
  column,
  activeColumn,
  activeOrder,
  onSort,
  className = "",
}: {
  label: string;
  column: EmployeeSortColumn;
  activeColumn?: EmployeeSortColumn | null;
  activeOrder?: SortOrder | null;
  onSort?: (column: EmployeeSortColumn) => void;
  className?: string;
}) {
  const active = activeColumn === column;
  return (
    <th className={className}>
      <button
        type="button"
        className={sortableHeaderClass}
        aria-label={
          active
            ? `${label}, сортировка ${activeOrder === "desc" ? "по убыванию" : "по возрастанию"}`
            : `${label}, сортировать`
        }
        aria-sort={active ? (activeOrder === "desc" ? "descending" : "ascending") : "none"}
        onClick={() => onSort?.(column)}
      >
        <span>{label}</span>
        {active ? <span aria-hidden="true">{sortIndicator(activeOrder)}</span> : null}
      </button>
    </th>
  );
}

function StaticHeader({ label, className = "" }: { label: string; className?: string }) {
  return (
    <th className={className}>
      {label}
    </th>
  );
}

export default function EmployeesTable({
  items,
  total,
  limit,
  offset,
  loading,
  onOpenEmployee,
  onChangePage,
  showCard2Button = false,
  directPersonalCardNav = false,
  managementView = false,
  showAdminDelete = false,
  deletingEmployeeId = null,
  onDeleteEmployee,
  sortable = false,
  sortColumn = null,
  sortOrder = null,
  onSortColumn,
}: Props) {
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(Math.max(total, 1) / limit));
  const colSpan = managementView ? 6 : 9;
  const canSort = sortable && !!onSortColumn;

  const thClass =
    "px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400";

  function headerCell(label: string, column: EmployeeSortColumn, className: string) {
    if (canSort) {
      return (
        <SortableHeader
          label={label}
          column={column}
          activeColumn={sortColumn}
          activeOrder={sortOrder}
          onSort={onSortColumn}
          className={className}
        />
      );
    }
    return <StaticHeader label={label} className={className} />;
  }

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr className="bg-zinc-100 dark:bg-zinc-900 text-left">
              {!managementView ? (
                <th className={`w-[72px] ${thClass}`}>
                  Таб. №
                </th>
              ) : null}
              {headerCell("ФИО", "fio", `min-w-[300px] ${thClass}`)}
              {!managementView ? null : headerCell("Должность", "position", `min-w-[220px] ${thClass}`)}
              {headerCell(
                managementView ? "Отделение" : "Отдел",
                "department",
                `min-w-[220px] ${thClass}`,
              )}
              {!managementView ? (
                <th className={`min-w-[220px] ${thClass}`}>
                  Должность
                </th>
              ) : null}
              {headerCell("Ставка", "rate", `w-[100px] ${thClass}`)}
              {!managementView ? (
                <>
                  <th className={`w-[110px] ${thClass}`}>
                    Дата с
                  </th>
                  <th className={`w-[110px] ${thClass}`}>
                    Дата по
                  </th>
                </>
              ) : null}
              {headerCell("Статус", "status", `w-[120px] ${thClass}`)}
              <th className={`w-[120px] ${thClass}`}>
                Действия
              </th>
            </tr>
          </thead>

          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={colSpan} className="px-3 py-2.5 text-[13px] text-zinc-600 dark:text-zinc-400">
                  {loading ? "Загрузка..." : "Записи не найдены."}
                </td>
              </tr>
            ) : (
              (items as any[]).map((it) => {
                const employeeId = getEmployeeId(it);
                const fio = getEmployeeFio(it);

                return (
                  <tr key={employeeId || fio} className="border-t border-zinc-200 dark:border-zinc-800 align-middle">
                    {!managementView ? (
                      <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-900 dark:text-zinc-50">
                        {employeeId || "—"}
                      </td>
                    ) : null}

                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-900 dark:text-zinc-50">
                      {fio}
                    </td>

                    {managementView ? (
                      <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                        {getPositionName(it)}
                      </td>
                    ) : null}

                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                      {getDepartmentName(it)}
                    </td>

                    {!managementView ? (
                      <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                        {getPositionName(it)}
                      </td>
                    ) : null}

                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                      {it.employment_rate ?? it.rate ?? "—"}
                    </td>

                    {!managementView ? (
                      <>
                        <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                          {formatDate(it.date_from ?? it.dateFrom ?? null)}
                        </td>
                        <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                          {formatDate(it.date_to ?? it.dateTo ?? null)}
                        </td>
                      </>
                    ) : null}

                    <td className="px-3 py-1.5 text-[13px] leading-4">
                      <EmployeeStatusBadge item={it} />
                      {it?.termination?.verification_status === "UNVERIFIED" ? (
                        <div className="mt-1 inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-900 dark:bg-amber-950/60 dark:text-amber-200">
                          Сведения не верифицированы
                        </div>
                      ) : null}
                    </td>

                    <td className="px-3 py-1.5">
                      <div className="flex items-center gap-1.5">
                        {managementView && it?.termination?.verification_status === "UNVERIFIED" && employeeId ? (
                          <button
                            type="button"
                            onClick={() => onOpenEmployee(employeeId)}
                            className={actionLinkClass}
                          >
                            Заполнить сведения об увольнении
                          </button>
                        ) : null}
                        {directPersonalCardNav ? (
                          <PersonalCardOpenAction item={it} />
                        ) : null}
                        {!directPersonalCardNav && !showCard2Button && !!employeeId ? (
                          <button
                            type="button"
                            onClick={() => onOpenEmployee(employeeId)}
                            className={actionLinkClass}
                          >
                            Открыть
                          </button>
                        ) : null}
                        {!directPersonalCardNav && showCard2Button && !!employeeId ? (
                          <Link
                            href={buildEmployeeCardHref(employeeId)}
                            title={OPEN_HR_DOSSIER_CTA}
                            aria-label={OPEN_HR_DOSSIER_CTA}
                            className={actionLinkClass}
                          >
                            Открыть
                          </Link>
                        ) : null}
                        {showAdminDelete && !!employeeId && onDeleteEmployee ? (
                          <button
                            type="button"
                            aria-label={`Удалить ${fio}`}
                            className={actionDeleteClass}
                            disabled={loading || deletingEmployeeId === employeeId}
                            onClick={() => onDeleteEmployee(it as EmployeeListItem)}
                          >
                            {deletingEmployeeId === employeeId ? "…" : "Удалить"}
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between border-t border-zinc-200 dark:border-zinc-800 px-3 py-2 text-sm">
        <div className="text-zinc-600 dark:text-zinc-400">
          Страница {page} из {pages}
          {loading ? " (обновление...)" : ""}
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            className="rounded border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-50"
            disabled={offset <= 0 || loading}
            onClick={() => onChangePage(Math.max(0, offset - limit))}
          >
            Назад
          </button>

          <button
            type="button"
            className="rounded border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-50"
            disabled={offset + limit >= total || loading}
            onClick={() => onChangePage(offset + limit)}
          >
            Вперёд
          </button>
        </div>
      </div>
    </div>
  );
}
