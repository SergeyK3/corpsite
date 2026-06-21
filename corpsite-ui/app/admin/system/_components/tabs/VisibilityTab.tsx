// FILE: corpsite-ui/app/admin/system/_components/tabs/VisibilityTab.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createPersonnelVisibilityAssignment,
  fetchEffectivePersonnelVisibility,
  fetchPersonnelVisibilityAssignments,
  mapAdminSystemApiError,
  revokePersonnelVisibilityAssignment,
  type EffectivePersonnelVisibility,
  type PersonnelVisibilityAssignment,
} from "../../_lib/adminSystemApi.client";
import ErrorBanner, { InfoBanner, SuccessBanner } from "../shared/ErrorBanner";
import TargetSearchField from "../shared/TargetSearchField";
import type { AccessTargetSearchItem } from "../../_lib/adminSystemApi.client";

const TARGET_TYPES = ["USER", "POSITION", "ORG_UNIT"] as const;
const SCOPE_TYPES = ["ORGANIZATION", "DEPARTMENT", "DEPARTMENT_GROUP"] as const;

function targetLabel(row: PersonnelVisibilityAssignment): string {
  if (row.target_type === "USER") return `USER #${row.target_user_id ?? "?"}`;
  if (row.target_type === "POSITION") return `POSITION #${row.target_position_id ?? "?"}`;
  if (row.target_type === "DEPARTMENT") return `DEPARTMENT #${row.target_department_id ?? "?"}`;
  return row.target_type;
}

function scopeLabel(row: PersonnelVisibilityAssignment): string {
  if (row.scope_type === "ORGANIZATION") return "Вся организация";
  if (row.scope_type === "DEPARTMENT") return `Отделение #${row.scope_department_id ?? "?"}`;
  if (row.scope_type === "DEPARTMENT_GROUP") return `Группа #${row.scope_department_group_id ?? "?"}`;
  return row.scope_type;
}

export default function VisibilityTab() {
  const [items, setItems] = useState<PersonnelVisibilityAssignment[]>([]);
  const [total, setTotal] = useState(0);
  const [showRevoked, setShowRevoked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [targetType, setTargetType] = useState<(typeof TARGET_TYPES)[number]>("USER");
  const [selectedTarget, setSelectedTarget] = useState<AccessTargetSearchItem | null>(null);
  const [scopeType, setScopeType] = useState<(typeof SCOPE_TYPES)[number]>("ORGANIZATION");
  const [scopeTarget, setScopeTarget] = useState<AccessTargetSearchItem | null>(null);
  const [scopeGroupId, setScopeGroupId] = useState("");
  const [canViewTasks, setCanViewTasks] = useState(false);

  const [effectiveUserId, setEffectiveUserId] = useState("");
  const [effective, setEffective] = useState<EffectivePersonnelVisibility | null>(null);

  const scopeTargetType = useMemo(() => {
    if (scopeType === "DEPARTMENT") return "ORG_UNIT";
    return null;
  }, [scopeType]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchPersonnelVisibilityAssignments({
        active_only: !showRevoked,
        limit: 200,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось загрузить назначения видимости"));
    } finally {
      setLoading(false);
    }
  }, [showRevoked]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleCreate(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    if (!selectedTarget) {
      setError("Выберите target");
      return;
    }
    if (scopeType === "DEPARTMENT" && !scopeTarget) {
      setError("Выберите отделение для scope");
      return;
    }
    if (scopeType === "DEPARTMENT_GROUP") {
      const gid = Number(scopeGroupId);
      if (!Number.isFinite(gid) || gid < 1) {
        setError("Укажите корректный group_id для DEPARTMENT_GROUP");
        return;
      }
    }

    setError(null);
    setSuccess(null);
    try {
      const targetTypeApi =
        targetType === "ORG_UNIT" ? "DEPARTMENT" : targetType;

      await createPersonnelVisibilityAssignment({
        target_type: targetTypeApi,
        target_user_id: targetTypeApi === "USER" ? selectedTarget.target_id : null,
        target_position_id: targetTypeApi === "POSITION" ? selectedTarget.target_id : null,
        target_department_id: targetTypeApi === "DEPARTMENT" ? selectedTarget.target_id : null,
        scope_type: scopeType,
        scope_department_id:
          scopeType === "DEPARTMENT" ? scopeTarget?.target_id ?? null : null,
        scope_department_group_id:
          scopeType === "DEPARTMENT_GROUP" ? Number(scopeGroupId) : null,
        can_view_personnel: true,
        can_view_tasks: canViewTasks,
      });
      setSuccess("Назначение создано");
      setSelectedTarget(null);
      setScopeTarget(null);
      await load();
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось создать назначение"));
    }
  }

  async function handleRevoke(assignmentId: number): Promise<void> {
    if (!window.confirm("Деактивировать назначение видимости?")) return;
    setError(null);
    setSuccess(null);
    try {
      await revokePersonnelVisibilityAssignment(assignmentId, "revoked from sysadmin UI");
      setSuccess(`Назначение #${assignmentId} деактивировано`);
      await load();
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось отозвать назначение"));
    }
  }

  async function handleEffectiveLookup(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    const uid = Number(effectiveUserId);
    if (!Number.isFinite(uid) || uid < 1) {
      setError("Укажите корректный user_id");
      return;
    }
    setError(null);
    try {
      const res = await fetchEffectivePersonnelVisibility(uid);
      setEffective(res);
    } catch (err) {
      setEffective(null);
      setError(mapAdminSystemApiError(err, "Не удалось получить effective visibility"));
    }
  }

  return (
    <div className="space-y-6">
      <InfoBanner>
        Видимость персонала (ADR-042 E1) открывает правый сайдбар и справочник без выдачи admin-функций.
        Роль отвечает за действия; visibility scope — за просмотр.
      </InfoBanner>

      {error ? <ErrorBanner message={error} /> : null}
      {success ? <SuccessBanner message={success} /> : null}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Создать назначение</h2>
        <form onSubmit={handleCreate} className="grid gap-3 md:grid-cols-2">
          <label className="block text-sm">
            Target type
            <select
              className="mt-1 w-full rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
              value={targetType}
              onChange={(e) => {
                setTargetType(e.target.value as (typeof TARGET_TYPES)[number]);
                setSelectedTarget(null);
              }}
            >
              {TARGET_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t === "ORG_UNIT" ? "DEPARTMENT (ORG_UNIT)" : t}
                </option>
              ))}
            </select>
          </label>

          <TargetSearchField
            label="Target"
            targetType={targetType}
            value={selectedTarget}
            onChange={setSelectedTarget}
          />

          <label className="block text-sm">
            Scope type
            <select
              className="mt-1 w-full rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
              value={scopeType}
              onChange={(e) => {
                setScopeType(e.target.value as (typeof SCOPE_TYPES)[number]);
                setScopeTarget(null);
              }}
            >
              {SCOPE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>

          {scopeTargetType ? (
            <TargetSearchField
              label="Scope target"
              targetType={scopeTargetType}
              value={scopeTarget}
              onChange={setScopeTarget}
            />
          ) : scopeType === "DEPARTMENT_GROUP" ? (
            <label className="block text-sm">
              deps_group.group_id
              <input
                className="mt-1 w-full rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
                value={scopeGroupId}
                onChange={(e) => setScopeGroupId(e.target.value)}
              />
            </label>
          ) : (
            <div className="text-sm text-zinc-500 dark:text-zinc-400 self-end pb-2">
              Organization scope — без дополнительного target
            </div>
          )}

          <label className="flex items-center gap-2 text-sm md:col-span-2">
            <input
              type="checkbox"
              checked={canViewTasks}
              onChange={(e) => setCanViewTasks(e.target.checked)}
            />
            Read-only просмотр задач (can_view_tasks)
          </label>

          <div className="md:col-span-2">
            <button
              type="submit"
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Создать
            </button>
          </div>
        </form>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Назначения ({total})</h2>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={showRevoked}
              onChange={(e) => setShowRevoked(e.target.checked)}
            />
            Показать отозванные
          </label>
        </div>

        {loading ? (
          <p className="text-sm text-zinc-500">Загрузка…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-zinc-500">Нет назначений</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left dark:border-zinc-700">
                  <th className="px-2 py-2">ID</th>
                  <th className="px-2 py-2">Target</th>
                  <th className="px-2 py-2">Scope</th>
                  <th className="px-2 py-2">Tasks RO</th>
                  <th className="px-2 py-2">Active</th>
                  <th className="px-2 py-2" />
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.assignment_id} className="border-b border-zinc-100 dark:border-zinc-800">
                    <td className="px-2 py-2">{row.assignment_id}</td>
                    <td className="px-2 py-2">{targetLabel(row)}</td>
                    <td className="px-2 py-2">{scopeLabel(row)}</td>
                    <td className="px-2 py-2">{row.can_view_tasks ? "да" : "нет"}</td>
                    <td className="px-2 py-2">{row.is_active ? "да" : "нет"}</td>
                    <td className="px-2 py-2">
                      {row.is_active ? (
                        <button
                          type="button"
                          className="text-red-600 hover:underline dark:text-red-400"
                          onClick={() => void handleRevoke(row.assignment_id)}
                        >
                          Отозвать
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Effective visibility</h2>
        <form onSubmit={handleEffectiveLookup} className="flex flex-wrap items-end gap-2">
          <label className="block text-sm">
            user_id
            <input
              className="mt-1 block rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
              value={effectiveUserId}
              onChange={(e) => setEffectiveUserId(e.target.value)}
            />
          </label>
          <button
            type="submit"
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600"
          >
            Проверить
          </button>
        </form>
        {effective ? (
          <pre className="overflow-x-auto rounded-lg bg-zinc-100 p-3 text-xs dark:bg-zinc-900">
            {JSON.stringify(effective, null, 2)}
          </pre>
        ) : null}
      </section>
    </div>
  );
}
