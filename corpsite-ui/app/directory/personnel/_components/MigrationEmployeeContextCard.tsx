// PMF-4C — employee operational context card.
"use client";

import type { EmployeeDetails } from "@/app/directory/employees/_lib/types";
import {
  employeeOrgUnitLabel,
  employeePositionLabel,
} from "@/lib/employeeOperationalAssignment";

type MigrationEmployeeContextCardProps = {
  employee: EmployeeDetails;
  iinOverride?: string | null;
};

function ContextField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-1 text-sm text-zinc-900 dark:text-zinc-100">{value || "—"}</dd>
    </div>
  );
}

function employeeRoleLabel(employee: EmployeeDetails): string {
  const roleName = employee.user?.role_name?.trim();
  if (roleName) return roleName;
  const login = employee.user?.login?.trim();
  if (login) return login;
  return "—";
}

export default function MigrationEmployeeContextCard({
  employee,
  iinOverride = null,
}: MigrationEmployeeContextCardProps) {
  const fio = employee.fio?.trim() || "—";
  const iin = iinOverride?.trim() || "—";

  return (
    <section
      aria-label="Контекст сотрудника"
      className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
    >
      <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Сотрудник</h2>
      <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <ContextField label="ФИО" value={fio} />
        <ContextField label="ИИН" value={iin} />
        <ContextField label="Отделение" value={employeeOrgUnitLabel(employee)} />
        <ContextField label="Должность" value={employeePositionLabel(employee)} />
        <ContextField label="Роль / учётная запись" value={employeeRoleLabel(employee)} />
      </dl>
      {!iinOverride ? (
        <p className="mt-3 text-xs text-zinc-500">
          ИИН отображается при наличии в связанных кадровых данных (будет добавлено на этапе
          сопоставления записей).
        </p>
      ) : null}
    </section>
  );
}
