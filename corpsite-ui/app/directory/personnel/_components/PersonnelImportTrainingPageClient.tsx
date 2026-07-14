"use client";

import * as React from "react";

import ImportEducationProfileCardModal from "./ImportEducationProfileCardModal";
import { IMPORT_RECORD_CARD_TITLE } from "@/lib/personnelCardTerminology";
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
  type EducationProfileSummary,
} from "../_lib/importApi.client";

/** Phase 2F.3 — employee education profiles (not document-candidates). */
export const PERSONNEL_IMPORT_TRAINING_UI_PHASE = "2f3-education-profiles";

export default function PersonnelImportTrainingPageClient({ batchId }: { batchId: number }) {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [items, setItems] = React.useState<EducationProfileSummary[]>([]);
  const [total, setTotal] = React.useState(0);
  const [options, setOptions] = React.useState<DepartmentRecodingOptions | null>(null);
  const [orgGroupId, setOrgGroupId] = React.useState("");
  const [departmentFilter, setDepartmentFilter] = React.useState("");
  const [nameQuery, setNameQuery] = React.useState("");
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
        limit,
        offset,
      });
      setItems(data.items);
      setTotal(data.total);
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setLoading(false);
    }
  }, [batchId, orgGroupId, departmentFilter, nameQuery, offset]);

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
      <div className="mb-4">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
          Образовательные профили сотрудников из импорта
        </h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Одна строка = один сотрудник. Обучение, сертификаты и категории — внутри {IMPORT_RECORD_CARD_TITLE.toLowerCase()} (staging,
          без auto-apply).
        </p>
      </div>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      <div className="mb-4 grid gap-2 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800 md:grid-cols-4">
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
          <option value="">Все отделы</option>
          {filteredDepartments.map((d) => (
            <option key={departmentFilterOptionValue(d)} value={departmentFilterOptionValue(d)}>
              {d.org_unit_name}
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
          Сотрудники ({total})
        </div>
        {loading ? (
          <div className="py-12 text-center text-zinc-500">Загрузка…</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 text-left text-[11px] uppercase text-zinc-500 dark:bg-zinc-900">
                <tr>
                  <th className="px-3 py-2">ФИО</th>
                  <th className="px-3 py-2">Отделение</th>
                  <th className="px-3 py-2">Должность</th>
                  <th className="px-3 py-2">Действие</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-zinc-500">
                      Нет сотрудников по выбранным фильтрам
                    </td>
                  </tr>
                ) : (
                  items.map((row) => (
                    <tr
                      key={row.aggregate_key ?? row.profile_id}
                      className="border-t border-zinc-100 dark:border-zinc-800"
                    >
                      <td className="px-3 py-2 font-medium">{row.full_name || "—"}</td>
                      <td className="px-3 py-2">{row.org_unit_name || row.department_source || "—"}</td>
                      <td className="px-3 py-2">{row.position_raw || "—"}</td>
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          disabled={cardLoading}
                          onClick={() => openCard(row.profile_id)}
                          className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                        >
                          Изменить
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
