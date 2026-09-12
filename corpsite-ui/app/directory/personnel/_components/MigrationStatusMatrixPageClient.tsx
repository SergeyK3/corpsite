"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { buildPprMigrationCardHref, type PprMigrationCardSection } from "@/lib/employeeCardNav";
import type { APIError } from "@/lib/types";
import { getMigrationStatusMatrix, listMigrationStatusUniverses, type MigrationMatrix, type MigrationSection, type MigrationUniverse } from "../_lib/migrationStatusApi.client";
import { getOrgUnitsTree, type TreeNode } from "../../org-units/_lib/api.client";
import { apiFetchJson } from "@/lib/api";

const COLUMNS: Array<{ section: MigrationSection; title: string; cardSection: PprMigrationCardSection }> = [
  { section: "general", title: "Общие сведения", cardSection: "general" },
  { section: "education", title: "Образование", cardSection: "education" },
  { section: "training", title: "Обучение и повышение квалификации", cardSection: "training" },
  { section: "relatives", title: "Родственники", cardSection: "family" },
  { section: "military", title: "Воинский учёт", cardSection: "military" },
  { section: "employment_biography", title: "Трудовая биография", cardSection: "employment_biography" },
  { section: "employment_history", title: "Трудовая деятельность / послужной список", cardSection: "assignment" },
  { section: "foreign_languages", title: "Знание иностранных языков", cardSection: "languages" },
  { section: "additional", title: "Дополнительные сведения", cardSection: "additional" },
  { section: "awards", title: "Награды", cardSection: "additional" },
  { section: "academic_degrees_titles", title: "Учёные степени и звания", cardSection: "additional" },
];

const STATUS_FILTER_OPTIONS = [
  ["NOT_STARTED", "Не начато"], ["PROCESSING", "Обрабатывается"],
  ["AUTO_READY", "Готово к согласованию"], ["REVIEW_REQUIRED", "Требуется ручная проверка"],
  ["CORRECTED_BY_HR", "Исправлено кадровиком, требуется перепроверка"], ["ACCEPTED", "Согласовано"],
  ["NO_SOURCE_DATA", "Нет исходных данных"], ["NOT_APPLICABLE", "Не применимо"],
  ["BLOCKED", "Заблокировано"], ["STALE", "Требуется обновление"], ["ERROR", "Ошибка обработки"],
] as const;

const REASON_FILTER_OPTIONS = [
  ["RUN_NO_SECTION_RESULT", "Для раздела ещё нет результата обработки"],
  ["RUN_PREVIEW_READY", "Автоматический результат готов к согласованию"],
  ["RUN_PARTICIPANT_ACCEPTED", "Результат сотрудника подтверждён"],
  ["RUN_APPROVED", "Запуск согласован"], ["RUN_RUNNING", "Выполняется обработка"],
  ["CONFLICT_NAME_PARSE", "Конфликт разбора ФИО"], ["CONFLICT_CANONICAL_VALUE", "Конфликт кадровых сведений"],
  ["CONFLICT_EDUCATION_IDENTITY", "Конфликт идентификации образования"],
  ["CONFLICT_TRAINING_IDENTITY", "Конфликт идентификации обучения"],
  ["SOURCE_FRAGMENT_UNREVIEWED", "Источник требует ручной проверки"],
  ["MANUAL_CORRECTION_PENDING_RECHECK", "Исправление ожидает перепроверки"],
  ["FINGERPRINT_SOURCE_CHANGED", "Изменились исходные сведения"],
  ["FINGERPRINT_TARGET_CHANGED", "Изменились сведения личной карточки"],
  ["FINGERPRINT_BINDING_CHANGED", "Изменилась кадровая или исходная связь"],
  ["FINGERPRINT_POLICY_CHANGED", "Изменились правила обработки"],
  ["BINDING_EMPLOYEE_LINK_STALE", "Кадровая связь сотрудника изменилась"],
  ["RUN_PARTICIPANT_ERROR", "Ошибка обработки результата сотрудника"],
] as const;

function positive(value: string | null): number | undefined {
  const number = Number(value); return Number.isInteger(number) && number > 0 ? number : undefined;
}

function summaryCount(
  matrix: MigrationMatrix,
  sectionCode: string,
  statusCode: string,
): number {
  return matrix.status_summary?.counts.find(
    (item) => item.section_code === sectionCode && item.status_code === statusCode,
  )?.count ?? 0;
}

function summaryTotal(matrix: MigrationMatrix, sectionCode: string): number {
  return matrix.status_summary?.statuses.reduce(
    (total, status) => total + summaryCount(matrix, sectionCode, status.code),
    0,
  ) ?? 0;
}

export default function MigrationStatusMatrixPageClient() {
  const router = useRouter(); const pathname = usePathname(); const searchParams = useSearchParams();
  const key = searchParams.toString(); const params = React.useMemo(() => new URLSearchParams(key), [key]);
  const universeId = positive(params.get("universe_id")); const page = positive(params.get("page")) ?? 1;
  const [universes, setUniverses] = React.useState<MigrationUniverse[]>([]);
  const [matrix, setMatrix] = React.useState<MigrationMatrix | null>(null);
  const [loading, setLoading] = React.useState(true); const [error, setError] = React.useState<number | null>(null);
  const [reload, setReload] = React.useState(0);
  const [tree, setTree] = React.useState<TreeNode[]>([]);
  const [departmentGroups, setDepartmentGroups] = React.useState<Array<{group_id:number;group_name:string}>>([]);
  const [positions, setPositions] = React.useState<Array<{position_id:number;name:string}>>([]);
  const tableScrollRef = React.useRef<HTMLDivElement>(null);
  const [tableScrollMax, setTableScrollMax] = React.useState(0);
  const [tableScrollLeft, setTableScrollLeft] = React.useState(0);
  const returnTo = React.useMemo(() => `${pathname}${key ? `?${key}` : ""}`, [pathname, key]);

  const replace = React.useCallback((changes: Record<string, string | number | undefined>, resetPage = true) => {
    const next = new URLSearchParams(key);
    Object.entries(changes).forEach(([name, value]) => value == null || value === "" ? next.delete(name) : next.set(name, String(value)));
    if (resetPage) next.delete("page");
    router.replace(`${pathname}${next.size ? `?${next.toString()}` : ""}`);
  }, [key, pathname, router]);

  React.useEffect(() => {
    let active = true; setLoading(true); setError(null);
    void listMigrationStatusUniverses().then((response) => {
      if (!active) return; const items = Array.isArray(response.items) ? response.items : []; setUniverses(items);
      if (!universeId && items.length === 1) replace({ universe_id: items[0].universe_id }, false);
    }).catch((e: APIError) => active && setError(e?.status ?? 500)).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [reload, universeId, replace]);

  React.useEffect(() => {
    if (!universeId) { setMatrix(null); return; }
    let active = true; setLoading(true); setError(null);
    void getMigrationStatusMatrix({ universe_id: universeId, page, page_size: 50, section: params.get("section") as MigrationSection || undefined, status: params.get("status") || undefined, reason: params.get("reason") || undefined, org_group_id:positive(params.get("org_group_id")), org_unit_id: positive(params.get("org_unit_id")), position_id:positive(params.get("position_id")), q: params.get("q") || undefined })
      .then((response) => active && setMatrix(response))
      .catch((e: APIError) => active && setError(e?.status ?? 500))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [universeId, page, key, params, reload]);
  React.useEffect(() => {
    let active = true;
    void Promise.all([
      getOrgUnitsTree(),
      apiFetchJson<{items?: Array<{group_id:number;group_name:string}>}>("/directory/department-groups", { query: { limit: 500 } }),
    ]).then(([orgTree, groupsResponse]) => {
      if (!active) return;
      setTree(orgTree.items);
      setDepartmentGroups(groupsResponse.items ?? []);
    }).catch(() => {
      if (!active) return;
      setTree([]);
      setDepartmentGroups([]);
    });
    return () => { active = false; };
  }, []);
  const allUnits = React.useMemo(() => {
    const result: TreeNode[] = [];
    const visit = (nodes: TreeNode[]) => nodes.forEach((node) => {
      result.push(node);
      visit(node.children ?? []);
    });
    visit(tree);
    return result;
  }, [tree]);
  const groups = React.useMemo(() => {
    const usedGroupIds = new Set(allUnits.map((unit) => unit.group_id).filter((value): value is number => value != null));
    return departmentGroups.filter((group) => usedGroupIds.has(group.group_id));
  }, [allUnits, departmentGroups]);
  const groupId=params.get("org_group_id")??""; const unitId=params.get("org_unit_id")??"";
  const units = React.useMemo(() => allUnits.filter((unit) => !groupId || String(unit.group_id ?? "") === groupId), [allUnits, groupId]);
  React.useEffect(() => {
    if (!unitId) { setPositions([]); return; }
    void apiFetchJson<{items?: Array<{position_id:number;name:string}>}>("/directory/positions", {
      query: { org_unit_id: unitId, scope: "allowed", limit: 500 },
    }).then((response) => setPositions(response.items ?? [])).catch(() => setPositions([]));
  }, [unitId]);

  React.useEffect(() => {
    const node = tableScrollRef.current;
    if (!node) { setTableScrollMax(0); setTableScrollLeft(0); return; }
    setTableScrollMax(Math.max(0, node.scrollWidth - node.clientWidth));
    setTableScrollLeft(node.scrollLeft);
  }, [matrix]);

  const selectedUniverse = universes.find((value) => value.universe_id === universeId);
  const pageCount = Math.max(1, Math.ceil((matrix?.total ?? 0) / (matrix?.page_size ?? 50)));
  const statusSummary = matrix?.status_summary;
  if (error === 403) return <main className="p-4" data-testid="migration-status-forbidden"><h1 className="text-xl font-semibold">Сводка личных карточек</h1><p className="mt-3">Недостаточно прав для просмотра сводки.</p></main>;
  return <main className="space-y-4 p-4" data-testid="migration-status-page">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-xl font-semibold">Сводка личных карточек</h1>{selectedUniverse ? <p className="text-sm text-zinc-500" data-testid="migration-status-calculated-at">Данные рассчитаны: {new Date(selectedUniverse.calculated_at).toLocaleString("ru-RU")}</p> : null}</div><div className="flex gap-2"><Link className="rounded-lg border px-3 py-2 text-sm" href="/directory/personnel/lk">Назад к личным карточкам</Link><button type="button" className="rounded-lg border px-3 py-2 text-sm" onClick={() => setReload((value) => value + 1)} data-testid="migration-status-refresh">Обновить данные отчёта</button></div></div>
    {universes.length > 1 ? <label className="block text-sm">Набор миграции<select aria-label="Набор миграции" className="ml-2 rounded border p-2" value={universeId ?? ""} onChange={(event) => replace({ universe_id: event.target.value })} data-testid="migration-status-universe"><option value="">Выберите набор</option>{universes.map((universe) => <option key={universe.universe_id} value={universe.universe_id}>BASE {universe.base_cohort_run_id}{universe.supplemental_cohort_run_ids.length ? `; supplemental: ${universe.supplemental_cohort_run_ids.join(", ")}` : ""}</option>)}</select></label> : null}
    {universes.length === 0 && !loading ? <p data-testid="migration-status-empty">Нет доступных данных отчёта.</p> : null}
    {error && error !== 403 ? <p role="alert" data-testid="migration-status-error">Не удалось загрузить сводку. Повторите попытку.</p> : null}
    {loading ? <p role="status" data-testid="migration-status-loading">Загрузка…</p> : null}
    {universeId ? <><div className="flex flex-wrap gap-2"><select aria-label="Группа отделений" value={groupId} onChange={e=>replace({org_group_id:e.target.value,org_unit_id:undefined,position_id:undefined})} className="rounded border p-2 text-sm"><option value="">Все группы</option>{groups.map(g=><option key={g.group_id} value={g.group_id}>{g.group_name}</option>)}</select><select aria-label="Отделение" value={unitId} onChange={e=>replace({org_unit_id:e.target.value,position_id:undefined})} className="rounded border p-2 text-sm"><option value="">Все отделения</option>{units.map(u=><option key={u.id} value={u.id}>{u.name}</option>)}</select><select aria-label="Должность" value={params.get("position_id")??""} onChange={e=>replace({position_id:e.target.value})} className="rounded border p-2 text-sm" disabled={!unitId}><option value="">Все должности</option>{positions.map(p=><option key={p.position_id} value={p.position_id}>{p.name}</option>)}</select><input aria-label="Фамилия сотрудника" placeholder="Фамилия сотрудника" defaultValue={params.get("q") ?? ""} onBlur={(event) => replace({ q: event.target.value })} className="rounded border p-2 text-sm" data-testid="migration-status-search"/><select aria-label="Раздел" value={params.get("section") ?? ""} onChange={(event) => replace({ section: event.target.value })} className="rounded border p-2 text-sm"><option value="">Все разделы</option>{COLUMNS.map((column) => <option key={column.section} value={column.section}>{column.title}</option>)}</select><select aria-label="Статус" value={params.get("status") ?? ""} onChange={(event) => replace({ status: event.target.value })} className="rounded border p-2 text-sm"><option value="">Все статусы</option>{STATUS_FILTER_OPTIONS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select><select aria-label="Причина" value={params.get("reason") ?? ""} onChange={(event) => replace({ reason: event.target.value })} className="rounded border p-2 text-sm"><option value="">Все причины</option>{REASON_FILTER_OPTIONS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></div>
      {matrix?.general_summary ? <section className="rounded-lg border p-3" aria-label="Краткие показатели" data-testid="migration-status-general-summary">
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
          <span>Всего сотрудников: {matrix.general_summary.total_active_employees}</span>
          <span>Общие сведения обработаны: {matrix.general_summary.processed}</span>
          <span>Требуется проверка ФИО: {matrix.general_summary.review_required}</span>
          <span>Обновлено текущим прогоном: {matrix.general_summary.updated_current_run}</span>
          <span>Пропущено как уже заполненное: {matrix.general_summary.skipped_already_filled}</span>
        </div>
      </section> : null}
      {statusSummary ? <section aria-labelledby="migration-status-summary-heading" data-testid="migration-status-summary">
        <h2 id="migration-status-summary-heading" className="text-lg font-semibold">Сводка по статусам личных карточек</h2>
        <div className="mt-2 w-full max-w-full overflow-x-auto" data-testid="migration-status-summary-scroll">
          <table className="min-w-max border-collapse text-sm" data-testid="migration-status-summary-table">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 min-w-64 border bg-white p-2 text-left dark:bg-zinc-950">Статус</th>
                {statusSummary.sections.map((item) => (
                  <th key={item.code} className="min-w-28 border p-2 text-center font-semibold leading-snug whitespace-normal break-words">
                    {item.title}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {statusSummary.statuses.map((statusItem) => (
                <tr key={statusItem.code}>
                  <th className="sticky left-0 z-10 min-w-64 border bg-white p-2 text-left font-medium dark:bg-zinc-950">{statusItem.title}</th>
                  {statusSummary.sections.map((sectionItem) => (
                    <td key={sectionItem.code} className="border p-2 text-center tabular-nums">
                      {summaryCount(matrix, sectionItem.code, statusItem.code)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-zinc-700 font-semibold dark:border-zinc-300" data-testid="migration-status-summary-total">
                <th scope="row" className="sticky left-0 z-10 min-w-64 border bg-white p-2 text-left dark:bg-zinc-950">Итого карточек</th>
                {statusSummary.sections.map((sectionItem) => (
                  <td key={sectionItem.code} className="border p-2 text-center tabular-nums">
                    {summaryTotal(matrix, sectionItem.code)}
                  </td>
                ))}
              </tr>
            </tfoot>
          </table>
        </div>
      </section> : null}
      {matrix && !loading ? matrix.items.length === 0 ? <p data-testid="migration-status-matrix-empty">По выбранным фильтрам данных нет.</p> : <>
        <h2 className="text-lg font-semibold">Подробная сводка по сотрудникам</h2>
        <div ref={tableScrollRef} className="w-full max-w-full overflow-x-scroll overflow-y-hidden pb-3" style={{ scrollbarGutter: "stable" }} data-testid="migration-status-table-scroll" onScroll={(event) => setTableScrollLeft(event.currentTarget.scrollLeft)}>
          <table className="w-[2200px] min-w-[2200px] table-fixed border-collapse" data-testid="migration-status-matrix"><thead><tr><th className="sticky left-0 z-20 w-56 border bg-white p-2 text-left dark:bg-zinc-950" data-testid="migration-status-employee-header">Сотрудник</th>{COLUMNS.map((column) => <th key={column.section} className="w-48 border p-2 text-left">{column.title}</th>)}</tr></thead><tbody>{matrix.items.map((row) => <tr key={row.person_id}><th className="sticky left-0 z-10 w-56 border bg-white p-2 text-left font-medium dark:bg-zinc-950" data-testid="migration-status-employee-cell">{row.full_name}</th>{COLUMNS.map((column) => { const cell = row.cells[column.section]; return <td key={column.section} className="w-48 border p-2">{cell ? <Link href={buildPprMigrationCardHref(row.person_id, column.cardSection, returnTo, universeId)} aria-label={`${column.title}: ${cell.status_label}. ${cell.reason_label}`} title={`${cell.status_label}. ${cell.reason_label}`} className="block"><strong>{cell.status_label}</strong><span className="block text-sm">{cell.reason_label}</span></Link> : <span>Нет данных</span>}</td>; })}</tr>)}</tbody></table>
        </div>
        {tableScrollMax > 0 ? <input aria-label="Горизонтальная прокрутка разделов" className="mb-3 block h-3 w-full cursor-ew-resize accent-zinc-400" data-testid="migration-status-scrollbar-control" type="range" min={0} max={tableScrollMax} value={tableScrollLeft} onChange={(event) => { const next = Number(event.target.value); const node = tableScrollRef.current; if (node) node.scrollLeft = next; setTableScrollLeft(next); }} /> : null}
      </> : null}
      {matrix && !loading ? <div className="flex items-center justify-between"><span>Страница {page} из {pageCount}</span><div className="flex gap-2"><button type="button" disabled={page <= 1} onClick={() => replace({ page: page - 1 }, false)} data-testid="migration-status-prev">Назад</button><button type="button" disabled={page >= pageCount} onClick={() => replace({ page: page + 1 }, false)} data-testid="migration-status-next">Вперёд</button></div></div> : null}</> : universes.length > 1 && !loading ? <p data-testid="migration-status-choose-universe">Выберите universe для просмотра матрицы.</p> : null}
  </main>;
}
