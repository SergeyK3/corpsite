"use client";

import * as React from "react";

import {
  applyEducationReconciliationDecision,
  buildEducationReconciliationSectionPayload,
  isProposalDigestMismatchError,
  listIntakeReconciliationDecisions,
  mapPersonnelApplicationsApiError,
  type ApplyEducationReconciliationDecisionResponse,
  type IntakeReconciliationDecision,
} from "../_lib/personnelApplicationsApi.client";

type Props = {
  applicationId: number;
  educationPayload: Record<string, unknown> | unknown[];
  onReviewDataChanged?: () => void | Promise<void>;
};

function actionLabel(action: string): string {
  switch (action) {
    case "add":
      return "Добавить";
    case "update_version":
      return "Обновить";
    case "keep_existing":
      return "Оставить без изменений";
    case "manual_review":
      return "Ручная проверка";
    default:
      return action;
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case "pending":
      return "Ожидает применения";
    case "applied":
      return "Применено";
    case "skipped_manual":
      return "Ручная обработка";
    case "blocked":
      return "Заблокировано";
    case "failed":
      return "Ошибка";
    default:
      return status;
  }
}

function formatFailureEvidence(evidence: Record<string, unknown> | null | undefined): string {
  if (!evidence || typeof evidence !== "object") return "Техническая ошибка применения решения.";
  const reason = typeof evidence.reason_code === "string" ? evidence.reason_code : null;
  const detail = evidence.detail;
  if (typeof detail === "string" && detail.trim()) {
    return reason ? `${reason}: ${detail}` : detail;
  }
  if (detail && typeof detail === "object") {
    const message =
      typeof (detail as { message?: unknown }).message === "string"
        ? String((detail as { message: string }).message)
        : null;
    const detailText =
      typeof (detail as { detail?: unknown }).detail === "string"
        ? String((detail as { detail: string }).detail)
        : null;
    const text = message || detailText;
    if (text) return reason ? `${reason}: ${text}` : text;
  }
  if (reason) return reason;
  return "Не удалось применить решение. Обратитесь к администратору.";
}

function outcomeMessage(result: ApplyEducationReconciliationDecisionResponse): string {
  if (result.apply_status === "applied") return "Решение применено";
  if (result.apply_status === "skipped_manual") return "Требуется ручная обработка";
  if (result.apply_status === "blocked") {
    const reason = result.reason_code ? `Причина: ${result.reason_code}. ` : "";
    return `${reason}Данные изменились. Решение необходимо принять повторно`;
  }
  if (result.apply_status === "failed") {
    return formatFailureEvidence(result.failure_evidence);
  }
  if (result.idempotent_replay) {
    return "Решение применено";
  }
  return "Решение обработано";
}

export default function EducationReconciliationDecisionsPanel({
  applicationId,
  educationPayload,
  onReviewDataChanged,
}: Props) {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [refreshError, setRefreshError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [items, setItems] = React.useState<IntakeReconciliationDecision[]>([]);
  const [applyingDecisionId, setApplyingDecisionId] = React.useState<number | null>(null);

  const reloadDecisions = React.useCallback(
    async (mode: "initial" | "refresh" = "initial"): Promise<string | null> => {
      setLoading(true);
      if (mode === "initial") {
        setError(null);
      }
      try {
        const data = await listIntakeReconciliationDecisions(applicationId, "education");
        setItems(data.items);
        return null;
      } catch (e) {
        const message = mapPersonnelApplicationsApiError(
          e,
          mode === "refresh"
            ? "Не удалось обновить данные рассмотрения"
            : "Не удалось загрузить решения сверки",
        );
        if (mode === "initial") {
          setItems([]);
          setError(message);
        }
        return message;
      } finally {
        setLoading(false);
      }
    },
    [applicationId],
  );

  React.useEffect(() => {
    void reloadDecisions("initial");
  }, [reloadDecisions]);

  async function refreshAfterApply() {
    try {
      await onReviewDataChanged?.();
      const reloadErr = await reloadDecisions("refresh");
      if (reloadErr) {
        setRefreshError(reloadErr);
      }
    } catch (refreshErr) {
      setRefreshError(
        mapPersonnelApplicationsApiError(refreshErr, "Не удалось обновить данные рассмотрения"),
      );
    }
  }

  async function handleApply(decision: IntakeReconciliationDecision) {
    if (applyingDecisionId != null) return;
    setApplyingDecisionId(decision.decision_id);
    setError(null);
    setRefreshError(null);
    setNotice(null);
    try {
      const sectionPayload = buildEducationReconciliationSectionPayload(educationPayload);
      const result = await applyEducationReconciliationDecision(
        applicationId,
        decision.decision_id,
        sectionPayload,
      );
      setNotice(outcomeMessage(result));
      setItems((prev) =>
        prev.map((item) =>
          item.decision_id === result.decision_id
            ? {
                ...item,
                apply_status: result.apply_status,
                reason_code: result.reason_code,
                failure_evidence: result.failure_evidence,
              }
            : item,
        ),
      );
      await refreshAfterApply();
    } catch (e) {
      if (isProposalDigestMismatchError(e)) {
        await refreshAfterApply();
        setError("Предложение устарело. Обновите данные рассмотрения и примите решение заново.");
      } else {
        setError(mapPersonnelApplicationsApiError(e, "Не удалось применить решение"));
      }
    } finally {
      setApplyingDecisionId(null);
    }
  }

  if (loading && items.length === 0) {
    return (
      <div className="mt-3 text-sm text-zinc-500" data-testid="education-recon-decisions-loading">
        Загрузка решений сверки…
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-3" data-testid="education-recon-decisions-panel">
      <h4 className="text-sm font-medium text-zinc-900 dark:text-zinc-50">Решения сверки (образование)</h4>
      {error ? (
        <p className="text-sm text-red-600" data-testid="education-recon-decisions-error">
          {error}
        </p>
      ) : null}
      {refreshError ? (
        <p className="text-sm text-amber-700 dark:text-amber-300" data-testid="education-recon-decisions-refresh-error">
          {refreshError}
        </p>
      ) : null}
      {notice ? (
        <p className="text-sm text-emerald-700 dark:text-emerald-300" data-testid="education-recon-decisions-notice">
          {notice}
        </p>
      ) : null}
      {!loading && items.length === 0 ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400" data-testid="education-recon-decisions-empty">
          Решений сверки нет
        </p>
      ) : (
      <ul className="space-y-2">
        {items.map((decision) => {
          const canApply = decision.apply_status === "pending";
          const isApplying = applyingDecisionId === decision.decision_id;
          return (
            <li
              key={decision.decision_id}
              className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800"
              data-testid={`education-recon-decision-${decision.decision_id}`}
              data-apply-status={decision.apply_status}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="space-y-1">
                  <div className="font-medium">
                    #{decision.decision_id} · {actionLabel(decision.action)} · индекс{" "}
                    {decision.proposal_index}
                  </div>
                  <div className="text-zinc-600 dark:text-zinc-400">
                    Статус: {statusLabel(decision.apply_status)} · {decision.reason_code}
                  </div>
                  {decision.apply_status === "blocked" ? (
                    <p
                      className="text-amber-700 dark:text-amber-300"
                      data-testid={`education-recon-blocked-${decision.decision_id}`}
                    >
                      {decision.reason_code ? `Причина: ${decision.reason_code}. ` : ""}
                      Данные изменились. Решение необходимо принять повторно
                    </p>
                  ) : null}
                  {decision.apply_status === "failed" ? (
                    <p
                      className="text-red-600"
                      data-testid={`education-recon-failed-${decision.decision_id}`}
                    >
                      {formatFailureEvidence(decision.failure_evidence)}
                    </p>
                  ) : null}
                  {decision.apply_status === "applied" ? (
                    <p
                      className="text-emerald-700 dark:text-emerald-300"
                      data-testid={`education-recon-applied-${decision.decision_id}`}
                    >
                      Решение применено
                    </p>
                  ) : null}
                  {decision.apply_status === "skipped_manual" ? (
                    <p
                      className="text-amber-700 dark:text-amber-300"
                      data-testid={`education-recon-skipped-${decision.decision_id}`}
                    >
                      Требуется ручная обработка
                    </p>
                  ) : null}
                </div>
                {canApply ? (
                  <button
                    type="button"
                    disabled={applyingDecisionId != null}
                    onClick={() => void handleApply(decision)}
                    className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
                    data-testid={`education-recon-apply-${decision.decision_id}`}
                  >
                    {isApplying ? "Применение…" : "Применить решение"}
                  </button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
      )}
    </div>
  );
}
