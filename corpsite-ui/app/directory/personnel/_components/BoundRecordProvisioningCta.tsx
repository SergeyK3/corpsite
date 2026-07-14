"use client";

import Link from "next/link";

import { buildEmployeeCardAccessHref } from "@/lib/employeeCardNav";
import { OPEN_HR_DOSSIER_CTA, OPEN_WORKING_EMPLOYEE_CARD_CTA } from "@/lib/personnelCardTerminology";

type Props = {
  employeeId: number;
};

export default function BoundRecordProvisioningCta({ employeeId }: Props) {
  return (
    <section className="space-y-3 rounded-lg border border-amber-200 bg-amber-50/80 p-4 dark:border-amber-900/60 dark:bg-amber-950/20">
      <div>
        <h3 className="text-sm font-semibold text-amber-950 dark:text-amber-100">Доступ к Corpsite</h3>
        <p className="mt-1 text-sm text-amber-950/90 dark:text-amber-100/90">
          Сотрудник уже создан в персонале. Если сотруднику нужен вход в систему, выдайте доступ к Corpsite.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Link
          href={buildEmployeeCardAccessHref(employeeId)}
          className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          {OPEN_HR_DOSSIER_CTA}
        </Link>
        <Link
          href={`/directory/staff?employeeId=${employeeId}`}
          className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
        >
          {OPEN_WORKING_EMPLOYEE_CARD_CTA}
        </Link>
      </div>
    </section>
  );
}
