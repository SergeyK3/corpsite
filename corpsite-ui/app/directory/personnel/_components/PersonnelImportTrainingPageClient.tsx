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
  rebuildDocumentCandidates,
  type DocumentCandidate,
  type DocumentCandidatesSummary,
  type EmployeeTrainingHistory,
} from "../_lib/importApi.client";

const SOURCE_FIELD_LABELS: Record<string, string> = {
  education_training_raw: "column_m / education_training_raw",
  education_raw: "column_h / education_raw",
  certification_raw: "column_n / certification_raw",
  training_raw: "training_raw",
};

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

type FilterPreset = "all" | "education" | "training" | "certification" | "needs_review" | "no_link";

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
  const [rebuilding, setRebuilding] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [summary, setSummary] = React.useState<DocumentCandidatesSummary | null>(null);
  const [items, setItems] = React.useState<DocumentCandidate[]>([]);
  const [total, setTotal] = React.useState(0);
  const [filterPreset, setFilterPreset] = React.useState<FilterPreset>("all");
  const [nameQuery, setNameQuery] = React.useState("");
  const [selectedRowId, setSelectedRowId] = React.useState<number | null>(null);
  const [history, setHistory] = React.useState<EmployeeTrainingHistory | null>(null);
  const [historyLoading, setHistoryLoading] = React.useState(false);

  const listParams = React.useMemo(() => {
    const params: Record<string, string | number | boolean | null> = {
      limit: 500,
      q_name: nameQuery || null,
    };
    switch (filterPreset) {
      case "education":
        params.document_kind = "education";
        break;
      case "training":
        params.document_kind = "training";
        break;
      case "certification":
        params.document_kind = "certification";
        break;
      case "needs_review":
        params.status = "PENDING";
        break;
      case "no_link":
        params.no_link = true;
        break;
      default:
        break;
    }
    return params;
  }, [filterPreset, nameQuery]);

  const loadList = React.useCallback(async () => {
    setLoading(true);
    try {
      const [sum, list] = await Promise.all([
        getDocumentCandidatesSummary(batchId),
        listDocumentCandidates(batchId, listParams),
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
  }, [batchId, listParams]);

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

  async function handleRebuild() {
    const ok = window.confirm(
      "Пересобрать candidates из staging-строк?\n\nБудут удалены только записи со статусом «На проверке» / «Отклонено» без связанного документа. Одобренные и созданные документы сохранятся."
    );
    if (!ok) return;
    setRebuilding(true);
    try {
      await rebuildDocumentCandidates(batchId);
      setSelectedRowId(null);
      await loadList();
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setRebuilding(false);
    }
  }

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6">
      <PersonnelSubNav />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Кандидаты документов</h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Batch #{batchId} — education / training / certification (staging, без auto-apply)
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
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
          <button
            type="button"
            disabled={rebuilding || loading}
            onClick={handleRebuild}
            className="rounded-lg bg-amber-600 px-3 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {rebuilding ? "Пересборка…" : "Rebuild candidates"}
          </button>
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

      <div className="mb-4 flex flex-wrap gap-2">
        {(
          [
            ["all", "Все"],
            ["education", "Образование"],
            ["training", "Обучение"],
            ["certification", "Сертификаты"],
            ["needs_review", "На проверке"],
            ["no_link", "Без ссылки"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setFilterPreset(key)}
            className={[
              "rounded-lg px-3 py-1.5 text-sm",
              filterPreset === key
                ? "bg-blue-600 text-white"
                : "border border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900",
            ].join(" ")}
          >
            {label}
          </button>
        ))}
        <input
          type="search"
          placeholder="Поиск по ФИО"
          value={nameQuery}
          onChange={(e) => setNameQuery(e.target.value)}
          className="min-w-[200px] flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        <section className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
          <div className="border-b border-zinc-200 px-4 py-3 text-sm font-semibold dark:border-zinc-800">
            Кандидаты документов ({total})
          </div>
          {loading ? (
            <div className="py-12 text-center text-zinc-500">Загрузка…</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead className="bg-zinc-50 text-left text-[10px] uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
                  <tr>
                    <th className="px-2 py-2">row_id</th>
                    <th className="px-2 py-2">ФИО</th>
                    <th className="px-2 py-2">ИИН</th>
                    <th className="px-2 py-2">kind</th>
                    <th className="px-2 py-2">category</th>
                    <th className="px-2 py-2">doc type</th>
                    <th className="px-2 py-2">source_field</th>
                    <th className="px-2 py-2">title</th>
                    <th className="px-2 py-2">organization</th>
                    <th className="px-2 py-2">specialty</th>
                    <th className="px-2 py-2">hours</th>
                    <th className="px-2 py-2">date</th>
                    <th className="px-2 py-2">raw_text</th>
                    <th className="px-2 py-2">status</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr>
                      <td colSpan={14} className="px-4 py-8 text-center text-zinc-500">
                        Нет candidates по выбранным фильтрам
                      </td>
                    </tr>
                  ) : (
                    items.map((item) => (
                      <tr
                        key={item.candidate_id}
                        className={[
                          "cursor-pointer border-t border-zinc-100 dark:border-zinc-800",
                          selectedRowId === item.row_id ? "bg-blue-50 dark:bg-blue-950/30" : "",
                        ].join(" ")}
                        onClick={() => setSelectedRowId(item.row_id)}
                      >
                        <td className="px-2 py-2 font-mono">{item.row_id}</td>
                        <td className="max-w-[120px] truncate px-2 py-2" title={item.full_name}>
                          {item.full_name || "—"}
                        </td>
                        <td className="px-2 py-2 font-mono">{item.iin_masked || "—"}</td>
                        <td className="px-2 py-2">{KIND_LABELS[item.document_kind] || item.document_kind}</td>
                        <td className="px-2 py-2">{item.category || "—"}</td>
                        <td className="max-w-[100px] truncate px-2 py-2" title={item.document_type}>
                          {item.document_type || "—"}
                        </td>
                        <td className="max-w-[90px] truncate px-2 py-2" title={item.source_field}>
                          {SOURCE_FIELD_LABELS[item.source_field] || item.source_field || "—"}
                        </td>
                        <td className="max-w-[120px] truncate px-2 py-2" title={item.title}>
                          {item.title || "—"}
                        </td>
                        <td className="max-w-[120px] truncate px-2 py-2" title={item.organization}>
                          {item.organization || "—"}
                        </td>
                        <td className="max-w-[100px] truncate px-2 py-2" title={item.specialty}>
                          {item.specialty || "—"}
                        </td>
                        <td className="px-2 py-2">{item.hours ?? "—"}</td>
                        <td className="whitespace-nowrap px-2 py-2">{item.issued_at ?? item.valid_until ?? "—"}</td>
                        <td className="max-w-[180px] truncate px-2 py-2" title={item.raw_text}>
                          {item.raw_text || "—"}
                        </td>
                        <td className="whitespace-nowrap px-2 py-2">
                          {STATUS_LABELS[item.status] || item.status}
                        </td>
                      </tr>
                    ))
                  )}
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
                <div className="text-zinc-500">row_id: {history.employee.row_id}</div>
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
                        {KIND_LABELS[doc.document_kind]} · {doc.document_type || "—"} ·{" "}
                        {doc.hours ? `${doc.hours} ч` : "—"} · {doc.issued_at ?? doc.valid_until ?? "без даты"}
                      </div>
                      <div className="mt-1 text-xs text-zinc-400">{doc.raw_text.slice(0, 120)}</div>
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
