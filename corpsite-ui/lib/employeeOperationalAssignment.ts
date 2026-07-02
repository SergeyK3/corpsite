import type { EmployeeDetails } from "@/app/directory/employees/_lib/types";

export function employeeOrgUnitLabel(details: EmployeeDetails | null | undefined): string {
  if (!details) return "—";
  const d = details as Record<string, unknown>;
  const orgUnit = d.org_unit as { name?: string } | null | undefined;
  return String(orgUnit?.name ?? d.org_unit_name ?? d.department_name ?? "").trim() || "—";
}

export function employeePositionLabel(details: EmployeeDetails | null | undefined): string {
  if (!details) return "—";
  const d = details as Record<string, unknown>;
  const position = d.position as { name?: string } | null | undefined;
  return String(position?.name ?? d.position_name ?? "").trim() || "—";
}

export function isOperationallyEnrolled(details: EmployeeDetails | null | undefined): boolean {
  if (!details) return false;
  const d = details as Record<string, unknown>;
  const orgUnitId = Number(
    (d.org_unit as { unit_id?: unknown } | null | undefined)?.unit_id ?? d.org_unit_id ?? 0,
  );
  const positionId = Number((d.position as { id?: unknown } | null | undefined)?.id ?? d.position_id ?? 0);
  return Number.isFinite(orgUnitId) && orgUnitId > 0 && Number.isFinite(positionId) && positionId > 0;
}

export function isActiveEmployee(details: EmployeeDetails | null | undefined): boolean {
  if (!details) return false;
  const status = String((details as Record<string, unknown>).status ?? "").trim().toLowerCase();
  return status === "active";
}
