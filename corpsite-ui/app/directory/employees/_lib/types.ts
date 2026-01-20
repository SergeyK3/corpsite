// corpsite-ui/app/directory/employees/_lib/types.ts

export type Department = {
  id: number;
  name: string | null;
};

export type Position = {
  id: number;
  name: string | null;
};

/**
 * То, что реально приходит с backend (/directory/employees и /directory/employees/{id})
 */
export type EmployeeDTO = {
  id: string;
  fio: string;

  department: Department;
  position: Position;

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
  fio: string;

  departmentId: number;
  departmentName: string | null;

  positionId: number;
  positionName: string | null;

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
    fio: dto.fio,

    departmentId: dto.department?.id ?? 0,
    departmentName: dto.department?.name ?? null,

    positionId: dto.position?.id ?? 0,
    positionName: dto.position?.name ?? null,

    rate: toNumber(dto.rate),
    status: dto.status,

    dateFrom: dto.date_from ?? null,
    dateTo,

    isActive,
  };
}
