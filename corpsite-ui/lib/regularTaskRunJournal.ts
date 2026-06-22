// FILE: corpsite-ui/lib/regularTaskRunJournal.ts

import {
  catchUpPresetLabel,
  runKindLabel,
  runStatusLabel,
  runTitleLabel,
  scheduleTypeLabel,
  uiFieldLabel,
} from "./i18n";
import { buildTaskPageHref } from "./taskNav";

export type RunMode = "dry" | "live";

export type RunStats = {
  templates_total?: number;
  templates_due?: number;
  created?: number;
  deduped?: number;
  errors?: number;
  item_count?: number;
  journal_warning?: string | null;
  occurrence_date?: string | null;
  run_kind?: string | null;
  catch_up?: CatchUpMeta | null;
  dry_run?: boolean;
  run_mode?: string | null;
};

export const JOURNAL_ORPHAN_WARNING =
  "Внимание: статистика запуска содержит результаты, но элементы журнала отсутствуют. Возможна неполная запись журнала.";

export type CatchUpMeta = {
  preset?: string | null;
  run_for_date?: string | null;
  schedule_type?: string | null;
  org_group_id?: number | null;
  org_unit_id?: number | null;
  executor_role_id?: number | null;
  templates_in_scope?: number | null;
};

export type RegularTaskRunRow = {
  run_id: number;
  started_at: string;
  finished_at?: string | null;
  status: string;
  stats?: RunStats | null;
  errors?: unknown;
  item_count?: number;
  journal_warning?: string | null;
};

export type RunItemMeta = {
  occurrence_date?: string | null;
  today_effective?: string | null;
  run_kind?: string | null;
  catch_up?: CatchUpMeta | null;
  schedule_type?: string | null;
  title_suffix?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  template_title?: string | null;
  title_final?: string | null;
  task_title?: string | null;
  due_date?: string | null;
  executor_role_name?: string | null;
  executor_user_name?: string | null;
  dedupe_mode?: string | null;
  assignment_scope?: string | null;
  deduped?: boolean;
  task_id?: number | null;
  reason?: string | null;
  dry_run?: boolean;
  origin_metadata_text?: string | null;
};

export type RegularTaskRunItemRow = {
  item_id: number;
  run_id: number;
  regular_task_id: number;
  status: string;
  started_at: string;
  finished_at?: string | null;
  period_id?: number | null;
  executor_role_id?: number | null;
  executor_role_name?: string | null;
  executor_role_code?: string | null;
  is_due: boolean;
  created_tasks: number;
  error?: string | null;
  meta?: RunItemMeta | null;
};

export type ParsedOriginMetadata = {
  source?: string;
  run_id?: string;
  occurrence_date?: string;
  run_kind?: string;
  period?: string;
};

export type RunSummary = {
  run_id: number;
  run_kind: string;
  run_kind_label: string;
  run_mode: RunMode | null;
  run_mode_label: string | null;
  occurrence_date: string | null;
  occurrence_date_label: string;
  period_label: string;
  schedule_type: string | null;
  schedule_type_label: string;
  templates_total: number;
  templates_due: number;
  created: number;
  deduped: number;
  errors: number;
  item_count: number;
  journal_warning: string | null;
  org_group_id: number | null;
  org_unit_id: number | null;
  org_scope_label: string;
  started_at_label: string;
  finished_at_label: string;
  status: string;
  status_label: string;
};

export type RunListEntry = {
  run_id: number;
  title: string;
  status: string;
  status_label: string;
  run_kind: string;
  run_kind_label: string;
  run_mode: RunMode | null;
  run_mode_label: string | null;
  started_at_label: string;
  occurrence_date_label: string;
  created: number;
  deduped: number;
  errors: number;
  counts_label: string;
};

export type ItemOutcome = "created" | "dedup" | "error" | "skip" | "other";

export type RunTaskListRow = {
  item_id: number;
  task_id: number | null;
  task_href: string | null;
  task_title: string;
  executor_label: string;
  deadline_label: string;
  outcome_label: string;
  outcome: ItemOutcome;
};

export type RunTaskListState =
  | { kind: "select_run" }
  | { kind: "loading" }
  | { kind: "load_error"; message: string }
  | { kind: "unavailable" }
  | { kind: "expected_not_loaded" }
  | { kind: "none_expected" }
  | { kind: "rows"; rows: RunTaskListRow[] };

export const RUN_TASK_LIST_EXPECTED_NOT_LOADED_MESSAGE =
  "Элементы журнала ожидаются, но не загружены. Обновите страницу или проверьте API.";

export function formatRunTaskListLoadError(itemsError: string): string {
  const message = String(itemsError ?? "").trim();
  return message
    ? `Не удалось загрузить элементы журнала: ${message}`
    : "Не удалось загрузить элементы журнала.";
}

const ORIGIN_LINE_RE =
  /^(Источник|ID запуска|Дата возникновения задачи|Тип запуска|Период):\s*(.+)$/u;

export function fmtDateTime(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("ru-RU");
}

export function fmtDate(value?: string | null): string {
  if (!value) return "—";
  const iso = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
    const [y, m, d] = iso.split("-").map(Number);
    const dt = new Date(y, m - 1, d);
    if (!Number.isNaN(dt.getTime())) {
      return dt.toLocaleDateString("ru-RU");
    }
  }
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleDateString("ru-RU");
}

export function parseOriginMetadataText(text?: string | null): ParsedOriginMetadata {
  const out: ParsedOriginMetadata = {};
  const raw = String(text ?? "").trim();
  if (!raw) return out;

  for (const line of raw.split("\n")) {
    const trimmed = line.trim().replace(/^---+$/, "");
    if (!trimmed) continue;
    const match = ORIGIN_LINE_RE.exec(trimmed);
    if (!match) continue;
    const [, key, value] = match;
    const v = String(value ?? "").trim();
    if (!v || v === "...") continue;
    switch (key) {
      case "Источник":
        out.source = v;
        break;
      case "ID запуска":
        out.run_id = v;
        break;
      case "Дата возникновения задачи":
        out.occurrence_date = v;
        break;
      case "Тип запуска":
        out.run_kind = v;
        break;
      case "Период":
        out.period = v;
        break;
      default:
        break;
    }
  }
  return out;
}

export function resolveOccurrenceDate(
  stats?: RunStats | null,
  items?: readonly RegularTaskRunItemRow[],
): string | null {
  const fromStats = String(stats?.occurrence_date ?? stats?.catch_up?.run_for_date ?? "").trim();
  if (fromStats) return fromStats;

  for (const item of items ?? []) {
    const meta = item.meta;
    if (!meta) continue;
    const direct = String(meta.occurrence_date ?? meta.today_effective ?? "").trim();
    if (direct) return direct;
    const parsed = parseOriginMetadataText(meta.origin_metadata_text);
    if (parsed.occurrence_date) return parsed.occurrence_date;
  }
  return null;
}

export function resolveRunKind(stats?: RunStats | null, items?: readonly RegularTaskRunItemRow[]): string {
  const fromStats = String(stats?.run_kind ?? "").trim().toLowerCase();
  if (fromStats) return fromStats;
  if (stats?.catch_up) return "catch_up";

  for (const item of items ?? []) {
    const kind = String(item.meta?.run_kind ?? "").trim().toLowerCase();
    if (kind) return kind;
    if (item.meta?.catch_up) return "catch_up";
  }
  return "automatic";
}

export function resolveScheduleType(
  stats?: RunStats | null,
  items?: readonly RegularTaskRunItemRow[],
): string | null {
  const fromCatchUp = String(stats?.catch_up?.schedule_type ?? "").trim();
  if (fromCatchUp) return fromCatchUp;

  for (const item of items ?? []) {
    const st = String(item.meta?.schedule_type ?? "").trim();
    if (st) return st;
  }
  return null;
}

export function resolvePeriodLabel(
  stats?: RunStats | null,
  items?: readonly RegularTaskRunItemRow[],
): string {
  const preset = String(stats?.catch_up?.preset ?? "").trim();
  if (preset) {
    const label = catchUpPresetLabel(preset);
    if (label && label !== preset) return label;
  }

  for (const item of items ?? []) {
    const parsed = parseOriginMetadataText(item.meta?.origin_metadata_text);
    if (parsed.period) return parsed.period;
  }

  for (const item of items ?? []) {
    const suffix = String(item.meta?.title_suffix ?? "").trim();
    if (suffix) return suffix;
    const start = String(item.meta?.period_start ?? "").trim();
    const end = String(item.meta?.period_end ?? "").trim();
    if (start && end) return `${fmtDate(start)} – ${fmtDate(end)}`;
  }

  return "—";
}

export function resolveRunMode(
  stats?: RunStats | null,
  items?: readonly RegularTaskRunItemRow[],
): RunMode | null {
  if (stats?.dry_run === true) return "dry";
  if (stats?.dry_run === false) return "live";

  const runMode = String(stats?.run_mode ?? "").trim().toLowerCase();
  if (runMode === "dry" || runMode === "dry_run" || runMode === "trial") return "dry";
  if (runMode === "live" || runMode === "production" || runMode === "execute") return "live";

  if (!items?.length) return null;

  const dryRunItems = items.filter(
    (item) => item.meta?.reason === "dry_run" || item.meta?.dry_run === true,
  );
  const liveOutcomeItems = items.filter(
    (item) => item.created_tasks > 0 || item.meta?.deduped === true,
  );

  if (dryRunItems.length > 0 && liveOutcomeItems.length === 0) return "dry";
  if (liveOutcomeItems.length > 0) return "live";
  if (dryRunItems.length > 0) return "dry";
  return null;
}

export function runModeLabel(mode: RunMode | null): string | null {
  if (mode === "dry") return "Пробный прогон";
  if (mode === "live") return "Боевой прогон";
  return null;
}

export function resolveOrgScopeLabel(stats?: RunStats | null): string {
  const catchUp = stats?.catch_up;
  if (!catchUp) return "—";

  const parts: string[] = [];
  if (catchUp.org_unit_id != null) {
    parts.push(`${uiFieldLabel("owner_unit")} #${catchUp.org_unit_id}`);
  }
  if (catchUp.org_group_id != null) {
    parts.push(`${uiFieldLabel("org_group")} #${catchUp.org_group_id}`);
  }
  return parts.length ? parts.join(" · ") : "—";
}

export function buildRunListEntry(
  run: RegularTaskRunRow,
  items: readonly RegularTaskRunItemRow[] = [],
): RunListEntry {
  const stats = run.stats ?? {};
  const runKind = resolveRunKind(stats);
  const occurrenceDate = resolveOccurrenceDate(stats);
  const created = Number(stats.created ?? 0);
  const deduped = Number(stats.deduped ?? 0);
  const errors = Number(stats.errors ?? 0);
  const runMode = resolveRunMode(stats, items);

  return {
    run_id: run.run_id,
    title: runTitleLabel(run.run_id),
    status: run.status,
    status_label: runStatusLabel(run.status),
    run_kind: runKind,
    run_kind_label: runKindLabel(runKind),
    run_mode: runMode,
    run_mode_label: runModeLabel(runMode),
    started_at_label: fmtDateTime(run.started_at),
    occurrence_date_label: fmtDate(occurrenceDate),
    created,
    deduped,
    errors,
    counts_label: `Создано: ${created} · Дедуп: ${deduped} · Ошибки: ${errors}`,
  };
}

export function resolveJournalWarning(
  run: RegularTaskRunRow,
  items: readonly RegularTaskRunItemRow[] = [],
): string | null {
  const fromApi = String(run.journal_warning ?? run.stats?.journal_warning ?? "").trim();
  if (fromApi) return fromApi;

  const stats = run.stats ?? {};
  const itemCount = run.item_count ?? stats.item_count ?? items.length;
  const created = Number(stats.created ?? 0);
  const deduped = Number(stats.deduped ?? 0);
  const templatesDue = Number(stats.templates_due ?? 0);
  if (
    Number(itemCount) === 0 &&
    (templatesDue > 0 || created + deduped > 0)
  ) {
    return JOURNAL_ORPHAN_WARNING;
  }
  return null;
}

export function buildRunSummary(
  run: RegularTaskRunRow,
  items: readonly RegularTaskRunItemRow[] = [],
): RunSummary {
  const stats = run.stats ?? {};
  const runKind = resolveRunKind(stats, items);
  const occurrenceDate = resolveOccurrenceDate(stats, items);
  const itemCount = Number(run.item_count ?? stats.item_count ?? items.length);
  const runMode = resolveRunMode(stats, items);

  return {
    run_id: run.run_id,
    run_kind: runKind,
    run_kind_label: runKindLabel(runKind),
    run_mode: runMode,
    run_mode_label: runModeLabel(runMode),
    occurrence_date: occurrenceDate,
    occurrence_date_label: fmtDate(occurrenceDate),
    period_label: resolvePeriodLabel(stats, items),
    schedule_type: resolveScheduleType(stats, items),
    schedule_type_label: scheduleTypeLabel(resolveScheduleType(stats, items)),
    templates_total: Number(stats.templates_total ?? 0),
    templates_due: Number(stats.templates_due ?? 0),
    created: Number(stats.created ?? 0),
    deduped: Number(stats.deduped ?? 0),
    errors: Number(stats.errors ?? 0),
    item_count: itemCount,
    journal_warning: resolveJournalWarning(run, items),
    org_group_id: stats.catch_up?.org_group_id ?? null,
    org_unit_id: stats.catch_up?.org_unit_id ?? null,
    org_scope_label: resolveOrgScopeLabel(stats),
    started_at_label: fmtDateTime(run.started_at),
    finished_at_label: fmtDateTime(run.finished_at),
    status: run.status,
    status_label: runStatusLabel(run.status),
  };
}

export function resolveItemOutcome(item: RegularTaskRunItemRow): ItemOutcome {
  const err = String(item.error ?? "").trim();
  const status = String(item.status ?? "").trim().toLowerCase();
  if (err || status === "error") return "error";
  if (status === "skip" || item.meta?.reason === "dry_run") return "skip";
  if (item.meta?.deduped === true) return "dedup";
  if (item.created_tasks > 0) return "created";
  return "other";
}

export function itemOutcomeLabel(item: RegularTaskRunItemRow): string {
  switch (resolveItemOutcome(item)) {
    case "created":
      return "Создано";
    case "dedup":
      return "Дедуп";
    case "error":
      return "Ошибка";
    case "skip":
      return "Пропущено";
    default:
      return runStatusLabel(item.status);
  }
}

export function itemOutcomeTone(item: RegularTaskRunItemRow): string {
  switch (resolveItemOutcome(item)) {
    case "created":
      return "text-emerald-800 dark:text-emerald-200";
    case "dedup":
      return "text-amber-800 dark:text-amber-200";
    case "error":
      return "text-red-700 dark:text-red-300";
    case "skip":
      return "text-zinc-600 dark:text-zinc-400";
    default:
      return "text-zinc-800 dark:text-zinc-200";
  }
}

export function resolveItemOccurrenceDate(item: RegularTaskRunItemRow): string | null {
  const meta = item.meta;
  if (!meta) return null;

  const direct = String(meta.occurrence_date ?? meta.today_effective ?? "").trim();
  if (direct) return direct;

  const parsed = parseOriginMetadataText(meta.origin_metadata_text);
  return parsed.occurrence_date ?? null;
}

export function roleLabel(value: {
  executor_role_id?: number | null;
  executor_role_name?: string | null;
  executor_role_code?: string | null;
}): string {
  const name = String(value.executor_role_name ?? "").trim();
  if (name) return name;

  const code = String(value.executor_role_code ?? "").trim();
  if (code) return code;

  if (value.executor_role_id != null) return `#${value.executor_role_id}`;
  return "—";
}

export function periodLabel(item: RegularTaskRunItemRow): string {
  const meta = item.meta;
  if (meta?.title_suffix) return String(meta.title_suffix);
  if (item.period_id != null) return `#${item.period_id}`;
  return "—";
}

export function itemTitleLabel(item: RegularTaskRunItemRow): string {
  const title = String(
    item.meta?.task_title ?? item.meta?.title_final ?? item.meta?.template_title ?? "",
  ).trim();
  if (title) return title;
  return `Шаблон №${item.regular_task_id}`;
}

export function resolveRunTaskDeadlineLabel(item: RegularTaskRunItemRow): string {
  const raw = String(item.meta?.due_date ?? "").trim();
  if (!raw) return "—";
  return fmtDate(raw);
}

export function resolveRunTaskExecutorLabel(item: RegularTaskRunItemRow): string {
  const role = roleLabel(item);
  const userName = String(item.meta?.executor_user_name ?? "").trim();
  if (role !== "—" && userName) {
    return `${role} (${userName})`;
  }
  if (role !== "—") return role;
  const metaRole = String(item.meta?.executor_role_name ?? "").trim();
  if (metaRole) return metaRole;
  return "—";
}

export function runTaskOutcomeLabel(item: RegularTaskRunItemRow): string {
  switch (resolveItemOutcome(item)) {
    case "created":
      return "создана";
    case "dedup":
      return "уже существовала";
    case "error":
      return "ошибка";
    case "skip":
      return "пропуск (dry-run)";
    default:
      return itemOutcomeLabel(item).toLowerCase();
  }
}

export function resolveRunTaskId(item: RegularTaskRunItemRow): number | null {
  const raw = item.meta?.task_id;
  const id = Math.trunc(Number(raw));
  if (!Number.isFinite(id) || id <= 0) return null;
  return id;
}

export function buildRunTaskListRows(items: readonly RegularTaskRunItemRow[]): RunTaskListRow[] {
  return [...items]
    .sort((a, b) => a.item_id - b.item_id)
    .map((item) => {
      const taskId = resolveRunTaskId(item);
      return {
        item_id: item.item_id,
        task_id: taskId,
        task_href: taskId != null ? buildTaskPageHref(taskId) : null,
        task_title: itemTitleLabel(item),
        executor_label: resolveRunTaskExecutorLabel(item),
        deadline_label: resolveRunTaskDeadlineLabel(item),
        outcome_label: runTaskOutcomeLabel(item),
        outcome: resolveItemOutcome(item),
      };
    });
}

export function resolveRunTaskListState(
  selectedRun: RegularTaskRunRow | null,
  runSummary: RunSummary | null,
  items: readonly RegularTaskRunItemRow[],
  itemsLoading: boolean,
  itemsError: string | null = null,
): RunTaskListState {
  if (!selectedRun || !runSummary) return { kind: "select_run" };
  if (itemsLoading) return { kind: "loading" };
  if (items.length > 0) {
    return { kind: "rows", rows: buildRunTaskListRows(items) };
  }

  const loadError = String(itemsError ?? "").trim();
  if (loadError) {
    return { kind: "load_error", message: formatRunTaskListLoadError(loadError) };
  }

  const itemCount = runSummary.item_count;

  if (itemCount > 0) {
    return { kind: "expected_not_loaded" };
  }

  if (itemCount === 0 && runSummary.journal_warning) {
    return { kind: "unavailable" };
  }

  if (
    runSummary.templates_due === 0 &&
    runSummary.created === 0 &&
    runSummary.deduped === 0
  ) {
    return { kind: "none_expected" };
  }

  return { kind: "none_expected" };
}

export function buildItemOriginView(item: RegularTaskRunItemRow): {
  occurrence_date: string | null;
  occurrence_date_label: string;
  run_kind_label: string;
  period_label: string;
  source_label: string;
  run_id: number | null;
  origin_run_id: string | null;
} {
  const parsed = parseOriginMetadataText(item.meta?.origin_metadata_text);
  const occurrenceDate = resolveItemOccurrenceDate(item);
  const runKind =
    String(item.meta?.run_kind ?? parsed.run_kind ?? "").trim().toLowerCase() ||
    (item.meta?.catch_up ? "catch_up" : "automatic");

  return {
    occurrence_date: occurrenceDate,
    occurrence_date_label: fmtDate(occurrenceDate),
    run_kind_label: parsed.run_kind || runKindLabel(runKind),
    period_label: parsed.period || periodLabel(item),
    source_label: parsed.source || (runKind === "catch_up" ? "Догоняющий запуск" : "Автоматический запуск"),
    run_id: item.run_id,
    origin_run_id: parsed.run_id ?? (item.run_id != null ? String(item.run_id) : null),
  };
}
