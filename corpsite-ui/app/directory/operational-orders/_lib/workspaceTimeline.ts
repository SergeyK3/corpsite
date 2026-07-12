export type TimelineStepState = "completed" | "current" | "blocked" | "future";

export type WorkspaceTimelineStep = {
  id: string;
  label: string;
  state: TimelineStepState;
};

const STEPS = [
  { id: "submitted", label: "Передан", minStage: 1 },
  { id: "accepted", label: "Принят", minStage: 2 },
  { id: "reviewed", label: "Проверен", minStage: 3 },
  { id: "translation", label: "Перевод", minStage: 4 },
  { id: "confirmation", label: "Подтверждение", minStage: 5 },
  { id: "reconciliation", label: "Согласование RU/KK", minStage: 6 },
  { id: "editorial_ready", label: "Редакционный пакет готов", minStage: 7 },
  { id: "promoted", label: "Официальный проект создан", minStage: 8 },
] as const;

const STAGE_INDEX: Record<string, number> = {
  SUBMITTED: 1,
  ACCEPTED: 2,
  INTAKE_REVIEW: 3,
  CLARIFICATION_REQUIRED: 3,
  READY_FOR_EDITORIAL: 3,
  TRANSLATION_REQUIRED: 4,
  TRANSLATION_IN_PROGRESS: 4,
  CONTENT_CONFIRMATION_REQUIRED: 5,
  BILINGUAL_RECONCILIATION: 6,
  EDITORIAL_PACKAGE_READY: 7,
  DOCUMENT_PROMOTED: 8,
};

export function buildWorkspaceTimeline(stage: string): WorkspaceTimelineStep[] {
  const currentIndex = STAGE_INDEX[stage] ?? 1;
  const blocked = stage === "CLARIFICATION_REQUIRED";

  return STEPS.map((step) => {
    let state: TimelineStepState = "future";
    if (step.minStage < currentIndex) state = "completed";
    else if (step.minStage === currentIndex) {
      if (blocked && step.id === "reviewed") state = "blocked";
      else state = "current";
    }
    return { id: step.id, label: step.label, state };
  });
}
