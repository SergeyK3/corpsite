// FILE: corpsite-ui/app/admin/system/org-units/_lib/adminOrgUnitsApi.client.ts
import { apiFetchJson } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";

export type OrgUnitDependencySummary = {
  can_delete: boolean;
  dependencies: Record<string, number>;
};

export type AdminOrgUnit = {
  unit_id: number;
  id?: number;
  parent_unit_id: number | null;
  parent_name?: string | null;
  name: string;
  code?: string | null;
  group_id?: number | null;
  group_name?: string | null;
  is_active: boolean;
  status?: string;
  child_count?: number;
  active_employee_count?: number;
  can_delete?: boolean;
};

export type AdminOrgUnitListResponse = {
  items: AdminOrgUnit[];
  total: number;
  limit: number;
  offset: number;
};

export type AdminOrgUnitCreatePayload = {
  name: string;
  parent_unit_id?: number | null;
  group_id: number;
  code?: string | null;
  is_active?: boolean;
  allow_duplicate?: boolean;
};

export type AdminOrgUnitUpdatePayload = {
  name?: string;
  code?: string | null;
  group_id?: number;
  parent_unit_id?: number;
  clear_parent?: boolean;
  is_active?: boolean;
  allow_duplicate?: boolean;
};

export type BulkDeleteResultItem = {
  unit_id: number;
  ok: boolean;
  error_code?: string;
  dependencies?: Record<string, number>;
  detail?: string;
};

export type BulkDeleteResponse = {
  results: BulkDeleteResultItem[];
  requested: number;
  deleted: number;
  failed: number;
};

export type AdminOrgUnitListParams = {
  q?: string;
  org_group_id?: number;
  parent_unit_id?: number;
  status?: "active" | "inactive" | "all";
  roots_only?: boolean;
  without_employees?: boolean;
  deletable_only?: boolean;
  limit?: number;
  offset?: number;
};

export const SINGLE_ROOT_INVARIANT_MESSAGE =
  "Корневое подразделение уже существует. Выберите родительское подразделение.";

export function isSingleRootInvariantDetail(detail: unknown): boolean {
  const text = String(
    typeof detail === "string"
      ? detail
      : detail && typeof detail === "object" && "detail" in detail
        ? (detail as { detail?: unknown }).detail
        : detail,
  ).trim();
  return text.includes("single-root invariant");
}

export function mapAdminOrgUnitsApiError(err: unknown, fallback: string): string {
  const e = err as { status?: number; body?: { detail?: unknown }; message?: string };
  const bodyDetail = e.body?.detail;
  if (isSingleRootInvariantDetail(bodyDetail) || isSingleRootInvariantDetail(e.message)) {
    return SINGLE_ROOT_INVARIANT_MESSAGE;
  }
  const mapped = formatThrownError(err, { fallback });
  if (isSingleRootInvariantDetail(mapped)) {
    return SINGLE_ROOT_INVARIANT_MESSAGE;
  }
  if (mapped.includes("cannot activate org unit: parent is inactive")) {
    return "Нельзя активировать подразделение: родительское подразделение неактивно.";
  }
  return mapped;
}

export async function fetchAdminOrgUnits(
  params: AdminOrgUnitListParams = {},
): Promise<AdminOrgUnitListResponse> {
  return apiFetchJson<AdminOrgUnitListResponse>("/admin/org-units", { query: params });
}

export async function fetchAdminOrgUnit(unitId: number): Promise<{
  item: AdminOrgUnit;
  dependencies: OrgUnitDependencySummary;
}> {
  return apiFetchJson(`/admin/org-units/${unitId}`);
}

export async function fetchAdminOrgUnitDependencies(
  unitId: number,
): Promise<OrgUnitDependencySummary> {
  return apiFetchJson(`/admin/org-units/${unitId}/dependencies`);
}

export async function createAdminOrgUnit(
  payload: AdminOrgUnitCreatePayload,
): Promise<{ item: AdminOrgUnit }> {
  return apiFetchJson("/admin/org-units", { method: "POST", body: payload });
}

export async function updateAdminOrgUnit(
  unitId: number,
  payload: AdminOrgUnitUpdatePayload,
): Promise<{ item: AdminOrgUnit }> {
  return apiFetchJson(`/admin/org-units/${unitId}`, { method: "PATCH", body: payload });
}

export async function activateAdminOrgUnit(unitId: number): Promise<{ item: AdminOrgUnit }> {
  return apiFetchJson(`/admin/org-units/${unitId}/activate`, { method: "POST" });
}

export async function deactivateAdminOrgUnit(unitId: number): Promise<{ item: AdminOrgUnit }> {
  return apiFetchJson(`/admin/org-units/${unitId}/deactivate`, { method: "POST" });
}

export async function deleteAdminOrgUnit(unitId: number): Promise<{ ok: boolean; unit_id: number }> {
  return apiFetchJson(`/admin/org-units/${unitId}`, { method: "DELETE" });
}

export async function bulkDeleteAdminOrgUnits(
  unitIds: number[],
): Promise<BulkDeleteResponse> {
  return apiFetchJson("/admin/org-units/bulk-delete", {
    method: "POST",
    body: { unit_ids: unitIds },
  });
}

export const DEPENDENCY_LABELS: Record<string, string> = {
  active_employees: "Активные сотрудники",
  users: "Пользователи",
  employees: "Сотрудники",
  regular_tasks: "Регулярные задачи",
  employee_events: "Кадровые события",
  person_assignments: "Назначения",
  org_unique_position: "Уникальные должности",
  child_org_units: "Дочерние подразделения",
  personnel_visibility_assignments: "Назначения видимости персонала",
  access_grants: "Права доступа",
  personnel_order_items: "Пункты кадровых приказов",
  org_unit_aliases: "Псевдонимы подразделений",
  org_unit_managers: "Руководители подразделений",
  user_org_units: "Привязки пользователей к подразделениям",
  org_unit_group_units: "Связи с группами отделений",
  legacy_position_mapping: "Наследуемые сопоставления должностей",
  permission_template_contour_rule: "Правила шаблонов доступа",
  operational_order_draft_workspaces: "Черновики операционных приказов",
  operational_order_text_provenance: "Происхождение текста операционных приказов",
  department_recoding: "Перекодировка подразделений",
  hr_change_events: "Кадровые изменения",
};

/** Приоритет отображения: сначала то, что важно оператору. */
export const DEPENDENCY_DISPLAY_ORDER: readonly string[] = [
  "active_employees",
  "users",
  "employees",
  "regular_tasks",
  "employee_events",
  "person_assignments",
  "org_unique_position",
  "child_org_units",
  "personnel_visibility_assignments",
  "access_grants",
  "personnel_order_items",
  "org_unit_aliases",
  "org_unit_managers",
  "user_org_units",
  "org_unit_group_units",
  "legacy_position_mapping",
  "permission_template_contour_rule",
  "operational_order_draft_workspaces",
  "operational_order_text_provenance",
  "department_recoding",
  "hr_change_events",
];

const DEPENDENCY_ORDER_INDEX = new Map(
  DEPENDENCY_DISPLAY_ORDER.map((key, index) => [key, index]),
);

export function dependencyLabel(key: string): string {
  return DEPENDENCY_LABELS[key] ?? "Связанные записи";
}

export function formatDependencyList(deps: Record<string, number>): string[] {
  return Object.entries(deps)
    .filter(([, count]) => count > 0)
    .sort(([a], [b]) => {
      const ai = DEPENDENCY_ORDER_INDEX.get(a) ?? Number.MAX_SAFE_INTEGER;
      const bi = DEPENDENCY_ORDER_INDEX.get(b) ?? Number.MAX_SAFE_INTEGER;
      if (ai !== bi) return ai - bi;
      return dependencyLabel(a).localeCompare(dependencyLabel(b), "ru");
    })
    .map(([key, count]) => `${dependencyLabel(key)}: ${count}`);
}

export type BulkDeleteResultRow = {
  unit_id: number;
  name: string;
  ok: boolean;
  error_code?: string;
  detail?: string;
  dependencies?: Record<string, number>;
};

export function buildBulkDeleteResultRows(
  results: BulkDeleteResultItem[],
  nameById: Map<number, string>,
): { deleted: BulkDeleteResultRow[]; failed: BulkDeleteResultRow[] } {
  const deleted: BulkDeleteResultRow[] = [];
  const failed: BulkDeleteResultRow[] = [];
  for (const row of results) {
    const entry: BulkDeleteResultRow = {
      unit_id: row.unit_id,
      name: nameById.get(row.unit_id) ?? `ID ${row.unit_id}`,
      ok: row.ok,
      error_code: row.error_code,
      detail: row.detail,
      dependencies: row.dependencies,
    };
    if (row.ok) deleted.push(entry);
    else failed.push(entry);
  }
  return { deleted, failed };
}

export function findRootUnits(items: AdminOrgUnit[]): AdminOrgUnit[] {
  return items.filter((u) => u.parent_unit_id == null);
}

export function resolveGroupLabel(
  groupId: number | null | undefined,
  groupName: string | null | undefined,
  groupLabelById: Map<number, string>,
): string {
  if (groupName?.trim()) return groupName.trim();
  if (groupId != null) {
    const fromCatalog = groupLabelById.get(groupId);
    if (fromCatalog) return fromCatalog;
    return String(groupId);
  }
  return "—";
}

export function canOfferNoParentOption(params: {
  mode: "create" | "edit";
  rootExists: boolean;
  activeUnit: AdminOrgUnit | null;
}): boolean {
  if (params.mode === "create") {
    return !params.rootExists;
  }
  return params.activeUnit?.parent_unit_id == null;
}

export function isOrgUnitHasDependenciesError(err: unknown): err is {
  status: number;
  body?: { detail?: { error_code?: string; dependencies?: Record<string, number> } };
} {
  if (!err || typeof err !== "object") return false;
  const e = err as { status?: number; body?: { detail?: unknown } };
  if (Number(e.status) !== 409) return false;
  const detail = e.body?.detail;
  if (!detail || typeof detail !== "object") return false;
  return (detail as { error_code?: string }).error_code === "ORG_UNIT_HAS_DEPENDENCIES";
}
