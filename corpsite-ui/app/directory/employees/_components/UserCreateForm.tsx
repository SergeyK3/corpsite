// FILE: corpsite-ui/app/directory/employees/_components/UserCreateForm.tsx
"use client";

import * as React from "react";

import { suggestPlatformUserLogin } from "@/lib/platformUserLoginSuggestion";

export type RoleOption = {
  id: number;
  label: string;
};

export type UserCreateFormValues = {
  login: string;
  password: string;
  role_id: string;
  is_active: boolean;
};

type UserCreateFormProps = {
  fullName: string;
  orgUnitLabel: string;
  initialValues: UserCreateFormValues;
  roleOptions: RoleOption[];
  saving?: boolean;
  error?: string | null;
  onSubmit: (values: UserCreateFormValues) => Promise<void> | void;
  onCancel: () => void;
};

function generatePassword(length = 12): string {
  const chars = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%";
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => chars[b % chars.length]).join("");
}

/** Full name suitable for OPS-028 login suggestion (not empty / placeholder). */
export function isValidFullNameForLogin(fullName: string): boolean {
  const trimmed = String(fullName || "").trim();
  return trimmed.length > 0 && trimmed !== "—";
}

/** Policy login from FIO; preserves currentLogin when FIO is temporarily invalid. */
export function resolvePolicyLogin(fullName: string, currentLogin = ""): string {
  if (!isValidFullNameForLogin(fullName)) {
    return currentLogin;
  }
  return suggestPlatformUserLogin(fullName);
}

function buildInitialFormValues(
  fullName: string,
  initialValues: UserCreateFormValues,
): UserCreateFormValues {
  return {
    login: isValidFullNameForLogin(fullName) ? suggestPlatformUserLogin(fullName) : "",
    password: initialValues.password,
    role_id: initialValues.role_id,
    is_active: initialValues.is_active,
  };
}

function mergeSyncedFormValues(
  fullName: string,
  initialValues: UserCreateFormValues,
  previous: UserCreateFormValues,
): UserCreateFormValues {
  return {
    login: resolvePolicyLogin(fullName, previous.login),
    password: initialValues.password,
    role_id: initialValues.role_id,
    is_active: initialValues.is_active,
  };
}

export default function UserCreateForm({
  fullName,
  orgUnitLabel,
  initialValues,
  roleOptions,
  saving = false,
  error = null,
  onSubmit,
  onCancel,
}: UserCreateFormProps) {
  const [values, setValues] = React.useState<UserCreateFormValues>(() =>
    buildInitialFormValues(fullName, initialValues),
  );
  const [showPassword, setShowPassword] = React.useState(false);

  React.useEffect(() => {
    setValues((previous) => mergeSyncedFormValues(fullName, initialValues, previous));
  }, [fullName, initialValues.password, initialValues.role_id, initialValues.is_active]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await onSubmit(values);
  }

  return (
    <form onSubmit={handleSubmit} className="flex h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="flex items-start justify-between border-b border-zinc-200 dark:border-zinc-800 px-6 py-5">
        <div>
          <h2 className="text-2xl font-semibold leading-tight text-zinc-900 dark:text-zinc-50">
            Создание пользователя
          </h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Аккаунт для сотрудника</p>
        </div>

        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
        >
          Закрыть
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
          {!!error && (
            <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-zinc-800 dark:text-zinc-200">ФИО</label>
            <input
              type="text"
              value={fullName}
              readOnly
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 px-4 py-2 text-sm text-zinc-700 dark:text-zinc-300 outline-none"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Отделение</label>
            <input
              type="text"
              value={orgUnitLabel}
              readOnly
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 px-4 py-2 text-sm text-zinc-700 dark:text-zinc-300 outline-none"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="user-login" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Логин <span className="text-red-400">*</span>
            </label>
            <input
              id="user-login"
              name="login"
              type="text"
              value={values.login}
              onChange={(e) => setValues((prev) => ({ ...prev, login: e.target.value }))}
              autoComplete="off"
              spellCheck={false}
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="user-password" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Пароль <span className="text-red-400">*</span>
            </label>
            <div className="flex gap-2">
              <input
                id="user-password"
                name="password"
                type={showPassword ? "text" : "password"}
                value={values.password}
                onChange={(e) => setValues((prev) => ({ ...prev, password: e.target.value }))}
                autoComplete="new-password"
                minLength={8}
                className="h-11 min-w-0 flex-1 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="shrink-0 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
              >
                {showPassword ? "Скрыть" : "Показать"}
              </button>
              <button
                type="button"
                onClick={() => setValues((prev) => ({ ...prev, password: generatePassword() }))}
                className="shrink-0 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
              >
                Сгенерировать
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="user-role" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Роль <span className="text-red-400">*</span>
            </label>
            <select
              id="user-role"
              name="role_id"
              value={values.role_id}
              onChange={(e) => setValues((prev) => ({ ...prev, role_id: e.target.value }))}
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
              required
            >
              <option value="" className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                Выберите роль
              </option>
              {roleOptions.map((opt) => (
                <option
                  key={opt.id}
                  value={String(opt.id)}
                  className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50"
                >
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <label className="flex items-center gap-2 text-sm text-zinc-800 dark:text-zinc-200">
            <input
              type="checkbox"
              checked={values.is_active}
              onChange={(e) => setValues((prev) => ({ ...prev, is_active: e.target.checked }))}
              className="h-4 w-4 rounded border-zinc-300 dark:border-zinc-700"
            />
            Активный пользователь
          </label>
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
          disabled={saving}
        >
          Закрыть
        </button>

        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? "Сохранение..." : "Создать"}
        </button>
      </div>
    </form>
  );
}
