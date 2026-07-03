import { apiFetchJson } from "./api";

export type PlatformRoleOption = {
  id: number;
  label: string;
  code: string;
};

const PYTEST_ROLE_PATTERN = /^pytest_/i;

/** Test roles from pytest fixtures — must not appear in operator-facing catalogs. */
export function isPytestTestRole(code?: string | null, name?: string | null): boolean {
  for (const raw of [code, name]) {
    const s = String(raw ?? "").trim();
    if (s && PYTEST_ROLE_PATTERN.test(s)) return true;
  }
  return false;
}

type RoleRow = {
  role_id?: number | null;
  id?: number | null;
  role_code?: string | null;
  code?: string | null;
  role_name?: string | null;
  name?: string | null;
  is_active?: boolean | null;
};

type RolesResponse =
  | RoleRow[]
  | {
      items?: RoleRow[];
      data?: RoleRow[];
    };

function normalizeRoleRows(payload: RolesResponse): RoleRow[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.items)) return payload.items;
  if (Array.isArray(payload.data)) return payload.data;
  return [];
}

/**
 * Full Platform Role catalog (`public.roles` task roles).
 * Explicitly excludes org scope filters — not "roles in use by users".
 */
export async function listPlatformRoleCatalog(args?: {
  limit?: number;
  activeOnly?: boolean;
}): Promise<PlatformRoleOption[]> {
  const limit = args?.limit ?? 500;
  const activeOnly = args?.activeOnly ?? true;

  const query: Record<string, string | number> = {
    limit,
    offset: 0,
  };
  if (activeOnly) query.is_active = "true";

  const data = await apiFetchJson<RolesResponse>("/directory/roles", { query });

  return normalizeRoleRows(data)
    .map((row) => {
      const id = Number(row.role_id ?? row.id ?? 0);
      const code = String(row.role_code ?? row.code ?? "").trim();
      const name = String(row.role_name ?? row.name ?? "").trim();
      const label = name || code || `#${id}`;
      return { id, label, code };
    })
    .filter((row) => Number.isFinite(row.id) && row.id > 0)
    .filter((row) => !isPytestTestRole(row.code, row.label))
    .sort((a, b) => a.label.localeCompare(b.label, "ru"));
}
