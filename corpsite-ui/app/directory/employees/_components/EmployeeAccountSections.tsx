"use client";

import * as React from "react";

import {
  createUser,
  getEmployee,
  mapApiErrorToMessage,
  updateUserRole,
} from "../_lib/api.client";
import { suggestPlatformUserLogin } from "@/lib/platformUserLoginSuggestion";
import {
  employeeOrgUnitId,
  resolveEmployeeOrgScopePrefill,
  type EmployeeOrgScopePrefill,
} from "@/lib/userCreateOrgScope";
import type { EmployeeDetails } from "../_lib/types";
import EmployeeEventsTimeline from "./EmployeeEventsTimeline";
import UserCreateDrawer from "./UserCreateDrawer";
import UserRoleEditDrawer from "./UserRoleEditDrawer";
import type { UserCreateFormValues } from "./UserCreateForm";

const readOnlyCardClass =
  "rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950";

function userStatusLabel(active: boolean | null | undefined): string {
  if (active === true) return "Активен";
  if (active === false) return "Неактивен";
  return "—";
}

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

function isTelegramBound(user: Record<string, unknown> | null | undefined): boolean {
  if (!user) return false;
  const username = user.telegram_username ?? user.telegramUsername;
  if (username != null && String(username).trim()) return true;
  const id = user.telegram_id ?? user.telegramId;
  return id != null && String(id).trim().length > 0;
}

function resolveTelegramId(user: Record<string, unknown> | null | undefined): string {
  if (!user) return "—";
  const id = user.telegram_id ?? user.telegramId;
  if (id != null && String(id).trim()) return String(id).trim();
  return "—";
}

function resolveLastLoginLabel(user: Record<string, unknown> | null | undefined): string | null {
  if (!user) return null;
  const raw = user.last_login_at ?? user.lastLoginAt ?? user.last_login ?? user.lastLogin;
  if (raw == null || !String(raw).trim()) return null;
  const parsed = new Date(String(raw));
  if (Number.isNaN(parsed.getTime())) return String(raw).trim();
  return parsed.toLocaleString("ru-RU");
}

function getEmployeeName(details: EmployeeDetails | null): string {
  if (!details) return "—";
  return String((details as any)?.fio ?? (details as any)?.full_name ?? (details as any)?.fullName ?? "—");
}

function getEmployeeNumericId(details: EmployeeDetails | null): number {
  const v = (details as any)?.employee_id ?? (details as any)?.employeeId ?? (details as any)?.id;
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

function buildDefaultUserCreateValues(loginSeed = ""): UserCreateFormValues {
  return {
    login: loginSeed,
    password: "",
    role_id: "",
    org_unit_id: "",
    is_active: true,
  };
}

type Props = {
  employeeId: string;
  refreshToken?: number;
  showEvents?: boolean;
  showTelegram?: boolean;
  initialUserCreateOpen?: boolean;
  /** Hide create-user CTA (e.g. read-only /directory/staff) but allow role edit. */
  readOnly?: boolean;
  /** Embedded in employee import card «Доступ» section — compact sub-layout. */
  embedded?: boolean;
};

export default function EmployeeAccountSections({
  employeeId,
  refreshToken = 0,
  showEvents = true,
  showTelegram = true,
  initialUserCreateOpen = false,
  readOnly = false,
  embedded = false,
}: Props) {
  const [loading, setLoading] = React.useState(true);
  const [details, setDetails] = React.useState<EmployeeDetails | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [eventsRefreshToken, setEventsRefreshToken] = React.useState(0);

  const [userCreateDrawerOpen, setUserCreateDrawerOpen] = React.useState(false);
  const [userCreateSaving, setUserCreateSaving] = React.useState(false);
  const [userCreateError, setUserCreateError] = React.useState<string | null>(null);
  const [userCreateInitialValues, setUserCreateInitialValues] = React.useState<UserCreateFormValues>(
    buildDefaultUserCreateValues(),
  );
  const [userCreateOrgScope, setUserCreateOrgScope] = React.useState<EmployeeOrgScopePrefill>({
    org_group_id: null,
    org_unit_id: null,
  });
  const [roleEditDrawerOpen, setRoleEditDrawerOpen] = React.useState(false);
  const [roleEditSaving, setRoleEditSaving] = React.useState(false);
  const [roleEditError, setRoleEditError] = React.useState<string | null>(null);

  const loadDetails = React.useCallback(async () => {
    if (!employeeId) {
      setDetails(null);
      setError(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await getEmployee(employeeId);
      setDetails(data);
    } catch (e) {
      setDetails(null);
      setError(mapApiErrorToMessage(e));
    } finally {
      setLoading(false);
    }
  }, [employeeId]);

  React.useEffect(() => {
    void loadDetails();
  }, [loadDetails, refreshToken]);

  const linkedUser = (details as any)?.user ?? null;
  const autoOpenAttemptedRef = React.useRef(false);

  React.useEffect(() => {
    autoOpenAttemptedRef.current = false;
  }, [employeeId, refreshToken]);

  function handleOpenUserCreateDrawer() {
    if (!details) return;
    const fio = getEmployeeName(details);
    const unitId = employeeOrgUnitId(details as Record<string, unknown>);
    setUserCreateError(null);
    setUserCreateInitialValues(buildDefaultUserCreateValues(suggestPlatformUserLogin(fio)));
    setUserCreateOrgScope({ org_group_id: null, org_unit_id: unitId });
    setUserCreateDrawerOpen(true);

    void (async () => {
      try {
        const scope = await resolveEmployeeOrgScopePrefill(unitId);
        setUserCreateOrgScope(scope);
      } catch {
        setUserCreateOrgScope({ org_group_id: null, org_unit_id: unitId });
      }
    })();
  }

  React.useEffect(() => {
    if (readOnly || !initialUserCreateOpen || autoOpenAttemptedRef.current || loading || !details || linkedUser) {
      return;
    }
    autoOpenAttemptedRef.current = true;
    handleOpenUserCreateDrawer();
    // handleOpenUserCreateDrawer is stable enough for one-shot auto-open after load
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialUserCreateOpen, loading, details, linkedUser]);

  function handleCloseUserCreateDrawer() {
    if (userCreateSaving) return;
    setUserCreateDrawerOpen(false);
    setUserCreateError(null);
  }

  async function handleCreateUser(values: UserCreateFormValues) {
    const employeeNumericId = getEmployeeNumericId(details);
    if (!employeeNumericId) {
      setUserCreateError("Не удалось определить сотрудника.");
      return;
    }

    setUserCreateSaving(true);
    setUserCreateError(null);
    try {
      const unitId = Number(values.org_unit_id);
      await createUser({
        employee_id: employeeNumericId,
        role_id: Number(values.role_id),
        login: values.login.trim(),
        password: values.password,
        unit_id: Number.isFinite(unitId) && unitId > 0 ? unitId : employeeOrgUnitId(details as Record<string, unknown>) ?? undefined,
        is_active: values.is_active,
      });
      setUserCreateDrawerOpen(false);
      await loadDetails();
      setEventsRefreshToken((t) => t + 1);
    } catch (e) {
      setUserCreateError(mapApiErrorToMessage(e));
    } finally {
      setUserCreateSaving(false);
    }
  }

  function handleOpenRoleEditDrawer() {
    if (!linkedUser || readOnly) return;
    setRoleEditError(null);
    setRoleEditDrawerOpen(true);
  }

  function handleCloseRoleEditDrawer() {
    if (roleEditSaving) return;
    setRoleEditDrawerOpen(false);
    setRoleEditError(null);
  }

  async function handleUpdateUserRole(nextRoleId: number) {
    const linked = linkedUser as Record<string, unknown> | null;
    const userId = Number(linked?.user_id ?? linked?.userId ?? 0);
    if (!Number.isFinite(userId) || userId < 1) {
      setRoleEditError("Не удалось определить пользователя.");
      return;
    }

    setRoleEditSaving(true);
    setRoleEditError(null);
    try {
      await updateUserRole(userId, nextRoleId);
      setRoleEditDrawerOpen(false);
      await loadDetails();
      setEventsRefreshToken((t) => t + 1);
    } catch (e) {
      setRoleEditError(mapApiErrorToMessage(e));
    } finally {
      setRoleEditSaving(false);
    }
  }

  const telegramLabel = resolveTelegramLabel(linkedUser as Record<string, unknown> | null);
  const telegramBound = isTelegramBound(linkedUser as Record<string, unknown> | null);
  const telegramId = resolveTelegramId(linkedUser as Record<string, unknown> | null);
  const lastLoginLabel = resolveLastLoginLabel(linkedUser as Record<string, unknown> | null);

  const embeddedCardClass =
    "rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950";
  const subsectionCardClass = embedded ? embeddedCardClass : readOnlyCardClass;

  const linkedUserId =
    linkedUser != null
      ? Number((linkedUser as Record<string, unknown>).user_id ?? (linkedUser as Record<string, unknown>).userId ?? 0)
      : 0;
  const linkedRoleId =
    linkedUser != null && (linkedUser as Record<string, unknown>).role_id != null
      ? Number((linkedUser as Record<string, unknown>).role_id)
      : null;
  const linkedRoleLabel = String(
    (linkedUser as Record<string, unknown> | null)?.role_name ??
      (linkedUser as Record<string, unknown> | null)?.role_id ??
      "—",
  );
  const linkedLogin = String((linkedUser as Record<string, unknown> | null)?.login ?? "—");

  const userCreateDrawer =
    userCreateDrawerOpen && details ? (
      <UserCreateDrawer
        key={`user-create-${employeeId}`}
        open={userCreateDrawerOpen}
        fullName={getEmployeeName(details)}
        initialOrgGroupId={userCreateOrgScope.org_group_id}
        initialOrgUnitId={userCreateOrgScope.org_unit_id}
        initialValues={userCreateInitialValues}
        saving={userCreateSaving}
        error={userCreateError}
        onClose={handleCloseUserCreateDrawer}
        onSubmit={handleCreateUser}
      />
    ) : null;

  const userRoleEditDrawer =
    roleEditDrawerOpen && linkedUser && Number.isFinite(linkedUserId) && linkedUserId > 0 ? (
      <UserRoleEditDrawer
        key={`user-role-edit-${linkedUserId}`}
        open={roleEditDrawerOpen}
        login={linkedLogin}
        currentRoleId={linkedRoleId}
        currentRoleLabel={linkedRoleLabel}
        saving={roleEditSaving}
        error={roleEditError}
        onClose={handleCloseRoleEditDrawer}
        onSubmit={handleUpdateUserRole}
      />
    ) : null;

  if (loading && !details) {
    return (
      <>
        <div className="py-6 text-sm text-zinc-500">Загрузка данных сотрудника…</div>
        {userCreateDrawer}
        {userRoleEditDrawer}
      </>
    );
  }

  if (error && !details) {
    return (
      <>
        <div className="py-6 text-sm text-red-600">{error}</div>
        {userCreateDrawer}
        {userRoleEditDrawer}
      </>
    );
  }

  if (!details) {
    return (
      <>
        <div className="py-6 text-sm text-zinc-500">Данные сотрудника недоступны.</div>
        {userCreateDrawer}
        {userRoleEditDrawer}
      </>
    );
  }

  const subsectionTitleClass = embedded
    ? "mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500"
    : "mb-3 text-sm font-medium text-zinc-900 dark:text-zinc-50";

  return (
    <>
      <div className={embedded ? "grid gap-4 lg:grid-cols-2" : "space-y-6"}>
        <section className={embedded ? "min-w-0" : undefined}>
          <h3 className={subsectionTitleClass}>Учётная запись Corpsite</h3>
          <div className={subsectionCardClass}>
            {linkedUser ? (
              <div className="space-y-1 text-sm text-zinc-900 dark:text-zinc-50">
                <div className="font-medium text-green-800 dark:text-green-300">
                  ✓ Учётная запись Corpsite существует
                </div>
                <div>
                  <span className="text-zinc-600 dark:text-zinc-400">Логин: </span>
                  {linkedUser.login ?? "—"}
                </div>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <span className="text-zinc-600 dark:text-zinc-400">Роль Corpsite: </span>
                    {linkedRoleLabel}
                  </div>
                  {!readOnly ? (
                    <button
                      type="button"
                      onClick={handleOpenRoleEditDrawer}
                      className="mt-2 shrink-0 self-start rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm text-zinc-800 transition hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800 sm:mt-0"
                    >
                      Изменить роль Corpsite
                    </button>
                  ) : null}
                </div>
                <div>
                  <span className="text-zinc-600 dark:text-zinc-400">Статус: </span>
                  {userStatusLabel(linkedUser.is_active)}
                </div>
                {lastLoginLabel ? (
                  <div>
                    <span className="text-zinc-600 dark:text-zinc-400">Последний вход: </span>
                    {lastLoginLabel}
                  </div>
                ) : null}
              </div>
            ) : readOnly ? (
              <div className="space-y-1 text-sm text-zinc-900 dark:text-zinc-50">
                <div className="text-sm font-medium text-amber-900 dark:text-amber-200">
                  □ Учётная запись Corpsite ещё не создана
                </div>
                <div className="text-sm text-zinc-700 dark:text-zinc-300">
                  Создание доступа доступно из HR-процессов (не из read-only просмотра персонала).
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-1">
                  <div className="text-sm font-medium text-amber-900 dark:text-amber-200">
                    □ Учётная запись Corpsite ещё не создана
                  </div>
                  <div className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
                    Доступ к Corpsite не создан
                  </div>
                  <div className="text-sm text-zinc-700 dark:text-zinc-300">
                    Создайте доступ, если сотрудник должен входить в систему или получать задачи.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleOpenUserCreateDrawer}
                  className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500"
                >
                  Создать доступ к Corpsite
                </button>
              </div>
            )}
          </div>
        </section>

        {showTelegram ? (
          <section className={embedded ? "min-w-0" : undefined}>
            <h3 className={subsectionTitleClass}>Telegram</h3>
            <div className={subsectionCardClass}>
              <div className="space-y-1 text-sm text-zinc-900 dark:text-zinc-50">
                <div>
                  <span className="text-zinc-600 dark:text-zinc-400">Статус привязки: </span>
                  {telegramBound ? "Привязан" : "Не привязан"}
                </div>
                {telegramBound ? (
                  <>
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">Telegram ID: </span>
                      {telegramId}
                    </div>
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">Username: </span>
                      {telegramLabel}
                    </div>
                  </>
                ) : null}
              </div>
              {embedded ? (
                <p className="mt-2 text-xs text-zinc-500">
                  Привязка и управление — в{" "}
                  <a href="/profile" className="font-medium text-blue-700 hover:underline dark:text-blue-300">
                    профиле пользователя
                  </a>
                  .
                </p>
              ) : null}
            </div>
          </section>
        ) : null}

        {showEvents && employeeId && !embedded ? (
          <EmployeeEventsTimeline employeeId={employeeId} refreshToken={eventsRefreshToken} />
        ) : null}
      </div>

      {userCreateDrawer}
      {userRoleEditDrawer}
    </>
  );
}
