// corpsite-ui/app/directory/employees/_lib/types.ts

export type Department = {
  id: number | null;
  name: string | null;
};

export type Position = {
  id: number | null;
  name: string | null;
};

export type OrgUnitRef = {
  unit_id: number | null;
  name: string | null;
  code: string | null;
  parent_unit_id: number | null;
  is_active: boolean | null;
};

/**
 * То, что реально приходит с backend (/directory/employees и /directory/employees/{id})
 */
export type EmployeeDTO = {
  id: string;
  fio: string | null;

  department: Department | null;
  position: Position | null;

  org_unit: OrgUnitRef | null;

  rate: string | number | null;
  status: "active" | "inactive" | string;

  date_from: string | null;
  date_to: string | null;

  source?: { relation?: string } | null;
};

export type EmployeesResponse = {
  items: EmployeeDTO[];
  total: number;
};

/**
 * Алиасы для совместимости с текущими компонентами UI
 */
export type EmployeeListResponse = EmployeesResponse;
export type EmployeeDetails = EmployeeDTO;

/**
 * Таблица сейчас умеет читать DTO напрямую
 */
export type EmployeeListItem = EmployeeDTO;

/**
 * Нормализованный формат (если понадобится единый вид)
 */
export type Employee = {
  id: string;
  fio: string | null;

  departmentId: number | null;
  departmentName: string | null;

  positionId: number | null;
  positionName: string | null;

  orgUnitId: number | null;
  orgUnitName: string | null;
  orgUnitCode: string | null;

  rate: number | null;

  status: string;

  dateFrom: string | null;
  dateTo: string | null;

  isActive: boolean;
};

// ---------------------------
// Org tree (Directory / Org Structure B1+B2)
// Contract aligned with backend: /directory/org-units/tree
// ---------------------------
export type OrgTreeNode = {
  unit_id: number;
  name: string;
  code: string | null;
  parent_unit_id: number | null;
  is_active?: boolean;
  children: OrgTreeNode[];
};

export type OrgTreeResponse = {
  items: OrgTreeNode[];
};

function toNumber(v: string | number | null | undefined): number | null {
  if (v == null || v === "") return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  const n = Number(String(v).replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

export function mapEmployee(dto: EmployeeDTO): Employee {
  const dateTo = dto.date_to ?? null;
  const isActive = dto.status === "active" || dateTo == null;

  return {
    id: dto.id,
    fio: dto.fio ?? null,

    departmentId: dto.department?.id ?? null,
    departmentName: dto.department?.name ?? null,

    positionId: dto.position?.id ?? null,
    positionName: dto.position?.name ?? null,

    orgUnitId: dto.org_unit?.unit_id ?? null,
    orgUnitName: dto.org_unit?.name ?? null,
    orgUnitCode: dto.org_unit?.code ?? null,

    rate: toNumber(dto.rate),
    status: dto.status,

    dateFrom: dto.date_from ?? null,
    dateTo,

    isActive,
  };
}