"use client";

import * as React from "react";

import IntakeDraftFormEditor, { reconcileIntakeDraftPayload } from "@/app/intake/_components/IntakeDraftFormEditor";
import {
  INTAKE_STEPS,
  emptyIntakeDraftPayload,
  resolveIntakeOnBehalfInitialStepIndex,
  type IntakeDraftPayload,
} from "@/app/intake/_lib/intakeApi.client";
import { intakePayloadsEqual } from "@/app/intake/_lib/intakePayloadCompare";
import {
  getIntakeOnBehalfEditSession,
  mapPersonnelApplicationsApiError,
  saveIntakeOnBehalfDraft,
} from "../_lib/personnelApplicationsApi.client";

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
  const [saving, setSaving] = React.useState(false);
  const [saveCommitted, setSaveCommitted] = React.useState(false);
  const payloadRef = React.useRef(payload);

  React.useEffect(() => {
    payloadRef.current = payload;
  }, [payload]);

  const isDirty = !intakePayloadsEqual(baselinePayload, payload);

  React.useEffect(() => {
    if (!open || applicationId == null) {
      setError(null);
      setBlockedReason(null);
      setEditable(false);
      setSaveCommitted(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSaveCommitted(false);
    void getIntakeOnBehalfEditSession(applicationId)
      .then((session) => {
        if (cancelled) return;
        const reconciled = reconcileIntakeDraftPayload(
          (session.draft.payload as IntakeDraftPayload | undefined) ?? emptyIntakeDraftPayload(),
        );
        const nextPayload = withInitialOnBehalfStep(reconciled);
        setBaselinePayload(reconciled);
        setPayload(nextPayload);
        setEditable(session.editable);
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
    setPayload(next);
    if (saveCommitted && !intakePayloadsEqual(baselinePayload, next)) {
      setSaveCommitted(false);
    }
  }

  async function handleSave() {
    if (applicationId == null || !editable || saving) return;
    const currentPayload = payloadRef.current;
    setSaving(true);
    setError(null);
    try {
      const result = await saveIntakeOnBehalfDraft(
        applicationId,
        currentPayload as unknown as Record<string, unknown>,
      );
      if (result.changed_fields.length === 0 && !intakePayloadsEqual(baselinePayload, currentPayload)) {
        setSaveCommitted(false);
        setError("Изменения не были сохранены. Проверьте данные и попробуйте снова.");
        return;
      }
      setBaselinePayload(currentPayload);
      setSaveCommitted(true);
      onSaved?.();
    } catch (e) {
      setSaveCommitted(false);
      setError(mapPersonnelApplicationsApiError(e, "Не удалось сохранить анкету"));
    } finally {
      setSaving(false);
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

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex justify-end" data-testid="intake-on-behalf-drawer">
      <button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-3xl flex-col border-l border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              Редактирование анкеты от имени претендента
            </h2>
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
          {!loading && blockedReason && !editable ? (
            <div
              className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
              data-testid="intake-on-behalf-blocked"
            >
              {blockedReason}
            </div>
          ) : null}
          {!loading && editable && error ? (
            <div
              className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200"
              data-testid="intake-on-behalf-save-error"
            >
              {error}
            </div>
          ) : null}
          {!loading && editable ? (
            <IntakeDraftFormEditor
              payload={payload}
              onChange={handlePayloadChange}
              readOnly={false}
              stepIndex={stepIndex}
              onStepIndexChange={setStepIndex}
              saving={saving}
              mode="hr-on-behalf"
              onPrimaryAction={() => void handleSave()}
              primaryActionBusy={saving}
              primaryActionLabel={primaryActionLabel}
              primaryActionDisabled={primaryActionDisabled}
              reviewNotice={reviewNotice}
              compact
              headerTitle={`Анкета претендента · шаг ${stepIndex + 1} из ${INTAKE_STEPS.length}`}
            />
          ) : null}
          {!loading && !editable && error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {error}
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
