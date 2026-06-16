// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelImportTrainingPageClient.tsx
"use client";

import * as React from "react";
import Link from "next/link";

import PersonnelSubNav from "./PersonnelSubNav";
import {
  getDocumentCandidatesSummary,
  getEmployeeTrainingHistory,
  listDocumentCandidates,
  mapImportApiError,
  type DocumentCandidate,
  type DocumentCandidatesSummary,
  type EmployeeTrainingHistory,
} from "../_lib/importApi.client";

const KIND_LABELS: Record<string, string> = {
  training: "Обучение",
  certification: "Сертификаты",
  education: "Образование",
};

const STATUS_LABELS: Record<string, string> = {
  PENDING: "На проверке",
  APPROVED: "Одобрено",
  REJECTED: "Отклонено",
  MERGED: "Объединено",
};

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{value}</div>
    </div>
  );
}

export default function PersonnelImportTrainingPageClient({ batchId }: { batchId: number }) {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [summary, setSummary] = React.useState<DocumentCandidatesSummary | null>(null);
  const [items, setItems] = React.useState<DocumentCandidate[]>([]);
  const [total, setTotal] = React.useState(0);
  const [kindFilter, setKindFilter] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("");
  const [nameQuery, setNameQuery] = React.useState("");
  const [selectedRowId, setSelectedRowId] = React.useState<number | null>(null);
  const [history, setHistory] = React.useState<EmployeeTrainingHistory | null>(null);
  const [historyLoading, setHistoryLoading] = React.useState(false);

  const loadList = React.useCallback(async () => {
    setLoading(true);
    try {
      const [sum, list] = await Promise.all([
        getDocumentCandidatesSummary(batchId),
        listDocumentCandidates(batchId, {
          document_kind: kindFilter || null,
          status: statusFilter || null,
          q_name: nameQuery || null,
          limit: 200,
        }),
      ]);
      setSummary(sum);
      setItems(list.items);
      setTotal(list.total);
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setLoading(false);
    }
  }, [batchId, kindFilter, statusFilter, nameQuery]);

  React.useEffect(() => {
    loadList();
  }, [loadList]);

  React.useEffect(() => {
    if (selectedRowId == null) {
      setHistory(null);
      return;
    }
    let cancelled = false;
    setHistoryLoading(true);
    getEmployeeTrainingHistory(batchId, selectedRowId)
      .then((data) => {
        if (!cancelled) setHistory(data);
      })
      .catch((e) => {
        if (!cancelled) setError(mapImportApiError(e));
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [batchId, selectedRowId]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <PersonnelSubNav />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Обучение и документы</h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Batch #{batchId} — нормализованные candidates (staging, без auto-apply)
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/directory/personnel/import/${batchId}`}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            ← Аналитика
          </Link>
          <Link
            href={`/directory/personnel/import/${batchId}/rows`}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            Строки batch
          </Link>
        </div>
      </div>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      ) : null}

      {summary ? (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <StatCard label="Всего candidates" value={summary.total_candidates} />
          <StatCard label="Обучение" value={summary.by_kind.training ?? 0} />
          <StatCard label="Сертификаты" value={summary.by_kind.certification ?? 0} />
          <StatCard label="Образование" value={summary.by_kind.education ?? 0} />
          <StatCard label="На проверке" value={summary.by_status.PENDING ?? 0} />
        </div>
      ) : null}

      <div className="mb-4 flex flex-wrap gap-3">
        <select
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
          className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        >
          <option value="">Все типы</option>
          <option value="training">Обучение</option>
          <option value="certification">Сертификаты</option>
          <option value="education">Образование</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        >
          <option value="">Все статусы</option>
          <option value="PENDING">На проверке</option>
          <option value="APPROVED">Одобрено</option>
          <option value="REJECTED">Отклонено</option>
        </select>
        <input
          type="search"
          placeholder="Поиск по ФИО"
          value={nameQuery}
          onChange={(e) => setNameQuery(e.target.value)}
          className="min-w-[200px] flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <section className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
          <div className="border-b border-zinc-200 px-4 py-3 text-sm font-semibold dark:border-zinc-800">
            Кандидаты документов ({total})
          </div>
          {loading ? (
            <div className="py-12 text-center text-zinc-500">Загрузка…</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-zinc-50 text-left text-[11px] uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
                  <tr>
                    <th className="px-3 py-2">Сотрудник</th>
                    <th className="px-3 py-2">Тип</th>
                    <th className="px-3 py-2">Название / ВУЗ</th>
                    <th className="px-3 py-2">Специальность</th>
                    <th className="px-3 py-2">Часы</th>
                    <th className="px-3 py-2">Дата</th>
                    <th className="px-3 py-2">Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr
                      key={item.candidate_id}
                      className={[
                        "cursor-pointer border-t border-zinc-100 dark:border-zinc-800",
                        selectedRowId === item.row_id ? "bg-blue-50 dark:bg-blue-950/30" : "",
                      ].join(" ")}
                      onClick={() => setSelectedRowId(item.row_id)}
                    >
                      <td className="px-3 py-2">
                        <div className="font-medium">{item.full_name || "—"}</div>
                        <div className="text-xs text-zinc-500">{item.department}</div>
                      </td>
                      <td className="px-3 py-2">{KIND_LABELS[item.document_kind] || item.document_kind}</td>
                      <td className="max-w-xs truncate px-3 py-2" title={item.title || item.organization}>
                        {item.document_kind === "education"
                          ? item.organization || item.title || item.raw_text.slice(0, 60)
                          : item.title || item.raw_text.slice(0, 60)}
                      </td>
                      <td className="px-3 py-2">{item.specialty || "—"}</td>
                      <td className="px-3 py-2">{item.hours ?? "—"}</td>
                      <td className="px-3 py-2">{item.issued_at ?? item.valid_until ?? "—"}</td>
                      <td className="px-3 py-2">{STATUS_LABELS[item.status] || item.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <aside className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">Карточка специалиста</h2>
          {!selectedRowId ? (
            <p className="text-sm text-zinc-500">Выберите строку в таблице для истории обучения.</p>
          ) : historyLoading ? (
            <p className="text-sm text-zinc-500">Загрузка истории…</p>
          ) : history ? (
            <div className="space-y-4 text-sm">
              <div>
                <div className="font-semibold text-zinc-900 dark:text-zinc-100">{history.employee.full_name}</div>
                <div className="text-zinc-500">{history.employee.department}</div>
                <div className="text-zinc-500">{history.employee.position}</div>
                <div className="mt-1 text-xs text-zinc-400">ИИН: {history.employee.iin_masked || "—"}</div>
              </div>
              <div>
                <div className="mb-2 text-xs font-medium uppercase text-zinc-500">История ({history.items.length})</div>
                <ul className="space-y-2">
                  {history.items.map((doc) => (
                    <li key={doc.candidate_id} className="rounded-lg bg-zinc-50 p-2 dark:bg-zinc-900">
                      <div className="font-medium">{doc.title || doc.raw_text.slice(0, 80)}</div>
                      <div className="text-xs text-zinc-500">
                        {KIND_LABELS[doc.document_kind]} · {doc.hours ? `${doc.hours} ч` : "—"} ·{" "}
                        {doc.issued_at ?? doc.valid_until ?? "без даты"}
                      </div>
                      {doc.external_url ? (
                        <a
                          href={doc.external_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-1 inline-block text-xs text-blue-600 hover:underline"
                        >
                          Google Drive / ссылка
                        </a>
                      ) : (
                        <div className="mt-1 text-xs text-zinc-400">Ссылка на диск: не указана</div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
