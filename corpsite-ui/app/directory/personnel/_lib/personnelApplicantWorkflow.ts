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
  return isIntakeTransferCompleted(status);
}

/** True after successful intake transfer (application reaches review_completed or later). */
export function isIntakeTransferCompleted(status: string | null | undefined): boolean {
  return PERSONAL_CARD_OPEN_STATUSES.has(String(status || "").trim());
}

export type ApplicantIntakeReviewAccessInput = {
  status: string;
  intake_draft_status?: string | null;
  intake_link_status?: string | null;
};

/** Intake submitted to HR, but PPR transfer not completed yet. */
export function canOpenApplicantIntakeReview(input: ApplicantIntakeReviewAccessInput): boolean {
  if (isIntakeTransferCompleted(input.status)) {
    return false;
  }
  const status = String(input.status || "").trim();
  const draftStatus = String(input.intake_draft_status || "").trim();
  const linkStatus = String(input.intake_link_status || "").trim();
  return (
    draftStatus === "submitted" ||
    linkStatus === "submitted" ||
    status === "intake_submitted" ||
    status === "under_review"
  );
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

const APPLICANT_INTAKE_LINK_STATUSES_WITH_PATH = new Set(["issued", "opened", "submitted"]);

/** Active intake link statuses for which a persisted `/intake/{token}` path may be shown. */
export function canDisplayApplicantIntakeLink(intakeLinkStatus: string | null | undefined): boolean {
  return APPLICANT_INTAKE_LINK_STATUSES_WITH_PATH.has(String(intakeLinkStatus || "").trim());
}

/**
 * Resolve applicant-facing intake URL path from browser session cache.
 * Raw token is not stored in DB; path is persisted locally when HR issues/reissues the link.
 */
export function resolveApplicantIntakeUrlPath(
  applicationId: number,
  intakeLinkStatus: string | null | undefined,
): string | null {
  if (!canDisplayApplicantIntakeLink(intakeLinkStatus)) {
    return null;
  }
  const path = readPersistedIntakeLinkPath(applicationId);
  return path?.trim() ? path.trim() : null;
}

export function formatApplicantIntakeUrlDisplay(url: string, maxLength = 48): string {
  const value = url.trim();
  if (value.length <= maxLength) return value;
  return `${value.slice(0, Math.max(0, maxLength - 1))}…`;
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

const INTAKE_ON_BEHALF_APPROVAL_STATUSES = new Set([
  "resolution_pending",
  "awaiting_director_resolution",
  "approved",
  "order_draft_created",
]);

const INTAKE_ON_BEHALF_TERMINAL_STATUSES = new Set([
  "completed",
  "withdrawn",
  "cancelled",
  "expired",
  "rejected",
  "resolution_rejected",
]);

export type IntakeOnBehalfEditAccessInput = {
  status: string;
  intake_draft_status?: string | null;
  is_read_only?: boolean;
};

export type IntakeOnBehalfEditAccess = {
  visible: boolean;
  enabled: boolean;
  blockedReason: string | null;
};

export function resolveIntakeOnBehalfEditAccess(
  input: IntakeOnBehalfEditAccessInput,
  reviewSections?: Array<{ status: string }>,
): IntakeOnBehalfEditAccess {
  const status = String(input.status || "").trim();
  const draftStatus = String(input.intake_draft_status || "").trim();

  if (input.is_read_only || INTAKE_ON_BEHALF_TERMINAL_STATUSES.has(status)) {
    return {
      visible: false,
      enabled: false,
      blockedReason: "Редактирование недоступно: обращение завершено или закрыто.",
    };
  }

  if (INTAKE_ON_BEHALF_APPROVAL_STATUSES.has(status)) {
    return {
      visible: true,
      enabled: false,
      blockedReason: "Редактирование недоступно: обращение на этапе согласования.",
    };
  }

  if (status === "revision_requested") {
    if (draftStatus !== "submitted") {
      return {
        visible: true,
        enabled: false,
        blockedReason: "Анкета претендента ещё не отправлена.",
      };
    }
    return { visible: true, enabled: true, blockedReason: null };
  }

  if (status === "under_review") {
    if (draftStatus !== "submitted") {
      return {
        visible: true,
        enabled: false,
        blockedReason: "Анкета претендента ещё не отправлена.",
      };
    }
    const hasRework = (reviewSections ?? []).some((section) => section.status === "rework_requested");
    if (hasRework) {
      return { visible: true, enabled: true, blockedReason: null };
    }
    return {
      visible: true,
      enabled: false,
      blockedReason:
        "Редактирование доступно только для разделов, возвращённых на уточнение.",
    };
  }

  if (draftStatus === "submitted") {
    return {
      visible: true,
      enabled: false,
      blockedReason:
        "Редактирование доступно только после возврата обращения HR или претенденту на уточнение.",
    };
  }

  return { visible: false, enabled: false, blockedReason: null };
}
