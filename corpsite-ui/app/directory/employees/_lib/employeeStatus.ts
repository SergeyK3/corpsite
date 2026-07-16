export type EmployeeStatusVariant = "active" | "inactive" | "terminated" | "archived" | "applicant";

export type EmployeeStatusMeta = {
  variant: EmployeeStatusVariant;
  label: string;
  active: boolean;
};

function computeIsActive(it: Record<string, unknown> | null | undefined): boolean {
  if (!it) return true;

  if (typeof it.status === "string") {
    const s = String(it.status).toLowerCase();
    if (s === "active") return true;
    if (s === "inactive" || s === "archived") return false;
  }

  if (typeof it.is_active === "boolean") return it.is_active;
  if (typeof it.isActive === "boolean") return it.isActive;
  if ("date_to" in it) return it.date_to == null;
  if ("dateTo" in it) return it.dateTo == null;
  return true;
}

export function employeeStatusMeta(it: unknown): EmployeeStatusMeta {
  const item = (it ?? {}) as Record<string, unknown>;
  const raw = String(item.status ?? "").trim().toLowerCase();
  const recordKind = String(item.record_kind ?? "").trim().toLowerCase();

  if (raw === "applicant" || recordKind === "applicant") {
    return { variant: "applicant", label: "Заявитель", active: false };
  }

  const active = computeIsActive(item);

  if (raw === "archived") {
    return { variant: "archived", label: "Архив", active: false };
  }

  if (active) {
    return { variant: "active", label: "Работает", active: true };
  }

  if (raw.includes("увол") || raw === "fired") {
    return { variant: "terminated", label: "Уволен", active: false };
  }

  const dateTo = item.date_to ?? item.dateTo;
  if (dateTo != null && String(dateTo).trim() !== "") {
    return { variant: "terminated", label: "Завершён", active: false };
  }

  return { variant: "inactive", label: "Не работает", active: false };
}

export function employeeStatusBadgeClass(variant: EmployeeStatusVariant): string {
  const base =
    "inline-flex items-center rounded-md border px-2 py-0.5 text-[12px] leading-4 font-medium";

  if (variant === "active") {
    return `${base} border-zinc-200 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 text-zinc-900 dark:text-zinc-50`;
  }

  if (variant === "applicant") {
    return `${base} border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-100`;
  }

  return `${base} border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-zinc-600 dark:text-zinc-400`;
}
