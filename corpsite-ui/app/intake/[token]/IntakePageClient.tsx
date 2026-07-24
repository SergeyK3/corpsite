"use client";

import * as React from "react";
import { useParams } from "next/navigation";

import IntakeDraftFormEditor, { reconcileIntakeDraftPayload } from "../_components/IntakeDraftFormEditor";
import {
  INTAKE_STEPS,
  autosaveIntakeDraft,
  emptyIntakeDraftPayload,
  mapIntakeApiError,
  openIntakeSession,
  submitIntakeDraft,
  type IntakeDraftPayload,
} from "../_lib/intakeApi.client";
import { collectIntakeDateValidationIssues, resolveIntakeDateIssueStepIndex } from "../_lib/intakeDateValidation";

export default function IntakePageClient() {
  const params = useParams<{ token: string }>();
  const token = String(params?.token || "").trim();

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [payload, setPayload] = React.useState<IntakeDraftPayload>(emptyIntakeDraftPayload());
  const [readOnly, setReadOnly] = React.useState(false);
  const [submitted, setSubmitted] = React.useState(false);
  const [stepIndex, setStepIndex] = React.useState(0);
  const [saving, setSaving] = React.useState(false);
  const [saveNotice, setSaveNotice] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [initialFocusTestId, setInitialFocusTestId] = React.useState<string | null>(null);

  const autosaveTimer = React.useRef<number | null>(null);

  React.useEffect(() => {
    if (!token) {
      setError("Ссылка недействительна.");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void openIntakeSession(token)
      .then((session) => {
        if (cancelled) return;
        const reconciled = reconcileIntakeDraftPayload(session.payload ?? emptyIntakeDraftPayload());
        setPayload(reconciled);
        setReadOnly(Boolean(session.read_only));
        setSubmitted(Boolean(session.read_only));
        const dateIssues = collectIntakeDateValidationIssues(reconciled);
        const reworkReopen =
          !session.read_only &&
          Boolean(session.submitted_at) &&
          session.status === "editable";
        if (reworkReopen && dateIssues.length > 0) {
          const firstIssue = dateIssues[0];
          setStepIndex(resolveIntakeDateIssueStepIndex(firstIssue));
          setInitialFocusTestId(firstIssue.focusTestId);
        } else {
          const idx = INTAKE_STEPS.findIndex((s) => s.id === session.payload?.current_step);
          setStepIndex(idx >= 0 ? idx : 0);
          setInitialFocusTestId(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(mapIntakeApiError(e, "Не удалось открыть анкету"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const scheduleAutosave = React.useCallback(
    (next: IntakeDraftPayload) => {
      if (readOnly || !token) return;
      if (autosaveTimer.current) window.clearTimeout(autosaveTimer.current);
      autosaveTimer.current = window.setTimeout(() => {
        setSaving(true);
        void autosaveIntakeDraft(token, next)
          .then(() => setSaveNotice("Сохранено"))
          .catch(() => setSaveNotice("Ошибка автосохранения"))
          .finally(() => setSaving(false));
      }, 800);
    },
    [readOnly, token],
  );

  const updatePayload = React.useCallback(
    (next: IntakeDraftPayload) => {
      setPayload(next);
      scheduleAutosave(next);
    },
    [scheduleAutosave],
  );

  async function handleSubmit() {
    if (!token || readOnly) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitIntakeDraft(token, payload);
      setSubmitted(true);
      setReadOnly(true);
    } catch (e) {
      setError(mapIntakeApiError(e, "Не удалось отправить анкету"));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <p className="text-sm text-zinc-500">Загрузка анкеты…</p>
      </div>
    );
  }

  if (error && !payload.personal.last_name && !submitted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 dark:bg-zinc-950">
        <div className="max-w-md rounded-xl border border-red-200 bg-white p-6 text-center dark:border-red-900 dark:bg-zinc-900">
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Анкета недоступна</h1>
          <p className="mt-2 text-sm text-red-700 dark:text-red-300">{error}</p>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 dark:bg-zinc-950">
        <div className="max-w-md rounded-xl border border-emerald-200 bg-white p-8 text-center dark:border-emerald-900 dark:bg-zinc-900">
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Анкета отправлена</h1>
          <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
            Ваши сведения переданы в отдел кадров. Дальнейшее редактирование недоступно.
          </p>
        </div>
      </div>
    );
  }

  return (
    <IntakeDraftFormEditor
      payload={payload}
      onChange={updatePayload}
      readOnly={readOnly}
      stepIndex={stepIndex}
      onStepIndexChange={setStepIndex}
      error={error}
      saveNotice={saveNotice}
      saving={saving}
      mode="public"
      onPrimaryAction={() => void handleSubmit()}
      primaryActionBusy={submitting}
      initialFocusTestId={initialFocusTestId}
      intakeToken={token}
    />
  );
}
