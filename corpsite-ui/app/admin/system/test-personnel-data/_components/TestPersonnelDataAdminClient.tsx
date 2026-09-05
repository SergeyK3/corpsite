"use client";

import { type KeyboardEvent as ReactKeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

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
  executeTestPersonnelDeletionRequest,
  forgetIdempotencyKey,
  forgetExecutionIdempotencyKey,
  getTestPersonnelDeletionRequest,
  listTestPersonnelDeletionRequests,
  previewTestPersonnel,
  stableIdempotencyKey,
  stableExecutionIdempotencyKey,
  submitTestPersonnelDeletionRequest,
  testPersonnelErrorCode,
  testPersonnelErrorMessage,
  testPersonnelErrorStatus,
  type TestPersonnelReasonCode,
  type TestPersonnelExecutionSnapshot,
  type TestPersonnelRequest,
  type TestPersonnelTarget,
} from "@/lib/testPersonnelDeletion";
import { canSeeTestPersonnelAdmin } from "@/lib/testPersonnelDeletionNav";

const BUTTON = "rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50";
const SECONDARY_BUTTON = "rounded-lg border border-zinc-300 px-4 py-2 text-sm font-semibold hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900";

const EXECUTION_BUTTON_LABEL = "Удалить одобренных тестовых претендентов";

function executionReason(reasonCode: string | null | undefined): string {
  const reasons: Record<string, string> = {
    TD_EXECUTION_DISABLED: "Исполнение удаления отключено",
    TD_EXECUTE_PERMISSION_REQUIRED: "Нет права на исполнение удаления",
    TD_MANIFEST_V1_READ_ONLY: "Manifest v1 не подлежит исполнению",
    TD_LEGACY_MANIFEST_NOT_EXECUTABLE: "Legacy-запрос не подлежит исполнению",
    TD_EMPLOYEE_DELETION_FORBIDDEN: "Запрос сотрудников не исполняется этим процессом",
    TD_EXECUTE_APPROVAL_REQUIRED: "Запрос не имеет действующего согласования",
    TD_APPROVAL_EXPIRED: "Срок согласования истёк",
    TD_APPROVAL_FINGERPRINT_MISMATCH: "Согласование больше не соответствует запросу",
    TD_FINGERPRINT_CHANGED: "Связи или fingerprint изменились",
    TD_READ_SNAPSHOT_CHANGED: "Сведения о запросе изменились; перечитайте запрос",
  };
  return reasons[String(reasonCode ?? "")] ?? "Запрос пока не готов к исполнению";
}

function targetKey(target: TestPersonnelTarget): string {
  return `${target.person_id}:${target.application_id}`;
}

function executionSnapshot(request: TestPersonnelRequest): TestPersonnelExecutionSnapshot | null {
  const approval = request.decisions?.findLast?.((item) => item.decision === "APPROVE") ??
    [...(request.decisions ?? [])].reverse().find((item) => item.decision === "APPROVE");
  const readiness = request.execution_readiness;
  if (
    !approval || !readiness || !request.approval_expires_at ||
    !request.fingerprint_version || !request.relationship_policy_version ||
    !request.catalog_version || !request.catalog_fingerprint
  ) return null;
  return {
    request_version: request.version,
    approval_decision_id: approval.decision_id,
    approval_request_version: approval.request_version,
    target_set_hash: request.target_set_hash,
    relationship_fingerprint: request.relationship_fingerprint,
    fingerprint_version: request.fingerprint_version,
    relationship_policy_version: request.relationship_policy_version,
    catalog_version: request.catalog_version,
    catalog_fingerprint: request.catalog_fingerprint,
    approval_expires_at: request.approval_expires_at,
    target_person_count: readiness.target_person_count,
  };
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
  const [executionDialogOpen, setExecutionDialogOpen] = useState(false);
  const [confirmedExecutionSnapshot, setConfirmedExecutionSnapshot] = useState<TestPersonnelExecutionSnapshot | null>(null);
  const [confirmationInput, setConfirmationInput] = useState("");
  const [executionOutcome, setExecutionOutcome] = useState<string | null>(null);
  const commandInFlight = useRef(false);
  const commandKeys = useRef<Map<string, string>>(new Map());
  const previewSequence = useRef(0);
  const detailSequence = useRef(0);
  const executionTriggerRef = useRef<HTMLButtonElement>(null);
  const executionDialogRef = useRef<HTMLDivElement>(null);
  const executionInitialFocusRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (executionDialogOpen) executionInitialFocusRef.current?.focus();
  }, [executionDialogOpen]);

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
    setExecutionDialogOpen(false);
    setConfirmationInput("");
    setExecutionOutcome(null);
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

  async function refreshAfterExecution(requestId: string) {
    try {
      setDetail(await getTestPersonnelDeletionRequest(requestId));
    } catch {
      // Preserve the safe execution result/error; the list remains another refresh path.
    }
    try {
      await loadRequests();
    } catch {
      // loadRequests owns its safe error projection.
    }
  }

  function closeExecutionDialog() {
    setExecutionDialogOpen(false);
    setConfirmationInput("");
    setConfirmedExecutionSnapshot(null);
    globalThis.setTimeout(() => executionTriggerRef.current?.focus(), 0);
  }

  function openExecutionDialog() {
    if (!detail || !executionAllowed) return;
    const snapshot = executionSnapshot(detail);
    if (!snapshot) {
      setError("Не удалось зафиксировать подтверждаемые сведения. Перечитайте запрос.");
      return;
    }
    setError(null);
    setExecutionOutcome(null);
    setConfirmationInput("");
    setConfirmedExecutionSnapshot(snapshot);
    setExecutionDialogOpen(true);
  }

  function handleExecutionDialogKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" && busyAction === null) {
      event.preventDefault();
      closeExecutionDialog();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = Array.from(executionDialogRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
    ) ?? []).filter((element) => !element.hasAttribute("hidden"));
    if (focusable.length === 0) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  async function runExecution() {
    const readiness = detail?.execution_readiness;
    if (
      !detail || !readiness?.allowed || !readiness.execution_enabled || commandInFlight.current ||
      !confirmedExecutionSnapshot || confirmationInput !== readiness.required_confirmation_phrase
    ) return;

    commandInFlight.current = true;
    detailSequence.current += 1;
    setBusyAction("execute-recheck");
    setError(null);
    setExecutionOutcome(null);
    const requestId = detail.request_id;
    const displayedSnapshot = confirmedExecutionSnapshot;
    let signature: string | null = null;
    try {
      const current = await getTestPersonnelDeletionRequest(requestId);
      const currentSnapshot = executionSnapshot(current);
      const snapshotChanged = (
        !current.execution_readiness?.allowed || !current.execution_readiness.execution_enabled ||
        !currentSnapshot || JSON.stringify(currentSnapshot) !== JSON.stringify(displayedSnapshot) ||
        current.execution_readiness.required_confirmation_phrase !== readiness.required_confirmation_phrase
      );
      if (snapshotChanged) {
        setDetail(current);
        closeExecutionDialog();
        setError("Подтверждённые сведения изменились. Проверьте запрос и введите фразу заново.");
        await loadRequests();
        return;
      }
      signature = JSON.stringify({
        requestId,
        confirmationPhrase: readiness.required_confirmation_phrase,
        expectedSnapshot: displayedSnapshot,
      });
      const idempotencyKey = stableExecutionIdempotencyKey(commandKeys.current, signature);
      setBusyAction("execute");
      const result = await executeTestPersonnelDeletionRequest(requestId, {
        idempotencyKey,
        confirmationPhrase: confirmationInput,
        expectedSnapshot: displayedSnapshot,
      });
      if (!["COMPLETED", "REAPPROVAL_REQUIRED", "FAILED"].includes(result.status)) {
        setError("Сервер вернул неизвестный результат. Удаление не считается завершённым; обновите сведения о запросе.");
      } else {
        forgetExecutionIdempotencyKey(commandKeys.current, signature);
        const replay = result.replayed ? " Показан сохранённый результат повторной отправки." : "";
        if (result.status === "COMPLETED") {
          setExecutionOutcome(`Удаление тестовых претендентов завершено.${replay}`);
        } else if (result.status === "REAPPROVAL_REQUIRED") {
          setExecutionOutcome(`Связи изменились. Требуется повторное согласование; удаление не выполнялось.${replay}`);
        } else {
          setExecutionOutcome(`Удаление не выполнено. Частичный результат не подтверждён.${replay}`);
        }
        closeExecutionDialog();
      }
    } catch (caught) {
      const code = testPersonnelErrorCode(caught);
      if (["TD_EXECUTE_IDEMPOTENCY_CONFLICT", "TD_EXECUTION_SNAPSHOT_CHANGED"].includes(code) && signature) {
        forgetExecutionIdempotencyKey(commandKeys.current, signature);
        closeExecutionDialog();
      }
      setError(testPersonnelErrorMessage(caught));
    } finally {
      await refreshAfterExecution(requestId);
      commandInFlight.current = false;
      setBusyAction(null);
    }
  }

  const approval = detail?.decisions?.findLast?.((item) => item.decision === "APPROVE") ??
    [...(detail?.decisions ?? [])].reverse().find((item) => item.decision === "APPROVE");
  const readiness = detail?.execution_readiness;
  const canExecute = me?.can_execute_test_personnel_deletion === true;
  const executionAllowed = readiness?.allowed === true && readiness.execution_enabled === true;
  const executionDisabledReason = readiness?.execution_enabled === false
    ? "Исполнение удаления отключено"
    : executionReason(readiness?.reason_code);
  const applicationCount = new Set((detail?.targets ?? []).map((target) => target.application_id)).size;

  return (
    <main className="space-y-6 p-4 sm:p-6" data-testid="test-personnel-admin-panel">
      <div className="space-y-6" inert={executionDialogOpen} aria-hidden={executionDialogOpen || undefined}>
      <header>
        <h1 id="test-personnel-admin-title" className="text-2xl font-semibold">Управление тестовыми данными персонала</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Предварительный просмотр не изменяет зафиксированный список. Запрос создаётся только из вручную выбранных записей.</p>
      </header>

      {error ? <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-900">{error}</p> : null}
      {executionOutcome ? <p role="status" className="rounded-lg border border-zinc-300 p-3 text-sm">{executionOutcome}</p> : null}

      <section className="space-y-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800" aria-labelledby="preview-title">
        <h2 id="preview-title" className="text-lg font-semibold">Безопасный предварительный просмотр</h2>
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
            {canExecute && readiness ? (
              <div className="space-y-1">
                <button
                  ref={executionTriggerRef}
                  type="button"
                  className={BUTTON}
                  disabled={!executionAllowed || busyAction !== null}
                  aria-describedby={!executionAllowed ? "execution-readiness-reason" : undefined}
                  onClick={openExecutionDialog}
                >
                  {EXECUTION_BUTTON_LABEL}
                </button>
                {!executionAllowed ? (
                  <p id="execution-readiness-reason" className="text-sm" role="note">
                    {executionDisabledReason}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      </div>

      {executionDialogOpen && detail && readiness ? (
        <div
          ref={executionDialogRef}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="execution-dialog-title"
          onKeyDown={handleExecutionDialogKeyDown}
        >
          <div className="max-h-[90vh] w-full max-w-2xl space-y-4 overflow-y-auto rounded-xl bg-white p-6 text-zinc-950 shadow-xl dark:bg-zinc-950 dark:text-zinc-50">
            <h2 id="execution-dialog-title" className="text-xl font-semibold">Окончательное подтверждение удаления</h2>
            {error ? <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-900">{error}</p> : null}
            <dl className="grid gap-2 text-sm sm:grid-cols-[minmax(12rem,auto)_1fr]">
              <dt className="font-semibold">Номер запроса</dt><dd>{detail.request_number}</dd>
              <dt className="font-semibold">Тип</dt><dd>Тестовые претенденты</dd>
              <dt className="font-semibold">Количество Person</dt><dd>{readiness.target_person_count}</dd>
              <dt className="font-semibold">Количество applications</dt><dd>{applicationCount}</dd>
              <dt className="font-semibold">Согласовал</dt><dd>{approval?.actor_display_name ?? (approval ? `Пользователь #${approval.actor_user_id}` : "—")}</dd>
              <dt className="font-semibold">Дата согласования</dt><dd>{formatDateTime(approval?.decided_at ?? detail.approved_at)}</dd>
              <dt className="font-semibold">Согласование действует до</dt><dd>{formatDateTime(detail.approval_expires_at)}</dd>
              <dt className="font-semibold">Manifest hash</dt><dd><code>{shortHash(detail.target_set_hash)}</code></dd>
              <dt className="font-semibold">Relationship hash</dt><dd><code>{shortHash(detail.relationship_fingerprint)}</code></dd>
              <dt className="font-semibold">Catalog hash</dt><dd><code>{shortHash(detail.catalog_fingerprint ?? "")}</code></dd>
            </dl>
            <p className="rounded-lg border-2 border-red-700 p-3 font-semibold" role="note">
              Внимание: будет выполнено физическое необратимое удаление одобренных тестовых претендентов.
            </p>
            <div className="rounded-lg bg-zinc-100 p-3 text-sm dark:bg-zinc-900">
              <p>Для продолжения вручную введите точную фразу:</p>
              <code className="mt-1 block select-all font-semibold">{readiness.required_confirmation_phrase}</code>
            </div>
            <label className="block text-sm font-semibold">
              Подтверждающая фраза
              <input
                ref={executionInitialFocusRef}
                autoComplete="off"
                value={confirmationInput}
                onChange={(event) => setConfirmationInput(event.target.value)}
                className="mt-1 w-full rounded-lg border border-zinc-400 bg-transparent px-3 py-2 font-mono"
              />
            </label>
            <div className="flex flex-wrap justify-end gap-2">
              <button type="button" className={SECONDARY_BUTTON} disabled={busyAction !== null} onClick={closeExecutionDialog}>
                Отмена
              </button>
              <button
                type="button"
                className={BUTTON}
                disabled={busyAction !== null || confirmationInput !== readiness.required_confirmation_phrase}
                onClick={() => void runExecution()}
              >
                {busyAction === "execute-recheck" ? "Проверка…" : busyAction === "execute" ? "Удаление…" : "Подтвердить необратимое удаление"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
