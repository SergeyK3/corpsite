// FILE: corpsite-ui/app/directory/employees/_components/EmployeeDrawer.tsx
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { apiAuthMe } from "@/lib/api";
import { canSeeHrProcessesNav } from "@/lib/personnelNav";
import { buildEmployeeCardHref } from "@/lib/employeeCardNav";
import {
  HR_DOSSIER_LINK_TEXT,
  OPEN_HR_DOSSIER_CTA,
  WORKING_EMPLOYEE_CARD_TITLE,
  WORKING_QUICK_VIEW_MODE,
} from "@/lib/personnelCardTerminology";
import type { MeInfo } from "@/lib/types";
import type { EmployeeDetails } from "../_lib/types";
import { getEmployee, mapApiErrorToMessage } from "../_lib/api.client";
import { employeeStatusMeta } from "../_lib/employeeStatus";
import EmployeeStatusBadge from "./EmployeeStatusBadge";

type Props = {
  employeeId: string | null;
  open: boolean;
  onClose: () => void;
  refreshToken?: number;
};

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const dt = new Date(v);
  if (Number.isNaN(dt.getTime())) return String(v);
  return dt.toLocaleDateString("ru-RU");
}

const readOnlyCardClass =
  "rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4";

function resolveTelegramLabel(user: Record<string, unknown> | null | undefined): string {
  if (!user) return "Telegram не привязан";
  const username = user.telegram_username ?? user.telegramUsername;
  if (username != null && String(username).trim()) {
    const s = String(username).trim();
    return s.startsWith("@") ? s : `@${s}`;
  }
  const id = user.telegram_id ?? user.telegramId;
  if (id != null && String(id).trim()) return String(id).trim();
  return "Telegram не привязан";
}

function accountSummary(user: Record<string, unknown> | null | undefined): string {
  if (!user) return "Учётная запись Corpsite не создана";
  const login = String(user.login ?? "").trim();
  const role = String(user.role_name ?? user.roleName ?? "").trim();
  const active = user.is_active ?? user.isActive;
  const status = active === true ? "активен" : active === false ? "неактивен" : "";
  const parts = [login ? `логин ${login}` : null, role || null, status || null].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Учётная запись создана";
}

export default function EmployeeDrawer({
  employeeId,
  open,
  onClose,
  refreshToken = 0,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [details, setDetails] = useState<EmployeeDetails | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [me, setMe] = useState<MeInfo | null>(null);

  const loadDetails = useCallback(async () => {
    if (!employeeId) {
      setDetails(null);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const d = await getEmployee(employeeId);
      setDetails(d);
    } catch (e) {
      setDetails(null);
      setError(mapApiErrorToMessage(e));
    } finally {
      setLoading(false);
    }
  }, [employeeId]);

  useEffect(() => {
    if (!open) {
      setMe(null);
      return;
    }

    let cancelled = false;
    void apiAuthMe()
      .then((info) => {
        if (!cancelled) setMe(info);
      })
      .catch(() => {
        if (!cancelled) setMe(null);
      });

    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open || !employeeId) {
      setDetails(null);
      setError(null);
      return;
    }

    void loadDetails();
  }, [employeeId, open, refreshToken, loadDetails]);

  if (!open) return null;

  const showHrCardLink = canSeeHrProcessesNav(me);
  const employeeCardHref =
    employeeId && showHrCardLink ? buildEmployeeCardHref(employeeId) : null;

  const displayFio =
    (details as Record<string, unknown> | null)?.fio ??
    (details as Record<string, unknown> | null)?.full_name ??
    (details as Record<string, unknown> | null)?.fullName ??
    (loading ? "Загрузка..." : "Сотрудник");

  const tabNo = details
    ? (details as Record<string, unknown>).employee_id ??
      (details as Record<string, unknown>).id ??
      employeeId
    : "";

  const orgUnitName =
    (details as any)?.org_unit?.name ??
    (details as any)?.orgUnit?.name ??
    (details as any)?.department?.name ??
    "—";

  const positionName =
    (details as any)?.position?.name ?? (details as any)?.position_name ?? "—";

  const rate = (details as any)?.employment_rate ?? (details as any)?.rate ?? "—";
  const dateFrom = fmtDate((details as any)?.date_from ?? (details as any)?.dateFrom);
  const dateTo = fmtDate((details as any)?.date_to ?? (details as any)?.dateTo);
  const linkedUser = ((details as any)?.user ?? null) as Record<string, unknown> | null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div
        className="absolute inset-0 bg-zinc-600/35 dark:bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative ml-auto flex h-full w-full max-w-[640px] flex-col border-l border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 px-6 py-5 dark:border-zinc-800">
          <div className="min-w-0">
            <h2 className="truncate text-2xl font-semibold leading-tight text-zinc-900 dark:text-zinc-50">
              {WORKING_EMPLOYEE_CARD_TITLE}
            </h2>
            <p className="mt-1 truncate text-sm font-medium text-zinc-800 dark:text-zinc-200">
              {String(displayFio)}
            </p>
            <p className="mt-0.5 text-sm text-zinc-600 dark:text-zinc-400">
              {details ? `Таб. № ${tabNo}` : WORKING_QUICK_VIEW_MODE}
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {employeeCardHref ? (
              <Link
                href={employeeCardHref}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500"
                onClick={onClose}
              >
                {OPEN_HR_DOSSIER_CTA}
              </Link>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Закрыть
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {error ? (
            <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
              {error}
            </div>
          ) : null}

          {details ? (
            <div className="space-y-6">
              <section>
                <h3 className="mb-3 text-sm font-medium text-zinc-900 dark:text-zinc-50">
                  Основные сведения
                </h3>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className={readOnlyCardClass}>
                    <div className="text-xs text-zinc-600 dark:text-zinc-400">Статус</div>
                    <div className="mt-1">
                      <EmployeeStatusBadge item={details} />
                    </div>
                  </div>
                  <div className={readOnlyCardClass}>
                    <div className="text-xs text-zinc-600 dark:text-zinc-400">Ставка</div>
                    <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{String(rate)}</div>
                  </div>
                  <div className={readOnlyCardClass}>
                    <div className="text-xs text-zinc-600 dark:text-zinc-400">Дата приёма</div>
                    <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{dateFrom}</div>
                  </div>
                  <div className={readOnlyCardClass}>
                    <div className="text-xs text-zinc-600 dark:text-zinc-400">Дата по</div>
                    <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{dateTo}</div>
                  </div>
                </div>
              </section>

              <section>
                <h3 className="mb-3 text-sm font-medium text-zinc-900 dark:text-zinc-50">
                  Текущее назначение
                </h3>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className={readOnlyCardClass}>
                    <div className="text-xs text-zinc-600 dark:text-zinc-400">Подразделение</div>
                    <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{orgUnitName}</div>
                  </div>
                  <div className={readOnlyCardClass}>
                    <div className="text-xs text-zinc-600 dark:text-zinc-400">Должность</div>
                    <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{positionName}</div>
                  </div>
                </div>
              </section>

              <section>
                <h3 className="mb-3 text-sm font-medium text-zinc-900 dark:text-zinc-50">Доступ</h3>
                <div className={readOnlyCardClass}>
                  <div className="text-sm text-zinc-900 dark:text-zinc-50">{accountSummary(linkedUser)}</div>
                  <div className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
                    {resolveTelegramLabel(linkedUser)}
                  </div>
                </div>
              </section>

              {employeeStatusMeta(details).active && employeeCardHref ? (
                <p className="text-xs text-zinc-500">
                  Для кадровых действий, удаления сотрудника и полной истории откройте{" "}
                  <Link href={employeeCardHref} className="font-medium text-blue-700 hover:underline dark:text-blue-300">
                    {HR_DOSSIER_LINK_TEXT}
                  </Link>
                  .
                </p>
              ) : null}
            </div>
          ) : loading ? (
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Загрузка данных...</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
