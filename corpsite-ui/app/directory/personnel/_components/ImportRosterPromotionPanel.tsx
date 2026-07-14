"use client";

import * as React from "react";

import {
  mapImportApiError,
  promoteImportRosterBatch,
  type RosterPromotionItem,
  type RosterPromotionOutcome,
} from "../_lib/importApi.client";
import { HR_DOSSIER_PLURAL, HR_DOSSIER_PLURAL_TITLE } from "@/lib/personnelCardTerminology";

const OUTCOME_LABELS: Record<RosterPromotionOutcome, string> = {
  would_create: "Будет создан",
  would_update: "Будет обновлён",
  already_linked: "Уже привязан",
  exists: "Уже существует",
  conflict: "Конфликт",
  blocked: "Ошибка",
};

function outcomeBadgeClass(outcome: RosterPromotionOutcome): string {
  switch (outcome) {
    case "would_create":
      return "border-blue-200 bg-blue-50 text-blue-900";
    case "would_update":
      return "border-indigo-200 bg-indigo-50 text-indigo-900";
    case "already_linked":
      return "border-green-200 bg-green-50 text-green-900";
    case "conflict":
      return "border-orange-200 bg-orange-50 text-orange-900";
    case "blocked":
      return "border-red-200 bg-red-50 text-red-900";
    default:
      return "border-zinc-200 bg-zinc-50 text-zinc-800";
  }
}

type Props = {
  batchId: number;
};

export default function ImportRosterPromotionPanel({ batchId }: Props) {
  const [loading, setLoading] = React.useState(false);
  const [preview, setPreview] = React.useState<RosterPromotionItem[]>([]);
  const [summary, setSummary] = React.useState<Record<string, number>>({});
  const [error, setError] = React.useState<string | null>(null);
  const [applied, setApplied] = React.useState(false);

  const loadPreview = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await promoteImportRosterBatch(batchId, { dry_run: true });
      setPreview(data.items);
      setSummary(data.summary || {});
      setApplied(false);
    } catch (e) {
      setError(mapImportApiError(e));
      setPreview([]);
      setSummary({});
    } finally {
      setLoading(false);
    }
  }, [batchId]);

  React.useEffect(() => {
    if (batchId > 0) {
      loadPreview();
    }
  }, [batchId, loadPreview]);

  async function applyPromotion() {
    setLoading(true);
    setError(null);
    try {
      const data = await promoteImportRosterBatch(batchId, { dry_run: false });
      setPreview(data.items);
      setSummary(data.summary || {});
      setApplied(true);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setLoading(false);
    }
  }

  const actionable = preview.filter((item) =>
    ["would_create", "would_update"].includes(item.outcome)
  ).length;

  return (
    <section className="mb-6 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            Сотрудники из импорта
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Создание карточек сотрудников в справочнике по строкам roster batch #{batchId}. Выполните
            перед promotion документов.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={loading}
            onClick={loadPreview}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm disabled:opacity-50 dark:border-zinc-700"
          >
            Dry Run
          </button>
          <button
            type="button"
            disabled={loading || actionable === 0}
            onClick={applyPromotion}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Создать/обновить {HR_DOSSIER_PLURAL}
          </button>
        </div>
      </div>

      {error ? (
        <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      {applied ? (
        <div className="mb-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900">
          {HR_DOSSIER_PLURAL_TITLE} обновлены. Можно переходить к promotion документов.
        </div>
      ) : null}

      <div className="mb-3 flex flex-wrap gap-2 text-xs">
        {Object.entries(OUTCOME_LABELS).map(([key, label]) => (
          <span key={key} className="rounded-full border border-zinc-200 px-2 py-0.5 dark:border-zinc-700">
            {label}: {summary[key] ?? 0}
          </span>
        ))}
      </div>

      {loading ? (
        <div className="py-6 text-center text-sm text-zinc-500">Загрузка…</div>
      ) : preview.length === 0 ? (
        <div className="py-6 text-center text-sm text-zinc-500">Нет roster-строк для promotion</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-zinc-50 text-left text-[11px] uppercase text-zinc-500 dark:bg-zinc-900">
              <tr>
                <th className="px-2 py-2">Статус</th>
                <th className="px-2 py-2">ФИО</th>
                <th className="px-2 py-2">ИИН</th>
                <th className="px-2 py-2">Отделение</th>
                <th className="px-2 py-2">Должность</th>
                <th className="px-2 py-2">Причина</th>
              </tr>
            </thead>
            <tbody>
              {preview.map((item) => (
                <tr key={item.row_id} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="px-2 py-2">
                    <span
                      className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${outcomeBadgeClass(item.outcome)}`}
                    >
                      {OUTCOME_LABELS[item.outcome]}
                    </span>
                  </td>
                  <td className="px-2 py-2">{item.full_name || "—"}</td>
                  <td className="px-2 py-2 font-mono text-xs">{item.iin || "—"}</td>
                  <td className="px-2 py-2">{item.org_unit_name || "—"}</td>
                  <td className="px-2 py-2">{item.position_name || "—"}</td>
                  <td className="px-2 py-2 text-xs text-zinc-500">{item.reason || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
