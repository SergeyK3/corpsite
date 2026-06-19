"use client";

import * as React from "react";

import {
  downloadCanonicalSnapshotExport,
  mapImportApiError,
} from "../_lib/importApi.client";

type Props = {
  snapshotId?: number;
  includeMetadata?: boolean;
  className?: string;
  label?: string;
};

export default function CanonicalSnapshotExportButton({
  snapshotId,
  includeMetadata = false,
  className = "",
  label = "Выгрузить эталонный Excel",
}: Props) {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleExport() {
    setLoading(true);
    setError(null);
    try {
      await downloadCanonicalSnapshotExport({
        source_type: "roster",
        snapshot_id: snapshotId,
        include_metadata: includeMetadata,
      });
    } catch (e) {
      setError(mapImportApiError(e, "Не удалось выгрузить эталонный Excel."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={className}>
      <button
        type="button"
        data-testid="canonical-snapshot-export-button"
        onClick={() => void handleExport()}
        disabled={loading}
        className="rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-900 hover:bg-emerald-100 disabled:opacity-50 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100"
      >
        {loading ? "Выгрузка…" : label}
      </button>
      {error ? <div className="mt-1 text-xs text-red-600">{error}</div> : null}
    </div>
  );
}
