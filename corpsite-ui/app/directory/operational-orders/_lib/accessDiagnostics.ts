import type { MeInfo } from "@/lib/types";

/** Minimum permission recommended for section visibility (documentation + diagnostics). */
export const OO_SECTION_READ_PERMISSION = "OPERATIONAL_ORDERS_INTAKE_READ";

/** Permissions that grant `has_operational_orders_read` on the backend. */
export const OO_READ_PROJECTION_SOURCES = [
  "OPERATIONAL_ORDERS_INTAKE_READ",
  "OPERATIONAL_ORDERS_INTAKE_OPERATE",
  "OPERATIONAL_ORDERS_PROMOTE",
  "OPERATIONAL_ORDERS_SIGNATURE_READINESS_READ",
] as const;

const PERMISSION_LABELS: Record<string, string> = {
  OPERATIONAL_ORDERS_INTAKE_READ: "Operational Orders Read (intake_read)",
  OPERATIONAL_ORDERS_INTAKE_OPERATE: "Operational Orders Operate",
  OPERATIONAL_ORDERS_PROMOTE: "Operational Orders Promote",
  OPERATIONAL_ORDERS_SIGNATURE_READINESS_READ: "Operational Orders Signature Readiness Read",
  OO_FORBIDDEN: "Operational Orders access denied",
};

export type OperationalOrdersAccessDiagnostics = {
  hasOperationalOrdersRead: boolean;
  hasPersonnelAdmin: boolean;
  missingRecommendedPermissions: string[];
  projectionFlags: {
    has_operational_orders_read: boolean;
    intake_read: boolean;
    intake_operate: boolean;
    promote: boolean;
    signature_readiness_read: boolean;
  };
  endpoint?: string;
  httpStatus?: number;
  errorCode?: string;
};

export function isOperationalOrdersDeveloperDiagnosticsEnabled(): boolean {
  return process.env.NODE_ENV === "development";
}

export function buildOperationalOrdersAccessDiagnostics(
  me: MeInfo | null | undefined,
  extra?: Pick<OperationalOrdersAccessDiagnostics, "endpoint" | "httpStatus" | "errorCode">,
): OperationalOrdersAccessDiagnostics {
  const perms = me?.operational_orders_permissions ?? {};
  const hasOperationalOrdersRead = Boolean(me?.is_privileged || me?.has_operational_orders_read);

  const projectionFlags = {
    has_operational_orders_read: me?.has_operational_orders_read === true,
    intake_read: perms.intake_read === true,
    intake_operate: perms.intake_operate === true,
    promote: perms.promote === true,
    signature_readiness_read: perms.signature_readiness_read === true,
  };

  const missingRecommendedPermissions = hasOperationalOrdersRead
    ? []
    : [OO_SECTION_READ_PERMISSION];

  return {
    hasOperationalOrdersRead,
    hasPersonnelAdmin: me?.has_personnel_admin === true,
    missingRecommendedPermissions,
    projectionFlags,
    ...extra,
  };
}

export function explainOperationalOrdersSectionAccessDenied(me: MeInfo | null | undefined): {
  title: string;
  message: string;
  diagnostics: OperationalOrdersAccessDiagnostics;
} {
  const diagnostics = buildOperationalOrdersAccessDiagnostics(me);

  return {
    title: "Нет доступа к разделу «Производственные приказы»",
    message:
      "Для доступа к разделу требуется разрешение Operational Orders Read (OPERATIONAL_ORDERS_INTAKE_READ) или эквивалентная projection has_operational_orders_read. " +
      "Доступ к кадровым процессам (Personnel Orders) не предоставляет автоматического доступа к производственным приказам.",
    diagnostics,
  };
}

export function explainOperationalOrdersApiForbidden(
  err: unknown,
  me: MeInfo | null | undefined,
  endpoint?: string,
): { message: string; diagnostics: OperationalOrdersAccessDiagnostics } {
  const e = err as { status?: number; details?: unknown; body?: unknown; detail?: unknown };
  const status = Number(e.status ?? 0);
  const body = (e.details ?? e.body ?? e.detail) as { code?: string } | undefined;
  const code = typeof body?.code === "string" ? body.code : status === 403 ? "OO_FORBIDDEN" : undefined;

  const diagnostics = buildOperationalOrdersAccessDiagnostics(me, {
    endpoint,
    httpStatus: status || undefined,
    errorCode: code,
  });

  const permissionHint = code && PERMISSION_LABELS[code] ? PERMISSION_LABELS[code] : "Operational Orders permission";
  const message =
    status === 403
      ? `Недостаточно прав для выполнения операции (${permissionHint}).`
      : "Не удалось выполнить операцию.";

  return { message, diagnostics };
}

export function formatAccessDiagnosticsForDeveloper(diagnostics: OperationalOrdersAccessDiagnostics): string[] {
  const lines = [
    `has_operational_orders_read: ${diagnostics.projectionFlags.has_operational_orders_read}`,
    `intake_read: ${diagnostics.projectionFlags.intake_read}`,
    `intake_operate: ${diagnostics.projectionFlags.intake_operate}`,
    `promote: ${diagnostics.projectionFlags.promote}`,
    `signature_readiness_read: ${diagnostics.projectionFlags.signature_readiness_read}`,
  ];

  if (diagnostics.missingRecommendedPermissions.length) {
    lines.push(`missing: ${diagnostics.missingRecommendedPermissions.join(", ")}`);
  }
  if (diagnostics.hasPersonnelAdmin) {
    lines.push("note: has_personnel_admin=true (HR access does not imply OO access)");
  }
  if (diagnostics.httpStatus) {
    lines.push(`http: ${diagnostics.httpStatus}${diagnostics.errorCode ? ` · ${diagnostics.errorCode}` : ""}`);
  }
  if (diagnostics.endpoint) {
    lines.push(`endpoint: ${diagnostics.endpoint}`);
  }

  return lines;
}
