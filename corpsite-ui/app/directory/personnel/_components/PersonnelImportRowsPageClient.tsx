// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelImportRowsPageClient.tsx
"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import {
  listStagingRows,
  mapImportApiError,
  SHEET_TYPE_LABELS,
  type StagingRow,
} from "../_lib/importApi.client";
import ImportBatchContextHeader from "./ImportBatchContextHeader";

const AGE_OPTIONS = [
  { value: "", label: "Все возраста" },
  { value: "under_30", label: "до 30" },
  { value: "30_39", label: "30–39" },
  { value: "40_49", label: "40–49" },
  { value: "50_59", label: "50–59" },
  { value: "60_64", label: "60–64" },
  { value: "65_plus", label: "65+" },
];

export default function PersonnelImportRowsPageClient({ batchId }: { batchId: number }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [items, setItems] = React.useState<StagingRow[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [department, setDepartment] = React.useState(searchParams.get("department") || "");
  const [sheetType, setSheetType] = React.useState(searchParams.get("sheet_type") || "");
  const [ageBucket, setAgeBucket] = React.useState(searchParams.get("age_bucket") || "");
  const [hasTraining, setHasTraining] = React.useState(searchParams.get("has_training") || "");
  const [hasCertification, setHasCertification] = React.useState(searchParams.get("has_certification") || "");
  const [riskType, setRiskType] = React.useState(searchParams.get("risk_type") || "");
  const [rosterScope, setRosterScope] = React.useState(searchParams.get("roster_scope") || "personnel");
  const [qName, setQName] = React.useState(searchParams.get("q_name") || "");
  const [qPosition, setQPosition] = React.useState(searchParams.get("q_position") || "");
  const [offset, setOffset] = React.useState(0);
  const limit = 50;

  const load = React.useCallback(() => {
    setLoading(true);
    listStagingRows(batchId, {
      department: department || undefined,
      sheet_type: sheetType || undefined,
      age_bucket: ageBucket || undefined,
      has_training: hasTraining === "" ? undefined : hasTraining === "true",
      has_certification: hasCertification === "" ? undefined : hasCertification === "true",
      risk_type: riskType || undefined,
      roster_scope: rosterScope || undefined,
      q_name: qName || undefined,
      q_position: qPosition || undefined,
      limit,
      offset,
    })
      .then((data) => {
        setItems(data.items);
        setTotal(data.total);
        setError(null);
      })
      .catch((e) => setError(mapImportApiError(e)))
      .finally(() => setLoading(false));
  }, [
    batchId,
    department,
    sheetType,
    ageBucket,
    hasTraining,
    hasCertification,
    riskType,
    rosterScope,
    qName,
    qPosition,
    offset,
  ]);

  React.useEffect(() => {
    load();
  }, [load]);

  const applyFilters = () => {
    const q = new URLSearchParams();
    if (department) q.set("department", department);
    if (sheetType) q.set("sheet_type", sheetType);
    if (ageBucket) q.set("age_bucket", ageBucket);
    if (hasTraining) q.set("has_training", hasTraining);
    if (hasCertification) q.set("has_certification", hasCertification);
    if (riskType) q.set("risk_type", riskType);
    if (rosterScope && rosterScope !== "personnel") q.set("roster_scope", rosterScope);
    if (qName) q.set("q_name", qName);
    if (qPosition) q.set("q_position", qPosition);
    const qs = q.toString();
    router.replace(`/directory/personnel/import/${batchId}/rows${qs ? `?${qs}` : ""}`);
    setOffset(0);
  };

  return (
    <div className="px-4 py-3">
      <ImportBatchContextHeader batchId={batchId} className="mb-4" />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Строки импорта</h1>
          <p className="text-sm text-zinc-500">Read-only просмотр staging-строк</p>
        </div>
        <Link
          href={`/directory/personnel/import/${batchId}`}
          className="text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          ← Кадровый паспорт
        </Link>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {(
          [
            ["personnel", "Персонал"],
            ["declaration", "Декларации"],
            ["technical", "Технические"],
            ["all", "Все строки"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setRosterScope(value)}
            className={[
              "rounded-lg px-3 py-1.5 text-sm font-medium transition",
              rosterScope === value
                ? "bg-blue-600 text-white"
                : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:bg-zinc-900 dark:text-zinc-200",
            ].join(" ")}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mb-4 grid gap-2 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800 md:grid-cols-3 lg:grid-cols-4">
        <input
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          placeholder="Отделение"
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
        />
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={sheetType}
          onChange={(e) => setSheetType(e.target.value)}
        >
          <option value="">Все типы листа</option>
          {Object.entries(SHEET_TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={ageBucket}
          onChange={(e) => setAgeBucket(e.target.value)}
        >
          {AGE_OPTIONS.map((o) => (
            <option key={o.value || "all"} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={hasTraining}
          onChange={(e) => setHasTraining(e.target.value)}
        >
          <option value="">Обучение: все</option>
          <option value="true">Есть обучение</option>
          <option value="false">Нет обучения</option>
        </select>
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={hasCertification}
          onChange={(e) => setHasCertification(e.target.value)}
        >
          <option value="">Категория: все</option>
          <option value="true">Есть категория</option>
          <option value="false">Нет категории</option>
        </select>
        <input
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          placeholder="Риск (risk_type)"
          value={riskType}
          onChange={(e) => setRiskType(e.target.value)}
        />
        <input
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          placeholder="Поиск по ФИО"
          value={qName}
          onChange={(e) => setQName(e.target.value)}
        />
        <input
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          placeholder="Поиск по должности"
          value={qPosition}
          onChange={(e) => setQPosition(e.target.value)}
        />
        <button
          type="button"
          onClick={applyFilters}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 md:col-span-2 lg:col-span-1"
        >
          Применить
        </button>
      </div>

      {error ? <div className="mb-4 text-sm text-red-600">{error}</div> : null}

      <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full text-sm">
          <thead className="bg-zinc-50 text-left text-[11px] uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
            <tr>
              <th className="px-3 py-2">ФИО</th>
              <th className="px-3 py-2">ИИН</th>
              <th className="px-3 py-2">Д.р.</th>
              <th className="px-3 py-2">Возр.</th>
              <th className="px-3 py-2">Отделение</th>
              <th className="px-3 py-2">Должность</th>
              <th className="px-3 py-2">Обучение</th>
              <th className="px-3 py-2">Категория</th>
              <th className="px-3 py-2">Лист</th>
              <th className="px-3 py-2">Строка</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-zinc-500">
                  Загрузка…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-zinc-500">
                  Строки не найдены.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.row_id} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="px-3 py-2">{row.full_name || "—"}</td>
                  <td className="px-3 py-2 font-mono text-xs">{row.iin || "—"}</td>
                  <td className="px-3 py-2">{row.birth_date || "—"}</td>
                  <td className="px-3 py-2">{row.age ?? "—"}</td>
                  <td className="max-w-[160px] truncate px-3 py-2" title={row.department}>
                    {row.department || "—"}
                  </td>
                  <td className="max-w-[160px] truncate px-3 py-2" title={row.position_raw}>
                    {row.position_raw || "—"}
                  </td>
                  <td className="max-w-[120px] truncate px-3 py-2" title={row.training_raw}>
                    {row.training_raw ? "да" : "—"}
                  </td>
                  <td className="max-w-[120px] truncate px-3 py-2" title={row.certification_raw}>
                    {row.certification_raw ? "да" : "—"}
                  </td>
                  <td className="px-3 py-2">{row.source_sheet}</td>
                  <td className="px-3 py-2">{row.source_row_number}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between text-sm text-zinc-600">
        <span>
          Показано {items.length} из {total}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={offset <= 0}
            onClick={() => setOffset(Math.max(0, offset - limit))}
            className="rounded border px-3 py-1 disabled:opacity-40"
          >
            Назад
          </button>
          <button
            type="button"
            disabled={offset + limit >= total}
            onClick={() => setOffset(offset + limit)}
            className="rounded border px-3 py-1 disabled:opacity-40"
          >
            Вперёд
          </button>
        </div>
      </div>
    </div>
  );
}
