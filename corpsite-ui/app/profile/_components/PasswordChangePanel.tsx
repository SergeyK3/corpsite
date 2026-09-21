"use client";

import * as React from "react";

import { apiAuthPasswordChange } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";

type Props = {
  onSuccess: () => void;
};

function PasswordVisibilityButton({
  visible,
  onToggle,
  fieldLabel,
  disabled,
}: {
  visible: boolean;
  onToggle: () => void;
  fieldLabel: string;
  disabled: boolean;
}) {
  const action = visible ? "Скрыть" : "Показать";
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      aria-label={`${action} ${fieldLabel}`}
      title={`${action} ${fieldLabel}`}
      className="absolute inset-y-0 right-0 flex items-center px-3 text-zinc-600 hover:text-zinc-900 disabled:opacity-60 dark:text-zinc-400 dark:hover:text-zinc-100"
    >
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2">
        {visible ? (
          <>
            <path d="M3 3l18 18" />
            <path d="M10.6 10.7a2 2 0 0 0 2.7 2.7" />
            <path d="M9.9 4.2A10.7 10.7 0 0 1 12 4c5.3 0 8.8 5.1 9.6 7.5a12 12 0 0 1-3.1 4.3" />
            <path d="M6.2 6.2A12.1 12.1 0 0 0 2.4 11.5C3.2 13.9 6.7 19 12 19c1 0 1.9-.2 2.8-.5" />
          </>
        ) : (
          <>
            <path d="M2.4 12S5.8 5 12 5s9.6 7 9.6 7-3.4 7-9.6 7S2.4 12 2.4 12Z" />
            <circle cx="12" cy="12" r="3" />
          </>
        )}
      </svg>
      <span className="sr-only">{action}</span>
    </button>
  );
}

export default function PasswordChangePanel({ onSuccess }: Props) {
  const [currentPassword, setCurrentPassword] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [confirmation, setConfirmation] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [currentVisible, setCurrentVisible] = React.useState(false);
  const [newVisible, setNewVisible] = React.useState(false);
  const [confirmationVisible, setConfirmationVisible] = React.useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (newPassword !== confirmation) {
      setError("Подтверждение нового пароля не совпадает.");
      return;
    }
    setBusy(true);
    try {
      await apiAuthPasswordChange({
        current_password: currentPassword,
        new_password: newPassword,
        new_password_confirmation: confirmation,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmation("");
      onSuccess();
    } catch (cause) {
      setError(formatThrownError(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-5">
      <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">Изменить пароль</h2>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        После изменения потребуется выполнить вход повторно.
      </p>
      <form className="mt-4 space-y-3" onSubmit={submit}>
        <label className="block text-sm text-zinc-700 dark:text-zinc-300">
          Текущий пароль
          <span className="relative mt-1 block">
            <input
              required
              autoComplete="current-password"
              type={currentVisible ? "text" : "password"}
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 pr-11 dark:border-zinc-700 dark:bg-zinc-900"
              disabled={busy}
            />
            <PasswordVisibilityButton
              visible={currentVisible}
              onToggle={() => setCurrentVisible((visible) => !visible)}
              fieldLabel="текущий пароль"
              disabled={busy}
            />
          </span>
        </label>
        <label className="block text-sm text-zinc-700 dark:text-zinc-300">
          Новый пароль
          <span className="relative mt-1 block">
            <input
              required
              minLength={8}
              maxLength={200}
              autoComplete="new-password"
              type={newVisible ? "text" : "password"}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 pr-11 dark:border-zinc-700 dark:bg-zinc-900"
              disabled={busy}
            />
            <PasswordVisibilityButton
              visible={newVisible}
              onToggle={() => setNewVisible((visible) => !visible)}
              fieldLabel="новый пароль"
              disabled={busy}
            />
          </span>
        </label>
        <label className="block text-sm text-zinc-700 dark:text-zinc-300">
          Подтверждение нового пароля
          <span className="relative mt-1 block">
            <input
              required
              minLength={8}
              maxLength={200}
              autoComplete="new-password"
              type={confirmationVisible ? "text" : "password"}
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 pr-11 dark:border-zinc-700 dark:bg-zinc-900"
              disabled={busy}
            />
            <PasswordVisibilityButton
              visible={confirmationVisible}
              onToggle={() => setConfirmationVisible((visible) => !visible)}
              fieldLabel="подтверждение нового пароля"
              disabled={busy}
            />
          </span>
        </label>
        {error ? <p role="alert" className="text-sm text-red-700 dark:text-red-300">{error}</p> : null}
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {busy ? "Сохраняем…" : "Изменить пароль"}
        </button>
      </form>
    </section>
  );
}
