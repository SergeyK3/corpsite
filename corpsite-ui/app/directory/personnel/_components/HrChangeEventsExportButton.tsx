"use client";

import * as React from "react";

import {
  downloadHrChangeEventsExport,
  mapHrChangeEventsApiError,
  type HrChangeEventsFilters,
} from "../_lib/hrChangeEventsApi.client";

type Props = {
  filters?: HrChangeEventsFilters;
  className?: string;
  label?: string;
};

export default function HrChangeEventsExportButton({
  filters = {},
  className = "",
  label = "Выгрузить изменения Excel",
}: Props) {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleExport() {
    setLoading(true);
    setError(null);
    try {
      await downloadHrChangeEventsExport(filters);
    } catch (e) {
      setError(mapHrChangeEventsApiError(e, "Не удалось выгрузить изменения Excel."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={className}>
      <button
        type="button"
        data-testid="hr-change-events-export-button"
        onClick={() => void handleExport()}
        disabled={loading}
        className="rounded-lg border border-blue-300 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-900 hover:bg-blue-100 disabled:opacity-50 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100"
      >
        {loading ? "Выгрузка…" : label}
      </button>
      {error ? <div className="mt-1 text-xs text-red-600">{error}</div> : null}
    </div>
  );
}
