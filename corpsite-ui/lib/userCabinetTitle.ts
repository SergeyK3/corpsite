import type { MeInfo } from "./types";

/** HR position from linked employee record (`public.positions.name`). */
export function resolveEmployeePositionTitle(me: MeInfo | null | undefined): string {
  return String(me?.position_name ?? "").trim();
}

/** Platform Role label from RBAC (`public.roles.name`). */
export function resolvePlatformRoleLabel(me: MeInfo | null | undefined): string {
  return String(me?.role_name_ru ?? me?.role_name ?? "").trim();
}

/** Platform roles whose cabinet identity follows RBAC, not a stale HR position snapshot. */
const PLATFORM_ROLE_CABINET_IDENTITY_CODES = new Set(["HR_HEAD"]);

export function platformRoleDefinesCabinetIdentity(roleCode: string | null | undefined): boolean {
  return PLATFORM_ROLE_CABINET_IDENTITY_CODES.has(String(roleCode ?? "").trim().toUpperCase());
}

/**
 * Cabinet header title: employee position first, Platform Role as fallback.
 * HR_HEAD is an exception: Platform Role change switches cabinet before HR updates position.
 */
export function resolveCabinetTitle(me: MeInfo | null | undefined): string {
  const role = resolvePlatformRoleLabel(me);
  if (platformRoleDefinesCabinetIdentity(me?.role_code) && role) {
    return role;
  }

  const position = resolveEmployeePositionTitle(me);
  if (position) return position;

  return role || "Сотрудник";
}
