"use client";

import * as React from "react";
import Link from "next/link";

import { buildEmployeeCardHref } from "@/lib/employeeCardNav";
import {
  formatPersonnelApplicationDate,
  formatPersonnelApplicationDateTime,
} from "../_lib/personnelApplicationLabels";
import type { PersonnelApplicationDetail } from "../_lib/personnelApplicationsApi.client";

type Props = {
  detail: PersonnelApplicationDetail;
  journalReturnHref: string;
};

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-0.5 text-sm text-zinc-800 dark:text-zinc-200">{value}</div>
    </div>
  );
}

export default function PersonnelApplicationEmploymentSection({ detail, journalReturnHref }: Props) {
  if (detail.status !== "completed" || detail.employee_id == null) {
    return null;
  }

  const orderLabel =
    detail.personnel_order_number && detail.personnel_order_date
      ? `№${detail.personnel_order_number} от ${formatPersonnelApplicationDate(detail.personnel_order_date)}`
      : detail.personnel_order_id
        ? `Приказ #${detail.personnel_order_id}`
        : "—";

  return (
    <section className="space-y-3" data-testid="personnel-application-employment-section">
      <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Трудоустройство</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field
          label="Сотрудник"
          value={
            <Link
              href={buildEmployeeCardHref(detail.employee_id, { returnTo: journalReturnHref })}
              className="text-blue-700 underline-offset-2 hover:underline dark:text-blue-300"
              data-testid="personnel-application-employee-link"
            >
              {detail.employee_full_name || `#${detail.employee_id}`}
            </Link>
          }
        />
        <Field
          label="Дата создания Employee"
          value={formatPersonnelApplicationDateTime(
            detail.employee_created_at || detail.hire_applied_at,
          )}
        />
        <Field
          label="Приказ о приёме"
          value={
            detail.personnel_order_id ? (
              <Link
                href={`/directory/personnel/orders?order_id=${detail.personnel_order_id}`}
                className="text-blue-700 underline-offset-2 hover:underline dark:text-blue-300"
                data-testid="personnel-application-hire-order-link"
              >
                {orderLabel}
              </Link>
            ) : (
              "—"
            )
          }
        />
        <Field
          label="Дата применения приказа"
          value={formatPersonnelApplicationDateTime(detail.hire_applied_at)}
        />
      </div>
    </section>
  );
}
