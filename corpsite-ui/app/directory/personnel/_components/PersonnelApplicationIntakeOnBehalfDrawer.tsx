"use client";

import * as React from "react";

import IntakeDraftFormEditor from "@/app/intake/_components/IntakeDraftFormEditor";
import { reconcileIntakeDraftPayload } from "@/app/intake/_lib/intakeDraftReconcile";
import {
  INTAKE_STEPS,
  emptyIntakeDraftPayload,
  resolveIntakeOnBehalfInitialStepIndex,
  type IntakeDraftPayload,
} from "@/app/intake/_lib/intakeApi.client";
import { collectIntakeDateValidationIssues } from "@/app/intake/_lib/intakeDateValidation";
import { intakePayloadsEqual } from "@/app/intake/_lib/intakePayloadCompare";
import {
  getIntakeOnBehalfEditSession,
  isIntakeOnBehalfDraftVersionConflict,
  mapPersonnelApplicationsApiError,
  saveIntakeOnBehalfDraft,
  submitIntakeOnBehalfDraft,
} from "../_lib/personnelApplicationsApi.client";
import { openIntakePdfByApplicationId } from "@/app/intake/_lib/intakePdfOpen.client";

type Props = {
  applicationId: number | null;
  open: boolean;
  onClose: () => void;
  onSaved?: () => void;
};

function withInitialOnBehalfStep(payload: IntakeDraftPayload): IntakeDraftPayload {
  const stepIndex = resolveIntakeOnBehalfInitialStepIndex();
  return {
    ...payload,
    current_step: INTAKE_STEPS[stepIndex].id,
  };
}

function isSubmittedOnBehalfSession(draftStatus: string | null): boolean {
  return String(draftStatus ?? "").trim() === "submitted";
}

export default function PersonnelApplicationIntakeOnBehalfDrawer({
  applicationId,
  open,
  onClose,
  onSaved,
}: Props) {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [blockedReason, setBlockedReason] = React.useState<string | null>(null);
  const [payload, setPayload] = React.useState<IntakeDraftPayload>(emptyIntakeDraftPayload());
  const [baselinePayload, setBaselinePayload] = React.useState<IntakeDraftPayload>(emptyIntakeDraftPayload());
  const [stepIndex, setStepIndex] = React.useState(0);
  const [editable, setEditable] = React.useState(false);
  const [applicationStatus, setApplicationStatus] = React.useState<string | null>(null);
  const [draftStatus, setDraftStatus] = React.useState<string | null>(null);
  const [submittedAt, setSubmittedAt] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [pdfGenerating, setPdfGenerating] = React.useState(false);
  const [saveCommitted, setSaveCommitted] = React.useState(false);
  const payloadRef = React.useRef(payload);
  const expectedUpdatedAtRef = React.useRef<string | null>(null);
  const sessionLoadSeqRef = React.useRef(0);
  const sessionHydratedRef = React.useRef(false);

  React.useEffect(() => {
    payloadRef.current = payload;
  }, [payload]);

  const isSubmittedView = isSubmittedOnBehalfSession(draftStatus);
  const showEditor = editable || isSubmittedView;
  const formReadOnly = isSubmittedView || !editable;
  const isDirty = editable && !intakePayloadsEqual(baselinePayload, payload);

  React.useEffect(() => {
    if (!open || applicationId == null) {
      setError(null);
      setBlockedReason(null);
      setEditable(false);
      setApplicationStatus(null);
      setDraftStatus(null);
      setSubmittedAt(null);
      setSubmitError(null);
      setSaveCommitted(false);
      expectedUpdatedAtRef.current = null;
      sessionHydratedRef.current = false;
      return;
    }
    let cancelled = false;
    const loadSeq = ++sessionLoadSeqRef.current;
    sessionHydratedRef.current = false;
    expectedUpdatedAtRef.current = null;
    setLoading(true);
    setError(null);
    setSaveCommitted(false);
    void getIntakeOnBehalfEditSession(applicationId)
      .then((session) => {
        if (cancelled || loadSeq !== sessionLoadSeqRef.current) return;
        const draftUpdatedAt = session.draft.updated_at?.trim() ?? "";
        if (!draftUpdatedAt) {
          setEditable(false);
          setError("Не удалось определить версию черновика для безопасного сохранения.");
          return;
        }
        const reconciled = reconcileIntakeDraftPayload(
          (session.draft.payload as IntakeDraftPayload | undefined) ?? emptyIntakeDraftPayload(),
        );
        expectedUpdatedAtRef.current = draftUpdatedAt;
        sessionHydratedRef.current = true;
        setBaselinePayload(reconciled);
        setPayload(withInitialOnBehalfStep(reconciled));
        setApplicationStatus(session.application_status);
        setEditable(session.editable);
        setDraftStatus(session.draft.status);
        setSubmittedAt(session.draft.submitted_at?.trim() || null);
        setBlockedReason(session.blocked_reason);
        setStepIndex(resolveIntakeOnBehalfInitialStepIndex());
      })
      .catch((e) => {
        if (!cancelled) {
          setError(mapPersonnelApplicationsApiError(e, "Не удалось открыть анкету для редактирования"));
          setEditable(false);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applicationId, open]);

  React.useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  function handlePayloadChange(next: IntakeDraftPayload) {
    if (!editable) return;
    setPayload(next);
    if (saveCommitted && !intakePayloadsEqual(baselinePayload, next)) {
      setSaveCommitted(false);
    }
  }

  async function handleSave() {
    const expectedUpdatedAt = expectedUpdatedAtRef.current?.trim() ?? "";
    if (applicationId == null || !editable || saving || !sessionHydratedRef.current || !expectedUpdatedAt) {
      return;
    }
    const currentPayload = payloadRef.current;
    setSaving(true);
    setError(null);
    try {
      const result = await saveIntakeOnBehalfDraft(
        applicationId,
        currentPayload as unknown as Record<string, unknown>,
        expectedUpdatedAt,
      );
      if (result.changed_fields.length === 0 && !intakePayloadsEqual(baselinePayload, currentPayload)) {
        setSaveCommitted(false);
        setError("Изменения не были сохранены. Проверьте данные и попробуйте снова.");
        return;
      }
      expectedUpdatedAtRef.current = result.draft_updated_at;
      setBaselinePayload(currentPayload);
      setSaveCommitted(true);
      onSaved?.();
    } catch (e) {
      setSaveCommitted(false);
      if (isIntakeOnBehalfDraftVersionConflict(e)) {
        setError(
          "Черновик был изменён в другой вкладке или другим пользователем. Обновите страницу и проверьте актуальные данные перед повторным сохранением.",
        );
        return;
      }
      setError(mapPersonnelApplicationsApiError(e, "Не удалось сохранить анкету"));
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmit() {
    if (isSubmittedView) {
      return;
    }
    const expectedUpdatedAt = expectedUpdatedAtRef.current?.trim() ?? "";
    if (
      applicationId == null ||
      !editable ||
      submitting ||
      saving ||
      !sessionHydratedRef.current ||
      !expectedUpdatedAt ||
      draftStatus !== "editable"
    ) {
      return;
    }
    const currentPayload = payloadRef.current;
    const dateIssues = collectIntakeDateValidationIssues(currentPayload);
    if (dateIssues.length > 0) {
      setError("Исправьте ошибки дат в анкете перед отправкой.");
      return;
    }
    setSubmitting(true);
    setError(null);
    setSubmitError(null);
    try {
      const result = await submitIntakeOnBehalfDraft(
        applicationId,
        currentPayload as unknown as Record<string, unknown>,
        expectedUpdatedAt,
      );
      expectedUpdatedAtRef.current = result.draft_updated_at;
      setBaselinePayload(currentPayload);
      setDraftStatus(result.status);
      setSubmittedAt(result.submitted_at);
      setApplicationStatus("intake_submitted");
      setEditable(false);
      setSaveCommitted(false);
      setSubmitError(null);
      setStepIndex(INTAKE_STEPS.findIndex((step) => step.id === "review"));
      onSaved?.();
    } catch (e) {
      const message = mapPersonnelApplicationsApiError(e, "Не удалось отправить анкету");
      if (isIntakeOnBehalfDraftVersionConflict(e)) {
        setError(
          "Черновик был изменён в другой вкладке или другим пользователем. Обновите страницу и проверьте актуальные данные перед повторной отправкой.",
        );
        setSubmitError(message);
        return;
      }
      setError(message);
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmitOnBehalf = editable && draftStatus === "editable" && !isSubmittedView;

  async function handleGeneratePdf() {
    if (applicationId == null || pdfGenerating) return;
    setPdfGenerating(true);
    setError(null);
    try {
      const result = await openIntakePdfByApplicationId(applicationId);
      if (!result.ok) {
        setError(result.error);
      }
    } finally {
      setPdfGenerating(false);
    }
  }

  const primaryActionLabel = saving
    ? "Сохранение…"
    : saveCommitted && !isDirty
      ? "Данные сохранены"
      : "Сохранить от имени претендента";
  const primaryActionDisabled = saveCommitted && !isDirty;
  const reviewNotice =
    INTAKE_STEPS[stepIndex]?.id === "review" && isDirty && !saving
      ? "Есть несохранённые изменения."
      : null;
  const drawerTitle = isSubmittedView
    ? "Анкета претендента"
    : "Редактирование анкеты от имени претендента";

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex justify-end" data-testid="intake-on-behalf-drawer">
      <button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-[min(96vw,1400px)] flex-col border-l border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{drawerTitle}</h2>
            <p className="mt-1 text-sm text-zinc-500">Обращение #{applicationId ?? "—"}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
          >
            Закрыть
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {loading ? (
            <p className="text-sm text-zinc-500" data-testid="intake-on-behalf-loading">
              Загрузка анкеты…
            </p>
          ) : null}
          {!loading && blockedReason && !showEditor ? (
            <div
              className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
              data-testid="intake-on-behalf-blocked"
            >
              {blockedReason}
            </div>
          ) : null}
          {!loading && showEditor && error ? (
            <div
              className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200"
              data-testid="intake-on-behalf-save-error"
            >
              {error}
            </div>
          ) : null}
          {!loading && isSubmittedView ? (
            <div
              className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"
              data-testid="intake-on-behalf-submitted-notice"
            >
              Анкета отправлена в отдел кадров. Просмотр и формирование PDF доступны.
            </div>
          ) : null}
          {!loading && showEditor ? (
            <IntakeDraftFormEditor
              payload={payload}
              onChange={handlePayloadChange}
              readOnly={formReadOnly}
              allowStepNavigation={isSubmittedView}
              stepIndex={stepIndex}
              onStepIndexChange={setStepIndex}
              saving={saving}
              mode="hr-on-behalf"
              onPrimaryAction={editable ? () => void handleSave() : undefined}
              primaryActionBusy={saving}
              primaryActionLabel={primaryActionLabel}
              primaryActionDisabled={primaryActionDisabled}
              onSecondaryAction={
                isSubmittedView || canSubmitOnBehalf ? () => void handleSubmit() : undefined
              }
              secondaryActionBusy={submitting}
              secondaryActionDisabled={isSubmittedView || submitting || saving}
              secondaryActionLabel={isSubmittedView ? "Анкета отправлена" : undefined}
              secondaryActionError={submitError}
              onGeneratePdf={() => void handleGeneratePdf()}
              pdfGenerating={pdfGenerating}
              reviewNotice={reviewNotice}
              compact
              applicationId={applicationId ?? undefined}
            />
          ) : null}
          {!loading && !showEditor && error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {error}
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
