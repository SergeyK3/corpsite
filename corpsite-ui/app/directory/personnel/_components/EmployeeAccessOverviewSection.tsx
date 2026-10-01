"use client";

import * as React from "react";

import {
  getEmployeeAccessState,
  getEmployeeTerminationPreview,
  resetEmployeePassword,
  type EmployeeAccessState,
  type EmployeePasswordReset,
  type EmployeeTerminationPreview,
} from "../_lib/employeeAccessApi.client";

type Props = { employeeId: string };

function yesNo(value: boolean): string {
  return value ? "Да" : "Нет";
}

function valueOrUnavailable(value: number | null | undefined): string {
  return value == null ? "Недоступно" : String(value);
}

function terminationLabel(value: boolean | null): string {
  if (value == null) return "Недоступно";
  return value ? "Есть применённое утверждённое TERMINATION" : "Не найдено";
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-zinc-100 py-2 text-sm last:border-b-0 dark:border-zinc-800">
      <span className="text-zinc-500 dark:text-zinc-400">{label}</span>
      <span className="text-right font-medium text-zinc-900 dark:text-zinc-100">{value}</span>
    </div>
  );
}

export default function EmployeeAccessOverviewSection({ employeeId }: Props) {
  const [state, setState] = React.useState<EmployeeAccessState | null>(null);
  const [preview, setPreview] = React.useState<EmployeeTerminationPreview | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [resetResult, setResetResult] = React.useState<EmployeePasswordReset | null>(null);
  const [resetting, setResetting] = React.useState(false);
  const [copyHint, setCopyHint] = React.useState<string | null>(null);

  React.useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setState(null);
    setPreview(null);
    void Promise.allSettled([
      getEmployeeAccessState(employeeId, { signal: controller.signal }),
      getEmployeeTerminationPreview(employeeId, { signal: controller.signal }),
    ]).then((results) => {
      if (controller.signal.aborted) return;
      const [stateResult, previewResult] = results;
      if (stateResult.status === "fulfilled") setState(stateResult.value);
      if (previewResult.status === "fulfilled") setPreview(previewResult.value);
      if (stateResult.status === "rejected" && previewResult.status === "rejected") {
        setError("Не удалось получить состояние доступа сотрудника.");
      }
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [employeeId]);

  if (loading) return <p className="text-sm text-zinc-500" data-testid="employee-access-loading">Загрузка состояния доступа…</p>;
  if (error) return <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200" data-testid="employee-access-error">{error}</p>;

  const counts = preview?.counts;
  const directGrants = counts?.active_direct_grants_by_target_type;
  async function issueTemporaryPassword() {
    if (!window.confirm("Выдать новый временный пароль? Предыдущий пароль перестанет работать.")) return;
    setResetting(true);
    setCopyHint(null);
    try {
      const result = await resetEmployeePassword(employeeId);
      setResetResult(result);
      setState((current) => current ? {
        ...current,
        must_change_password: true,
        token_version: result.token_version,
        lock_active: result.brute_force_lock_cleared ? false : current.lock_active,
        lock_reason: result.brute_force_lock_cleared ? null : current.lock_reason,
        locked_until: result.brute_force_lock_cleared ? null : current.locked_until,
        automatic_lock_active: result.brute_force_lock_cleared ? false : current.automatic_lock_active,
      } : current);
    } catch {
      setError("Не удалось выдать временный пароль.");
    } finally {
      setResetting(false);
    }
  }
  async function copyTemporaryPassword() {
    if (!resetResult) return;
    try {
      await navigator.clipboard.writeText(resetResult.temporary_password);
      setCopyHint("Пароль скопирован.");
    } catch {
      setCopyHint("Не удалось скопировать пароль. Скопируйте его вручную.");
    }
  }
  return (
    <div className="space-y-4" data-testid="employee-access-overview">
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Учётная запись</h3>
          <div className="mt-2">
            <Fact label="Связь с User" value={state ? (state.has_linked_user ? "Связана" : "Нет") : preview?.linkage_state ?? "Недоступно"} />
            <Fact label="Аккаунт активен" value={state ? yesNo(state.is_active) : "Недоступно"} />
            <Fact label="Требуется смена пароля" value={state ? yesNo(state.must_change_password) : "Недоступно"} />
            <Fact label="Блокировка" value={state ? yesNo(state.lock_active) : "Недоступно"} />
            <Fact label="Причина блокировки" value={state?.lock_reason || "—"} />
            <Fact label="Блокировка до" value={state?.locked_until || "—"} />
            <Fact label="Автоматическая блокировка" value={state ? yesNo(state.automatic_lock_active) : "Недоступно"} />
            <Fact label="token_version" value={state?.token_version ?? "Недоступно"} />
          </div>
          {state?.has_linked_user ? (
            <div className="mt-4">
              <button type="button" className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900" onClick={() => void issueTemporaryPassword()} disabled={resetting} data-testid="issue-temporary-password">
                {resetting ? "Выдача…" : "Выдать временный пароль"}
              </button>
            </div>
          ) : null}
        </section>
        <section className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Предварительный просмотр прекращения доступа</h3>
          <div className="mt-2">
            <Fact label="Активное кадровое назначение" value={preview ? yesNo(preview.has_active_assignment) : "Недоступно"} />
            <Fact label="TERMINATION" value={preview ? terminationLabel(preview.has_applied_approved_termination_event) : "Недоступно"} />
            <Fact label="Незавершённые персональные задачи" value={valueOrUnavailable(counts?.unfinished_personal_tasks)} />
            <Fact label="Активные персональные согласования" value={valueOrUnavailable(counts?.active_personal_approvals)} />
            <Fact label="Назначения входящих документов" value={valueOrUnavailable(counts?.active_incoming_document_assignments)} />
            <Fact label="Ожидающие notifications/deliveries" value={valueOrUnavailable(counts?.pending_notifications_deliveries)} />
          </div>
        </section>
      </div>
      <section className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Действующие прямые grants</h3>
        <div className="mt-2 grid gap-x-6 sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(directGrants ?? { USER: null, EMPLOYEE: null, PERSON: null, ASSIGNMENT: null }).map(([type, count]) => (
            <Fact key={type} label={type} value={valueOrUnavailable(count)} />
          ))}
        </div>
      </section>
      {resetResult ? (
        <section className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100" data-testid="temporary-password-result">
          <h3 className="font-semibold">Временный пароль</h3>
          <p className="mt-1 font-mono text-base" data-testid="temporary-password-value">{resetResult.temporary_password}</p>
          <button type="button" className="mt-3 rounded-md border border-amber-700 px-3 py-1.5 font-medium hover:bg-amber-100 dark:border-amber-400 dark:hover:bg-amber-900/40" onClick={() => void copyTemporaryPassword()} data-testid="copy-temporary-password">Копировать</button>
          {copyHint ? <p className="mt-2" data-testid="temporary-password-copy-hint">{copyHint}</p> : null}
          <p className="mt-3">Передайте пароль сотруднику безопасным каналом. При входе потребуется сменить пароль.</p>
        </section>
      ) : null}
      {preview?.warnings.length ? (
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100" data-testid="employee-access-warnings">
          <h3 className="font-semibold">Предупреждения</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5">{preview.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
        </section>
      ) : null}
    </div>
  );
}
