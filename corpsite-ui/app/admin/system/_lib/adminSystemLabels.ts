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
