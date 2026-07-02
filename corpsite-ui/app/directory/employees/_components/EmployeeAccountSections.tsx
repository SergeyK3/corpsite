"use client";

import * as React from "react";

import {
  createUser,
  getEmployee,
  getRoles,
  mapApiErrorToMessage,
} from "../_lib/api.client";
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
    is_active: true,
  };
}

function translitLoginSeed(name: string): string {
  const map: Record<string, string> = {
    а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z", и: "i",
    й: "y", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t",
    у: "u", ф: "f", х: "h", ц: "ts", ч: "ch", ш: "sh", щ: "sch", ъ: "", ы: "y", ь: "",
    э: "e", ю: "yu", я: "ya",
  };
  const parts = String(name || "")
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return "";
  const last = parts[parts.length - 1] ?? "";
  const firstInitial = (parts[0] ?? "").slice(0, 1);
  const raw = `${last}${firstInitial}`.split("").map((ch) => map[ch] ?? ch).join("");
  return raw.replace(/[^a-z0-9._-]+/g, "").slice(0, 64);
}

function normalizeItems<T>(v: unknown): T[] {
  if (Array.isArray(v)) return v as T[];
  if (v && typeof v === "object" && Array.isArray((v as { items?: unknown[] }).items)) {
    return (v as { items: T[] }).items;
  }
  return [];
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
  const [roleOptions, setRoleOptions] = React.useState<Array<{ id: number; label: string }>>([]);

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
    setUserCreateError(null);
    setUserCreateInitialValues(buildDefaultUserCreateValues(translitLoginSeed(fio)));
    setUserCreateDrawerOpen(true);

    void (async () => {
      try {
        const rolesObj = await getRoles({ limit: 200, offset: 0 });
        const items = normalizeItems<any>(rolesObj);
        setRoleOptions(
          items
            .map((r) => ({
              id: Number(r.role_id ?? r.id),
              label: String(r.role_name ?? r.name ?? `#${r.role_id ?? r.id}`),
            }))
            .filter((r) => Number.isFinite(r.id) && r.id > 0),
        );
      } catch {
        setRoleOptions([]);
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
      await createUser({
        employee_id: employeeNumericId,
        role_id: Number(values.role_id),
        login: values.login.trim(),
        password: values.password,
        unit_id: (details as any)?.org_unit?.unit_id ?? undefined,
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
  const orgUnitLabel =
    (details as any)?.org_unit?.name ??
    (details as any)?.orgUnit?.name ??
    (details as any)?.org_unit_name ??
    "—";

  if (loading) {
    return <div className="py-6 text-sm text-zinc-500">Загрузка данных сотрудника…</div>;
  }

  if (error) {
    return <div className="py-6 text-sm text-red-600">{error}</div>;
  }

  if (!details) {
    return <div className="py-6 text-sm text-zinc-500">Данные сотрудника недоступны.</div>;
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

      <UserCreateDrawer
        open={userCreateDrawerOpen}
        fullName={getEmployeeName(details)}
        orgUnitLabel={orgUnitLabel}
        initialValues={userCreateInitialValues}
        roleOptions={roleOptions}
        saving={userCreateSaving}
        error={userCreateError}
        onClose={handleCloseUserCreateDrawer}
        onSubmit={handleCreateUser}
      />
    </>
  );
}
