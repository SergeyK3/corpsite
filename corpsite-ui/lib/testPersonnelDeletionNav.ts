import type { MeInfo } from "./types";

export const TEST_PERSONNEL_ADMIN_HREF = "/admin/system/test-personnel-data";
export const TEST_PERSONNEL_APPROVALS_HREF = "/directory/personnel/test-data-deletion-approvals";

export function canSeeTestPersonnelAdmin(me: MeInfo | null | undefined): boolean {
  return me?.can_request_test_personnel_deletion === true;
}

export function canSeeTestPersonnelApprovals(me: MeInfo | null | undefined): boolean {
  return me?.can_approve_test_personnel_deletion === true;
}

export function isTestPersonnelAdminRoute(pathname: string): boolean {
  return pathname === TEST_PERSONNEL_ADMIN_HREF || pathname.startsWith(`${TEST_PERSONNEL_ADMIN_HREF}/`);
}

export function isTestPersonnelApprovalsRoute(pathname: string): boolean {
  return pathname === TEST_PERSONNEL_APPROVALS_HREF || pathname.startsWith(`${TEST_PERSONNEL_APPROVALS_HREF}/`);
}
