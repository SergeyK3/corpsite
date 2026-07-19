// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelImportUploadPageClient.tsx
"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { mapImportApiError, uploadControlList, type ImportSummary } from "../_lib/importApi.client";

export default function PersonnelImportUploadPageClient() {
  const router = useRouter();
  const [file, setFile] = React.useState<File | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<{
    batch_id: number;
    file_name: string;
    summary: ImportSummary;
    warnings: string[];
  } | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Выберите Excel-файл (.xlsx).");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const data = await uploadControlList(file);
      setResult(data);
    } catch (err) {
      setError(mapImportApiError(err, "Не удалось выполнить stage-import."));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="px-4 py-3">
      <div className="mb-4">
        <h1 className="text-xl font-semibold">Загрузка контрольного списка</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Файл будет распарсен и сохранён в staging (<code>hr_import_*</code>). Apply не выполняется.
          Имя файла должно быть вида <code>контрольныйYYMM.xlsx</code>, например{" "}
          <code>контрольный2606.xlsx</code>.
        </p>
      </div>

      <form onSubmit={onSubmit} className="rounded-xl border border-zinc-200 p-6 dark:border-zinc-800">
        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Excel-файл (.xlsx)
          <input
            type="file"
            accept=".xlsx,.xlsm"
            className="mt-2 block w-full text-sm"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={uploading}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {uploading ? "Импорт…" : "Запустить stage-import"}
          </button>
          {!result ? (
            <Link
              href="/directory/personnel/import"
              className="rounded-lg border border-zinc-300 px-4 py-2 text-sm hover:bg-zinc-50 dark:border-zinc-700"
            >
              К списку импортов
            </Link>
          ) : null}
        </div>
      </form>

      {error ? (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      ) : null}

      {result ? (
        <div className="mt-6 rounded-xl border border-green-200 bg-green-50 p-4 text-sm dark:border-green-900 dark:bg-green-950">
          <div className="font-medium text-green-900 dark:text-green-100">Импорт завершён</div>
          <div className="mt-2 space-y-1 text-green-800 dark:text-green-200">
            <div>Batch ID: {result.batch_id}</div>
            <div>Файл: {result.file_name}</div>
            <div>Всего строк: {result.summary.total_rows}</div>
            <div>Валидных ИИН: {result.summary.valid_iin}</div>
            <div>С обучением: {result.summary.with_training}</div>
            <div>С категорией: {result.summary.with_certification}</div>
          </div>
          {result.warnings.length ? (
            <ul className="mt-3 list-disc pl-5 text-xs text-green-700 dark:text-green-300">
              {result.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          ) : null}
          <button
            type="button"
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            onClick={() => router.push(`/directory/personnel/import/${result.batch_id}`)}
          >
            Открыть аналитику
          </button>
        </div>
      ) : (
        <div className="mt-6 rounded-xl border border-dashed border-zinc-300 p-4 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
          <p className="font-medium">Альтернатива: CLI</p>
          <pre className="mt-2 overflow-x-auto rounded bg-zinc-100 p-3 text-xs dark:bg-zinc-900">
            {`python scripts/import_hr_control_list.py --file "контрольный июнь.xlsx" --stage --imported-by 1`}
          </pre>
          <p className="mt-2">После CLI-импорта откройте последний batch в списке импортов.</p>
        </div>
      )}
    </div>
  );
}
