"use client";

import * as React from "react";

import type { MeInfo } from "@/lib/types";

import {
  createTranslationAssignment,
  parseTranslationAssignments,
  translationAssignmentAction,
} from "../_lib/api";
import { formatDateTime, formatPartyReference } from "../_lib/mappers";
import type { OperationalOrdersPermissions, WorkspaceDetail } from "../_lib/types";
import {
  isActiveTranslationStatus,
  isHistoricalTranslationStatus,
  translationStatusBadgeClass,
  translationStatusLabel,
} from "../_lib/status";
import CompactFingerprint from "./CompactFingerprint";

type Props = {
  detail: WorkspaceDetail;
  frozen: boolean;
  perms: OperationalOrdersPermissions;
  me: MeInfo | null;
  pending: boolean;
  onUpdated: (detail: WorkspaceDetail) => void;
  onError: (err: unknown) => void;
};

function localeDirection(source: string, target: string): string {
  return `${source.toUpperCase()} → ${target.toUpperCase()}`;
}

function AssignmentCard({
  assignment,
  showActions,
  onAction,
  pending,
  blocks,
  canAct,
}: {
  assignment: ReturnType<typeof parseTranslationAssignments>[number];
  showActions: boolean;
  onAction: (action: "accept" | "start" | "cancel" | "complete", assignmentId: number) => void;
  pending: boolean;
  blocks: WorkspaceDetail["blocks"];
  canAct: (action: "accept" | "start" | "cancel" | "complete") => boolean;
}) {
  const targetBlock = blocks.find((b) => b.locale === assignment.target_locale);

  return (
    <article className="rounded-lg border p-3 dark:border-zinc-700" data-testid={`translation-assignment-${assignment.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-medium">{localeDirection(assignment.source_locale, assignment.target_locale)}</div>
          <span className={`mt-1 inline-flex rounded-md border px-2 py-0.5 text-xs ${translationStatusBadgeClass(assignment.status)}`}>
            {translationStatusLabel(assignment.status)}
          </span>
        </div>
        <span className="text-xs text-zinc-400">#{assignment.id}</span>
      </div>
      <dl className="mt-3 grid gap-1 text-sm md:grid-cols-2">
        <div>
          <dt className="text-xs text-zinc-500">Исполнитель</dt>
          <dd>{formatPartyReference(assignment.assigned_to_type, assignment.assigned_to_reference, assignment.assigned_to_display_name)}</dd>
        </div>
        <div>
          <dt className="text-xs text-zinc-500">Назначил</dt>
          <dd>user #{assignment.assigned_by_user_id}</dd>
        </div>
        <div>
          <dt className="text-xs text-zinc-500">Запрошен</dt>
          <dd>{formatDateTime(assignment.requested_at)}</dd>
        </div>
        <div>
          <dt className="text-xs text-zinc-500">Принят</dt>
          <dd>{formatDateTime(assignment.accepted_at)}</dd>
        </div>
        <div>
          <dt className="text-xs text-zinc-500">Завершён</dt>
          <dd>{formatDateTime(assignment.completed_at)}</dd>
        </div>
        <div>
          <dt className="text-xs text-zinc-500">Срок</dt>
          <dd>{formatDateTime(assignment.due_at)}</dd>
        </div>
        <div>
          <dt className="text-xs text-zinc-500">Source block v</dt>
          <dd>{assignment.source_block_version}</dd>
        </div>
        <div>
          <dt className="text-xs text-zinc-500">Target block v</dt>
          <dd>{assignment.target_block_version ?? "—"}</dd>
        </div>
      </dl>
      <div className="mt-2 space-y-1">
        <CompactFingerprint value={assignment.source_content_fingerprint} label="source fp" />
        {assignment.produced_content_fingerprint ? (
          <CompactFingerprint value={assignment.produced_content_fingerprint} label="produced fp" />
        ) : null}
      </div>
      {assignment.notes ? <p className="mt-2 text-sm text-zinc-600">{assignment.notes}</p> : null}
      {showActions ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {assignment.status === "REQUESTED" && canAct("accept") ? (
            <button type="button" className="rounded border px-2 py-1 text-xs" disabled={pending} onClick={() => onAction("accept", assignment.id)}>
              Принять
            </button>
          ) : null}
          {assignment.status === "ACCEPTED" && canAct("start") ? (
            <button type="button" className="rounded border px-2 py-1 text-xs" disabled={pending} onClick={() => onAction("start", assignment.id)}>
              Начать
            </button>
          ) : null}
          {assignment.status === "IN_PROGRESS" && targetBlock && canAct("complete") ? (
            <button type="button" className="rounded border px-2 py-1 text-xs" disabled={pending} onClick={() => onAction("complete", assignment.id)}>
              Завершить
            </button>
          ) : null}
          {["REQUESTED", "ACCEPTED", "IN_PROGRESS"].includes(assignment.status) && canAct("cancel") ? (
            <button type="button" className="rounded border px-2 py-1 text-xs text-red-700" disabled={pending} onClick={() => onAction("cancel", assignment.id)}>
              Отменить
            </button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

export default function TranslationAssignmentsSection({
  detail,
  frozen,
  perms,
  me,
  pending,
  onUpdated,
  onError,
}: Props) {
  const assignments = parseTranslationAssignments(detail);
  const active = assignments.filter((a) => isActiveTranslationStatus(a.status));
  const history = assignments.filter((a) => isHistoricalTranslationStatus(a.status));

  const [showCreate, setShowCreate] = React.useState(false);
  const [targetLocale, setTargetLocale] = React.useState<"ru" | "kk">("kk");
  const [assigneeRef, setAssigneeRef] = React.useState("");
  const [assigneeName, setAssigneeName] = React.useState("");
  const [notes, setNotes] = React.useState("");

  const canAssign = !frozen && Boolean(perms.translation_assign);
  const canWork = !frozen && Boolean(perms.translation_work);
  const userId = me?.user_id != null ? String(me.user_id) : null;

  function canActOnAssignment(assignment: ReturnType<typeof parseTranslationAssignments>[number], action: "accept" | "start" | "complete" | "cancel"): boolean {
    if (action === "cancel") return canAssign;
    const isAssignee =
      assignment.assigned_to_type === "PERSON" && userId != null && assignment.assigned_to_reference === userId;
    return canWork || isAssignee;
  }

  async function mutate(action: () => Promise<WorkspaceDetail>) {
    try {
      const updated = await action();
      onUpdated(updated);
    } catch (e) {
      onError(e);
    }
  }

  function handleAction(action: "accept" | "start" | "cancel" | "complete", assignmentId: number) {
    const assignment = assignments.find((a) => a.id === assignmentId);
    if (!assignment) return;
    const targetBlock = detail.blocks.find((b) => b.locale === assignment.target_locale);
    void mutate(async () => {
      const payload: Record<string, unknown> = {
        expected_version: detail.workspace.version,
        assignment_expected_version: assignment.version,
      };
      if (action === "complete" && targetBlock) {
        payload.target_block_id = targetBlock.block_id;
        payload.block_expected_version = targetBlock.version;
      }
      return translationAssignmentAction(detail.workspace.workspace_id, assignmentId, action, payload);
    });
  }

  return (
    <section className="rounded-xl border p-4 dark:border-zinc-800" id="section-translations">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Перевод</h3>
        {canAssign ? (
          <button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Скрыть форму" : "Назначить перевод"}
          </button>
        ) : null}
      </div>

      {showCreate && canAssign ? (
        <div className="mb-4 rounded-lg border border-dashed p-3 dark:border-zinc-700">
          <div className="grid gap-2 md:grid-cols-2">
            <label className="text-sm">
              Целевой язык
              <select className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-950" value={targetLocale} onChange={(e) => setTargetLocale(e.target.value as "ru" | "kk")}>
                <option value="kk">KK</option>
                <option value="ru">RU</option>
              </select>
            </label>
            <label className="text-sm">
              PERSON reference
              <input className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-950" value={assigneeRef} onChange={(e) => setAssigneeRef(e.target.value)} placeholder="user id" />
            </label>
            <label className="text-sm md:col-span-2">
              Display name
              <input className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-950" value={assigneeName} onChange={(e) => setAssigneeName(e.target.value)} />
            </label>
            <label className="text-sm md:col-span-2">
              Примечание
              <input className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-950" value={notes} onChange={(e) => setNotes(e.target.value)} />
            </label>
          </div>
          <button
            type="button"
            className="mt-3 rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            disabled={pending || !assigneeRef.trim()}
            onClick={() =>
              void mutate(() =>
                createTranslationAssignment(detail.workspace.workspace_id, {
                  target_locale: targetLocale,
                  assigned_to: {
                    reference_type: "PERSON",
                    reference: assigneeRef.trim(),
                    display_name: assigneeName.trim() || null,
                  },
                  notes: notes.trim() || undefined,
                  expected_version: detail.workspace.version,
                }),
              )
            }
          >
            Создать assignment
          </button>
        </div>
      ) : null}

      {!assignments.length ? (
        <p className="text-sm text-zinc-500" data-testid="translations-empty">
          Перевод не назначен
        </p>
      ) : (
        <div className="space-y-4">
          {active.length ? (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">Активные</h4>
              <div className="space-y-3">
                {active.map((a) => (
                  <AssignmentCard
                    key={a.id}
                    assignment={a}
                    blocks={detail.blocks}
                    pending={pending}
                    showActions={!frozen && (canWork || canAssign)}
                    canAct={(action) => canActOnAssignment(a, action)}
                    onAction={handleAction}
                  />
                ))}
              </div>
            </div>
          ) : null}
          {history.length ? (
            <details>
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-zinc-500">История ({history.length})</summary>
              <div className="mt-2 space-y-3">
                {history.map((a) => (
                  <AssignmentCard key={a.id} assignment={a} blocks={detail.blocks} pending={pending} showActions={false} canAct={() => false} onAction={handleAction} />
                ))}
              </div>
            </details>
          ) : null}
        </div>
      )}
    </section>
  );
}
