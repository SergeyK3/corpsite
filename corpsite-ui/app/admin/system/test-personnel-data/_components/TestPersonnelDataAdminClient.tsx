"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  RequestSummary,
  StateNotice,
  TargetManifest,
  formatDateTime,
  shortHash,
  statusLabel,
  targetIsBlocked,
} from "@/components/test-personnel-deletion/TestPersonnelDeletionShared";
import { useCurrentUser } from "@/lib/currentUser";
import {
  REASON_OPTIONS,
  cancelTestPersonnelDeletionRequest,
  createTestPersonnelDeletionRequest,
  forgetIdempotencyKey,
  getTestPersonnelDeletionRequest,
  listTestPersonnelDeletionRequests,
  previewTestPersonnel,
  stableIdempotencyKey,
  submitTestPersonnelDeletionRequest,
  testPersonnelErrorMessage,
  testPersonnelErrorStatus,
  type TestPersonnelReasonCode,
  type TestPersonnelRequest,
  type TestPersonnelTarget,
} from "@/lib/testPersonnelDeletion";
import { canSeeTestPersonnelAdmin } from "@/lib/testPersonnelDeletionNav";

const BUTTON = "rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50";
const SECONDARY_BUTTON = "rounded-lg border border-zinc-300 px-4 py-2 text-sm font-semibold hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900";

function targetKey(target: TestPersonnelTarget): string {
  return `${target.person_id}:${target.application_id}`;
}

export default function TestPersonnelDataAdminClient() {
  const me = useCurrentUser();
  const allowed = canSeeTestPersonnelAdmin(me);
  const [mask, setMask] = useState("");
  const [previewMask, setPreviewMask] = useState("");
  const [preview, setPreview] = useState<TestPersonnelTarget[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [reasonCode, setReasonCode] = useState<TestPersonnelReasonCode>("LEGACY_SYNTHETIC_TEST_DATA");
  const [requests, setRequests] = useState<TestPersonnelRequest[]>([]);
  const [detail, setDetail] = useState<TestPersonnelRequest | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewComplete, setPreviewComplete] = useState(false);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const commandInFlight = useRef(false);
  const commandKeys = useRef<Map<string, string>>(new Map());
  const previewSequence = useRef(0);
  const detailSequence = useRef(0);

  const loadRequests = useCallback(async () => {
    if (!allowed) return;
    setRequestsLoading(true);
    try {
      setRequests(await listTestPersonnelDeletionRequests());
    } catch (caught) {
      setError(testPersonnelErrorMessage(caught));
    } finally {
      setRequestsLoading(false);
    }
  }, [allowed]);

  useEffect(() => {
    void loadRequests();
  }, [loadRequests]);

  const chosenTargets = useMemo(
    () => preview.filter((target) => selected.has(targetKey(target)) && !targetIsBlocked(target)),
    [preview, selected],
  );

  if (!allowed) {
    return (
      <section className="p-4 sm:p-6" aria-labelledby="test-personnel-admin-title">
        <h1 id="test-personnel-admin-title" className="text-xl font-semibold">Управление тестовыми данными персонала</h1>
        <p role="alert" className="mt-3 text-sm text-red-800">Недостаточно прав для просмотра панели.</p>
      </section>
    );
  }

  async function runPreview() {
    if (previewLoading) return;
    const sequence = ++previewSequence.current;
    const submittedMask = mask.trim();
    setPreviewLoading(true);
    setPreviewComplete(false);
    setError(null);
    try {
      const response = await previewTestPersonnel(submittedMask);
      if (sequence !== previewSequence.current) return;
      setPreview(response.items);
      setSelected(new Set());
      setPreviewMask(submittedMask);
      setPreviewComplete(true);
    } catch (caught) {
      if (sequence !== previewSequence.current) return;
      setError(testPersonnelErrorMessage(caught));
    } finally {
      if (sequence === previewSequence.current) setPreviewLoading(false);
    }
  }

  function changeMask(value: string) {
    previewSequence.current += 1;
    setMask(value);
    setPreviewMask("");
    setPreview([]);
    setSelected(new Set());
    setPreviewComplete(false);
    setPreviewLoading(false);
  }

  function toggleTarget(target: TestPersonnelTarget) {
    if (targetIsBlocked(target)) return;
    const key = targetKey(target);
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function openRequest(requestId: string) {
    if (commandInFlight.current) return;
    const sequence = ++detailSequence.current;
    setDetailLoading(true);
    setDetail(null);
    setError(null);
    try {
      const loaded = await getTestPersonnelDeletionRequest(requestId);
      if (sequence === detailSequence.current) setDetail(loaded);
    } catch (caught) {
      if (sequence === detailSequence.current) setError(testPersonnelErrorMessage(caught));
    } finally {
      if (sequence === detailSequence.current) setDetailLoading(false);
    }
  }

  async function createRequest() {
    if (commandInFlight.current || chosenTargets.length === 0) return;
    commandInFlight.current = true;
    detailSequence.current += 1;
    setBusyAction("create");
    setError(null);
    const targets = chosenTargets.map(({ person_id, application_id }) => ({ person_id, application_id }));
    const signature = JSON.stringify({ reasonCode, previewMask, targets });
    const idempotencyKey = stableIdempotencyKey(commandKeys.current, "create", signature);
    try {
      const created = await createTestPersonnelDeletionRequest({
        reason_code: reasonCode,
        original_mask: previewMask,
        targets,
        idempotency_key: idempotencyKey,
      });
      forgetIdempotencyKey(commandKeys.current, "create", signature);
      setSelected(new Set());
      try {
        setDetail(await getTestPersonnelDeletionRequest(created.request_id));
      } catch {
        setError("Запрос создан, но его detail не удалось обновить. Откройте запрос из списка.");
      }
      await loadRequests();
    } catch (caught) {
      setError(testPersonnelErrorMessage(caught));
    } finally {
      commandInFlight.current = false;
      setBusyAction(null);
    }
  }

  async function runCommand(action: "submit" | "cancel") {
    if (!detail || commandInFlight.current) return;
    commandInFlight.current = true;
    detailSequence.current += 1;
    setBusyAction(action);
    setError(null);
    const requestId = detail.request_id;
    const signature = JSON.stringify({ requestId, version: detail.version });
    const idempotencyKey = stableIdempotencyKey(commandKeys.current, action, signature);
    try {
      const result = action === "submit"
        ? await submitTestPersonnelDeletionRequest(requestId, detail.version, idempotencyKey)
        : await cancelTestPersonnelDeletionRequest(requestId, detail.version, idempotencyKey);
      forgetIdempotencyKey(commandKeys.current, action, signature);
      setDetail((current) => current?.request_id === requestId ? {
        ...current,
        status: result.status,
        stored_status: result.stored_status,
        version: result.version,
        expires_at: result.expires_at,
        approval_expires_at: result.approval_expires_at,
      } : current);
      try {
        setDetail(await getTestPersonnelDeletionRequest(requestId));
      } catch {
        setError("Команда выполнена, но detail не удалось обновить. Откройте запрос из списка.");
      }
      await loadRequests();
    } catch (caught) {
      setError(testPersonnelErrorMessage(caught));
      if (testPersonnelErrorStatus(caught) === 409) {
        try {
          setDetail(await getTestPersonnelDeletionRequest(requestId));
        } catch {
          // Preserve the original safe conflict message when refresh is unavailable.
        }
      }
    } finally {
      commandInFlight.current = false;
      setBusyAction(null);
    }
  }

  const approval = detail?.decisions?.findLast?.((item) => item.decision === "APPROVE") ??
    [...(detail?.decisions ?? [])].reverse().find((item) => item.decision === "APPROVE");

  return (
    <main className="space-y-6 p-4 sm:p-6" data-testid="test-personnel-admin-panel">
      <header>
        <h1 id="test-personnel-admin-title" className="text-2xl font-semibold">Управление тестовыми данными персонала</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Preview не изменяет manifest. Запрос создаётся только из вручную выбранных записей.</p>
      </header>

      {error ? <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-900">{error}</p> : null}

      <section className="space-y-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800" aria-labelledby="preview-title">
        <h2 id="preview-title" className="text-lg font-semibold">Безопасный preview</h2>
        <form className="flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); void runPreview(); }}>
          <label className="min-w-64 flex-1 text-sm">
            Маска отображаемого имени
            <input
              value={mask}
              onChange={(event) => changeMask(event.target.value)}
              minLength={3}
              required
              className="mt-1 w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
              placeholder="Например: Тестовый кандидат*"
            />
          </label>
          <button type="submit" className={`${BUTTON} self-end`} disabled={previewLoading || mask.trim().length < 3}>
            {previewLoading ? "Поиск…" : "Найти"}
          </button>
        </form>
        {preview.length ? (
          <TargetManifest targets={preview} selectable selected={selected} onToggle={toggleTarget} />
        ) : previewLoading ? (
          <p role="status" className="text-sm text-zinc-600">Поиск записей…</p>
        ) : previewComplete ? (
          <p className="rounded-lg border border-dashed p-4 text-sm">По заданной маске записи не найдены.</p>
        ) : (
          <p className="text-sm text-zinc-600">Введите маску для поиска тестовых записей.</p>
        )}
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-72 text-sm">
            Причина
            <select value={reasonCode} onChange={(event) => setReasonCode(event.target.value as TestPersonnelReasonCode)} className="mt-1 w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700">
              {REASON_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <button type="button" className={BUTTON} disabled={!chosenTargets.length || busyAction !== null} onClick={() => void createRequest()}>
            {busyAction === "create" ? "Создание…" : "Создать запрос на удаление"}
          </button>
          <span className="text-sm text-zinc-600">Выбрано: {chosenTargets.length}</span>
        </div>
      </section>

      <section className="space-y-3" aria-labelledby="requests-title">
        <h2 id="requests-title" className="text-lg font-semibold">Созданные запросы</h2>
        {requestsLoading && requests.length === 0 ? <p role="status">Загрузка запросов…</p> : requests.length === 0 ? (
          <p className="rounded-lg border border-dashed p-4 text-sm">Запросов пока нет.</p>
        ) : (
          <div className="grid gap-2">
            {requests.map((request) => (
              <button key={request.request_id} type="button" disabled={detailLoading || busyAction !== null} className="rounded-xl border border-zinc-200 p-3 text-left hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-800 dark:hover:bg-zinc-900" onClick={() => void openRequest(request.request_id)}>
                <span className="font-semibold">{request.request_number}</span>
                <span className="ml-2 text-sm">{statusLabel(request.status)}</span>
                <span className="ml-2 text-xs text-zinc-500">hash {shortHash(request.target_set_hash)}</span>
                <span className="mt-1 block text-xs text-zinc-500">
                  Инициатор: {request.initiated_by_display_name ?? `Пользователь #${request.initiated_by_user_id}`}; срок: {formatDateTime(request.approval_expires_at ?? request.expires_at)}
                </span>
              </button>
            ))}
          </div>
        )}
        {detailLoading ? <p role="status">Загрузка точного manifest…</p> : null}
      </section>

      {detail ? (
        <section className="space-y-4 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800" aria-labelledby="request-detail-title">
          <h2 id="request-detail-title" className="text-lg font-semibold">Точный manifest {detail.request_number}</h2>
          <RequestSummary request={detail} />
          <StateNotice status={detail.status} />
          <TargetManifest targets={detail.targets ?? []} />
          {detail.status === "APPROVED" ? (
            <div className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-950" data-testid="admin-approved-message">
              <p className="font-semibold">Удаление одобрено руководителем отдела кадров</p>
              <p>Согласующий: {approval?.actor_display_name ?? (approval ? `Пользователь #${approval.actor_user_id}` : "—")}</p>
              <p>Дата: {formatDateTime(approval?.decided_at ?? detail.approved_at)}</p>
              <p>Комментарий: {approval?.comment || "без комментария"}</p>
              <p>Целей: {detail.targets?.length ?? 0}; hash: {shortHash(detail.target_set_hash)}; действует до: {formatDateTime(detail.approval_expires_at)}</p>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            {detail.status === "DRAFT" || detail.status === "REAPPROVAL_REQUIRED" ? (
              <button type="button" className={BUTTON} disabled={busyAction !== null} onClick={() => void runCommand("submit")}>
                {busyAction === "submit" ? "Отправка…" : "Отправить на согласование"}
              </button>
            ) : null}
            {["DRAFT", "PENDING_HR_APPROVAL", "APPROVED", "REAPPROVAL_REQUIRED"].includes(detail.status) ? (
              <button type="button" className={SECONDARY_BUTTON} disabled={busyAction !== null} onClick={() => void runCommand("cancel")}>
                {busyAction === "cancel" ? "Отмена…" : "Отменить запрос"}
              </button>
            ) : null}
          </div>
        </section>
      ) : null}
    </main>
  );
}
