import type { MeInfo } from "@/lib/types";

import type { OperationalOrdersPermissions } from "./types";

export function getOperationalOrdersPermissions(
  me: MeInfo | null | undefined,
): OperationalOrdersPermissions {
  const perms = me?.operational_orders_permissions;
  if (!perms) {
    if (me?.is_privileged) {
      return {
        intake_create: true,
        intake_read: true,
        intake_operate: true,
        translation_assign: true,
        translation_work: true,
        content_confirm: true,
        reconcile: true,
        editorial_ready: true,
        promote: true,
        signature_readiness_read: true,
        assign_signing_authority: true,
        mark_ready_for_signature: true,
        return_from_signature: true,
      };
    }
    return {};
  }
  return perms;
}

export function canSeeOperationalOrdersNav(me: MeInfo | null | undefined): boolean {
  if (me?.is_privileged) return true;
  return me?.has_operational_orders_read === true;
}

export function canOperateWorkspace(
  me: MeInfo | null | undefined,
  workspaceCreatorUserId?: number,
): boolean {
  if (me?.is_privileged) return true;
  const perms = getOperationalOrdersPermissions(me);
  if (perms.intake_operate) return true;
  if (me?.user_id && workspaceCreatorUserId && me.user_id === workspaceCreatorUserId) {
    return true;
  }
  return false;
}

export function canPromoteWorkspace(me: MeInfo | null | undefined): boolean {
  if (me?.is_privileged) return true;
  return Boolean(getOperationalOrdersPermissions(me).promote);
}

export function canAssignSigningAuthority(me: MeInfo | null | undefined): boolean {
  if (me?.is_privileged) return true;
  return Boolean(getOperationalOrdersPermissions(me).assign_signing_authority);
}

export function canMarkReadyForSignature(me: MeInfo | null | undefined): boolean {
  if (me?.is_privileged) return true;
  return Boolean(getOperationalOrdersPermissions(me).mark_ready_for_signature);
}

export function canReturnFromSignature(me: MeInfo | null | undefined): boolean {
  if (me?.is_privileged) return true;
  return Boolean(getOperationalOrdersPermissions(me).return_from_signature);
}
