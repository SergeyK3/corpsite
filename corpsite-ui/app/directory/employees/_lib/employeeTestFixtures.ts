import type { Department, EmployeeDTO, LinkedUserDTO, OrgUnitRef, Position } from "./types";

type EmployeeInput = Omit<Partial<EmployeeDTO>, "id" | "user" | "department" | "position" | "org_unit"> & {
  id?: string | number | null;
  employee_id?: number;
  employment_rate?: number;
  is_active?: boolean;
  user?: Partial<LinkedUserDTO> | null;
  department?: Partial<Department> | null;
  position?: Partial<Position> | null;
  org_unit?: Partial<OrgUnitRef> | null;
};

/** Complete API-shaped employee while keeping legacy list aliases used in tests. */
export function employeeFixture(input: EmployeeInput): EmployeeDTO & { employee_id?: number; employment_rate?: number } {
  const user = input.user ? {
    user_id: input.user.user_id ?? 1,
    login: input.user.login ?? null,
    role_id: input.user.role_id ?? null,
    role_name: input.user.role_name ?? null,
    is_active: input.user.is_active ?? true,
    ...input.user,
  } : null;
  return {
    ...input,
    id: input.id == null ? input.employee_id == null ? null : String(input.employee_id) : String(input.id),
    fio: input.fio ?? null,
    department: input.department ? { id: input.department.id ?? null, name: input.department.name ?? null } : null,
    position: input.position ? { id: input.position.id ?? null, name: input.position.name ?? null, ...input.position } : null,
    org_unit: input.org_unit ? { unit_id: input.org_unit.unit_id ?? null, name: input.org_unit.name ?? null, code: input.org_unit.code ?? null, parent_unit_id: input.org_unit.parent_unit_id ?? null, is_active: input.org_unit.is_active ?? null, ...input.org_unit } : null,
    rate: input.rate ?? input.employment_rate ?? null,
    status: input.status ?? "active",
    date_from: input.date_from ?? null,
    date_to: input.date_to ?? null,
    user,
  };
}
