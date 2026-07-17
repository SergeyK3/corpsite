import {
  personnelApplicationStatusBadgeClass,
  personnelApplicationStatusLabel,
} from "./personnelApplicationLabels";

export type ApplicantWorkflowStatusInput = {
  status: string;
  intake_link_status?: string | null;
  intake_draft_status?: string | null;
};

export type ApplicantWorkflowStatus = {
  key: string;
  label: string;
};

const PERSONAL_CARD_OPEN_STATUSES = new Set([
  "intake_submitted",
  "under_review",
  "review_completed",
  "resolution_pending",
  "awaiting_director_resolution",
  "approved",
  "order_draft_created",
  "completed",
]);

const HIRE_ORDER_FROM_CARD_STATUSES = new Set([
  "intake_submitted",
  "under_review",
  "review_completed",
  "resolution_pending",
  "awaiting_director_resolution",
  "approved",
  "order_draft_created",
]);

const TERMINAL_STATUSES = new Set([
  "completed",
  "withdrawn",
  "cancelled",
  "expired",
  "rejected",
  "resolution_rejected",
]);

export function resolveApplicantWorkflowStatus(
  input: ApplicantWorkflowStatusInput,
): ApplicantWorkflowStatus {
  const status = String(input.status || "").trim();
  const linkStatus = String(input.intake_link_status || "").trim();
  const draftStatus = String(input.intake_draft_status || "").trim();

  if (TERMINAL_STATUSES.has(status)) {
    return { key: status, label: personnelApplicationStatusLabel(status) };
  }

  if (status === "registered") {
    return { key: "new_application", label: "Новое заявление" };
  }

  if (status === "intake_pending") {
    if (linkStatus === "opened" || draftStatus === "editable") {
      return { key: "filling", label: "Заполняет" };
    }
    return { key: "awaiting_fill", label: "Ожидает заполнения" };
  }

  if (status === "intake_submitted") {
    return { key: "card_filled", label: "Личная карточка заполнена" };
  }

  if (status === "under_review") {
    return { key: "under_review", label: "На проверке HR" };
  }

  if (status === "review_completed") {
    return { key: "ready_for_processing", label: "Готово к оформлению" };
  }

  if (status === "resolution_pending" || status === "awaiting_director_resolution") {
    return { key: status, label: "Ожидает резолюции директора" };
  }

  if (status === "approved" || status === "order_draft_created") {
    return { key: status, label: personnelApplicationStatusLabel(status) };
  }

  if (status === "revision_requested") {
    return { key: status, label: "На уточнении" };
  }

  return { key: status || "unknown", label: personnelApplicationStatusLabel(status) };
}

export function applicantWorkflowStatusBadgeClass(input: ApplicantWorkflowStatusInput): string {
  const workflow = resolveApplicantWorkflowStatus(input);
  switch (workflow.key) {
    case "new_application":
      return "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-200";
    case "awaiting_fill":
      return "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200";
    case "filling":
      return "bg-indigo-100 text-indigo-900 dark:bg-indigo-950 dark:text-indigo-200";
    case "card_filled":
      return "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200";
    case "under_review":
      return "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200";
    case "ready_for_processing":
      return "bg-teal-100 text-teal-900 dark:bg-teal-950 dark:text-teal-200";
    default:
      return personnelApplicationStatusBadgeClass(input.status);
  }
}

export function canOpenApplicantPersonalCard(status: string | null | undefined): boolean {
  return PERSONAL_CARD_OPEN_STATUSES.has(String(status || "").trim());
}

export function canCreateHireOrderFromApplicantCard(status: string | null | undefined): boolean {
  return HIRE_ORDER_FROM_CARD_STATUSES.has(String(status || "").trim());
}

export function buildIntakePublicUrl(intakeUrlPath: string | null | undefined): string | null {
  const path = String(intakeUrlPath || "").trim();
  if (!path) return null;
  if (typeof window !== "undefined" && window.location?.origin) {
    return `${window.location.origin}${path.startsWith("/") ? path : `/${path}`}`;
  }
  return path;
}

const INTAKE_LINK_STORAGE_PREFIX = "personnel-intake-link:";

export function persistIntakeLinkPath(applicationId: number, intakeUrlPath: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(`${INTAKE_LINK_STORAGE_PREFIX}${applicationId}`, intakeUrlPath);
  } catch {
    // ignore quota / privacy mode
  }
}

export function readPersistedIntakeLinkPath(applicationId: number): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(`${INTAKE_LINK_STORAGE_PREFIX}${applicationId}`);
  } catch {
    return null;
  }
}

export function clearPersistedIntakeLinkPath(applicationId: number): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(`${INTAKE_LINK_STORAGE_PREFIX}${applicationId}`);
  } catch {
    // ignore
  }
}

export async function copyTextToClipboard(text: string): Promise<boolean> {
  if (!text.trim()) return false;
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // fall through
    }
  }
  return false;
}
