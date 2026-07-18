"use client";

import * as React from "react";

import ImportEducationProfileCardModal from "./ImportEducationProfileCardModal";
import ImportBatchContextHeader from "./ImportBatchContextHeader";
import { IMPORT_RECORD_CARD_TITLE } from "@/lib/personnelCardTerminology";
import {
  renderPortfolioColumnPreview,
  TRAINING_CONTENT_FILTER_LABELS,
  type TrainingContentFilter,
} from "../_lib/importEducationProfileDisplay";
import {
  departmentFilterOptionValue,
  getDepartmentRecodingOptions,
  getEducationProfileDetail,
  listEducationProfiles,
  mapImportApiError,
  parseDepartmentFilterValue,
  parseGroupFilterValue,
  resolveGroupIdFromOptions,
  type DepartmentRecodingOptions,
  type EducationProfileDetail,
  type EducationProfilesSummary,
  type EducationProfileSummary,
  type PortfolioColumnPreview,
} from "../_lib/importApi.client";

/** Phase 2F.3 — employee education profiles (not document-candidates). */
export const PERSONNEL_IMPORT_TRAINING_UI_PHASE = "2f3-education-profiles";

const EMPTY_SUMMARY: EducationProfilesSummary = {
  total: 0,
  with_education: 0,
  with_training: 0,
  with_certificates: 0,
  with_categories: 0,
  without_portfolio: 0,
};

function TrainingSummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2 dark:border-zinc-800">
      <div className="text-[11px] uppercase tracking-[0.08em] text-zinc-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-100">{value}</div>
    </div>
  );
}

function PortfolioPreviewCell({ preview }: { preview?: PortfolioColumnPreview }) {
  const rendered = renderPortfolioColumnPreview(preview);
  const empty = rendered.primary === "Нет сведений";
  return (
    <div className={empty ? "text-zinc-400" : "text-zinc-800 dark:text-zinc-100"}>
      <div className="whitespace-pre-wrap break-words">{rendered.primary}</div>
      {rendered.suffix ? <div className="mt-1 text-xs text-zinc-500">{rendered.suffix}</div> : null}
    </div>
  );
}

export default function PersonnelImportTrainingPageClient({ batchId }: { batchId: number }) {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [items, setItems] = React.useState<EducationProfileSummary[]>([]);
  const [total, setTotal] = React.useState(0);
  const [summary, setSummary] = React.useState<EducationProfilesSummary>(EMPTY_SUMMARY);
  const [options, setOptions] = React.useState<DepartmentRecodingOptions | null>(null);
  const [orgGroupId, setOrgGroupId] = React.useState("");
  const [departmentFilter, setDepartmentFilter] = React.useState("");
  const [nameQuery, setNameQuery] = React.useState("");
  const [contentFilter, setContentFilter] = React.useState<TrainingContentFilter>("");
  const [offset, setOffset] = React.useState(0);
  const limit = 50;

  const [cardDetail, setCardDetail] = React.useState<EducationProfileDetail | null>(null);
  const [cardLoading, setCardLoading] = React.useState(false);

  React.useEffect(() => {
    getDepartmentRecodingOptions().then(setOptions).catch(() => setOptions(null));
  }, []);

  const filteredDepartments = React.useMemo(() => {
    const all = options?.departments ?? [];
    const groupId = resolveGroupIdFromOptions(options, orgGroupId);
    if (!groupId) return all;
    return all.filter((d) => d.org_group_id === groupId);
  }, [options, orgGroupId]);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const dept = parseDepartmentFilterValue(departmentFilter);
      const group = parseGroupFilterValue(orgGroupId);
      const data = await listEducationProfiles(batchId, {
        ...group,
        ...dept,
        q_name: nameQuery || undefined,
        content_filter: contentFilter || undefined,
        limit,
        offset,
      });
      setItems(data.items);
      setTotal(data.total);
      setSummary(data.summary ?? EMPTY_SUMMARY);
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setLoading(false);
    }
  }, [batchId, orgGroupId, departmentFilter, nameQuery, contentFilter, offset]);

  React.useEffect(() => {
    load();
  }, [load]);

  async function openCard(profileId: number) {
    setCardLoading(true);
    try {
      const detail = await getEducationProfileDetail(batchId, profileId);
      setCardDetail(detail);
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setCardLoading(false);
    }
  }

  return (
    <div
      className="px-4 py-3"
      data-ui-phase={PERSONNEL_IMPORT_TRAINING_UI_PHASE}
      data-batch-id={batchId}
    >
      <ImportBatchContextHeader batchId={batchId} className="mb-4" />

      <div className="mb-4">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Обучение</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Образовательные профили сотрудников из импорта: образование, обучение, сертификаты и категории в{" "}
          {IMPORT_RECORD_CARD_TITLE.toLowerCase()} (staging, без auto-apply).
        </p>
      </div>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      <section
        className="mb-4 grid gap-2 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800 sm:grid-cols-2 lg:grid-cols-6"
        data-testid="import-training-summary"
      >
        <TrainingSummaryCard label="Всего сотрудников" value={summary.total} />
        <TrainingSummaryCard label="С образованием" value={summary.with_education} />
        <TrainingSummaryCard label="С обучением" value={summary.with_training} />
        <TrainingSummaryCard label="С сертификатами" value={summary.with_certificates} />
        <TrainingSummaryCard label="С категориями" value={summary.with_categories} />
        <TrainingSummaryCard label="Без сведений" value={summary.without_portfolio} />
      </section>

      <div
        className="mb-4 grid gap-2 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800 md:grid-cols-5"
        data-testid="import-training-filters"
      >
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={orgGroupId}
          onChange={(e) => {
            setOrgGroupId(e.target.value);
            setDepartmentFilter("");
            setOffset(0);
          }}
        >
          <option value="">Все группы отделений</option>
          {options?.groups.map((g) => (
            <option key={g.value} value={g.value}>
              {g.label}
            </option>
          ))}
        </select>
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={departmentFilter}
          onChange={(e) => {
            setDepartmentFilter(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">Все отделения</option>
          {filteredDepartments.map((d) => (
            <option key={departmentFilterOptionValue(d)} value={departmentFilterOptionValue(d)}>
              {d.org_unit_name}
            </option>
          ))}
        </select>
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={contentFilter}
          onChange={(e) => {
            setContentFilter(e.target.value as TrainingContentFilter);
            setOffset(0);
          }}
          data-testid="import-training-content-filter"
        >
          {(Object.keys(TRAINING_CONTENT_FILTER_LABELS) as TrainingContentFilter[]).map((value) => (
            <option key={value || "all"} value={value}>
              {TRAINING_CONTENT_FILTER_LABELS[value]}
            </option>
          ))}
        </select>
        <input
          type="search"
          placeholder="Поиск по ФИО"
          value={nameQuery}
          onChange={(e) => {
            setNameQuery(e.target.value);
            setOffset(0);
          }}
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950 md:col-span-2"
        />
      </div>

      <section className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
        <div className="border-b border-zinc-200 px-4 py-3 text-sm font-semibold dark:border-zinc-800">
          Образовательные профили ({total})
        </div>
        {loading ? (
          <div className="py-12 text-center text-zinc-500">Загрузка…</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm" data-testid="import-training-table">
              <thead className="bg-zinc-50 text-left text-[11px] uppercase text-zinc-500 dark:bg-zinc-900">
                <tr>
                  <th className="px-3 py-2">ФИО</th>
                  <th className="px-3 py-2">Отделение</th>
                  <th className="px-3 py-2">Образование</th>
                  <th className="px-3 py-2">Обучение</th>
                  <th className="px-3 py-2">Сертификаты</th>
                  <th className="px-3 py-2">Категории</th>
                  <th className="px-3 py-2">Действие</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-zinc-500">
                      Нет профилей по выбранным фильтрам
                    </td>
                  </tr>
                ) : (
                  items.map((row) => (
                    <tr
                      key={row.aggregate_key ?? row.profile_id}
                      className="border-t border-zinc-100 dark:border-zinc-800"
                      data-testid={`import-training-row-${row.profile_id}`}
                    >
                      <td className="px-3 py-2 font-medium">{row.full_name || "—"}</td>
                      <td className="px-3 py-2">{row.org_unit_name || row.department_source || "—"}</td>
                      <td className="px-3 py-2 align-top">
                        <PortfolioPreviewCell preview={row.education} />
                      </td>
                      <td className="px-3 py-2 align-top">
                        <PortfolioPreviewCell preview={row.training} />
                      </td>
                      <td className="px-3 py-2 align-top">
                        <PortfolioPreviewCell preview={row.certificates} />
                      </td>
                      <td className="px-3 py-2 align-top">
                        <PortfolioPreviewCell preview={row.categories} />
                      </td>
                      <td className="px-3 py-2 align-top">
                        <button
                          type="button"
                          disabled={cardLoading}
                          onClick={() => openCard(row.profile_id)}
                          className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
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
        )}
        {total > limit ? (
          <div className="flex items-center justify-between border-t border-zinc-200 px-4 py-3 text-sm dark:border-zinc-800">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
              className="rounded border px-3 py-1 disabled:opacity-40"
            >
              ← Назад
            </button>
            <span className="text-zinc-500">
              {offset + 1}–{Math.min(offset + limit, total)} из {total}
            </span>
            <button
              type="button"
              disabled={offset + limit >= total}
              onClick={() => setOffset(offset + limit)}
              className="rounded border px-3 py-1 disabled:opacity-40"
            >
              Вперёд →
            </button>
          </div>
        ) : null}
      </section>

      {cardDetail ? (
        <ImportEducationProfileCardModal
          batchId={batchId}
          detail={cardDetail}
          onClose={() => setCardDetail(null)}
          onSaved={() => {
            setCardDetail(null);
            load();
          }}
        />
      ) : null}
    </div>
  );
}
