export const INTAKE_LINK_STATUS_LABELS: Record<string, string> = {
  issued: "Ссылка выдана",
  opened: "Анкета открыта",
  submitted: "Анкета заполнена",
  expired: "Ссылка истекла",
  revoked: "Ссылка отозвана",
};

export const INTAKE_DRAFT_STATUS_LABELS: Record<string, string> = {
  editable: "Черновик",
  submitted: "Анкета заполнена",
};

export function intakeLinkStatusLabel(status: string | null | undefined): string {
  const key = String(status || "").trim();
  if (!key) return "Не выдана";
  return INTAKE_LINK_STATUS_LABELS[key] || key;
}

export function intakeDraftStatusLabel(status: string | null | undefined): string {
  const key = String(status || "").trim();
  if (!key) return "—";
  return INTAKE_DRAFT_STATUS_LABELS[key] || key;
}

export function intakeLinkStatusBadgeClass(status: string | null | undefined): string {
  switch (status) {
    case "issued":
      return "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200";
    case "opened":
      return "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200";
    case "submitted":
      return "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200";
    case "expired":
    case "revoked":
      return "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
    default:
      return "bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400";
  }
}
