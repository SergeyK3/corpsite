"use client";

import * as React from "react";
import Link from "next/link";

import {
  directorResolutionLabel,
  formatPersonnelApplicationDateTime,
} from "../_lib/personnelApplicationLabels";
import {
  applyPersonnelApplication,
  changeDirectorResolution,
  createHireOrderDraft,
  getDirectorResolutionAudit,
  mapPersonnelApplicationsApiError,
  openDirectorResolution,
  recordDirectorResolution,
  reopenDirectorResolution,
  type DirectorResolutionAuditItem,
  type PersonnelApplicationDetail,
} from "../_lib/personnelApplicationsApi.client";
import { DirectorResolutionBadge } from "./PersonnelApplicationStatusBadge";

type Props = {
  detail: PersonnelApplicationDetail;
  onRefresh: () => void;
};

type PendingAction =
  | { kind: "record"; outcome: "approved" | "rejected" | "revision_requested" }
  | { kind: "change"; outcome: "approved" | "rejected" | "revision_requested" }
  | null;

const OUTCOME_LABELS: Record<string, string> = {
  approved: "Согласовать приём",
  rejected: "Отказать",
  revision_requested: "Вернуть HR на уточнение",
};

export default function PersonnelApplicationResolutionSection({ detail, onRefresh }: Props) {
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [pending, setPending] = React.useState<PendingAction>(null);
  const [comment, setComment] = React.useState("");
  const [audit, setAudit] = React.useState<DirectorResolutionAuditItem[]>([]);

  const loadAudit = React.useCallback(async () => {
    try {
      const items = await getDirectorResolutionAudit(detail.application_id);
      setAudit(items);
    } catch {
      setAudit([]);
    }
  }, [detail.application_id]);

  React.useEffect(() => {
    void loadAudit();
  }, [loadAudit, detail.status, detail.director_resolution_status, detail.personnel_order_id]);

  async function runSimple(action: string, fn: () => Promise<unknown>) {
    setBusy(action);
    setError(null);
    try {
      await fn();
      await loadAudit();
      onRefresh();
    } catch (e) {
      setError(mapPersonnelApplicationsApiError(e, "Не удалось выполнить действие"));
    } finally {
      setBusy(null);
    }
  }

  async function confirmPending() {
    if (!pending) return;
    if (
      (pending.outcome === "rejected" || pending.outcome === "revision_requested") &&
      !comment.trim()
    ) {
      setError("Укажите комментарий.");
      return;
    }
    const actionKey = `${pending.kind}:${pending.outcome}`;
    setBusy(actionKey);
    setError(null);
    try {
      if (pending.kind === "record") {
        await recordDirectorResolution(detail.application_id, pending.outcome, comment.trim());
      } else {
        await changeDirectorResolution(detail.application_id, pending.outcome, comment.trim());
      }
      setPending(null);
      setComment("");
      await loadAudit();
      onRefresh();
    } catch (e) {
      setError(mapPersonnelApplicationsApiError(e, "Не удалось сохранить резолюцию"));
    } finally {
      setBusy(null);
    }
  }

  const canOpen = detail.status === "review_completed";
  const canDecide = detail.status === "resolution_pending";
  const canReopen = detail.status === "revision_requested";
  const canChange = ["approved", "rejected", "revision_requested"].includes(detail.status);
  const canCreateOrder =
    detail.status === "approved" && detail.personnel_order_id == null;
  const canApply =
    !detail.is_read_only &&
    (detail.status === "approved" || detail.status === "order_draft_created") &&
    detail.personnel_order_id != null &&
    detail.director_resolution_status === "approved";
  const hasOrder = detail.personnel_order_id != null;
  const readOnly = Boolean(detail.is_read_only);

  return (
    <section className="space-y-3" data-testid="personnel-application-resolution-section">
      <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Резолюция директора</h3>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">Статус</div>
          <div className="mt-1">
            {detail.director_resolution_status ? (
              <DirectorResolutionBadge status={detail.director_resolution_status} />
            ) : (
              <span className="text-sm text-zinc-500">{directorResolutionLabel(null)}</span>
            )}
          </div>
        </div>
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">Дата</div>
          <div className="mt-0.5 text-sm text-zinc-800 dark:text-zinc-200">
            {formatPersonnelApplicationDateTime(detail.director_resolution_at)}
          </div>
        </div>
        <div className="sm:col-span-2">
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">Комментарий</div>
          <div className="mt-0.5 text-sm text-zinc-800 dark:text-zinc-200">
            {detail.director_resolution_note || "—"}
          </div>
        </div>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <div className="flex flex-wrap gap-2">
        {!readOnly && canOpen ? (
          <button
            type="button"
            disabled={busy != null}
            onClick={() =>
              void runSimple("open", () => openDirectorResolution(detail.application_id))
            }
            className="rounded-lg bg-amber-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            data-testid="resolution-open-button"
          >
            {busy === "open" ? "Открытие…" : "Открыть резолюцию"}
          </button>
        ) : null}

        {!readOnly && canDecide
          ? (["approved", "rejected", "revision_requested"] as const).map((outcome) => (
              <button
                key={outcome}
                type="button"
                disabled={busy != null}
                onClick={() => {
                  setPending({ kind: "record", outcome });
                  setComment("");
                }}
                className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
                data-testid={`resolution-record-${outcome}`}
              >
                {OUTCOME_LABELS[outcome]}
              </button>
            ))
          : null}

        {!readOnly && canReopen ? (
          <button
            type="button"
            disabled={busy != null}
            onClick={() =>
              void runSimple("reopen", () => reopenDirectorResolution(detail.application_id))
            }
            className="rounded-lg border border-sky-300 px-3 py-1.5 text-sm text-sky-800 dark:border-sky-900 dark:text-sky-300"
            data-testid="resolution-reopen-button"
          >
            Повторно на рассмотрение
          </button>
        ) : null}

        {!readOnly && canChange && !canDecide
          ? (["approved", "rejected", "revision_requested"] as const).map((outcome) => (
              <button
                key={`change-${outcome}`}
                type="button"
                disabled={busy != null}
                onClick={() => {
                  setPending({ kind: "change", outcome });
                  setComment(detail.director_resolution_note || "");
                }}
                className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
                data-testid={`resolution-change-${outcome}`}
              >
                Изменить: {OUTCOME_LABELS[outcome]}
              </button>
            ))
          : null}

        {!readOnly && canCreateOrder ? (
          <button
            type="button"
            disabled={busy != null}
            onClick={() =>
              void runSimple("hire-draft", () => createHireOrderDraft(detail.application_id))
            }
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            data-testid="hire-order-draft-button"
          >
            {busy === "hire-draft" ? "Создание…" : "Создать черновик приказа"}
          </button>
        ) : null}

        {canApply ? (
          <button
            type="button"
            disabled={busy != null}
            onClick={() =>
              void runSimple("apply", () => applyPersonnelApplication(detail.application_id))
            }
            className="rounded-lg bg-green-700 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            data-testid="application-apply-button"
          >
            {busy === "apply" ? "Применение…" : "Применить приказ и принять на работу"}
          </button>
        ) : null}
      </div>

      {pending ? (
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-sm font-medium">{OUTCOME_LABELS[pending.outcome]}</p>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="mt-2 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            rows={3}
            placeholder={
              pending.outcome === "approved"
                ? "Комментарий (необязательно)"
                : "Комментарий (обязательно)"
            }
            data-testid="resolution-comment-input"
          />
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              disabled={busy != null}
              onClick={() => void confirmPending()}
              className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
              data-testid="resolution-confirm-button"
            >
              Подтвердить
            </button>
            <button
              type="button"
              onClick={() => {
                setPending(null);
                setComment("");
              }}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            >
              Отмена
            </button>
          </div>
        </div>
      ) : null}

      {hasOrder ? (
        <Link
          href={`/directory/personnel/orders?order_id=${detail.personnel_order_id}`}
          className="inline-flex text-sm text-blue-700 underline-offset-2 hover:underline dark:text-blue-300"
          data-testid="resolution-order-link"
        >
          Открыть приказ #{detail.personnel_order_id}
        </Link>
      ) : null}

      {audit.length > 0 ? (
        <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
          <div className="font-medium">Audit резолюции</div>
          <ul className="mt-2 space-y-2">
            {audit.map((item) => (
              <li key={item.audit_id} data-testid={`resolution-audit-${item.audit_id}`}>
                <div>
                  {item.action} · {item.new_application_status}
                  {item.new_resolution_status ? ` / ${item.new_resolution_status}` : ""}
                </div>
                <div className="text-xs text-zinc-500">
                  {formatPersonnelApplicationDateTime(item.created_at)} · user #{item.actor_user_id}
                </div>
                {item.comment ? <div className="text-zinc-700 dark:text-zinc-300">{item.comment}</div> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
