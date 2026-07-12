import type { EmployeeDTO } from "@/app/directory/employees/_lib/types";
import { fetchDepartmentGroups } from "@/lib/orgScope";
import { resolveEmployeeOrgScopePrefill } from "@/lib/userCreateOrgScope";

import type { EmployeeSearchOption } from "./personnelOrderEmployeeSearch";

export type CurrentPlacementView = {
  org_group_id: number | null;
  org_group_name: string | null;
  org_unit_id: number | null;
  org_unit_name: string | null;
  position_id: number | null;
  position_name: string | null;
  rate: string | null;
};

function formatRate(value: string | number | null | undefined): string | null {
  if (value == null || value === "") return null;
  const text = String(value).trim();
  return text || null;
}

export function employeeDtoToSearchOption(row: EmployeeDTO): EmployeeSearchOption {
  const employeeId = Number(row.id);
  return {
    employee_id: Number.isFinite(employeeId) && employeeId > 0 ? employeeId : 0,
    full_name: String(row.fio || "").trim() || `#${row.id}`,
    org_unit_id: row.org_unit?.unit_id ?? null,
    org_unit_name: row.org_unit?.name ?? null,
    position_id: row.position?.id ?? null,
    position_name: row.position?.name ?? null,
    rate: formatRate(row.rate),
    status: String(row.status || "").trim().toLowerCase(),
  };
}

export async function resolveOrgGroupName(groupId: number | null): Promise<string | null> {
  if (groupId == null) return null;
  try {
    const groups = await fetchDepartmentGroups();
    const match = groups.find((row) => Number(row.group_id) === groupId);
    return match?.group_name ? String(match.group_name).trim() : null;
  } catch {
    return null;
  }
}

/** Build read-only current placement from employee search/detail row. */
export async function resolveCurrentPlacementView(
  option: EmployeeSearchOption,
): Promise<CurrentPlacementView> {
  let org_group_id: number | null = null;
  let org_group_name: string | null = null;

  if (option.org_unit_id != null) {
    const prefill = await resolveEmployeeOrgScopePrefill(option.org_unit_id);
    org_group_id = prefill.org_group_id;
    org_group_name = await resolveOrgGroupName(org_group_id);
  }

  return {
    org_group_id,
    org_group_name,
    org_unit_id: option.org_unit_id,
    org_unit_name: option.org_unit_name,
    position_id: option.position_id,
    position_name: option.position_name,
    rate: option.rate,
  };
}
