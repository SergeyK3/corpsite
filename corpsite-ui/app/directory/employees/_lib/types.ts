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
  id: string | null;
  person_id?: number | null;
  record_kind?: "employee" | "applicant" | string | null;
  fio: string | null;

  department: Department | null;
  position: Position | null;

  org_unit: OrgUnitRef | null;

  rate: string | number | null;
  status: "active" | "inactive" | string;

  date_from: string | null;
  date_to: string | null;

  user?: LinkedUserDTO | null;

  source?: { relation?: string } | null;
};

export type EmployeesResponse = {
  items: EmployeeDTO[];
  total: number;
};

export type EmployeeCreatePayload = {
  full_name: string;
  org_unit_id: number;
  position_id: number;
  date_from?: string | null;
  employment_rate?: number | null;
};

export type EmployeeUpdatePayload = {
  full_name?: string;
};

export type EmployeeEventDTO = {
  event_id: number;
  event_type: string;
  event_label?: string | null;
  event_class?: string | null;
  lifecycle_status?: string | null;
  metadata?: Record<string, unknown> | null;
  effective_date: string;
  from_org_unit_id: number | null;
  to_org_unit_id: number | null;
  from_position_id: number | null;
  to_position_id: number | null;
  from_rate: number | null;
  to_rate: number | null;
  order_ref: string | null;
  order_id?: number | null;
  order_item_id?: number | null;
  order_number?: string | null;
  order_date?: string | null;
  order_status?: string | null;
  order_item_number?: number | null;
  comment: string | null;
  created_by: number;
  created_at: string;
};

export type EmployeeEventsResponse = {
  items: EmployeeEventDTO[];
  total: number;
};

export type EmployeeTransferPayload = {
  to_org_unit_id: number;
  to_position_id?: number;
  to_employment_rate?: number;
  effective_date: string;
  order_ref?: string;
  comment?: string;
};

export type EmployeeTransferResponse = {
  item: EmployeeDetails;
  event: EmployeeEventDTO;
};

export type EmployeeCorrectGeneralPayload = {
  domain: "general";
  full_name: string;
  effective_date: string;
  reason: string;
  comment: string;
};

export type EmployeeCorrectAssignmentPayload = {
  domain: "assignment";
  org_unit_id: number;
  position_id?: number;
  employment_rate?: number;
  date_from: string | null;
  date_to?: string | null;
  effective_date: string;
  reason: string;
  comment: string;
};

export type EmployeeCorrectPayload = EmployeeCorrectGeneralPayload | EmployeeCorrectAssignmentPayload;

export type EmployeeCorrectResponse = {
  item: EmployeeDetails;
  event: EmployeeEventDTO;
};

export type LinkedUserDTO = {
  user_id: number;
  login: string | null;
  role_id: number | null;
  role_name: string | null;
  is_active: boolean;
  telegram_id?: number | null;
  telegram_username?: string | null;
};

export type UserDTO = {
  user_id: number;
  employee_id: number | null;
  full_name: string | null;
  login: string | null;
  google_login: string | null;
  role_id: number | null;
  role_name: string | null;
  unit_id: number | null;
  is_active: boolean;
  created_at?: string | null;
};

export type UserCreatePayload = {
  employee_id: number;
  role_id: number;
  login: string;
  password: string;
  unit_id?: number | null;
  is_active?: boolean;
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