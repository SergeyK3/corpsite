// FILE: corpsite-ui/app/admin/system/_components/personnel-lifecycle/EffectivePersonViewer.tsx
"use client";

import { useState } from "react";

import {
  fetchEffectivePerson,
  mapPersonnelLifecycleApiError,
  type EffectivePersonResponse,
} from "../../_lib/personnelLifecycleApi.client";
import ErrorBanner from "../shared/ErrorBanner";
import JsonViewer from "../shared/JsonViewer";

export default function EffectivePersonViewer() {
  const [personKey, setPersonKey] = useState("");
  const [assignmentKey, setAssignmentKey] = useState("");
  const [snapshotId, setSnapshotId] = useState("");
  const [result, setResult] = useState<EffectivePersonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLoad(): Promise<void> {
    const key = personKey.trim();
    if (!key) {
      setError("Укажите person_key");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchEffectivePerson({
        person_key: key,
        assignment_key: assignmentKey.trim() || undefined,
        snapshot_id: snapshotId ? Number(snapshotId) : undefined,
      });
      setResult(data);
    } catch (err) {
      setResult(null);
      setError(mapPersonnelLifecycleApiError(err, "Не удалось загрузить effective person"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-4" data-testid="effective-person-viewer">
      <h2 className="text-lg font-semibold">Effective Person Viewer</h2>
      <ErrorBanner message={error} />

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs">
          person_key
          <input
            value={personKey}
            onChange={(e) => setPersonKey(e.target.value)}
            className="mt-1 block w-64 rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="effective-person-key-input"
          />
        </label>
        <label className="text-xs">
          assignment_key (optional)
          <input
            value={assignmentKey}
            onChange={(e) => setAssignmentKey(e.target.value)}
            className="mt-1 block w-48 rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
          />
        </label>
        <label className="text-xs">
          snapshot_id (optional)
          <input
            type="number"
            min={1}
            value={snapshotId}
            onChange={(e) => setSnapshotId(e.target.value)}
            className="mt-1 block w-32 rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
          />
        </label>
        <button
          type="button"
          disabled={loading}
          onClick={() => void handleLoad()}
          className="rounded-lg bg-zinc-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-200 dark:text-zinc-900"
          data-testid="effective-person-load-btn"
        >
          {loading ? "…" : "Load"}
        </button>
      </div>

      {result ? (
        <div className="space-y-4 rounded-lg border border-zinc-200 p-4 dark:border-zinc-700" data-testid="effective-person-result">
          <div className="grid gap-2 text-sm sm:grid-cols-2">
            <span>snapshot_id: {result.snapshot_id}</span>
            <span>entry_id: {result.entry_id}</span>
            <span>scope_type: {result.scope_type}</span>
            <span>record_kind: {result.record_kind}</span>
          </div>
          <JsonViewer title="Canonical Payload" value={result.canonical_payload} testId="effective-person-canonical" />
          <JsonViewer title="Effective Payload" value={result.effective_payload} testId="effective-person-effective" />
          <JsonViewer title="Applied Overrides" value={result.applied_override_ids} testId="effective-person-overrides" />
          <JsonViewer title="Override IDs" value={result.applied_override_ids} />
        </div>
      ) : (
        <p className="text-sm text-zinc-500" data-testid="effective-person-empty">
          Введите person_key и нажмите Load.
        </p>
      )}
    </section>
  );
}
