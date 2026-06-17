"use client";

import * as React from "react";

import {
  getRowMedicalCategoryHistory,
  mapImportApiError,
  type RowMedicalCategoryHistory,
} from "../_lib/importApi.client";
import { calcRecordValidityNote } from "../_lib/importProfileEditor";

type Props = {
  batchId: number;
  rowId: number | null;
  open: boolean;
  onClose: () => void;
};

export default function ImportCategoryCardModal({ batchId, rowId, open, onClose }: Props) {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [detail, setDetail] = React.useState<RowMedicalCategoryHistory | null>(null);

  React.useEffect(() => {
    if (!open || rowId == null) {
      setDetail(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    getRowMedicalCategoryHistory(batchId, rowId)
      .then((data) => {
        if (cancelled) return;
        setDetail(data);
        setError(null);
      })
      .catch((e) => {
        if (!cancelled) setError(mapImportApiError(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [batchId, open, rowId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-950"
        role="dialog"
        aria-modal="true"
        aria-labelledby="category-card-title"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="category-card-title" className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              {detail?.full_name || "Карточка категории"}
            </h2>
            {detail ? (
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                {detail.position_raw || "—"}
                {detail.org_unit_name || detail.department
                  ? ` · ${detail.org_unit_name || detail.department}`
                  : ""}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            Закрыть
          </button>
        </div>

        {error ? <div className="mb-4 text-sm text-red-600">{error}</div> : null}

        {loading ? (
          <div className="py-10 text-center text-sm text-zinc-500">Загрузка…</div>
        ) : detail ? (
          <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 text-left text-[11px] uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
                <tr>
                  <th className="px-3 py-2">Дата категории</th>
                  <th className="px-3 py-2">Категория</th>
                  <th className="px-3 py-2">Специальность</th>
                  <th className="px-3 py-2">Примечание</th>
                </tr>
              </thead>
              <tbody>
                {detail.items.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-zinc-500">
                      Категории не найдены
                    </td>
                  </tr>
                ) : (
                  detail.items.map((item, index) => (
                    <tr key={`${item.date}-${item.category}-${index}`} className="border-t border-zinc-100 dark:border-zinc-800">
                      <td className="px-3 py-2">{item.date || "—"}</td>
                      <td className="px-3 py-2">{item.category_label || "—"}</td>
                      <td className="px-3 py-2">{item.specialty || "—"}</td>
                      <td className="px-3 py-2 text-xs text-zinc-600 dark:text-zinc-400">
                        {item.validity_note || calcRecordValidityNote(item.date) || "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </div>
  );
}
