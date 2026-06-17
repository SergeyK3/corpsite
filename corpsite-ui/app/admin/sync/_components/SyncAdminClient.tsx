// FILE: corpsite-ui/app/admin/sync/_components/SyncAdminClient.tsx
"use client";

import * as React from "react";

import {
  downloadBase64Zip,
  exportSyncPackage,
  fetchSyncMeta,
  formatSyncTimestamp,
  mapSyncApiError,
  previewSyncPackage,
  type SyncExportResponse,
  type SyncPreviewItem,
  type SyncPreviewResponse,
} from "../_lib/syncApi.client";

type ActivityRecord = {
  at: string;
  label: string;
  detail: string;
};

const STATUS_STYLES: Record<string, string> = {
  new: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  update: "bg-blue-100 text-blue-900 dark:bg-blue-950 dark:text-blue-200",
  merge: "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-200",
  identical: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  conflict: "bg-amber-100 text-amber-950 dark:bg-amber-950 dark:text-amber-200",
  orphan: "bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-200",
  ambiguous: "bg-yellow-100 text-yellow-900 dark:bg-yellow-950 dark:text-yellow-200",
};

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] ?? "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{status}</span>
  );
}

function SummaryTile({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className={`rounded-xl border px-3 py-2 ${tone ?? "border-zinc-200 dark:border-zinc-800"}`}>
      <div className="text-xs text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function PreviewTable({ items }: { items: SyncPreviewItem[] }) {
  if (!items.length) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">Нет записей для отображения.</p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400">
          <tr>
            <th className="px-3 py-2">Employee Key</th>
            <th className="px-3 py-2">Сотрудник</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Action</th>
            <th className="px-3 py-2">Changed Sections</th>
            <th className="px-3 py-2">Reason</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.employee_key} className="border-t border-zinc-200 dark:border-zinc-800">
              <td className="px-3 py-2 font-mono text-xs">{item.employee_key}</td>
              <td className="px-3 py-2">{item.employee_name || "—"}</td>
              <td className="px-3 py-2">
                <StatusBadge status={item.status} />
                {item.status === "conflict" ? (
                  <div className="mt-1 text-xs font-medium text-amber-700 dark:text-amber-300">
                    Conflict · Review required
                    {item.conflict_type ? ` (${item.conflict_type})` : ""}
                  </div>
                ) : null}
              </td>
              <td className="px-3 py-2">{item.action}</td>
              <td className="px-3 py-2">
                {item.changed_sections?.length ? item.changed_sections.join(", ") : "—"}
              </td>
              <td className="px-3 py-2 max-w-xs text-xs text-zinc-600 dark:text-zinc-400">
                {item.reason || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SyncAdminClient() {
  const [schemaVersion, setSchemaVersion] = React.useState("—");
  const [packageVersion, setPackageVersion] = React.useState("—");
  const [metaError, setMetaError] = React.useState<string | null>(null);

  const [sourceInstanceId, setSourceInstanceId] = React.useState("vps-pilot");
  const [sourceOrgId, setSourceOrgId] = React.useState("");
  const [sourceOrgName, setSourceOrgName] = React.useState("");
  const [environment, setEnvironment] = React.useState<"server" | "local" | "staging">("server");
  const [notes, setNotes] = React.useState("");
  const [exporting, setExporting] = React.useState(false);
  const [exportError, setExportError] = React.useState<string | null>(null);
  const [exportResult, setExportResult] = React.useState<SyncExportResponse | null>(null);

  const [packageFile, setPackageFile] = React.useState<File | null>(null);
  const [previewing, setPreviewing] = React.useState(false);
  const [previewError, setPreviewError] = React.useState<string | null>(null);
  const [previewResult, setPreviewResult] = React.useState<SyncPreviewResponse | null>(null);

  const [lastExport, setLastExport] = React.useState<ActivityRecord | null>(null);
  const [lastPreview, setLastPreview] = React.useState<ActivityRecord | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const meta = await fetchSyncMeta();
        if (cancelled) return;
        setSchemaVersion(meta.schema_version);
        setPackageVersion(meta.package_version);
      } catch (err) {
        if (!cancelled) setMetaError(mapSyncApiError(err, "Не удалось загрузить метаданные sync."));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onExport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceInstanceId.trim() || !sourceOrgId.trim() || !sourceOrgName.trim()) {
      setExportError("Заполните source instance id и организацию.");
      return;
    }
    setExporting(true);
    setExportError(null);
    try {
      const result = await exportSyncPackage({
        source_instance_id: sourceInstanceId.trim(),
        source_organization_id: sourceOrgId.trim(),
        source_organization_name: sourceOrgName.trim(),
        environment,
        notes: notes.trim() || undefined,
      });
      setExportResult(result);
      downloadBase64Zip(result.package_base64, result.package_name);
      const at = new Date().toISOString();
      setLastExport({
        at,
        label: result.package_name,
        detail: `employees=${result.employee_count}, overrides=${result.override_count}, validation=${result.validation_ok ? "ok" : "fail"}`,
      });
    } catch (err) {
      setExportError(mapSyncApiError(err, "Не удалось выполнить экспорт."));
    } finally {
      setExporting(false);
    }
  };

  const onPreview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!packageFile) {
      setPreviewError("Выберите ZIP-пакет.");
      return;
    }
    setPreviewing(true);
    setPreviewError(null);
    try {
      const result = await previewSyncPackage(packageFile);
      setPreviewResult(result);
      const at = new Date().toISOString();
      setLastPreview({
        at,
        label: result.package_name || packageFile.name,
        detail: `records=${result.total_records}, identical=${result.identical_count}, conflict=${result.conflict_count}, apply_allowed=${result.apply_allowed_count}`,
      });
    } catch (err) {
      setPreviewError(mapSyncApiError(err, "Не удалось выполнить preview."));
    } finally {
      setPreviewing(false);
    }
  };

  return (
    <div className="px-4 py-3 max-w-6xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold">Синхронизация данных (HR Sync)</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Read-only интерфейс: экспорт пакета, загрузка и предпросмотр. Apply и разрешение конфликтов недоступны (Phase D.1).
        </p>
      </div>

      <section className="mb-6 rounded-2xl border border-zinc-200 p-4 dark:border-zinc-800">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Состояние Sync</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <div className="text-xs text-zinc-500">Schema</div>
            <div className="font-medium">{schemaVersion}</div>
          </div>
          <div>
            <div className="text-xs text-zinc-500">Package</div>
            <div className="font-medium">{packageVersion}</div>
          </div>
          <div>
            <div className="text-xs text-zinc-500">Последний экспорт</div>
            <div className="text-sm">{lastExport ? formatSyncTimestamp(lastExport.at) : "—"}</div>
            {lastExport ? <div className="text-xs text-zinc-500">{lastExport.detail}</div> : null}
          </div>
          <div>
            <div className="text-xs text-zinc-500">Последний preview</div>
            <div className="text-sm">{lastPreview ? formatSyncTimestamp(lastPreview.at) : "—"}</div>
            {lastPreview ? <div className="text-xs text-zinc-500">{lastPreview.detail}</div> : null}
          </div>
        </div>
        {metaError ? (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{metaError}</div>
        ) : null}
      </section>

      <section className="mb-6 rounded-2xl border border-zinc-200 p-4 dark:border-zinc-800">
        <h2 className="text-base font-semibold">Экспорт пакета</h2>
        <form onSubmit={onExport} className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            Source instance id
            <input
              className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              value={sourceInstanceId}
              onChange={(e) => setSourceInstanceId(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Environment
            <select
              className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              value={environment}
              onChange={(e) => setEnvironment(e.target.value as "server" | "local" | "staging")}
            >
              <option value="server">server</option>
              <option value="local">local</option>
              <option value="staging">staging</option>
            </select>
          </label>
          <label className="block text-sm">
            Source organization id
            <input
              className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              value={sourceOrgId}
              onChange={(e) => setSourceOrgId(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Source organization name
            <input
              className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              value={sourceOrgName}
              onChange={(e) => setSourceOrgName(e.target.value)}
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            Notes
            <textarea
              className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </label>
          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={exporting}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {exporting ? "Экспорт…" : "Экспортировать"}
            </button>
          </div>
        </form>
        {exportError ? (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{exportError}</div>
        ) : null}
        {exportResult ? (
          <div className="mt-4 rounded-xl border border-green-200 bg-green-50 p-4 text-sm dark:border-green-900 dark:bg-green-950">
            <div className="font-medium text-green-900 dark:text-green-100">Экспорт выполнен</div>
            <ul className="mt-2 space-y-1 text-green-800 dark:text-green-200">
              <li>Имя пакета: {exportResult.package_name}</li>
              <li>employees: {exportResult.employee_count}</li>
              <li>overrides: {exportResult.override_count}</li>
              <li>validation_ok: {exportResult.validation_ok ? "true" : "false"}</li>
            </ul>
            {exportResult.warnings.length ? (
              <ul className="mt-2 list-disc pl-5 text-xs">
                {exportResult.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            ) : null}
            <button
              type="button"
              className="mt-3 rounded-lg border border-green-700 px-3 py-1.5 text-xs hover:bg-green-100 dark:hover:bg-green-900"
              onClick={() => downloadBase64Zip(exportResult.package_base64, exportResult.package_name)}
            >
              Скачать снова
            </button>
          </div>
        ) : null}
      </section>

      <section className="mb-6 rounded-2xl border border-zinc-200 p-4 dark:border-zinc-800">
        <h2 className="text-base font-semibold">Загрузить пакет и предпросмотр</h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          ZIP хранится только на время preview-запроса. Данные в БД не изменяются.
        </p>
        <form onSubmit={onPreview} className="mt-4">
          <label className="block text-sm font-medium">
            Sync package (.zip)
            <input
              type="file"
              accept=".zip,application/zip"
              className="mt-2 block w-full text-sm"
              onChange={(e) => setPackageFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <button
            type="submit"
            disabled={previewing}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {previewing ? "Preview…" : "Предпросмотр"}
          </button>
        </form>
        {previewError ? (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{previewError}</div>
        ) : null}

        {previewResult ? (
          <div className="mt-6 space-y-4">
            {!previewResult.validation_ok ? (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
                validation_ok: false
                {previewResult.errors.length ? (
                  <ul className="mt-2 list-disc pl-5 text-xs">
                    {previewResult.errors.map((err) => (
                      <li key={err}>{err}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}

            <div className="grid gap-2 grid-cols-2 sm:grid-cols-4 lg:grid-cols-8">
              <SummaryTile label="new" value={previewResult.new_count} />
              <SummaryTile label="update" value={previewResult.update_count} />
              <SummaryTile label="merge" value={previewResult.merge_count} />
              <SummaryTile label="identical" value={previewResult.identical_count} />
              <SummaryTile label="orphan" value={previewResult.orphan_count} />
              <SummaryTile label="ambiguous" value={previewResult.ambiguous_count} />
              <SummaryTile label="conflict" value={previewResult.conflict_count} tone="border-amber-300 dark:border-amber-800" />
              <SummaryTile label="apply_allowed" value={previewResult.apply_allowed_count} />
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <SummaryTile label="skipped" value={previewResult.skipped_count} />
              <SummaryTile label="total_records" value={previewResult.total_records} />
            </div>

            {previewResult.warnings.length ? (
              <ul className="list-disc pl-5 text-xs text-amber-700 dark:text-amber-300">
                {previewResult.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            ) : null}

            <PreviewTable items={previewResult.items} />
          </div>
        ) : null}
      </section>
    </div>
  );
}
