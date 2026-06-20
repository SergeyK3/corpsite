// FILE: corpsite-ui/app/admin/system/_components/tabs/EnrollmentTab.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  applyEnrollmentQueueItem,
  approveEnrollmentBulk,
  approveEnrollmentQueueItem,
  detectEnrollment,
  fetchEnrollmentExplain,
  fetchEnrollmentQueue,
  mapAdminSystemApiError,
  rejectEnrollmentBulk,
  rejectEnrollmentQueueItem,
  type EnrollmentExplain,
  type EnrollmentQueueItem,
} from "../../_lib/adminSystemApi.client";
import { ENROLLMENT_APPLY_NOTICE, formatDateTime } from "../../_lib/adminSystemLabels";
import ErrorBanner, { InfoBanner, SuccessBanner } from "../shared/ErrorBanner";

const STATUSES = ["", "PENDING", "APPROVED", "REJECTED", "ENROLLED", "SUPERSEDED"];

export default function EnrollmentTab() {
  const [items, setItems] = useState<EnrollmentQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [selected, setSelected] = useState<EnrollmentQueueItem | null>(null);
  const [explain, setExplain] = useState<EnrollmentExplain | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [comment, setComment] = useState("");
  const [detectDryRun, setDetectDryRun] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchEnrollmentQueue({
        queue_status: statusFilter || undefined,
        limit: 200,
      });
      setItems(res.items);
      setTotal(res.total);
      setSelectedIds(new Set());
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось загрузить очередь"));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const pageIds = useMemo(() => items.map((item) => item.queue_id), [items]);
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id));

  async function loadExplain(queueId: number): Promise<void> {
    try {
      const data = await fetchEnrollmentExplain(queueId);
      setExplain(data);
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось загрузить explain"));
    }
  }

  async function handleSelectRow(item: EnrollmentQueueItem): Promise<void> {
    setSelected(item);
    setExplain(null);
    await loadExplain(item.queue_id);
  }

  function toggleRow(queueId: number): void {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(queueId)) next.delete(queueId);
      else next.add(queueId);
      return next;
    });
  }

  function toggleAllPage(): void {
    if (allPageSelected) setSelectedIds(new Set());
    else setSelectedIds(new Set(pageIds));
  }

  async function handleDetect(): Promise<void> {
    setError(null);
    setSuccess(null);
    try {
      const res = await detectEnrollment({ dry_run: detectDryRun, limit: 100 });
      setSuccess(
        detectDryRun
          ? `Dry-run: найдено ${res.candidate_count ?? 0} кандидатов (employee не создаётся)`
          : `Enqueued: ${res.enqueued?.length ?? 0} элементов`,
      );
      await load();
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Detect failed"));
    }
  }

  async function handleApprove(queueId: number): Promise<void> {
    setError(null);
    try {
      await approveEnrollmentQueueItem(queueId, comment || undefined);
      setSuccess(`Queue #${queueId} approved`);
      await load();
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Approve failed"));
    }
  }

  async function handleReject(queueId: number): Promise<void> {
    setError(null);
    try {
      await rejectEnrollmentQueueItem(queueId, comment || undefined);
      setSuccess(`Queue #${queueId} rejected`);
      await load();
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Reject failed"));
    }
  }

  async function handleApply(queueId: number): Promise<void> {
    setError(null);
    try {
      const res = await applyEnrollmentQueueItem(queueId);
      setSuccess(
        res.already_applied
          ? `Queue #${queueId} уже применён`
          : `Employee #${res.employee_id} создан/переиспользован`,
      );
      await load();
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Apply failed"));
    }
  }

  async function handleBulkApprove(): Promise<void> {
    const ids = Array.from(selectedIds);
    if (!ids.length) {
      setError("Выберите элементы очереди");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await approveEnrollmentBulk(ids, comment || undefined);
      setSuccess(`Approved: ${res.succeeded}, failed: ${res.failed}`);
      await load();
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Bulk approve failed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleBulkReject(): Promise<void> {
    const ids = Array.from(selectedIds);
    if (!ids.length) {
      setError("Выберите элементы очереди");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await rejectEnrollmentBulk(ids, comment || undefined);
      setSuccess(`Rejected: ${res.succeeded}, failed: ${res.failed}`);
      await load();
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Bulk reject failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <InfoBanner message={ENROLLMENT_APPLY_NOTICE} />
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          Статус
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="mt-1 block rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
          >
            {STATUSES.map((s) => (
              <option key={s || "all"} value={s}>
                {s || "Все"}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1 text-sm">
          <input
            type="checkbox"
            checked={detectDryRun}
            onChange={(e) => setDetectDryRun(e.target.checked)}
          />
          detect dry_run
        </label>
        <button
          type="button"
          onClick={() => void handleDetect()}
          className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white"
        >
          Найти кандидатов
        </button>
        <button
          type="button"
          disabled={busy || selectedIds.size === 0}
          onClick={() => void handleBulkApprove()}
          className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50"
        >
          Approve Selected ({selectedIds.size})
        </button>
        <button
          type="button"
          disabled={busy || selectedIds.size === 0}
          onClick={() => void handleBulkReject()}
          className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50"
        >
          Reject Selected
        </button>
        <button type="button" onClick={() => void load()} className="rounded-lg border px-3 py-2 text-sm">
          Обновить
        </button>
      </div>

      <p className="text-sm text-zinc-600">В очереди: {total}</p>

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
          {loading ? (
            <p className="p-4 text-sm">Загрузка…</p>
          ) : (
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 dark:bg-zinc-900">
                <tr>
                  <th className="px-3 py-2 text-left">
                    <input
                      type="checkbox"
                      checked={allPageSelected}
                      onChange={toggleAllPage}
                      aria-label="Выбрать все"
                    />
                  </th>
                  <th className="px-3 py-2 text-left">ID</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-left">Reason</th>
                  <th className="px-3 py-2 text-left">Person / Assignment</th>
                  <th className="px-3 py-2 text-left">Detected</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr
                    key={item.queue_id}
                    onClick={() => void handleSelectRow(item)}
                    className={`cursor-pointer border-t dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-900 ${
                      selected?.queue_id === item.queue_id ? "bg-blue-50 dark:bg-blue-950/30" : ""
                    }`}
                  >
                    <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(item.queue_id)}
                        onChange={() => toggleRow(item.queue_id)}
                        aria-label={`Выбрать queue ${item.queue_id}`}
                      />
                    </td>
                    <td className="px-3 py-2">{item.queue_id}</td>
                    <td className="px-3 py-2">{item.queue_status}</td>
                    <td className="px-3 py-2">{item.reason}</td>
                    <td className="px-3 py-2">
                      p:{item.person_id ?? "—"} / a:{item.assignment_id ?? "—"}
                    </td>
                    <td className="px-3 py-2">{formatDateTime(item.detected_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <aside className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
          <h3 className="font-medium">Карточка кандидата</h3>
          {selected ? (
            <div className="mt-2 space-y-3 text-sm">
              <div>Queue #{selected.queue_id}</div>
              <div>Status: {selected.queue_status}</div>
              <div>Reason: {selected.reason}</div>

              {explain?.explanation ? (
                <div className="rounded border border-zinc-200 bg-zinc-50 p-3 text-xs dark:border-zinc-700 dark:bg-zinc-900">
                  <div className="font-medium">Explain panel</div>
                  <div className="mt-2">
                    <span className="font-medium">Причина:</span>{" "}
                    {explain.explanation.reason_label ?? selected.reason}
                  </div>
                  {explain.explanation.source?.change_event_id ? (
                    <div className="mt-1">
                      <span className="font-medium">Источник:</span> hr_change_event #
                      {explain.explanation.source.change_event_id}
                      {explain.explanation.source.change_event_type
                        ? ` (${explain.explanation.source.change_event_type})`
                        : ""}
                    </div>
                  ) : null}
                  {explain.explanation.person ? (
                    <div className="mt-2">
                      <div className="font-medium">Person</div>
                      <div>ФИО: {explain.explanation.person.full_name ?? "—"}</div>
                      <div>ИИН: {explain.explanation.person.iin ?? "—"}</div>
                    </div>
                  ) : null}
                  {explain.explanation.assignment ? (
                    <div className="mt-2">
                      <div className="font-medium">Назначение</div>
                      <div>
                        Подразделение:{" "}
                        {explain.explanation.assignment.org_unit_name ??
                          explain.explanation.assignment.org_unit_id ??
                          "—"}
                      </div>
                      <div>
                        Должность:{" "}
                        {explain.explanation.assignment.position_name ??
                          explain.explanation.assignment.position_id ??
                          "—"}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              <div className="text-xs text-zinc-500 break-all">{selected.idempotency_key}</div>
              {selected.decision_comment ? (
                <div className="text-xs">Comment: {selected.decision_comment}</div>
              ) : null}
              <textarea
                placeholder="Комментарий approve/reject"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                className="mt-2 w-full rounded border p-2 text-xs dark:border-zinc-600 dark:bg-zinc-900"
                rows={2}
              />
              <div className="flex flex-col gap-1">
                {selected.queue_status === "PENDING" ? (
                  <button
                    type="button"
                    onClick={() => void handleApprove(selected.queue_id)}
                    className="rounded bg-green-600 px-2 py-1 text-xs text-white"
                  >
                    Approve
                  </button>
                ) : null}
                {selected.queue_status === "PENDING" || selected.queue_status === "APPROVED" ? (
                  <button
                    type="button"
                    onClick={() => void handleReject(selected.queue_id)}
                    className="rounded bg-zinc-600 px-2 py-1 text-xs text-white"
                  >
                    Reject
                  </button>
                ) : null}
                {selected.queue_status === "APPROVED" ? (
                  <button
                    type="button"
                    onClick={() => void handleApply(selected.queue_id)}
                    className="rounded bg-blue-600 px-2 py-1 text-xs text-white"
                  >
                    Apply
                  </button>
                ) : null}
                {selected.queue_status !== "APPROVED" ? (
                  <p className="text-xs text-zinc-500">Apply только для APPROVED</p>
                ) : null}
              </div>
            </div>
          ) : (
            <p className="mt-2 text-sm text-zinc-500">Выберите строку в таблице</p>
          )}
        </aside>
      </div>
    </div>
  );
}
