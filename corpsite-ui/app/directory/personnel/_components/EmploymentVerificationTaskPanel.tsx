"use client";

import * as React from "react";

import ConfirmDialog from "@/app/admin/system/_components/shared/ConfirmDialog";

import {
  buildEmploymentCompareRows,
  formatTaskCreatedAt,
  summarizeEmploymentRecord,
} from "../_lib/employmentVerificationCompare";
import {
  confirmEmploymentTask,
  mapPersonnelVerificationApiError,
  rejectEmploymentTask,
  verificationErrorKind,
  type EmploymentTaskReviewResponse,
} from "../_lib/personnelVerificationApi.client";
import EmploymentVerificationCompareTable from "./EmploymentVerificationCompareTable";

type Props = {
  review: EmploymentTaskReviewResponse;
  onClose: () => void;
  onDecided: () => void | Promise<void>;
  onConflict?: () => void | Promise<void>;
};

type PendingAction = "confirm" | "reject" | null;

export default function EmploymentVerificationTaskPanel({
  review,
  onClose,
  onDecided,
  onConflict,
}: Props) {
  const [pendingAction, setPendingAction] = React.useState<PendingAction>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [completed, setCompleted] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const taskId = review.task.task_id;
  const decisionAllowed =
    review.task.status === "pending" &&
    (review.verification_state == null ||
      review.verification_state === "" ||
      review.verification_state === "pending");

  const compareRows = React.useMemo(
    () => buildEmploymentCompareRows(review.prior, review.revision),
    [review.prior, review.revision],
  );

  const expectedPriorUpdatedAt =
    review.task.prior_updated_at || review.prior.updated_at;
  const actionsDisabled =
    !decisionAllowed || submitting || completed || !expectedPriorUpdatedAt;

  async function runDecision(action: "confirm" | "reject") {
    if (!decisionAllowed || !expectedPriorUpdatedAt || submitting || completed) return;
    setSubmitting(true);
    setError(null);
    try {
      const body = { expected_prior_updated_at: expectedPriorUpdatedAt };
      if (action === "confirm") {
        await confirmEmploymentTask(taskId, body);
      } else {
        await rejectEmploymentTask(taskId, body);
      }
      setCompleted(true);
      setPendingAction(null);
      await onDecided();
      // Parent closes the panel and clears selection after a successful decision.
    } catch (e) {
      if (verificationErrorKind(e) === "conflict") {
        setPendingAction(null);
        await onConflict?.();
        return;
      }
      setError(
        mapPersonnelVerificationApiError(
          e,
          action === "confirm"
            ? "Не удалось подтвердить редакцию."
            : "Не удалось отклонить редакцию.",
        ),
      );
      setPendingAction(null);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section
      className="space-y-4 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
      data-testid="employment-verification-task-panel"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
            {review.person_full_name}
          </h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Задание создано {formatTaskCreatedAt(review.task.created_at)}
          </p>
        </div>
        <button
          type="button"
          className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600"
          onClick={onClose}
          data-testid="employment-verification-close"
        >
          Закрыть
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800">
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Текущая запись
          </div>
          <div className="mt-1 font-medium text-zinc-900 dark:text-zinc-50">
            {summarizeEmploymentRecord(review.prior)}
          </div>
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50/50 px-3 py-2 text-sm dark:border-amber-900/40 dark:bg-amber-950/20">
          <div className="text-xs font-medium uppercase tracking-wide text-amber-800 dark:text-amber-200">
            Предлагаемая редакция
          </div>
          <div className="mt-1 font-medium text-zinc-900 dark:text-zinc-50">
            {summarizeEmploymentRecord(review.revision)}
          </div>
        </div>
      </div>

      <EmploymentVerificationCompareTable rows={compareRows} />

      {error ? (
        <div
          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-100"
          data-testid="employment-verification-action-error"
          role="alert"
        >
          {error}
        </div>
      ) : null}

      {decisionAllowed ? (
        <div className="flex flex-wrap gap-2" data-testid="employment-verification-actions">
          <button
            type="button"
            className="rounded-lg bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={actionsDisabled}
            onClick={() => setPendingAction("confirm")}
            data-testid="employment-verification-confirm"
          >
            Подтвердить
          </button>
          <button
            type="button"
            className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={actionsDisabled}
            onClick={() => setPendingAction("reject")}
            data-testid="employment-verification-reject"
          >
            Отклонить
          </button>
        </div>
      ) : (
        <p
          className="text-sm text-zinc-600 dark:text-zinc-400"
          data-testid="employment-verification-actions-unavailable"
        >
          Действия недоступны: задание уже не ожидает решения.
        </p>
      )}

      <ConfirmDialog
        open={pendingAction != null && decisionAllowed}
        title={
          pendingAction === "reject"
            ? "Отклонить предлагаемую редакцию?"
            : "Подтвердить предлагаемую редакцию?"
        }
        message={
          pendingAction === "reject"
            ? "Текущая запись останется действующей, предлагаемая редакция будет аннулирована."
            : "Предлагаемая редакция станет действующей, текущая запись будет заменена."
        }
        confirmLabel={pendingAction === "reject" ? "Отклонить" : "Подтвердить"}
        confirmDisabled={submitting}
        onCancel={() => {
          if (!submitting) setPendingAction(null);
        }}
        onConfirm={() => {
          if (pendingAction) void runDecision(pendingAction);
        }}
      />
    </section>
  );
}
