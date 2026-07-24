"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import { canSeeHrProcessesNav } from "@/lib/personnelNav";

import {
  formatTaskCreatedAt,
  summarizeEmploymentRecord,
} from "../_lib/employmentVerificationCompare";
import {
  EMPLOYMENT_VERIFICATION_BASE_PATH,
  getEmploymentTaskReview,
  listPendingEmploymentTasks,
  mapPersonnelVerificationApiError,
  verificationErrorKind,
  type EmploymentTaskReviewResponse,
  type VerificationTaskResponse,
} from "../_lib/personnelVerificationApi.client";
import EmploymentVerificationTaskPanel from "./EmploymentVerificationTaskPanel";

type QueueRow = {
  task: VerificationTaskResponse;
  review: EmploymentTaskReviewResponse | null;
  loadError: string | null;
};

const DECISION_SUCCESS_MESSAGE = "Решение сохранено. Очередь обновлена.";
const CONFLICT_ALREADY_PROCESSED_MESSAGE =
  "Задание уже обработано или данные изменились. Очередь обновлена.";

function parseTaskId(raw: string | null): number | null {
  if (!raw) return null;
  const value = Number(raw);
  return Number.isFinite(value) && value > 0 ? value : null;
}

export default function EmploymentVerificationPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlTaskId = React.useMemo(
    () => parseTaskId(searchParams.get("task_id")),
    [searchParams],
  );

  // Local selection is the source of truth for the detail card; URL stays in sync.
  const [selectedTaskId, setSelectedTaskId] = React.useState<number | null>(urlTaskId);
  const [allowed, setAllowed] = React.useState<boolean | null>(null);
  const [rows, setRows] = React.useState<QueueRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [decisionNotice, setDecisionNotice] = React.useState<string | null>(null);
  const [selectedReview, setSelectedReview] =
    React.useState<EmploymentTaskReviewResponse | null>(null);
  const [detailLoading, setDetailLoading] = React.useState(false);
  const [detailError, setDetailError] = React.useState<string | null>(null);

  const reviewRequestSeqRef = React.useRef(0);
  const skipUrlSyncRef = React.useRef(false);
  const prevUrlTaskIdRef = React.useRef<number | null>(urlTaskId);

  const invalidateDetailRequests = React.useCallback(() => {
    reviewRequestSeqRef.current += 1;
  }, []);

  const syncUrl = React.useCallback(
    (taskId: number | null) => {
      skipUrlSyncRef.current = true;
      router.replace(
        taskId == null
          ? EMPLOYMENT_VERIFICATION_BASE_PATH
          : `${EMPLOYMENT_VERIFICATION_BASE_PATH}?task_id=${taskId}`,
      );
    },
    [router],
  );

  const loadQueue = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const me = await apiAuthMe();
      if (!canSeeHrProcessesNav(me)) {
        setAllowed(false);
        setRows([]);
        return;
      }
      setAllowed(true);
      const list = await listPendingEmploymentTasks({ limit: 100 });
      const items = Array.isArray(list.items) ? list.items : [];
      const reviews = await Promise.all(
        items.map(async (task) => {
          try {
            const review = await getEmploymentTaskReview(task.task_id);
            return { task, review, loadError: null } satisfies QueueRow;
          } catch (e) {
            return {
              task,
              review: null,
              loadError: mapPersonnelVerificationApiError(
                e,
                "Не удалось загрузить карточку задания",
              ),
            } satisfies QueueRow;
          }
        }),
      );
      setRows(reviews);
    } catch (e) {
      setRows([]);
      setError(
        mapPersonnelVerificationApiError(e, "Не удалось загрузить очередь проверки"),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  // Deep link / browser back-forward → adopt URL only when the query actually changes.
  // Ignore stale URL values after local open/close while router.replace is in flight.
  React.useEffect(() => {
    if (skipUrlSyncRef.current) {
      skipUrlSyncRef.current = false;
      prevUrlTaskIdRef.current = urlTaskId;
      return;
    }
    if (urlTaskId !== prevUrlTaskIdRef.current) {
      prevUrlTaskIdRef.current = urlTaskId;
      setSelectedTaskId(urlTaskId);
    }
  }, [urlTaskId]);

  React.useEffect(() => {
    if (selectedTaskId == null) {
      invalidateDetailRequests();
      setSelectedReview(null);
      setDetailLoading(false);
      return;
    }

    const requestId = selectedTaskId;
    const requestSeq = ++reviewRequestSeqRef.current;
    setSelectedReview(null);
    setDetailError(null);
    setDetailLoading(true);

    getEmploymentTaskReview(requestId)
      .then((review) => {
        if (requestSeq !== reviewRequestSeqRef.current) return;
        if (review.task.task_id !== requestId) return;
        setSelectedReview(review);
      })
      .catch(async (e) => {
        if (requestSeq !== reviewRequestSeqRef.current) return;
        setSelectedReview(null);
        const kind = verificationErrorKind(e);
        if (kind === "conflict") {
          setDetailError(CONFLICT_ALREADY_PROCESSED_MESSAGE);
          setSelectedTaskId(null);
          syncUrl(null);
          await loadQueue();
          return;
        }
        setDetailError(
          mapPersonnelVerificationApiError(e, "Не удалось открыть задание"),
        );
      })
      .finally(() => {
        if (requestSeq !== reviewRequestSeqRef.current) return;
        setDetailLoading(false);
      });
  }, [selectedTaskId, invalidateDetailRequests, loadQueue, syncUrl]);

  function openTask(taskId: number) {
    setDecisionNotice(null);
    setDetailError(null);
    setSelectedReview(null);
    setDetailLoading(true);
    setSelectedTaskId(taskId);
    syncUrl(taskId);
  }

  function closeTask() {
    setDetailError(null);
    setSelectedTaskId(null);
    setSelectedReview(null);
    setDetailLoading(false);
    invalidateDetailRequests();
    syncUrl(null);
  }

  async function handleDecided() {
    setDecisionNotice(DECISION_SUCCESS_MESSAGE);
    setDetailError(null);
    setSelectedTaskId(null);
    setSelectedReview(null);
    setDetailLoading(false);
    invalidateDetailRequests();
    syncUrl(null);
    await loadQueue();
  }

  async function handleDecisionConflict() {
    setDecisionNotice(null);
    setSelectedTaskId(null);
    setSelectedReview(null);
    setDetailLoading(false);
    invalidateDetailRequests();
    syncUrl(null);
    setDetailError(CONFLICT_ALREADY_PROCESSED_MESSAGE);
    await loadQueue();
  }

  const visibleReview =
    selectedReview &&
    selectedTaskId != null &&
    selectedReview.task.task_id === selectedTaskId
      ? selectedReview
      : null;

  if (allowed === false) {
    return (
      <div className="px-4 py-6" data-testid="employment-verification-forbidden">
        <h1 className="text-xl font-semibold">Проверка трудовой биографии</h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          Недостаточно прав для просмотра очереди проверки.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4 px-4 py-3" data-testid="employment-verification-page">
      <div>
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
          Проверка трудовой биографии
        </h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Очередь предлагаемых редакций внешней трудовой биографии, ожидающих подтверждения
          кадрового администратора.
        </p>
      </div>

      {error ? (
        <div
          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-100"
          data-testid="employment-verification-queue-error"
          role="alert"
        >
          {error}
        </div>
      ) : null}

      {decisionNotice ? (
        <div
          className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-100"
          data-testid="employment-verification-action-success"
          role="status"
        >
          {decisionNotice}
        </div>
      ) : null}

      {loading ? (
        <p className="text-sm text-zinc-500" data-testid="employment-verification-loading">
          Загрузка очереди…
        </p>
      ) : rows.length === 0 ? (
        <div
          className="rounded-xl border border-dashed border-zinc-300 px-4 py-8 text-center text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400"
          data-testid="employment-verification-empty"
        >
          Нет заданий на проверку редакций трудовой биографии.
        </div>
      ) : (
        <div
          className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800"
          data-testid="employment-verification-queue"
        >
          <table className="min-w-full text-sm">
            <thead className="bg-zinc-50 text-left text-zinc-600 dark:bg-zinc-900 dark:text-zinc-300">
              <tr>
                <th className="px-3 py-2 font-medium">Сотрудник</th>
                <th className="px-3 py-2 font-medium">Текущая запись</th>
                <th className="px-3 py-2 font-medium">Предлагаемая редакция</th>
                <th className="px-3 py-2 font-medium">Создано</th>
                <th className="px-3 py-2 font-medium">Действие</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ task, review, loadError }) => (
                <tr
                  key={task.task_id}
                  className="border-t border-zinc-100 dark:border-zinc-800"
                  data-testid={`employment-verification-row-${task.task_id}`}
                >
                  <td className="px-3 py-2 font-medium text-zinc-900 dark:text-zinc-50">
                    {review?.person_full_name || `Person #${task.person_id}`}
                  </td>
                  <td className="px-3 py-2 text-zinc-700 dark:text-zinc-200">
                    {review
                      ? summarizeEmploymentRecord(review.prior)
                      : loadError || "—"}
                  </td>
                  <td className="px-3 py-2 text-zinc-700 dark:text-zinc-200">
                    {review
                      ? summarizeEmploymentRecord(review.revision)
                      : loadError || "—"}
                  </td>
                  <td className="px-3 py-2 text-zinc-600 dark:text-zinc-300">
                    {formatTaskCreatedAt(task.created_at)}
                  </td>
                  <td className="px-3 py-2">
                    <Link
                      href={`${EMPLOYMENT_VERIFICATION_BASE_PATH}?task_id=${task.task_id}`}
                      className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
                      onClick={(event) => {
                        event.preventDefault();
                        openTask(task.task_id);
                      }}
                      data-testid={`employment-verification-open-${task.task_id}`}
                    >
                      Открыть
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedTaskId != null ? (
        <div className="space-y-2" data-testid="employment-verification-detail">
          {detailLoading ? (
            <p
              className="text-sm text-zinc-500"
              data-testid="employment-verification-detail-loading"
            >
              Загрузка задания…
            </p>
          ) : null}
          {detailError ? (
            <div
              className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-100"
              data-testid="employment-verification-detail-error"
              role="alert"
            >
              {detailError}
              <button
                type="button"
                className="ml-3 underline"
                onClick={closeTask}
              >
                Закрыть
              </button>
            </div>
          ) : null}
          {visibleReview ? (
            <EmploymentVerificationTaskPanel
              key={visibleReview.task.task_id}
              review={visibleReview}
              onClose={closeTask}
              onDecided={handleDecided}
              onConflict={handleDecisionConflict}
            />
          ) : null}
        </div>
      ) : detailError ? (
        <div
          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-100"
          data-testid="employment-verification-detail-error"
          role="alert"
        >
          {detailError}
        </div>
      ) : null}
    </div>
  );
}
