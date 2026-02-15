// FILE: corpsite-ui/app/regular-tasks/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  apiAuthMe,
  clearAccessToken,
  isAuthed,
  apiGetRegularTasks,
  apiGetRegularTask,
  apiCreateRegularTask,
  apiPatchRegularTask,
  apiActivateRegularTask,
  apiDeactivateRegularTask,
} from "@/lib/api";

type MeInfo = {
  user_id?: number;
  role_id?: number;
  role_name_ru?: string;
  role_name?: string;
  full_name?: string;
  login?: string;
};

type APIErrorLike = {
  status?: number;
  message?: string;
  details?: any;
  body?: any;
};

type RegularTask = {
  regular_task_id: number;
  title: string;
  description?: string | null;
  code?: string | null;

  is_active?: boolean;

  executor_role_id?: number | null;

  schedule_type?: string | null;
  schedule_params?: any;

  create_offset_days?: number;
  due_offset_days?: number;

  created_by_user_id?: number | null;
  updated_at?: string | null;

  // из backend /regular-tasks (app/api/regular_tasks.py)
  schedule_issue?: string | null;
};

function env(name: string, fallback = ""): string {
  const v = process.env[name];
  return (v ?? fallback).toString().trim();
}

function parseIntSetCsv(raw: string): Set<number> {
  const out = new Set<number>();
  const s = String(raw ?? "").trim();
  if (!s) return out;
  for (const part of s.split(",")) {
    const n = Number(String(part).trim());
    if (Number.isFinite(n) && n > 0) out.add(n);
  }
  return out;
}

function isUnauthorized(e: any): boolean {
  return Number(e?.status ?? 0) === 401;
}

function formatUserError(e: any): string {
  const status = Number(e?.status ?? 0);
  const body =
    (e as APIErrorLike)?.details ??
    (e as APIErrorLike)?.body ??
    undefined;
  const msg = String(
    (e as APIErrorLike)?.message ??
      body?.message ??
      body?.detail ??
      body?.error ??
      "",
  ).trim();

  const base =
    status === 401
      ? "Требуется авторизация."
      : status === 403
        ? "Недостаточно прав."
        : status === 404
          ? "Объект не найден."
          : status === 409
            ? "Конфликт данных. Обновите страницу и попробуйте снова."
            : status === 422
              ? "Некорректные данные. Проверьте заполнение полей."
              : status >= 500
                ? "Ошибка сервера. Попробуйте позже."
                : "Не удалось выполнить запрос.";

  return status
    ? `(${status}) ${base}${msg ? ` ${msg}` : ""}`
    : `${base}${msg ? ` ${msg}` : ""}`;
}

function uiActiveLabel(v: boolean | undefined): string {
  if (v === true) return "Активен";
  if (v === false) return "Неактивен";
  return "—";
}

function uiScheduleTypeLabel(v: any): string {
  const s = String(v ?? "").trim().toLowerCase();
  if (!s) return "—";
  if (s === "weekly") return "еженедельно";
  if (s === "monthly") return "ежемесячно";
  if (s === "yearly") return "ежегодно";
  if (s === "daily") return "ежедневно";
  return String(v);
}

function jsonPretty(v: any): string {
  try {
    if (v === undefined || v === null) return "{}";
    if (typeof v === "string") return v.trim() ? v : "{}";
    return JSON.stringify(v, null, 2);
  } catch {
    return "{}";
  }
}

function parseJsonOrNull(text: string): any | null {
  const s = String(text ?? "").trim();
  if (!s) return {};
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

function validatePayload(p: Record<string, any>): string | null {
  const title = String(p.title ?? "").trim();
  if (!title) return "Название обязательно.";
  if (p.schedule_params === null)
    return "Параметры расписания должны быть корректным JSON.";
  return null;
}

type Toast = { kind: "success" | "error" | "info"; text: string };

export default function RegularTasksPage() {
  const router = useRouter();

  // auth/me
  const [me, setMe] = useState<MeInfo | null>(null);
  const [meLoading, setMeLoading] = useState(true);
  const [meError, setMeError] = useState<string | null>(null);

  const roleTitle = useMemo(() => {
    const t = String(me?.role_name_ru ?? me?.role_name ?? "").trim();
    return t || "Сотрудник";
  }, [me]);

  // access: templates are for support/admin only
  const SUPPORT_ROLE_IDS = useMemo(() => {
    // можно расширить без правок кода: NEXT_PUBLIC_SUPPORT_ROLE_IDS="1,58,59"
    const fromEnv = parseIntSetCsv(env("NEXT_PUBLIC_SUPPORT_ROLE_IDS", ""));
    if (fromEnv.size > 0) return fromEnv;
    // дефолт: ADMIN (role_id=1)
    return new Set<number>([1]);
  }, []);

  const canSeeTemplates = useMemo(() => {
    const rid = Number(me?.role_id ?? 0);
    return rid > 0 && SUPPORT_ROLE_IDS.has(rid);
  }, [me, SUPPORT_ROLE_IDS]);

  // list filters
  const [status, setStatus] = useState<"active" | "inactive" | "all">("active");
  const [q, setQ] = useState<string>("");

  const [applied, setApplied] = useState<{
    status: "active" | "inactive" | "all";
    q: string;
  }>({
    status: "active",
    q: "",
  });

  // list + card
  const [items, setItems] = useState<RegularTask[]>([]);
  const [total, setTotal] = useState<number | undefined>(undefined);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [card, setCard] = useState<RegularTask | null>(null);
  const [cardLoading, setCardLoading] = useState(false);
  const [cardError, setCardError] = useState<string | null>(null);

  // mode: view/create/edit
  const [mode, setMode] = useState<"view" | "create" | "edit">("view");

  // toast
  const [toast, setToast] = useState<Toast | null>(null);
  function showToast(kind: Toast["kind"], text: string) {
    setToast({ kind, text });
    window.setTimeout(() => setToast(null), 3000);
  }

  // form
  const [fTitle, setFTitle] = useState<string>("");
  const [fDescription, setFDescription] = useState<string>("");
  const [fCode, setFCode] = useState<string>("");
  const [fExecutorRoleId, setFExecutorRoleId] = useState<string>("");
  const [fScheduleType, setFScheduleType] = useState<string>("");
  const [fScheduleParams, setFScheduleParams] = useState<string>("{}");
  const [fCreateOffsetDays, setFCreateOffsetDays] = useState<string>("0");
  const [fDueOffsetDays, setFDueOffsetDays] = useState<string>("0");

  const selectedFromList = useMemo(() => {
    if (!selectedId) return null;
    return items.find((x) => x.regular_task_id === selectedId) ?? null;
  }, [items, selectedId]);

  function resetFormFromTask(t?: RegularTask | null) {
    const x = t ?? null;
    setFTitle(String(x?.title ?? ""));
    setFDescription(String(x?.description ?? ""));
    setFCode(String(x?.code ?? ""));
    setFExecutorRoleId(x?.executor_role_id != null ? String(x.executor_role_id) : "");
    setFScheduleType(String(x?.schedule_type ?? ""));
    setFScheduleParams(jsonPretty(x?.schedule_params ?? {}));
    setFCreateOffsetDays(String(x?.create_offset_days ?? 0));
    setFDueOffsetDays(String(x?.due_offset_days ?? 0));
  }

  function buildPayload(): Record<string, any> {
    const scheduleParamsParsed = parseJsonOrNull(fScheduleParams);

    const payload: Record<string, any> = {
      title: fTitle.trim(),
      description: fDescription.trim() ? fDescription.trim() : null,
      code: fCode.trim() ? fCode.trim() : null,
      executor_role_id: fExecutorRoleId.trim() ? Number(fExecutorRoleId) : null,
      schedule_type: fScheduleType.trim() ? fScheduleType.trim() : null,
      schedule_params: scheduleParamsParsed,
      create_offset_days: Number(fCreateOffsetDays || "0"),
      due_offset_days: Number(fDueOffsetDays || "0"),
    };

    if (payload.description === null) delete payload.description;
    if (payload.code === null) delete payload.code;
    if (payload.executor_role_id === null) delete payload.executor_role_id;
    if (payload.schedule_type === null) delete payload.schedule_type;

    return payload;
  }

  const draftPayload = useMemo(() => buildPayload(), [
    fTitle,
    fDescription,
    fCode,
    fExecutorRoleId,
    fScheduleType,
    fScheduleParams,
    fCreateOffsetDays,
    fDueOffsetDays,
  ]);

  const draftError = useMemo(() => validatePayload(draftPayload), [draftPayload]);

  function redirectToLogin() {
    clearAccessToken();
    router.replace("/login");
  }

  async function reloadList(opts?: { useCurrentFilters?: boolean }) {
    setListLoading(true);
    setListError(null);

    try {
      const s = opts?.useCurrentFilters === false ? applied.status : status;
      const qq = opts?.useCurrentFilters === false ? applied.q : q.trim();

      // ВАЖНО: используем единый api-клиент, без ручного fetch/token
      const data = await apiGetRegularTasks({
        status: s,
        q: qq ? qq : undefined,
        limit: 50,
        offset: 0,
      });

      setItems(data as any);
      setTotal(undefined); // текущий backend /regular-tasks отдаёт список; total нет
      setApplied({ status: s, q: qq });

      if (selectedId && !data.some((x) => x.regular_task_id === selectedId)) {
        setSelectedId(null);
        setCard(null);
        setMode("view");
      }
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      setItems([]);
      setTotal(undefined);
      setSelectedId(null);
      setCard(null);
      setMode("view");
      setListError(formatUserError(e));
    } finally {
      setListLoading(false);
    }
  }

  async function reloadCard(id: number) {
    setCardLoading(true);
    setCardError(null);

    try {
      const data = (await apiGetRegularTask({ regularTaskId: id })) as any;
      setCard(data as RegularTask);
      if (mode === "edit") resetFormFromTask(data as any);
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      setCard(null);
      setCardError(formatUserError(e));
    } finally {
      setCardLoading(false);
    }
  }

  async function onCreate() {
    setCardError(null);
    setCardLoading(true);

    try {
      const payload = buildPayload();
      const err = validatePayload(payload);
      if (err) throw new Error(err);

      const res = await apiCreateRegularTask({ payload });
      const newId = Number(res?.regular_task_id ?? res?.id ?? 0);

      showToast("success", "Шаблон создан.");
      await reloadList();

      if (newId > 0) {
        setSelectedId(newId);
        setMode("view");
        await reloadCard(newId);
      } else {
        setMode("view");
      }
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      setCardError(formatUserError(e));
      showToast("error", "Не удалось создать шаблон.");
    } finally {
      setCardLoading(false);
    }
  }

  async function onSaveEdit() {
    if (!selectedId) return;

    setCardError(null);
    setCardLoading(true);

    try {
      const payload = buildPayload();
      const err = validatePayload(payload);
      if (err) throw new Error(err);

      await apiPatchRegularTask({ regularTaskId: selectedId, payload });

      setMode("view");
      showToast("success", "Изменения сохранены.");
      await Promise.all([reloadCard(selectedId), reloadList()]);
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      setCardError(formatUserError(e));
      showToast("error", "Не удалось сохранить изменения.");
    } finally {
      setCardLoading(false);
    }
  }

  async function onToggleActive(active: boolean) {
    if (!selectedId) return;

    setCardError(null);
    setCardLoading(true);

    try {
      if (active) {
        await apiActivateRegularTask({ regularTaskId: selectedId });
      } else {
        await apiDeactivateRegularTask({ regularTaskId: selectedId });
      }

      showToast("success", active ? "Шаблон активирован." : "Шаблон деактивирован.");
      await Promise.all([reloadCard(selectedId), reloadList()]);
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      setCardError(formatUserError(e));
      showToast("error", "Не удалось выполнить действие.");
    } finally {
      setCardLoading(false);
    }
  }

  function openCreate() {
    setSelectedId(null);
    setCard(null);
    setMode("create");
    resetFormFromTask(null);
    setCardError(null);
  }

  function openEdit() {
    if (!selectedId) return;
    setMode("edit");
    resetFormFromTask(card ?? selectedFromList);
    setCardError(null);
  }

  function cancelInline() {
    setMode("view");
    setCardError(null);
    if (selectedId) resetFormFromTask(card ?? selectedFromList);
    else resetFormFromTask(null);
  }

  const filtersChanged = useMemo(() => {
    return status !== applied.status || q.trim() !== applied.q;
  }, [status, q, applied]);

  const activeFlag =
    (card?.is_active ?? selectedFromList?.is_active) === true
      ? true
      : (card?.is_active ?? selectedFromList?.is_active) === false
        ? false
        : undefined;

  const cardTitle =
    mode === "create"
      ? "Создание шаблона"
      : mode === "edit"
        ? `Редактирование • #${selectedId ?? "—"}`
        : card?.title ?? selectedFromList?.title ?? (selectedId ? `#${selectedId}` : "Карточка");

  // bootstrap: auth + me + initial list
  useEffect(() => {
    void (async () => {
      setMeLoading(true);
      setMeError(null);

      if (!isAuthed()) {
        router.replace("/login");
        return;
      }

      try {
        const data = (await apiAuthMe()) as any;
        setMe(data as MeInfo);
      } catch (e: any) {
        if (isUnauthorized(e)) {
          redirectToLogin();
          return;
        }
        setMeError(formatUserError(e));
        setMe(null);
      } finally {
        setMeLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (meLoading) return;
    if (!me || !canSeeTemplates) return;
    void reloadList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meLoading, me, canSeeTemplates]);

  useEffect(() => {
    if (!selectedId) {
      setCard(null);
      setCardError(null);
      if (mode !== "create") setMode("view");
      return;
    }
    void reloadCard(selectedId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  function logout() {
    clearAccessToken();
    router.replace("/login");
  }

  const toastBorder =
    toast?.kind === "success"
      ? "border-emerald-900/50"
      : toast?.kind === "error"
        ? "border-red-900/50"
        : "border-zinc-800";

  const toastText =
    toast?.kind === "success"
      ? "text-emerald-200"
      : toast?.kind === "error"
        ? "text-red-200"
        : "text-zinc-200";

  function scheduleIssueBadge(t: RegularTask) {
    const issue = String(t.schedule_issue ?? "").trim();
    if (!issue) return null;

    const label =
      issue === "UNSUPPORTED_YEARLY"
        ? "yearly не поддержан"
        : issue === "MONTHLY_MISSING_BYMONTHDAY"
          ? "monthly без bymonthday"
          : issue;

    return (
      <span className="ml-2 inline-flex items-center rounded-md border border-red-900/60 bg-red-950/40 px-2 py-0.5 text-[11px] text-red-200">
        {label}
      </span>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      {/* TITLE */}
      <div className="mb-6">
        <div className="text-2xl font-semibold text-zinc-100">{roleTitle}</div>
        <div className="mt-1 text-sm text-zinc-400">Регулярные задачи</div>
      </div>

      {/* TOP BAR */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-zinc-400">
          {meLoading ? "Загрузка профиля…" : meError ? "Ошибка профиля" : null}
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/"
            className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60"
            title="Перейти в кабинет"
          >
            Кабинет
          </Link>

          <button
            onClick={logout}
            className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60"
            title="Сбросить токен и перейти на страницу входа"
          >
            Выйти
          </button>
        </div>
      </div>

      {meError ? (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {meError}
        </div>
      ) : null}

      {!meLoading && me && !canSeeTemplates ? (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-200">
          Доступ к разделу регулярных задач (шаблонов) ограничен. Этот раздел предназначен для службы поддержки/администраторов.
        </div>
      ) : null}

      {toast ? (
        <div className={`mb-4 rounded-lg border ${toastBorder} bg-zinc-950/40 p-3 text-sm ${toastText}`}>
          {toast.text}
        </div>
      ) : null}

      {/* MAIN */}
      {!meLoading && me && canSeeTemplates ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* LIST */}
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-zinc-100">Список</div>

              <button
                onClick={() => void reloadList()}
                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                disabled={listLoading}
              >
                {listLoading ? "Обновление…" : "Обновить"}
              </button>
            </div>

            {/* Filters */}
            <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as any)}
                className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
              >
                <option value="active">Активные</option>
                <option value="inactive">Неактивные</option>
                <option value="all">Все</option>
              </select>

              <div className="sm:col-span-2">
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void reloadList();
                  }}
                  className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                  placeholder="Поиск"
                />
                <div className="mt-1 text-[11px] text-zinc-500">
                  Enter — применить. {total != null ? `Всего: ${total}.` : ""}
                </div>
              </div>
            </div>

            <div className="mb-3 flex gap-2">
              <button
                onClick={openCreate}
                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60"
                title="Создать новый шаблон"
              >
                + Создать
              </button>

              <button
                onClick={() => void reloadList()}
                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                disabled={listLoading || !filtersChanged}
                title={!filtersChanged ? "Фильтры не менялись" : "Применить фильтры"}
              >
                Применить фильтры
              </button>
            </div>

            {listError ? (
              <div className="mb-3 text-sm text-red-300">Ошибка списка: {listError}</div>
            ) : null}
            {listLoading ? <div className="text-sm text-zinc-400">Загрузка…</div> : null}

            {!listLoading && !listError && items.length === 0 ? (
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3 text-sm text-zinc-400">
                Ничего не найдено.
              </div>
            ) : null}

            <div className="space-y-2">
              {items.map((t) => {
                const id = t.regular_task_id;
                const active = selectedId === id;
                const isActive = uiActiveLabel(t.is_active === true ? true : t.is_active === false ? false : undefined);

                return (
                  <button
                    key={id}
                    onClick={() => {
                      setSelectedId(id);
                      setMode("view");
                      setCardError(null);
                    }}
                    className={[
                      "w-full rounded-lg border px-3 py-2 text-left",
                      active ? "border-zinc-600 bg-zinc-900" : "border-zinc-800 bg-zinc-950/40 hover:bg-zinc-900/60",
                    ].join(" ")}
                    title="Открыть карточку"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="font-medium text-zinc-100">
                        {t.title || `Шаблон #${id}`}
                        {scheduleIssueBadge(t)}
                      </div>
                      <div className="text-xs text-zinc-400">{isActive}</div>
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">
                      #{id}
                      {t.code ? ` • код: ${t.code}` : ""}
                      {t.executor_role_id != null ? ` • роль: ${t.executor_role_id}` : ""}
                      {t.schedule_type ? ` • ${uiScheduleTypeLabel(t.schedule_type)}` : ""}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* CARD */}
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-zinc-100">Карточка</div>

              <button
                onClick={() => (selectedId ? void reloadCard(selectedId) : null)}
                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                disabled={!selectedId || cardLoading}
                title={!selectedId ? "Сначала выберите шаблон" : "Обновить"}
              >
                {cardLoading ? "Обновление…" : "Обновить"}
              </button>
            </div>

            {cardError ? <div className="mb-3 text-sm text-red-300">Ошибка: {cardError}</div> : null}
            {cardLoading ? <div className="mb-3 text-sm text-zinc-400">Загрузка…</div> : null}

            <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
              <div className="text-lg font-semibold text-zinc-100">{cardTitle}</div>

              {mode === "view" && selectedId ? (
                <>
                  <div className="mt-1 text-sm text-zinc-400">
                    Статус: <span className="text-zinc-200">{uiActiveLabel(activeFlag)}</span> • #{selectedId}
                  </div>

                  <div className="mt-2 text-xs text-zinc-400">
                    Код: <span className="text-zinc-200">{card?.code ?? selectedFromList?.code ?? "—"}</span> • Тип расписания:{" "}
                    <span className="text-zinc-200">
                      {uiScheduleTypeLabel(card?.schedule_type ?? selectedFromList?.schedule_type)}
                    </span>{" "}
                    • Роль: <span className="text-zinc-200">{card?.executor_role_id ?? selectedFromList?.executor_role_id ?? "—"}</span>
                  </div>
                </>
              ) : mode === "create" ? (
                <div className="mt-1 text-sm text-zinc-400">Заполните поля и нажмите «Создать».</div>
              ) : mode === "edit" ? (
                <div className="mt-1 text-sm text-zinc-400">Редактирование параметров шаблона #{selectedId}.</div>
              ) : (
                <div className="mt-2 text-sm text-zinc-400">Выберите шаблон слева или нажмите «Создать».</div>
              )}
            </div>

            {/* Actions (view only) */}
            {mode === "view" ? (
              <div className="mt-3 rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                <div className="mb-2 text-sm font-semibold text-zinc-100">Действия</div>

                {!selectedId ? (
                  <div className="text-sm text-zinc-400">Сначала выберите шаблон.</div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={openEdit}
                      disabled={!selectedId || cardLoading}
                      className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                    >
                      Редактировать
                    </button>

                    <button
                      onClick={() => void onToggleActive(true)}
                      disabled={!selectedId || cardLoading}
                      className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                    >
                      Активировать
                    </button>

                    <button
                      onClick={() => void onToggleActive(false)}
                      disabled={!selectedId || cardLoading}
                      className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                    >
                      Деактивировать
                    </button>
                  </div>
                )}
              </div>
            ) : null}

            {/* Inline form (create/edit) */}
            {mode === "create" || mode === "edit" ? (
              <div className="mt-3 rounded-2xl border border-zinc-800 bg-zinc-950/30 p-4">
                <div className="grid grid-cols-1 gap-3">
                  <div>
                    <label className="block text-xs text-zinc-400">Название *</label>
                    <input
                      value={fTitle}
                      onChange={(e) => setFTitle(e.target.value)}
                      className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                      placeholder="Например: Еженедельный отчёт отдела"
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-zinc-400">Описание</label>
                    <textarea
                      value={fDescription}
                      onChange={(e) => setFDescription(e.target.value)}
                      className="mt-1 w-full min-h-[84px] resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                      placeholder="Описание (опционально)"
                    />
                  </div>

                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <div>
                      <label className="block text-xs text-zinc-400">Код</label>
                      <input
                        value={fCode}
                        onChange={(e) => setFCode(e.target.value)}
                        className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                        placeholder="Уникальный код (опционально)"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-zinc-400">ID роли исполнителя</label>
                      <input
                        value={fExecutorRoleId}
                        onChange={(e) => setFExecutorRoleId(e.target.value)}
                        className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                        inputMode="numeric"
                        placeholder="Напр: 285"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <div>
                      <label className="block text-xs text-zinc-400">Тип расписания</label>
                      <input
                        value={fScheduleType}
                        onChange={(e) => setFScheduleType(e.target.value)}
                        className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                        placeholder='Напр: "weekly" / "monthly"'
                      />
                      <div className="mt-1 text-[11px] text-zinc-500">Например: weekly, monthly, yearly.</div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs text-zinc-400">Создание (смещение, дней)</label>
                        <input
                          value={fCreateOffsetDays}
                          onChange={(e) => setFCreateOffsetDays(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                          inputMode="numeric"
                          placeholder="0"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-400">Срок сдачи (смещение, дней)</label>
                        <input
                          value={fDueOffsetDays}
                          onChange={(e) => setFDueOffsetDays(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                          inputMode="numeric"
                          placeholder="0"
                        />
                      </div>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs text-zinc-400">Параметры расписания (JSON)</label>
                    <textarea
                      value={fScheduleParams}
                      onChange={(e) => setFScheduleParams(e.target.value)}
                      className="mt-1 w-full min-h-[140px] resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 font-mono text-xs text-zinc-100 outline-none"
                      placeholder='Напр: {"weekday":1} или {"bymonthday":[27]}'
                    />
                    {draftError ? (
                      <div className="mt-2 text-xs text-red-300">Ошибка: {draftError}</div>
                    ) : (
                      <div className="mt-2 text-xs text-zinc-500">Можно сохранять.</div>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => void (mode === "create" ? onCreate() : onSaveEdit())}
                      disabled={cardLoading || !!draftError}
                      className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                      title={draftError ? "Исправьте ошибки" : mode === "create" ? "Создать" : "Сохранить"}
                    >
                      {cardLoading ? "Выполняется…" : mode === "create" ? "Создать" : "Сохранить"}
                    </button>

                    <button
                      onClick={cancelInline}
                      disabled={cardLoading}
                      className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                    >
                      Отмена
                    </button>
                  </div>
                </div>
              </div>
            ) : null}

            {/* JSON (kept: useful for support) */}
            <details className="mt-3 rounded-xl border border-zinc-800 bg-zinc-950/20 p-3">
              <summary className="cursor-pointer text-sm text-zinc-300">Детали (JSON)</summary>
              <pre className="mt-2 overflow-auto text-xs text-zinc-200">
                {JSON.stringify(card ?? selectedFromList, null, 2)}
              </pre>
            </details>
          </div>
        </div>
      ) : null}
    </div>
  );
}
