// FILE: corpsite-ui/app/admin/system/_lib/adminSystemLabels.ts

export const ENFORCEMENT_NOTICE =
  "Права доступа пока не ограничивают интерфейс, если enforcement выключен.";

export const ENROLLMENT_APPLY_NOTICE =
  "Employee создаётся только после apply. Rejected элементы не переоткрываются без нового события.";

export const SENSITIVE_METADATA_KEYS = [
  "password",
  "password_hash",
  "password_plain",
  "temp_password",
  "token",
  "access_token",
  "refresh_token",
  "secret",
  "hash",
];

export function metadataHasSensitiveKeys(metadata: unknown): string[] {
  if (!metadata || typeof metadata !== "object") return [];
  const found: string[] = [];
  const walk = (obj: Record<string, unknown>, prefix = ""): void => {
    for (const [key, value] of Object.entries(obj)) {
      const full = prefix ? `${prefix}.${key}` : key;
      const lower = key.toLowerCase();
      if (SENSITIVE_METADATA_KEYS.some((s) => lower.includes(s))) {
        found.push(full);
      }
      if (value && typeof value === "object" && !Array.isArray(value)) {
        walk(value as Record<string, unknown>, full);
      }
    }
  };
  walk(metadata as Record<string, unknown>);
  return found;
}

export const AUDIT_EVENT_HIGHLIGHT: Record<string, string> = {
  LOGIN_FAILED: "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200",
  USER_LOCKED: "bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-200",
  ACCESS_GRANTED: "bg-green-100 text-green-900 dark:bg-green-950 dark:text-green-200",
  ACCESS_REVOKED: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  ENROLLMENT_APPROVED: "bg-blue-100 text-blue-900 dark:bg-blue-950 dark:text-blue-200",
  ENROLLMENT_REJECTED: "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200",
  ENROLLMENT_COMPLETED: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  VISIBILITY_GRANTED: "bg-teal-100 text-teal-900 dark:bg-teal-950 dark:text-teal-200",
  VISIBILITY_REVOKED: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
};

export function auditEventClass(eventType: string): string {
  return (
    AUDIT_EVENT_HIGHLIGHT[eventType] ??
    "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
  );
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("ru-RU");
}

export function formatFieldValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "NULL";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export const GRANT_SAFETY_WARNINGS: Record<string, string> = {
  ACCESS_NONE:
    "Внимание: роль ACCESS_NONE явно задаёт уровень NONE. При включённом enforcement может блокировать доступ.",
  SYSADMIN_CABINET:
    "Внимание: роль SYSADMIN_CABINET предоставляет доступ к кабинету системного администратора. Sidebar до Phase C2 остаётся по role_id=2.",
  ACCESS_ADMIN:
    "Внимание: роль ACCESS_ADMIN предоставляет полный административный доступ к API управления правами.",
};

export function formatActorLabel(
  userId?: number | null,
  label?: string | null,
  login?: string | null,
): string {
  if (!userId) return "—";
  if (label && label !== login) return `${label} (#${userId})`;
  if (login) return `${login} (#${userId})`;
  return `User #${userId}`;
}

export function formatAuditTargets(event: {
  target_user_id?: number | null;
  target_user_label?: string | null;
  target_user_login?: string | null;
  target_person_id?: number | null;
  target_person_label?: string | null;
  target_employee_id?: number | null;
  target_employee_label?: string | null;
}): string[] {
  const lines: string[] = [];
  if (event.target_user_id != null) {
    lines.push(
      formatActorLabel(
        event.target_user_id,
        event.target_user_label,
        event.target_user_login,
      ),
    );
  }
  if (event.target_person_id != null) {
    const name = event.target_person_label
      ? `${event.target_person_label} (#${event.target_person_id})`
      : `Person #${event.target_person_id}`;
    lines.push(name);
  }
  if (event.target_employee_id != null) {
    const name = event.target_employee_label
      ? `${event.target_employee_label} (#${event.target_employee_id})`
      : `Employee #${event.target_employee_id}`;
    lines.push(name);
  }
  return lines;
}

export type ResolutionSource = {
  grant_id?: number;
  access_role_code?: string;
  access_level?: string;
  level_rank?: number;
  source_type?: string;
  target_id?: number;
};

export function buildEffectiveAccessSummary(effective: {
  effective_role_code?: string;
  access_level?: string;
  level_rank?: number;
  explanation?: { resolution_sources?: ResolutionSource[] };
}): {
  sources: ResolutionSource[];
  resultLabel: string;
} {
  const sources = effective.explanation?.resolution_sources ?? [];
  const resultLabel = `${effective.access_level ?? "—"} (${effective.effective_role_code ?? "—"}, rank ${effective.level_rank ?? "—"})`;
  return { sources, resultLabel };
}
