// FILE: corpsite-ui/app/admin/sync/_components/SyncAdminClient.tsx
"use client";

import * as React from "react";

import { loadTenant } from "@/lib/tenant";

import {
  applySyncPackage,
  downloadBase64Zip,
  exportSyncPackage,
  fetchSyncMeta,
  formatSyncTimestamp,
  mapSyncApiError,
  previewSyncPackage,
  zipSizeKbFromBase64,
  type SyncApplyResponse,
  type SyncExportResponse,
  type SyncPreviewItem,
  type SyncPreviewResponse,
} from "../_lib/syncApi.client";

type ActivityRecord = {
  at: string;
  label: string;
  detail: string;
};

type ExportResultView = SyncExportResponse & {
  exportedAt: string;
  zipSizeKb: number;
};

const STATUS_STYLES: Record<string, string> = {
  identical: "bg-green-100 text-green-900 dark:bg-green-950 dark:text-green-200",
  new: "bg-blue-100 text-blue-900 dark:bg-blue-950 dark:text-blue-200",
  update: "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200",
  merge: "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-200",
  conflict: "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200",
  orphan: "bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-200",
  ambiguous: "bg-yellow-100 text-yellow-900 dark:bg-yellow-950 dark:text-yellow-200",
};

const STATUS_LABELS: Record<string, string> = {
  new: "Новый",
  update: "Изменение",
  merge: "Объединение",
  identical: "Идентичный",
  conflict: "Конфликт",
  orphan: "Сирота",
  ambiguous: "Неоднозначный",
};

const ACTION_LABELS: Record<string, string> = {
  insert: "Вставка",
  update: "Обновление",
  skip: "Пропуск",
  review_required: "Требует проверки",
};

const PREVIEW_SUMMARY_TILES: Array<{
  key: keyof SyncPreviewResponse;
  label: string;
  tone?: string;
}> = [
  { key: "new_count", label: "Новые" },
  { key: "update_count", label: "Изменения" },
  { key: "merge_count", label: "Объединение" },
  { key: "identical_count", label: "Идентичные" },
  { key: "orphan_count", label: "Сироты" },
  { key: "ambiguous_count", label: "Неоднозначные" },
  { key: "conflict_count", label: "Конфликты", tone: "border-red-300 dark:border-red-800" },
  { key: "apply_allowed_count", label: "Готово к применению" },
];

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] ?? "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
  const label = STATUS_LABELS[status] ?? status;
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>
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
            <th className="px-3 py-2">Ключ сотрудника</th>
            <th className="px-3 py-2">Сотрудник</th>
            <th className="px-3 py-2">Статус</th>
            <th className="px-3 py-2">Действие</th>
            <th className="px-3 py-2">Изменённые разделы</th>
            <th className="px-3 py-2">Причина</th>
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
                  <div className="mt-1 text-xs font-medium text-red-700 dark:text-red-300">
                    Конфликт · Требует проверки
                    {item.conflict_type ? ` (${item.conflict_type})` : ""}
                  </div>
                ) : null}
              </td>
              <td className="px-3 py-2">{ACTION_LABELS[item.action] ?? item.action}</td>
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
  const previewResultsRef = React.useRef<HTMLDivElement | null>(null);

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
  const [exportResult, setExportResult] = React.useState<ExportResultView | null>(null);

  const [packageFile, setPackageFile] = React.useState<File | null>(null);
  const [previewing, setPreviewing] = React.useState(false);
  const [previewError, setPreviewError] = React.useState<string | null>(null);
  const [previewResult, setPreviewResult] = React.useState<SyncPreviewResponse | null>(null);

  const [applying, setApplying] = React.useState(false);
  const [dryRunning, setDryRunning] = React.useState(false);
  const [applyError, setApplyError] = React.useState<string | null>(null);
  const [applyResult, setApplyResult] = React.useState<SyncApplyResponse | null>(null);

  const [lastExport, setLastExport] = React.useState<ActivityRecord | null>(null);
  const [lastPreview, setLastPreview] = React.useState<ActivityRecord | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [meta, tenant] = await Promise.all([fetchSyncMeta(), loadTenant()]);
        if (cancelled) return;
        setSchemaVersion(meta.schema_version);
        setPackageVersion(meta.package_version);
        if (tenant.orgId) {
          setSourceOrgId((prev) => prev || tenant.orgId!);
        }
        if (tenant.orgName) {
          setSourceOrgName((prev) => prev || tenant.orgName);
        }
      } catch (err) {
        if (!cancelled) setMetaError(mapSyncApiError(err, "Не удалось загрузить метаданные sync."));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    if (!previewResult) return;
    previewResultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [previewResult]);

  const canApplySection =
    Boolean(packageFile) && Boolean(previewResult) && Boolean(previewResult?.validation_ok);
  const applyAllowedCount = previewResult?.apply_allowed_count ?? 0;
  const canDryRunApply = canApplySection;
  const canRealApply = canApplySection && applyAllowedCount > 0;

  const onPackageFileChange = (file: File | null) => {
    setPackageFile(file);
    setPreviewResult(null);
    setApplyResult(null);
    setPreviewError(null);
    setApplyError(null);
  };

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
      const exportedAt = new Date().toISOString();
      const enriched: ExportResultView = {
        ...result,
        exportedAt,
        zipSizeKb: zipSizeKbFromBase64(result.package_base64),
      };
      setExportResult(enriched);
      downloadBase64Zip(result.package_base64, result.package_name);
      setLastExport({
        at: exportedAt,
        label: result.package_name,
        detail: `сотрудники=${result.employee_count}, overrides=${result.override_count}, ${zipSizeKbFromBase64(result.package_base64)} КБ`,
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
    setApplyResult(null);
    setApplyError(null);
    try {
      const result = await previewSyncPackage(packageFile);
      setPreviewResult(result);
      const at = new Date().toISOString();
      setLastPreview({
        at,
        label: result.package_name || packageFile.name,
        detail: `всего=${result.total_records}, идентичные=${result.identical_count}, конфликты=${result.conflict_count}`,
      });
    } catch (err) {
      setPreviewError(mapSyncApiError(err, "Не удалось выполнить preview."));
    } finally {
      setPreviewing(false);
    }
  };

  const runApply = async (dryRun: boolean) => {
    if (!packageFile) {
      setApplyError("Выберите ZIP-пакет.");
      return;
    }
    if (!previewResult) {
      setApplyError("Сначала выполните предпросмотр пакета.");
      return;
    }
    if (!previewResult.validation_ok) {
      setApplyError("Пакет не прошёл проверку — применение недоступно.");
      return;
    }
    if (!dryRun && previewResult.apply_allowed_count === 0) {
      setApplyError("Нет записей, разрешённых для применения.");
      return;
    }
    if (
      !dryRun &&
      !window.confirm(
        "Вы собираетесь применить sync-пакет.\n\nБудут применены только разрешённые изменения.\nКонфликты, сироты и неоднозначные записи применены не будут.",
      )
    ) {
      return;
    }

    if (dryRun) {
      setDryRunning(true);
    } else {
      setApplying(true);
    }
    setApplyError(null);
    try {
      const result = await applySyncPackage(packageFile, { dry_run: dryRun });
      setApplyResult(result);
    } catch (err) {
      setApplyError(mapSyncApiError(err, dryRun ? "Не удалось выполнить dry-run." : "Не удалось применить пакет."));
    } finally {
      setApplying(false);
      setDryRunning(false);
    }
  };

  return (
    <div className="px-4 py-3 max-w-6xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold">Синхронизация данных (HR Sync)</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Экспорт пакета, предпросмотр и безопасное применение с apply gate (Phase D.2). Разрешение конфликтов недоступно.
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
              <li>Размер ZIP: {exportResult.zipSizeKb} КБ</li>
              <li>Дата/время: {formatSyncTimestamp(exportResult.exportedAt)}</li>
              <li>Сотрудники: {exportResult.employee_count}</li>
              <li>Overrides: {exportResult.override_count}</li>
              <li>Проверка: {exportResult.validation_ok ? "успешно" : "ошибка"}</li>
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
              onChange={(e) => onPackageFileChange(e.target.files?.[0] ?? null)}
            />
          </label>
          <button
            type="submit"
            disabled={previewing}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {previewing ? "Предпросмотр…" : "Предпросмотр"}
          </button>
        </form>
        {previewError ? (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{previewError}</div>
        ) : null}

        {previewResult ? (
          <div ref={previewResultsRef} className="mt-6 scroll-mt-4 space-y-4">
            {!previewResult.validation_ok ? (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
                Проверка пакета не пройдена
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
              {PREVIEW_SUMMARY_TILES.map(({ key, label, tone }) => (
                <SummaryTile
                  key={key}
                  label={label}
                  value={Number(previewResult[key] ?? 0)}
                  tone={tone}
                />
              ))}
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <SummaryTile label="Пропущено" value={previewResult.skipped_count} />
              <SummaryTile label="Всего записей" value={previewResult.total_records} />
            </div>

            {previewResult.warnings.length ? (
              <ul className="list-disc pl-5 text-xs text-amber-700 dark:text-amber-300">
                {previewResult.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            ) : null}

            <PreviewTable items={previewResult.items} />

            <div className="rounded-2xl border border-zinc-200 p-4 dark:border-zinc-800">
              <h3 className="text-base font-semibold">Применение пакета</h3>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                Применяются только записи, разрешённые apply gate. Конфликты, сироты, неоднозначные и идентичные записи не изменяют БД.
              </p>
              <div className="mt-4 grid gap-2 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
                <SummaryTile label="Готово к применению" value={previewResult.apply_allowed_count} />
                <SummaryTile
                  label="Заблокировано"
                  value={previewResult.conflict_count}
                  tone="border-amber-300 dark:border-amber-800"
                />
                <SummaryTile
                  label="Конфликты"
                  value={previewResult.conflict_count}
                  tone="border-red-300 dark:border-red-800"
                />
                <SummaryTile label="Сироты" value={previewResult.orphan_count} />
                <SummaryTile label="Неоднозначные" value={previewResult.ambiguous_count} />
                <SummaryTile label="Идентичные/пропущенные" value={previewResult.identical_count + previewResult.skipped_count} />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={!canDryRunApply || dryRunning || applying}
                  onClick={() => runApply(true)}
                  className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-50 disabled:opacity-60 dark:border-zinc-700 dark:hover:bg-zinc-900"
                >
                  {dryRunning ? "Dry-run…" : "Проверить применение (dry-run)"}
                </button>
                <button
                  type="button"
                  disabled={!canRealApply || applying || dryRunning}
                  onClick={() => runApply(false)}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
                >
                  {applying ? "Применение…" : "Применить пакет"}
                </button>
              </div>
              {!previewResult ? (
                <p className="mt-2 text-xs text-zinc-500">Выполните предпросмотр, чтобы активировать применение.</p>
              ) : null}
              {previewResult && previewResult.apply_allowed_count === 0 ? (
                <p className="mt-2 text-xs text-zinc-500">
                  Нет разрешённых записей для реального применения. Dry-run доступен для проверки.
                </p>
              ) : null}
              {applyError ? (
                <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{applyError}</div>
              ) : null}
              {applyResult ? (
                <div
                  className={`mt-4 rounded-xl border p-4 text-sm ${
                    applyResult.dry_run
                      ? "border-sky-200 bg-sky-50 dark:border-sky-900 dark:bg-sky-950"
                      : "border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950"
                  }`}
                >
                  <div className="font-medium">
                    {applyResult.dry_run ? "Dry-run выполнен (БД не изменена)" : "Пакет применён"}
                  </div>
                  <div className="mt-3 grid gap-2 grid-cols-2 sm:grid-cols-4">
                    <SummaryTile label="Применено" value={applyResult.summary.applied} />
                    <SummaryTile label="Пропущено" value={applyResult.summary.skipped} />
                    <SummaryTile label="Заблокировано" value={applyResult.summary.blocked} />
                    <SummaryTile label="Идентичные" value={applyResult.summary.identical} />
                  </div>
                  {applyResult.errors.length ? (
                    <ul className="mt-3 list-disc pl-5 text-xs text-red-700 dark:text-red-300">
                      {applyResult.errors.map((err) => (
                        <li key={err}>{err}</li>
                      ))}
                    </ul>
                  ) : null}
                  {applyResult.warnings.length ? (
                    <ul className="mt-2 list-disc pl-5 text-xs text-amber-700 dark:text-amber-300">
                      {applyResult.warnings.map((w) => (
                        <li key={w}>{w}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
