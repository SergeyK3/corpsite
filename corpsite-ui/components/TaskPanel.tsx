// FILE: corpsite-ui/components/TaskPanel.tsx
"use client";

import { useMemo, useState } from "react";
import { APIError, TaskAction, TaskDetails } from "@/lib/types";

type Props = {
  task: TaskDetails | null;
  loading: boolean;
  error: APIError | null;
  onAction: (action: TaskAction, payload: { report_link?: string; current_comment?: string }) => Promise<void>;
};

function renderError(e: APIError) {
  if (e.status === 403) return "Нет доступа (403). Проверьте Dev User ID или права (RBAC/ACL).";
  if (e.status === 404) return "Задача не найдена (404).";
  if (e.status === 409) return "Конфликт состояния (409): задача уже изменилась. Обновите карточку.";
  return `Ошибка (${e.status}): ${e.message ?? "Request failed"}`;
}

function normalizeAllowedActions(v: any): string[] {
  if (Array.isArray(v)) return v.filter((x) => typeof x === "string" && x.trim().length > 0);
  return [];
}

export default function TaskPanel({ task, loading, error, onAction }: Props) {
  const allowedActions = useMemo(() => normalizeAllowedActions(task?.allowed_actions), [task?.allowed_actions]);
  const allowed = useMemo(() => new Set<string>(allowedActions), [allowedActions]);

  const [reportLink, setReportLink] = useState("");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  const showReport = task && allowed.has("report");
  const showDecision = task && (allowed.has("approve") || allowed.has("reject"));

  async function run(action: TaskAction) {
    setBusy(true);
    try {
      const payload: any = { current_comment: comment?.trim() || "" };
      if (action === "report") payload.report_link = reportLink?.trim() || "";
      await onAction(action, payload);
      setComment("");
      if (action === "report") setReportLink("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      {!task && !loading && !error && <div className="muted">Выберите задачу слева.</div>}
      {loading && <div>Loading…</div>}
      {error && <div className="error">{renderError(error)}</div>}

      {task && (
        <>
          <div className="panel__head">
            <div className="panel__title">
              <span className="mono">Задача #{task.task_id}</span>
              <div className="h1">{task.title}</div>
            </div>
            <div className="panel__status">
              <div className="badge">{task.status}</div>
              <div className="muted">срок: {task.deadline ? String(task.deadline) : "—"}</div>
            </div>
          </div>

          {task.description ? <div className="panel__desc">{task.description}</div> : <div className="muted">Описание: —</div>}

          <div className="panel__section">
            <div className="muted">Allowed actions: {allowedActions.join(", ") || "—"}</div>
          </div>

          {showReport && (
            <div className="panel__section">
              <div className="h2">Отчёт по задаче</div>
              <label className="label">Link</label>
              <input className="input" value={reportLink} onChange={(e) => setReportLink(e.target.value)} placeholder="https://..." />
              <label className="label">Comment</label>
              <textarea className="textarea" value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Комментарий…" />
              <div className="row">
                <button className="btn btn--primary" disabled={busy} onClick={() => run("report")}>
                  Send report
                </button>
              </div>
            </div>
          )}

          {showDecision && (
            <div className="panel__section">
              <div className="h2">Решение</div>
              <label className="label">Comment</label>
              <textarea className="textarea" value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Комментарий…" />
              <div className="row">
                {allowed.has("approve") && (
                  <button className="btn btn--primary" disabled={busy} onClick={() => run("approve")}>
                    Approve
                  </button>
                )}
                {allowed.has("reject") && (
                  <button className="btn btn--danger" disabled={busy} onClick={() => run("reject")}>
                    Reject
                  </button>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
