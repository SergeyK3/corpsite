"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  RequestSummary,
  StateNotice,
  TargetManifest,
  shortHash,
  statusLabel,
} from "@/components/test-personnel-deletion/TestPersonnelDeletionShared";
import { useCurrentUser } from "@/lib/currentUser";
import {
  approveTestPersonnelDeletionRequest,
  forgetIdempotencyKey,
  getTestPersonnelDeletionApproval,
  listTestPersonnelDeletionApprovals,
  rejectTestPersonnelDeletionRequest,
  stableIdempotencyKey,
  testPersonnelErrorMessage,
  testPersonnelErrorStatus,
  type TestPersonnelRequest,
} from "@/lib/testPersonnelDeletion";
import { canSeeTestPersonnelApprovals } from "@/lib/testPersonnelDeletionNav";

const BUTTON = "rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50";
const DANGER_BUTTON = "rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-50";

export default function TestPersonnelDeletionApprovalsClient() {
  const me = useCurrentUser();
  const allowed = canSeeTestPersonnelApprovals(me);
  const [queue, setQueue] = useState<TestPersonnelRequest[]>([]);
  const [detail, setDetail] = useState<TestPersonnelRequest | null>(null);
  const [comment, setComment] = useState("");
  const [attested, setAttested] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busyAction, setBusyAction] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const commandInFlight = useRef(false);
  const commandKeys = useRef<Map<string, string>>(new Map());
  const detailSequence = useRef(0);

  const loadQueue = useCallback(async () => {
    if (!allowed) return;
    setLoading(true);
    setError(null);
    try {
      setQueue(await listTestPersonnelDeletionApprovals());
    } catch (caught) {
      setError(testPersonnelErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, [allowed]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  if (!allowed) {
    return (
      <section className="p-4 sm:p-6" aria-labelledby="test-personnel-approval-title">
        <h1 id="test-personnel-approval-title" className="text-xl font-semibold">Согласование удаления тестовых данных</h1>
        <p role="alert" className="mt-3 text-sm text-red-800">Недостаточно прав для просмотра панели.</p>
      </section>
    );
  }

  async function openRequest(requestId: string) {
    if (commandInFlight.current) return;
    const sequence = ++detailSequence.current;
    setLoading(true);
    setDetail(null);
    setError(null);
    try {
      const loaded = await getTestPersonnelDeletionApproval(requestId);
      if (sequence !== detailSequence.current) return;
      setDetail(loaded);
      setComment("");
      setAttested(false);
    } catch (caught) {
      if (sequence === detailSequence.current) setError(testPersonnelErrorMessage(caught));
    } finally {
      if (sequence === detailSequence.current) setLoading(false);
    }
  }

  const needsAttestation = Boolean(
    detail?.targets?.some((target) =>
      target.requires_hr_synthetic_confirmation || target.hr_attestation_codes.length > 0,
    ),
  );

  async function decide(action: "approve" | "reject") {
    if (!detail || commandInFlight.current || (action === "approve" && needsAttestation && !attested)) return;
    commandInFlight.current = true;
    detailSequence.current += 1;
    setBusyAction(action);
    setError(null);
    const requestId = detail.request_id;
    const normalizedComment = comment.trim();
    const signature = JSON.stringify({
      requestId,
      version: detail.version,
      comment: normalizedComment,
      submittedSyntheticConfirmed: action === "approve" && attested,
    });
    const idempotencyKey = stableIdempotencyKey(commandKeys.current, action, signature);
    try {
      const input = {
        version: detail.version,
        idempotencyKey,
        comment: normalizedComment,
        submittedSyntheticConfirmed: action === "approve" && attested,
      };
      const result = action === "approve"
        ? await approveTestPersonnelDeletionRequest(requestId, input)
        : await rejectTestPersonnelDeletionRequest(requestId, input);
      forgetIdempotencyKey(commandKeys.current, action, signature);
      setDetail((current) => current?.request_id === requestId ? {
        ...current,
        status: result.status,
        stored_status: result.stored_status,
        version: result.version,
        expires_at: result.expires_at,
        approved_at: result.approved_at,
        approval_expires_at: result.approval_expires_at,
      } : current);
      try {
        setDetail(await getTestPersonnelDeletionApproval(requestId));
      } catch {
        setError("Решение сохранено, но detail не удалось обновить. Обновите очередь.");
      }
      await loadQueue();
    } catch (caught) {
      setError(testPersonnelErrorMessage(caught));
      if (testPersonnelErrorStatus(caught) === 409) {
        try {
          setDetail(await getTestPersonnelDeletionApproval(requestId));
        } catch {
          // Preserve the original safe conflict message when refresh is unavailable.
        }
      }
    } finally {
      commandInFlight.current = false;
      setBusyAction(null);
    }
  }

  return (
    <main className="space-y-5 p-4 sm:p-6" data-testid="test-personnel-approvals-panel">
      <header>
        <h1 id="test-personnel-approval-title" className="text-2xl font-semibold">Согласование удаления тестовых данных</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Решение относится только к зафиксированному manifest. Физическое удаление недоступно.</p>
      </header>

      {error ? <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-900">{error}</p> : null}

      <section className="space-y-3" aria-labelledby="approval-queue-title">
        <h2 id="approval-queue-title" className="text-lg font-semibold">Ожидают согласования</h2>
        {loading && queue.length === 0 ? <p role="status">Загрузка…</p> : null}
        {!loading && queue.length === 0 ? <p className="rounded-lg border border-dashed p-4 text-sm">Нет запросов, ожидающих решения.</p> : null}
        <div className="grid gap-2">
          {queue.map((request) => (
            <button key={request.request_id} type="button" disabled={loading || busyAction !== null} className="rounded-xl border border-zinc-200 p-3 text-left hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-800 dark:hover:bg-zinc-900" onClick={() => void openRequest(request.request_id)}>
              <span className="font-semibold">{request.request_number}</span>
              <span className="ml-2 text-sm">{statusLabel(request.status)}</span>
              <span className="ml-2 text-xs text-zinc-500">инициатор: {request.initiated_by_display_name ?? `Пользователь #${request.initiated_by_user_id}`}; целей: {request.targets?.length ?? 0}; hash {shortHash(request.target_set_hash)}</span>
            </button>
          ))}
        </div>
      </section>

      {detail ? (
        <section className="space-y-4 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800" aria-labelledby="approval-detail-title">
          <h2 id="approval-detail-title" className="text-lg font-semibold">Точный manifest {detail.request_number}</h2>
          <RequestSummary request={detail} />
          <StateNotice status={detail.status} />
          <TargetManifest targets={detail.targets ?? []} />
          {detail.status === "PENDING_HR_APPROVAL" ? (
            <>
              {needsAttestation ? (
                <label className="flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
                  <input type="checkbox" checked={attested} onChange={(event) => setAttested(event.target.checked)} />
                  <span>Подтверждаю, что записи со статусом intake_submitted имеют синтетический характер.</span>
                </label>
              ) : null}
              <label className="block text-sm">
                Безопасный комментарий (необязательно)
                <textarea value={comment} onChange={(event) => setComment(event.target.value)} maxLength={500} rows={3} className="mt-1 w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700" />
              </label>
              <div className="flex flex-wrap gap-2">
                <button type="button" className={BUTTON} disabled={busyAction !== null || (needsAttestation && !attested)} onClick={() => void decide("approve")}>
                  {busyAction === "approve" ? "Одобрение…" : "Одобрить удаление"}
                </button>
                <button type="button" className={DANGER_BUTTON} disabled={busyAction !== null} onClick={() => void decide("reject")}>
                  {busyAction === "reject" ? "Отклонение…" : "Отклонить"}
                </button>
              </div>
            </>
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
