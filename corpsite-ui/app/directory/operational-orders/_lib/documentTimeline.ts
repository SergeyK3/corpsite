import type { DocumentDetail } from "./types";
import { documentStatusLabel } from "./status";

export type DocumentTimelineStepState = "completed" | "current" | "future" | "deferred";

export type DocumentTimelineStep = {
  id: string;
  label: string;
  state: DocumentTimelineStepState;
  note?: string;
};

export function buildDocumentLifecycleTimeline(detail: DocumentDetail): DocumentTimelineStep[] {
  const doc = detail.document;
  const status = doc.status;
  const hasAuthority = Boolean(detail.signing_authority);
  const readinessOk = detail.readiness_validation?.is_valid === true;
  const hasReadinessAudit =
    detail.latest_lifecycle_transition?.action === "SIGNATURE_READINESS_VALIDATED" || readinessOk;
  const isReady = status === "READY_FOR_SIGNATURE";
  const wasReturned =
    detail.latest_lifecycle_transition?.action === "DOCUMENT_RETURNED_TO_CREATED" && status === "CREATED";

  const steps: DocumentTimelineStep[] = [
    {
      id: "created",
      label: "Документ создан",
      state: "completed",
    },
    {
      id: "signing_authority",
      label: "Назначен подписант",
      state: hasAuthority ? "completed" : status === "CREATED" && !hasAuthority ? "current" : "future",
    },
    {
      id: "readiness",
      label: "Проверена готовность",
      state: hasReadinessAudit
        ? "completed"
        : hasAuthority && status === "CREATED"
          ? "current"
          : "future",
    },
    {
      id: "ready_for_signature",
      label: "Готов к подписи",
      state: isReady ? "completed" : hasReadinessAudit && status === "CREATED" ? "current" : "future",
      note: wasReturned ? "Ранее возвращён из очереди подписи" : undefined,
    },
    {
      id: "signed",
      label: "Подписан",
      state: "deferred",
      note: "Ещё не реализовано",
    },
    {
      id: "registered",
      label: "Зарегистрирован",
      state: "deferred",
      note: "Ещё не реализовано",
    },
  ];

  if (status === "CREATED" && !isReady && !hasAuthority && !hasReadinessAudit) {
    steps[0].state = "current";
  }

  return steps;
}

export function documentTimelineStatusHint(status: string): string {
  if (status === "READY_FOR_SIGNATURE") return documentStatusLabel(status);
  if (status === "CREATED") return "Документ ещё не передан на подпись";
  return documentStatusLabel(status);
}
