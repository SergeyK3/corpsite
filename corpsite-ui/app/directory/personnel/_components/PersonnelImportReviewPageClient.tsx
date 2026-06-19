"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import ImportCategoryCardModal from "./ImportCategoryCardModal";
import ImportDiffStatusBadge from "./ImportDiffStatusBadge";
import ImportMonthlyDiffSummaryPanel from "./ImportMonthlyDiffSummaryPanel";
import ImportRosterPromotionPanel from "./ImportRosterPromotionPanel";
import {
  departmentFilterOptionValue,
  getDepartmentRecodingOptions,
  getDeclarationsExportUrl,
  listStagingRows,
  mapImportApiError,
  parseDepartmentFilterValue,
  type DepartmentRecodingOptions,
  type StagingRow,
} from "../_lib/importApi.client";
import {
  formatMedicalCategoryLabel,
  MEDICAL_CATEGORY_FILTER_OPTIONS,
} from "../_lib/importCategoryUtils";

type ReviewMode = "personnel" | "declaration" | "technical";

const DECLARATION_TYPE_LABELS: Record<string, string> = {
  doctors: "Врачи",
  nurses: "Медсестры / СМР",
  junior_staff: "Младший персонал",
  other_staff: "Прочие",
  part_time: "Совместители",
};

const STAFF_TYPE_LABELS: Record<string, string> = {
  doctors: "Врачи",
  nurses: "Медсестры",
  junior_staff: "Санитарки",
  other_staff: "Прочие",
};

const TECHNICAL_CATEGORY_LABELS: Record<string, string> = {
  highest: "Высшая",
  first: "Первая",
  second: "Вторая",
  none: "Без категории",
  certificate: "Сертификат",
  other: "Прочая",
};

function ReviewFilters({
  mode,
  options,
  values,
  onChange,
}: {
  mode: ReviewMode;
  options: DepartmentRecodingOptions | null;
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
}) {
  const departments =
    options?.departments.filter(
      (d) => !values.org_group_id || String(d.org_group_id) === values.org_group_id
    ) ?? [];

  return (
    <div className="mb-4 grid gap-2 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800 md:grid-cols-3 lg:grid-cols-4">
      <select
        className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        value={values.org_group_id}
        onChange={(e) => onChange("org_group_id", e.target.value)}
      >
        <option value="">Все группы</option>
        {options?.groups.map((g) => (
          <option key={g.value} value={g.value}>
            {g.label}
          </option>
        ))}
      </select>
      <select
        className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        value={values.org_unit_id}
        onChange={(e) => onChange("org_unit_id", e.target.value)}
      >
        <option value="">Все отделения</option>
        {departments.map((d) => (
          <option key={departmentFilterOptionValue(d)} value={departmentFilterOptionValue(d)}>
            {d.org_unit_name}
          </option>
        ))}
      </select>
      {mode === "personnel" ? (
        <>
          <select
            className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            value={values.certification_category}
            onChange={(e) => onChange("certification_category", e.target.value)}
          >
            {MEDICAL_CATEGORY_FILTER_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            value={values.part_time}
            onChange={(e) => onChange("part_time", e.target.value)}
          >
            <option value="">Совместители: все</option>
            <option value="only">Только совместители</option>
            <option value="exclude">Только основные</option>
          </select>
        </>
      ) : null}
      {mode === "declaration" || mode === "technical" ? (
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={values.staff_type}
          onChange={(e) => onChange("staff_type", e.target.value)}
        >
          <option value="">Все типы персонала</option>
          {Object.entries(STAFF_TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      ) : null}
      {mode === "technical" ? (
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={values.certification_category}
          onChange={(e) => onChange("certification_category", e.target.value)}
        >
          <option value="">Все категории</option>
          {Object.entries(TECHNICAL_CATEGORY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      ) : null}
      <input
        className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        placeholder="Поиск по ФИО"
        value={values.q_name}
        onChange={(e) => onChange("q_name", e.target.value)}
      />
    </div>
  );
}

export default function PersonnelImportReviewPageClient({ batchId }: { batchId: number }) {
  const searchParams = useSearchParams();
  const mode = (searchParams.get("mode") as ReviewMode) || "personnel";

  const [items, setItems] = React.useState<StagingRow[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [options, setOptions] = React.useState<DepartmentRecodingOptions | null>(null);
  const [offset, setOffset] = React.useState(0);
  const [categoryRowId, setCategoryRowId] = React.useState<number | null>(null);
  const [showUnchanged, setShowUnchanged] = React.useState(false);
  const limit = 50;

  const [filters, setFilters] = React.useState({
    org_group_id: searchParams.get("org_group_id") || searchParams.get("department_group") || "",
    org_unit_id: searchParams.get("org_unit_id") || "",
    certification_category: searchParams.get("certification_category") || "",
    staff_type: searchParams.get("staff_type") || "",
    part_time: searchParams.get("part_time") || "",
    q_name: searchParams.get("q_name") || "",
  });

  React.useEffect(() => {
    setOffset(0);
    setCategoryRowId(null);
  }, [batchId, mode, showUnchanged]);

  React.useEffect(() => {
    setFilters({
      org_group_id: searchParams.get("org_group_id") || searchParams.get("department_group") || "",
      org_unit_id: searchParams.get("org_unit_id") || "",
      certification_category: searchParams.get("certification_category") || "",
      staff_type: searchParams.get("staff_type") || "",
      part_time: searchParams.get("part_time") || "",
      q_name: searchParams.get("q_name") || "",
    });
    setOffset(0);
  }, [searchParams]);

  React.useEffect(() => {
    getDepartmentRecodingOptions().then(setOptions).catch(() => setOptions(null));
  }, []);

  const load = React.useCallback(() => {
    setLoading(true);
    const params: Record<string, string | number | boolean | null | undefined> = {
      roster_scope: mode,
      org_group_id: filters.org_group_id ? Number(filters.org_group_id) : undefined,
      ...parseDepartmentFilterValue(filters.org_unit_id),
      certification_category: filters.certification_category || undefined,
      part_time: filters.part_time || undefined,
      q_name: filters.q_name || undefined,
      hide_unchanged: !showUnchanged,
      limit,
      offset,
    };

    if (mode === "personnel") {
      params.staff_types = "doctors,nurses";
    } else if (filters.staff_type) {
      params.staff_type = filters.staff_type;
    }

    listStagingRows(batchId, params)
      .then((data) => {
        setItems(data.items);
        setTotal(data.total);
        setError(null);
      })
      .catch((e) => setError(mapImportApiError(e)))
      .finally(() => setLoading(false));
  }, [batchId, mode, filters, offset, showUnchanged]);

  React.useEffect(() => {
    load();
  }, [load]);

  function updateFilter(key: string, value: string) {
    setFilters((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "org_group_id") {
        next.org_unit_id = "";
      }
      return next;
    });
    setOffset(0);
  }

  function handlePrint() {
    window.print();
  }

  const exportUrl = getDeclarationsExportUrl(batchId, {
    org_group_id: filters.org_group_id ? Number(filters.org_group_id) : undefined,
    ...parseDepartmentFilterValue(filters.org_unit_id),
    staff_type: filters.staff_type || undefined,
    q_name: filters.q_name || undefined,
  });

  const pageTitle =
    mode === "declaration" ? "Декларации" : mode === "technical" ? "Технические" : "Мед. категории";

  return (
    <div className="px-4 py-3">
      <ImportCategoryCardModal
        batchId={batchId}
        rowId={categoryRowId}
        open={categoryRowId != null}
        onClose={() => setCategoryRowId(null)}
      />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{pageTitle}</h1>
          <p className="text-sm text-zinc-500">
            Batch #{batchId} · read-only · без apply
            {mode === "personnel" ? " · только врачи и медсёстры" : ""}
          </p>
        </div>
        {mode === "declaration" ? (
          <div className="flex gap-2 print:hidden">
            <a
              href={exportUrl}
              className="rounded-lg border border-zinc-300 px-3 py-2 text-sm hover:bg-zinc-50 dark:border-zinc-700"
            >
              Скачать Excel
            </a>
            <button
              type="button"
              onClick={handlePrint}
              className="rounded-lg border border-zinc-300 px-3 py-2 text-sm hover:bg-zinc-50 dark:border-zinc-700"
            >
              Печать
            </button>
          </div>
        ) : null}
      </div>

      <div className="print:hidden">
        <ImportMonthlyDiffSummaryPanel
          batchId={batchId}
          showUnchanged={showUnchanged}
          onShowUnchangedChange={setShowUnchanged}
          onRecomputed={load}
        />
        <ImportRosterPromotionPanel batchId={batchId} />

      <ReviewFilters mode={mode} options={options} values={filters} onChange={updateFilter} />
      </div>

      {error ? <div className="mb-4 text-sm text-red-600">{error}</div> : null}

      <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full text-sm">
          <thead className="bg-zinc-50 text-left text-[11px] uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
            <tr>
              {mode === "declaration" ? (
                <>
                  <th className="px-3 py-2">ФИО</th>
                  <th className="px-3 py-2">Diff</th>
                  <th className="px-3 py-2">Отделение</th>
                  <th className="px-3 py-2">Тип декларации</th>
                </>
              ) : mode === "technical" ? (
                <>
                  <th className="px-3 py-2">Название строки</th>
                  <th className="px-3 py-2">Diff</th>
                  <th className="px-3 py-2">Возраст</th>
                  <th className="px-3 py-2">Отделение</th>
                  <th className="px-3 py-2">Должность</th>
                  <th className="px-3 py-2">Категория</th>
                  <th className="px-3 py-2" />
                </>
              ) : (
                <>
                  <th className="px-3 py-2">ФИО</th>
                  <th className="px-3 py-2">Diff</th>
                  <th className="px-3 py-2">Отделение</th>
                  <th className="px-3 py-2">Должность</th>
                  <th className="px-3 py-2">Категория</th>
                  <th className="px-3 py-2">Дата категории</th>
                  <th className="px-3 py-2" />
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-zinc-500">
                  Загрузка…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-zinc-500">
                  {!showUnchanged ? (
                    <div className="space-y-1">
                      <p className="font-medium text-zinc-700 dark:text-zinc-300">Изменений не обнаружено</p>
                      <p className="text-xs">
                        No changes detected — импорт совпадает с каноническим реестром или нет строк по фильтрам.
                      </p>
                    </div>
                  ) : (
                    "Строки не найдены"
                  )}
                </td>
              </tr>
            ) : mode === "declaration" ? (
              items.map((row) => (
                <tr key={row.row_id} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="px-3 py-2">{row.full_name || "—"}</td>
                  <td className="px-3 py-2">
                    <ImportDiffStatusBadge status={row.diff_status} compact />
                  </td>
                  <td className="px-3 py-2">{row.org_unit_name || row.department || "—"}</td>
                  <td className="px-3 py-2">
                    {DECLARATION_TYPE_LABELS[row.declaration_group || ""] ||
                      row.declaration_group ||
                      "—"}
                  </td>
                </tr>
              ))
            ) : mode === "technical" ? (
              items.map((row) => (
                <tr key={row.row_id} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="px-3 py-2">{row.full_name || row.classification || "—"}</td>
                  <td className="px-3 py-2">
                    <ImportDiffStatusBadge status={row.diff_status} compact />
                  </td>
                  <td className="px-3 py-2">{row.age ?? "—"}</td>
                  <td className="px-3 py-2">{row.org_unit_name || row.department || "—"}</td>
                  <td className="px-3 py-2">{row.position_raw || "—"}</td>
                  <td className="px-3 py-2">
                    {TECHNICAL_CATEGORY_LABELS[row.certification_group || "none"] || "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Link
                      href={`/directory/personnel/import/${batchId}/review/${row.row_id}`}
                      className="text-blue-600 hover:underline"
                    >
                      Открыть
                    </Link>
                  </td>
                </tr>
              ))
            ) : (
              items.map((row) => (
                <tr key={row.row_id} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="px-3 py-2">
                    {row.full_name || "—"}
                    {row.is_part_time ? (
                      <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-800">
                        совмещ
                      </span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2">
                    <ImportDiffStatusBadge status={row.diff_status} compact />
                  </td>
                  <td className="px-3 py-2">{row.org_unit_name || row.department || "—"}</td>
                  <td className="px-3 py-2">{row.position_raw || "—"}</td>
                  <td className="px-3 py-2">
                    {formatMedicalCategoryLabel(row.latest_medical_category) || "—"}
                  </td>
                  <td className="px-3 py-2">{row.latest_medical_category_date || "—"}</td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => setCategoryRowId(row.row_id)}
                      className="text-blue-600 hover:underline"
                    >
                      Открыть
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between text-sm text-zinc-600 print:hidden">
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
