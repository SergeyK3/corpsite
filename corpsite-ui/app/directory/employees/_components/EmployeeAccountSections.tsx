"use client";

import * as React from "react";

import {
  createUser,
  getEmployee,
  mapApiErrorToMessage,
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
import type { UserCreateFormValues } from "./UserCreateForm";

const readOnlyCardClass =
  "rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950";

function SectionBlock({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3 className="mb-3 text-sm font-medium text-zinc-900 dark:text-zinc-50">{title}</h3>
      {children}
    </section>
  );
}

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
};

export default function EmployeeAccountSections({
  employeeId,
  refreshToken = 0,
  showEvents = true,
  showTelegram = true,
  initialUserCreateOpen = false,
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
    if (!initialUserCreateOpen || autoOpenAttemptedRef.current || loading || !details || linkedUser) {
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

  const telegramLabel = resolveTelegramLabel(linkedUser as Record<string, unknown> | null);

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

  if (loading && !details) {
    return (
      <>
        <div className="py-6 text-sm text-zinc-500">Загрузка данных сотрудника…</div>
        {userCreateDrawer}
      </>
    );
  }

  if (error && !details) {
    return (
      <>
        <div className="py-6 text-sm text-red-600">{error}</div>
        {userCreateDrawer}
      </>
    );
  }

  if (!details) {
    return (
      <>
        <div className="py-6 text-sm text-zinc-500">Данные сотрудника недоступны.</div>
        {userCreateDrawer}
      </>
    );
  }

  return (
    <>
      <div className="space-y-6">
        <SectionBlock title="Учётная запись Corpsite">
          <div className={readOnlyCardClass}>
            {linkedUser ? (
              <div className="space-y-1 text-sm text-zinc-900 dark:text-zinc-50">
                <div className="font-medium text-green-800 dark:text-green-300">
                  ✓ Учётная запись Corpsite существует
                </div>
                <div>
                  <span className="text-zinc-600 dark:text-zinc-400">Логин: </span>
                  {linkedUser.login ?? "—"}
                </div>
                <div>
                  <span className="text-zinc-600 dark:text-zinc-400">Роль доступа: </span>
                  {linkedUser.role_name ?? linkedUser.role_id ?? "—"}
                </div>
                <div>
                  <span className="text-zinc-600 dark:text-zinc-400">Статус доступа: </span>
                  {userStatusLabel(linkedUser.is_active)}
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
        </SectionBlock>

        {showTelegram ? (
          <SectionBlock title="Telegram">
            <div className={readOnlyCardClass}>
              <div className="text-sm text-zinc-900 dark:text-zinc-50">{telegramLabel}</div>
            </div>
          </SectionBlock>
        ) : null}

        {showEvents && employeeId ? (
          <EmployeeEventsTimeline employeeId={employeeId} refreshToken={eventsRefreshToken} />
        ) : null}
      </div>

      {userCreateDrawer}
    </>
  );
}
