import type { MeInfo } from "./types";

/** HR position from linked employee record (`public.positions.name`). */
export function resolveEmployeePositionTitle(me: MeInfo | null | undefined): string {
  return String(me?.position_name ?? "").trim();
}

/** Platform Role label from RBAC (`public.roles.name`). */
export function resolvePlatformRoleLabel(me: MeInfo | null | undefined): string {
  return String(me?.role_name_ru ?? me?.role_name ?? "").trim();
}

/**
 * Cabinet header title: employee position first, Platform Role as fallback.
 * RBAC fields are unchanged; this affects display only.
 */
export function resolveCabinetTitle(me: MeInfo | null | undefined): string {
  const position = resolveEmployeePositionTitle(me);
  if (position) return position;

  const role = resolvePlatformRoleLabel(me);
  return role || "Сотрудник";
}
