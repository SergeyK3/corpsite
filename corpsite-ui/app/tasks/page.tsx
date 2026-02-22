// FILE: corpsite-ui/app/tasks/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { apiAuthMe, apiFetchJson, apiGetTask, apiPostTaskAction } from "@/lib/api";
import { isAuthed, logout } from "@/lib/auth";
import type { AllowedAction, TaskAction, TaskListItem } from "@/lib/types";

const ACTION_RU: Record<string, string> = {
  report: "Отправить отчёт",
  approve: "Согласовать",
  reject: "Отклонить",
  archive: "В архив",
};

type ScopeMode = "all" | "admin" | "functional";

function actionsRu(actions: AllowedAction[] | undefined | null): string {
  if (!actions || actions.length === 0) return "—";
  return actions.map((a) => ACTION_RU[String(a)] ?? String(a)).join(" / ");
}

function taskIdOf(t: any): number {
  return Number(t?.task_id ?? t?.id ?? 0);
}

function taskTitleOf(t: any): string {
  const id = taskIdOf(t);
  const title = String(t?.title ?? "").trim();
  return title || (id > 0 ? `Задача №${id}` : "Задача");
}

function statusTextOf(t: any): string {
  const sRu = String(t?.status_name_ru ?? "").trim();
  const sCode = String(t?.status_code ?? "").trim();
  const sLegacy = String(t?.status ?? "").trim();
  if (sRu) return sRu;
  if (sCode) return sCode;
  if (sLegacy) return sLegacy;
  const sid = t?.status_id;
  if (sid != null) return `status_id=${sid}`;
  return "—";
}

function allowedActionsOf(t: any): AllowedAction[] {
  const a = t?.allowed_actions;
  if (Array.isArray(a)) return a.filter(Boolean) as AllowedAction[];
  return [];
}

function normalizeMsg(msg: string): string {
  const s = String(msg || "").trim();
  return s || "Ошибка запроса";
}

function isUnauthorized(e: any): boolean {
  return Number(e?.status ?? 0) === 401;
}

function formatDeadline(t: any): string {
  const raw =
    t?.due_at ??
    t?.due_date ??
    t?.deadline ??
    t?.deadline_at ??
    t?.deadline_date ??
    t?.due ??
    null;

  if (!raw) return "—";
  const s = String(raw).trim();
  if (!s) return "—";

  if (/^\d{2}\.\d{2}\.\d{4}/.test(s)) return s;

  const d = new Date(s);
  if (!Number.isFinite(d.getTime())) return s;
  try {
    return d.toLocaleDateString("ru-RU");
  } catch {
    return s;
  }
}

function scopeRu(v: ScopeMode): string {
  if (v === "admin") return "Админ";
  if (v === "functional") return "Функционал";
  return "Все";
}

function normalizeList<T>(body: any): T[] {
  if (Array.isArray(body)) return body as T[];
  if (body?.items && Array.isArray(body.items)) return body.items as T[];
  return [];
}

function fmtDtRu(raw: any): string {
  if (!raw) return "";
  const s = String(raw).trim();
  if (!s) return "";
  const d = new Date(s);
  if (!Number.isFinite(d.getTime())) return s;
  try {
    return d.toLocaleString("ru-RU");
  } catch {
    return s;
  }
}

function roleLabelOfReport(src: any, kind: "submitted" | "approved"): string {
  const nameKey = kind === "submitted" ? "report_submitted_by_role_name" : "report_approved_by_role_name";
  const codeKey = kind === "submitted" ? "report_submitted_by_role_code" : "report_approved_by_role_code";
  const idKey = kind === "submitted" ? "report_submitted_by" : "report_approved_by";

  const name = String(src?.[nameKey] ?? "").trim();
  if (name) return name;

  const code = String(src?.[codeKey] ?? "").trim();
  if (code) return code;

  const id = src?.[idKey];
  if (id != null && String(id).trim()) return `ID ${String(id)}`;

  return "—";
}

// --- report_link helpers (http(s) vs UNC/local path) ---
function isHttpUrl(s: string): boolean {
  const v = (s || "").trim();
  return /^https?:\/\//i.test(v);
}

function isUncPath(s: string): boolean {
  const v = (s || "").trim();
  return /^\\\\[^\\]+\\.+/i.test(v);
}

function isWindowsDrivePath(s: string): boolean {
  const v = (s || "").trim();
  return /^[a-zA-Z]:\\/.test(v);
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // ignore
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "-9999px";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

type ReportUiState = "none" | "draft" | "sent_waiting" | "approved" | "rejected_or_archived";

function computeReportUiState(src: any): ReportUiState {
  const statusCode = String(src?.status_code ?? "").trim().toUpperCase();
  const link = String(src?.report_link ?? "").trim();
  const submittedAt = src?.report_submitted_at ?? null;
  const approvedAt = src?.report_approved_at ?? null;

  if (statusCode === "ARCHIVED") return "rejected_or_archived";

  if (approvedAt) return "approved";

  // "sent" = есть submitted_at или хотя бы link (на ранних данных link может быть, submitted_at нет)
  const sent = Boolean(submittedAt) || Boolean(link);

  if (sent) {
    // если по статусу ждём согласование — явно показываем
    if (statusCode === "WAITING_APPROVAL") return "sent_waiting";
    // если статус не WAITING_APPROVAL, но отчёт уже отправлен — всё равно показываем как "отправлен"
    return "sent_waiting";
  }

  // отчёта нет, но можно отправлять — это "черновик" (ввод)
  return "draft";
}

function reportStatusBadgeText(st: ReportUiState): string {
  if (st === "approved") return "Отчёт согласован";
  if (st === "sent_waiting") return "Отчёт отправлен на согласование";
  if (st === "draft") return "Отчёт не отправлен";
  if (st === "rejected_or_archived") return "Задача в архиве";
  return "—";
}

function reportStatusBadgeClass(st: ReportUiState): string {
  // без “ярких” цветов, но с лёгким различием
  if (st === "approved") return "border-zinc-700 bg-zinc-950/40 text-zinc-200";
  if (st === "sent_waiting") return "border-zinc-700 bg-zinc-950/40 text-zinc-200";
  if (st === "draft") return "border-zinc-800 bg-zinc-950/20 text-zinc-300";
  if (st === "rejected_or_archived") return "border-zinc-800 bg-zinc-950/20 text-zinc-400";
  return "border-zinc-800 bg-zinc-950/20 text-zinc-400";
}

export default function TasksPage() {
  const router = useRouter();

  const [ready, setReady] = useState(false);

  const [limit, setLimit] = useState<number>(50);
  const [offset, setOffset] = useState<number>(0);

  const [scope, setScope] = useState<ScopeMode>("all");

  const [list, setList] = useState<TaskListItem[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [item, setItem] = useState<any | null>(null);
  const [itemLoading, setItemLoading] = useState(false);
  const [itemError, setItemError] = useState<string | null>(null);

  const [reportLink, setReportLink] = useState<string>("");
  const [reason, setReason] = useState<string>("");

  const [copyHint, setCopyHint] = useState<string>("");

  // UI hint after actions (so user sees what happened even if they forget)
  const [uiNotice, setUiNotice] = useState<string>("");

  const selectedFromList = useMemo(() => {
    if (!selectedId) return null;
    return (list as any[]).find((x) => taskIdOf(x) === selectedId) ?? null;
  }, [list, selectedId]);

  const effectiveAllowed = useMemo(() => {
    const src: any = item ?? selectedFromList;
    return allowedActionsOf(src);
  }, [item, selectedFromList]);

  const effectiveStatus = useMemo(() => {
    const src: any = item ?? selectedFromList;
    return statusTextOf(src);
  }, [item, selectedFromList]);

  function can(action: AllowedAction): boolean {
    return effectiveAllowed.includes(action);
  }

  function redirectToLogin() {
    logout();
    router.replace("/login");
  }

  async function reloadList(nextOffset?: number) {
    setListLoading(true);
    setListError(null);

    try {
      const qOffset = typeof nextOffset === "number" ? nextOffset : offset;

      const body = await apiFetchJson<any>("/tasks", {
        query: {
          limit,
          offset: qOffset,
          assignment_scope: scope === "all" ? undefined : scope,
        } as any,
      });

      const data = normalizeList<TaskListItem>(body);
      setList(data);

      if (selectedId && !data.some((x: any) => taskIdOf(x) === selectedId)) {
        setSelectedId(null);
        setItem(null);
      }
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      const st = e?.status;
      const msg = normalizeMsg(e?.message || "Не удалось загрузить список задач");
      setList([]);
      setSelectedId(null);
      setItem(null);
      setListError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setListLoading(false);
    }
  }

  async function reloadItem(id: number) {
    setItemLoading(true);
    setItemError(null);

    try {
      const data = await apiGetTask({ taskId: id, includeArchived: true });
      setItem(data);
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      const st = e?.status;
      const msg = normalizeMsg(e?.message || "Не удалось загрузить задачу");
      setItem(null);
      setItemError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setItemLoading(false);
    }
  }

  async function runAction(action: TaskAction) {
    if (!selectedId) return;

    setItemError(null);
    setUiNotice("");
    setItemLoading(true);

    try {
      if (action === "reject") {
        const r = reason.trim();
        if (!r) {
          setItemError("Отклонение: обязательно заполните примечание (причину).");
          return;
        }
      }

      if (action === "report") {
        const link = reportLink.trim();
        if (!link) {
          setItemError("Отчёт: укажите ссылку/путь.");
          return;
        }

        const existingLink = String((item?.report_link ?? selectedFromList?.report_link) || "").trim();
        if (existingLink && existingLink !== link) {
          const ok = window.confirm("Отчёт уже отправлен. Вы действительно хотите заменить ссылку?");
          if (!ok) return;
        }

        await apiPostTaskAction({
          taskId: selectedId,
          action,
          payload: {
            report_link: link,
            current_comment: reason.trim() ? reason.trim() : undefined,
            ...(reason.trim() ? ({ reason: reason.trim() } as any) : null),
          } as any,
        });

        setUiNotice("Отчёт отправлен на согласование.");
        setReason("");
      } else if (action === "approve") {
        await apiPostTaskAction({
          taskId: selectedId,
          action,
          payload: reason.trim() ? ({ reason: reason.trim() } as any) : undefined,
        });
        setUiNotice("Отчёт согласован.");
        setReason("");
      } else if (action === "reject") {
        await apiPostTaskAction({
          taskId: selectedId,
          action,
          payload: reason.trim() ? ({ reason: reason.trim() } as any) : undefined,
        });
        setUiNotice("Отчёт отклонён.");
        // reason оставляем (это полезно видеть), но можно сбросить — по желанию
      } else if (action === "archive") {
        await apiPostTaskAction({
          taskId: selectedId,
          action,
          payload: reason.trim() ? ({ reason: reason.trim() } as any) : undefined,
        });
        setUiNotice("Задача перемещена в архив.");
      }

      await Promise.all([reloadItem(selectedId), reloadList()]);
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      const st = e?.status;
      const msg = normalizeMsg(e?.message || "Не удалось выполнить действие");
      setItemError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setItemLoading(false);
    }
  }

  useEffect(() => {
    void (async () => {
      if (!isAuthed()) {
        router.replace("/login");
        return;
      }

      try {
        await apiAuthMe();
      } catch (e: any) {
        if (isUnauthorized(e)) {
          redirectToLogin();
          return;
        }
        setListError(normalizeMsg(e?.message || "Ошибка авторизации"));
        return;
      }

      setReady(true);
      setOffset(0);
      await reloadList(0);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!ready) return;
    void reloadList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, limit, offset, scope]);

  useEffect(() => {
    // при смене выбранной задачи — сбрасываем локальные поля формы
    setCopyHint("");
    setUiNotice("");
    setReason("");
    if (!selectedId) {
      setItem(null);
      setItemError(null);
      setReportLink("");
      return;
    }
    void reloadItem(selectedId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  // после загрузки item: подставляем report_link в поле ввода (чтобы явно видеть, что хранится)
  useEffect(() => {
    const src: any = item ?? selectedFromList ?? null;
    const existing = String(src?.report_link || "").trim();
    if (!selectedId) return;

    // если поле пустое — заполним из БД
    if (!reportLink.trim() && existing) {
      setReportLink(existing);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item, selectedFromList, selectedId]);

  // если пришло approved_at — покажем явный сигнал эксперту (ключевой кейс: "не дошло что согласовано")
  useEffect(() => {
    const src: any = item ?? selectedFromList ?? null;
    if (!selectedId || !src) return;

    const approvedAt = src?.report_approved_at ?? null;
    const submittedAt = src?.report_submitted_at ?? null;

    if (approvedAt) {
      setUiNotice("Отчёт согласован.");
      return;
    }
    if (submittedAt) {
      // если уже отправляли — показываем “на согласовании”
      setUiNotice("Отчёт отправлен на согласование.");
      return;
    }
  }, [item, selectedFromList, selectedId]);

  const grouped = useMemo(() => {
    const m = new Map<string, any[]>();
    for (const t of list as any[]) {
      const key = statusTextOf(t) || "—";
      if (!m.has(key)) m.set(key, []);
      m.get(key)!.push(t);
    }

    for (const arr of m.values()) {
      arr.sort((a, b) => {
        const daRaw = a?.due_at ?? a?.due_date ?? a?.deadline ?? null;
        const dbRaw = b?.due_at ?? b?.due_date ?? b?.deadline ?? null;
        const da = daRaw ? new Date(String(daRaw)).getTime() : Number.POSITIVE_INFINITY;
        const db = dbRaw ? new Date(String(dbRaw)).getTime() : Number.POSITIVE_INFINITY;
        if (da !== db) return da - db;
        return taskIdOf(a) - taskIdOf(b);
      });
    }

    const keys = Array.from(m.keys());
    keys.sort((a, b) => a.localeCompare(b, "ru"));
    return { map: m, keys };
  }, [list]);

  const selectedTitle = taskTitleOf(item ?? selectedFromList);
  const selectedDeadline = selectedId ? formatDeadline(item ?? selectedFromList) : "—";

  const reportSrc: any = item ?? selectedFromList ?? {};
  const reportLinkExisting = String(reportSrc?.report_link || "").trim();
  const reportSubmittedAt = reportSrc?.report_submitted_at ?? null;
  const reportSubmittedBy = reportSrc?.report_submitted_by ?? null;
  const reportApprovedAt = reportSrc?.report_approved_at ?? null;
  const reportApprovedBy = reportSrc?.report_approved_by ?? null;
  const reportCurrentComment = String(reportSrc?.report_current_comment || "").trim();

  const submittedByLabel = roleLabelOfReport(reportSrc, "submitted");
  const approvedByLabel = roleLabelOfReport(reportSrc, "approved");

  const reportIsHttp = reportLinkExisting ? isHttpUrl(reportLinkExisting) : false;
  const reportIsUncOrLocal = reportLinkExisting ? isUncPath(reportLinkExisting) || isWindowsDrivePath(reportLinkExisting) : false;

  const reportUiState = computeReportUiState(reportSrc);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-zinc-400">
          Показано: <span className="text-zinc-200">{list.length}</span>
          {listLoading ? <span className="ml-2">• загрузка…</span> : null}
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-md border border-zinc-800 bg-zinc-950/40 p-1">
            {(["all", "admin", "functional"] as ScopeMode[]).map((v) => (
              <button
                key={v}
                onClick={() => setScope(v)}
                className={[
                  "rounded-md px-3 py-2 text-xs",
                  scope === v ? "bg-zinc-900 text-zinc-100" : "text-zinc-300 hover:bg-zinc-900/60",
                ].join(" ")}
                disabled={listLoading}
                title="Контур задач"
              >
                {scopeRu(v)}
              </button>
            ))}
          </div>

          <button
            onClick={() => void reloadList()}
            className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
            disabled={listLoading}
          >
            Обновить
          </button>

          <input
            value={String(limit)}
            onChange={(e) => setLimit(Number(e.target.value || "0"))}
            className="w-20 rounded-md border border-zinc-800 bg-zinc-950/40 px-2 py-2 text-sm text-zinc-200 outline-none"
            inputMode="numeric"
            title="limit"
          />
        </div>
      </div>

      {listError ? (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {listError}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-950/20 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-zinc-100">Список</div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setOffset((v) => Math.max(0, v - limit))}
                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                disabled={listLoading || offset <= 0}
                title="Предыдущая страница"
              >
                Назад
              </button>
              <button
                onClick={() => setOffset((v) => v + limit)}
                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                disabled={listLoading || list.length < limit}
                title="Следующая страница"
              >
                Далее
              </button>
            </div>
          </div>

          {grouped.keys.length === 0 && !listLoading ? (
            <div className="text-sm text-zinc-400">Задач нет.</div>
          ) : (
            <div className="space-y-3">
              {grouped.keys.map((k) => {
                const items = grouped.map.get(k) ?? [];
                return (
                  <details key={k} open className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-3">
                    <summary className="cursor-pointer select-none text-sm text-zinc-200">
                      {k} <span className="text-zinc-500">({items.length})</span>
                    </summary>

                    <div className="mt-3 space-y-2">
                      {items.map((t) => {
                        const id = taskIdOf(t);
                        const isSel = selectedId === id;
                        const deadline = formatDeadline(t);
                        const actions = allowedActionsOf(t);

                        return (
                          <button
                            key={id}
                            onClick={() => setSelectedId(id)}
                            className={[
                              "w-full rounded-lg border px-3 py-2 text-left",
                              isSel
                                ? "border-zinc-600 bg-zinc-900"
                                : "border-zinc-800 bg-zinc-950/40 hover:bg-zinc-900/60",
                            ].join(" ")}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="font-medium text-zinc-100">{taskTitleOf(t)}</div>
                              <div className="text-xs text-zinc-400">Дедлайн: {deadline}</div>
                            </div>

                            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500">
                              <span>№{id}</span>
                              <span>доступно: {actionsRu(actions)}</span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </details>
                );
              })}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-950/20 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-zinc-100">Карточка</div>

            <button
              onClick={() => (selectedId ? void reloadItem(selectedId) : null)}
              className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
              disabled={!selectedId || itemLoading}
            >
              Обновить
            </button>
          </div>

          {itemError ? (
            <div className="mb-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {itemError}
            </div>
          ) : null}

          {!selectedId ? (
            <div className="text-sm text-zinc-400">Выберите задачу слева.</div>
          ) : (
            <>
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-lg font-semibold text-zinc-100">{selectedTitle}</div>
                    <div className="mt-1 text-sm text-zinc-400">№{selectedId}</div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <div className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-200">
                      {effectiveStatus}
                    </div>

                    <div className={["rounded-md border px-2 py-1 text-xs", reportStatusBadgeClass(reportUiState)].join(" ")}>
                      {reportStatusBadgeText(reportUiState)}
                    </div>
                  </div>
                </div>

                <div className="mt-2 text-xs text-zinc-500">
                  Дедлайн: <span className="text-zinc-200">{selectedDeadline}</span>
                </div>

                <div className="mt-2 text-xs text-zinc-500">
                  Доступные действия: <span className="text-zinc-400">{actionsRu(effectiveAllowed)}</span>
                </div>

                {uiNotice ? (
                  <div className="mt-3 rounded-lg border border-zinc-800 bg-zinc-950/30 px-3 py-2 text-sm text-zinc-200">
                    {uiNotice}
                  </div>
                ) : null}

                <div className="mt-4 grid grid-cols-1 gap-3">
                  {reportLinkExisting ? (
                    <div className="rounded-md border border-zinc-800 bg-zinc-900/40 p-3">
                      <div className="mb-1 text-xs text-zinc-400">Отчёт</div>

                      {reportIsHttp ? (
                        <a
                          href={reportLinkExisting}
                          target="_blank"
                          rel="noreferrer"
                          className="break-all text-sm text-blue-400 underline"
                        >
                          Открыть отчёт
                        </a>
                      ) : (
                        <div className="space-y-2">
                          <div className="break-all text-sm text-zinc-200">{reportLinkExisting}</div>
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              onClick={async () => {
                                const ok = await copyToClipboard(reportLinkExisting);
                                setCopyHint(ok ? "Путь скопирован" : "Не удалось скопировать");
                                window.setTimeout(() => setCopyHint(""), 1500);
                              }}
                              className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60"
                            >
                              Скопировать путь
                            </button>
                            {reportIsUncOrLocal ? (
                              <div className="text-xs text-zinc-500">UNC/локальный путь не открывается браузером напрямую.</div>
                            ) : (
                              <div className="text-xs text-zinc-500">Ссылка не является http(s).</div>
                            )}
                            {copyHint ? <div className="text-xs text-zinc-400">• {copyHint}</div> : null}
                          </div>
                        </div>
                      )}

                      {reportSubmittedAt ? (
                        <div className="mt-2 text-xs text-zinc-400">
                          Отчёт отправлен: <span className="text-zinc-200">{fmtDtRu(reportSubmittedAt)}</span>
                        </div>
                      ) : null}

                      {reportSubmittedBy ? (
                        <div className="text-xs text-zinc-400">
                          Отправил: <span className="text-zinc-200">{submittedByLabel}</span>
                        </div>
                      ) : null}

                      {reportApprovedAt ? (
                        <div className="mt-2 text-xs text-zinc-400">
                          Решение принято: <span className="text-zinc-200">{fmtDtRu(reportApprovedAt)}</span>
                        </div>
                      ) : null}

                      {reportApprovedBy ? (
                        <div className="text-xs text-zinc-400">
                          Принял решение: <span className="text-zinc-200">{approvedByLabel}</span>
                        </div>
                      ) : null}

                      {reportCurrentComment ? (
                        <div className="mt-2 text-xs text-zinc-400">
                          Комментарий: <span className="text-zinc-200">{reportCurrentComment}</span>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {can("report") ? (
                    <div>
                      <label className="block text-xs text-zinc-400">Ссылка/путь на отчёт</label>
                      <input
                        value={reportLink}
                        onChange={(e) => setReportLink(e.target.value)}
                        className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                        placeholder="https://... или \\server\share\... или d:\..."
                      />
                    </div>
                  ) : null}

                  <div>
                    <label className="block text-xs text-zinc-400">
                      Примечание{can("reject") ? " (обязательно для “Отклонить”) " : " (опционально) "}
                    </label>
                    <textarea
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      className="mt-1 w-full min-h-[90px] resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                      placeholder="Причина / комментарий…"
                    />
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  {can("report") ? (
                    <button
                      onClick={() => void runAction("report")}
                      disabled={itemLoading}
                      className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                    >
                      {ACTION_RU.report}
                    </button>
                  ) : null}

                  {can("approve") ? (
                    <button
                      onClick={() => void runAction("approve")}
                      disabled={itemLoading}
                      className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                    >
                      {ACTION_RU.approve}
                    </button>
                  ) : null}

                  {can("reject") ? (
                    <button
                      onClick={() => void runAction("reject")}
                      disabled={itemLoading}
                      className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                    >
                      {ACTION_RU.reject}
                    </button>
                  ) : null}

                  {can("archive") ? (
                    <button
                      onClick={() => {
                        const ok = window.confirm("Переместить в архив — точно?");
                        if (ok) void runAction("archive");
                      }}
                      disabled={itemLoading}
                      className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                    >
                      {ACTION_RU.archive}
                    </button>
                  ) : null}
                </div>
              </div>

              <details className="mt-3 rounded-xl border border-zinc-800 bg-zinc-950/20 p-3">
                <summary className="cursor-pointer text-sm text-zinc-300">Детали (JSON)</summary>
                <pre className="mt-2 overflow-auto text-xs text-zinc-200">{JSON.stringify(item ?? selectedFromList, null, 2)}</pre>
              </details>
            </>
          )}
        </div>
      </div>
    </div>
  );
}