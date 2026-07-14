"use client";

import Link from "next/link";

import EmployeeStatusBadge from "../../employees/_components/EmployeeStatusBadge";
import type { EmployeeDetails } from "../../employees/_lib/types";
import { buildHrChangeEventsHref } from "../_lib/hrChangeEventsApi.client";

type Props = {
  employeeId: string;
  details: EmployeeDetails;
};

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const dt = new Date(v);
  if (Number.isNaN(dt.getTime())) return String(v);
  return dt.toLocaleDateString("ru-RU");
}

function fieldCard(label: string, value: string) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-zinc-50/80 px-3 py-2.5 dark:border-zinc-800 dark:bg-zinc-900/40">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-0.5 text-sm font-medium text-zinc-900 dark:text-zinc-50">{value}</div>
    </div>
  );
}

export default function EmployeeCardGeneralSection({ employeeId, details }: Props) {
  const d = details as Record<string, unknown>;
  const fio = String(d.fio ?? d.full_name ?? d.fullName ?? "—").trim() || "—";
  const tabNo = String(d.employee_id ?? d.id ?? employeeId);
  const dateFrom = fmtDate((d.date_from ?? d.dateFrom) as string | null | undefined);
  const dateTo = fmtDate((d.date_to ?? d.dateTo) as string | null | undefined);

  const employeeNumericId = Number(employeeId);
  const changeEventsHref = buildHrChangeEventsHref(
    Number.isFinite(employeeNumericId) && employeeNumericId > 0
      ? { employee_id: employeeNumericId }
      : {},
  );

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {fieldCard("ФИО", fio)}
        {fieldCard("Табельный номер", tabNo)}
        <div className="rounded-lg border border-zinc-200 bg-zinc-50/80 px-3 py-2.5 dark:border-zinc-800 dark:bg-zinc-900/40">
          <div className="text-xs text-zinc-500">Статус</div>
          <div className="mt-1">
            <EmployeeStatusBadge item={details} />
          </div>
        </div>
        {fieldCard("Дата приёма", dateFrom)}
        {fieldCard("Дата по", dateTo)}
      </div>
      <p className="text-xs text-zinc-500">
        <Link href={changeEventsHref} className="font-medium text-blue-700 hover:underline dark:text-blue-300">
          История изменений реестра
        </Link>
        {" · "}
        сверка с HR-импортом и каноническим реестром
      </p>
    </div>
  );
}
