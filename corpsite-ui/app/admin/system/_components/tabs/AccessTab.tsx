// FILE: corpsite-ui/app/admin/system/_components/tabs/AccessTab.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createAccessGrant,
  fetchAccessGrants,
  fetchAccessRoles,
  fetchEffectiveAccessUser,
  fetchGuardMode,
  mapAdminSystemApiError,
  revokeAccessGrant,
  formatAccessRoleLabel,
  type AccessGrant,
  type AccessRoleRef,
  type AccessTargetSearchItem,
  type EffectiveAccess,
  type GuardModeInfo,
} from "../../_lib/adminSystemApi.client";
import { ENFORCEMENT_NOTICE, GRANT_SAFETY_WARNINGS, buildEffectiveAccessSummary } from "../../_lib/adminSystemLabels";
import ErrorBanner, { InfoBanner, SuccessBanner } from "../shared/ErrorBanner";
import TargetSearchField from "../shared/TargetSearchField";

const TARGET_TYPES = ["USER", "EMPLOYEE", "PERSON", "ASSIGNMENT", "POSITION", "ORG_UNIT"];
const SCOPE_TYPES = ["GLOBAL", "ORG_UNIT", "SELF"];

export default function AccessTab() {
  const [grants, setGrants] = useState<AccessGrant[]>([]);
  const [roles, setRoles] = useState<AccessRoleRef[]>([]);
  const [guardMode, setGuardMode] = useState<GuardModeInfo | null>(null);
  const [total, setTotal] = useState(0);
  const [showRevoked, setShowRevoked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [effectiveUserId, setEffectiveUserId] = useState("");
  const [effective, setEffective] = useState<EffectiveAccess | null>(null);
  const [effectiveOpen, setEffectiveOpen] = useState(false);

  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [targetType, setTargetType] = useState("USER");
  const [selectedTarget, setSelectedTarget] = useState<AccessTargetSearchItem | null>(null);
  const [scopeType, setScopeType] = useState("GLOBAL");
  const [scopeTarget, setScopeTarget] = useState<AccessTargetSearchItem | null>(null);
  const [reason, setReason] = useState("");

  const selectedRole = useMemo(
    () => roles.find((r) => String(r.access_role_id) === selectedRoleId) ?? null,
    [roles, selectedRoleId],
  );

  const loadGrants = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const active = await fetchAccessGrants({ active_only: true, limit: 200 });
      let all = active.items;
      let count = active.total;
      if (showRevoked) {
        const revoked = await fetchAccessGrants({ active_only: false, limit: 200 });
        all = revoked.items;
        count = revoked.total;
      }
      setGrants(all);
      setTotal(count);
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось загрузить grants"));
    } finally {
      setLoading(false);
    }
  }, [showRevoked]);

  useEffect(() => {
    void loadGrants();
  }, [loadGrants]);

  useEffect(() => {
    void (async () => {
      try {
        const [roleRows, mode] = await Promise.all([fetchAccessRoles(), fetchGuardMode()]);
        setRoles(roleRows);
        setGuardMode(mode);
        if (roleRows.length) {
          setSelectedRoleId((prev) => prev || String(roleRows[0].access_role_id));
        }
      } catch (err) {
        setError(mapAdminSystemApiError(err, "Не удалось загрузить справочники"));
      }
    })();
  }, []);

  async function handleCreateGrant(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    if (!selectedRole || !selectedTarget) {
      setError("Выберите роль и target");
      return;
    }
    setError(null);
    setSuccess(null);
    try {
      await createAccessGrant({
        access_role_id: selectedRole.access_role_id,
        target_type: targetType,
        target_id: selectedTarget.target_id,
        scope_type: scopeType,
        scope_id: scopeType === "ORG_UNIT" && scopeTarget ? scopeTarget.target_id : null,
        reason: reason || undefined,
      });
      setSuccess("Grant создан");
      await loadGrants();
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось создать grant"));
    }
  }

  async function handleRevoke(grantId: number): Promise<void> {
    setError(null);
    setSuccess(null);
    try {
      await revokeAccessGrant(grantId);
      setSuccess(`Grant #${grantId} отозван`);
      await loadGrants();
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось отозвать grant"));
    }
  }

  async function loadEffective(): Promise<void> {
    const uid = Number(effectiveUserId);
    if (!uid) return;
    setError(null);
    try {
      const data = await fetchEffectiveAccessUser(uid);
      setEffective(data);
      setEffectiveOpen(true);
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось загрузить effective access"));
    }
  }

  return (
    <div className="space-y-4">
      <InfoBanner message={ENFORCEMENT_NOTICE} />
      {guardMode?.shadow_mode ? (
        <InfoBanner message="Режим проверки прав: shadow." />
      ) : null}
      {guardMode?.enforcement_active ? (
        <InfoBanner message="Режим принудительной проверки прав включён." />
      ) : null}
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
        <h3 className="font-medium">Effective access по пользователю</h3>
        <div className="mt-2 flex flex-wrap gap-2">
          <input
            type="number"
            placeholder="user_id"
            value={effectiveUserId}
            onChange={(e) => setEffectiveUserId(e.target.value)}
            className="w-32 rounded border px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900"
          />
          <button
            type="button"
            onClick={() => void loadEffective()}
            className="rounded-lg bg-blue-600 px-3 py-1 text-sm text-white"
          >
            Показать
          </button>
        </div>
        {effective && effectiveOpen ? (
          <div className="mt-3 rounded border border-zinc-200 bg-zinc-50 p-3 text-sm dark:border-zinc-700 dark:bg-zinc-900">
            <h4 className="font-medium">Effective Access Resolution</h4>
            <div className="mt-2">
              <strong>{effective.effective_role_code}</strong> ({effective.access_level}, rank{" "}
              {effective.level_rank})
            </div>

            {(() => {
              const { sources, resultLabel } = buildEffectiveAccessSummary(effective);
              return (
                <div className="mt-3 space-y-2">
                  <div className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
                    Источник grants:
                  </div>
                  {sources.length ? (
                    <ul className="space-y-1 text-sm">
                      {sources.map((src) => (
                        <li key={src.grant_id}>
                          <span className="font-medium">{src.access_level}</span>
                          <span className="text-zinc-500"> ← </span>
                          <span>{src.source_type}</span>
                          <span className="text-xs text-zinc-500">
                            {" "}
                            ({src.access_role_code}, grant #{src.grant_id})
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-zinc-500">Нет matching grants → implicit NONE</p>
                  )}
                  <div className="rounded border border-zinc-200 bg-white p-2 text-sm dark:border-zinc-700 dark:bg-zinc-950">
                    <span className="font-medium">Результат:</span> {resultLabel}
                  </div>
                </div>
              );
            })()}

            <details className="mt-3">
              <summary className="cursor-pointer font-medium text-xs">Raw explanation</summary>
              <pre className="mt-2 max-h-64 overflow-auto text-xs">
                {JSON.stringify(
                  {
                    explanation: effective.explanation,
                    matched_grants: effective.matched_grants,
                    deny_grants: effective.deny_grants,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
            {(effective.deny_grants?.length ?? 0) > 0 ? (
              <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                Explicit NONE в deny_grants — не блокирует UI при выключенном enforcement.
              </p>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
        <h3 className="font-medium">Выдать доступ</h3>
        <form onSubmit={(e) => void handleCreateGrant(e)} className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-sm sm:col-span-2">
            Роль доступа
            <select
              required
              value={selectedRoleId}
              onChange={(e) => setSelectedRoleId(e.target.value)}
              className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            >
              {roles.map((role) => (
                <option key={role.access_role_id} value={role.access_role_id}>
                  {formatAccessRoleLabel(role)}
                </option>
              ))}
            </select>
          </label>

          {selectedRole?.code && GRANT_SAFETY_WARNINGS[selectedRole.code] ? (
            <p className="text-sm text-amber-700 sm:col-span-2 dark:text-amber-300">
              {GRANT_SAFETY_WARNINGS[selectedRole.code]}
            </p>
          ) : null}

          <label className="text-sm">
            target_type
            <select
              value={targetType}
              onChange={(e) => setTargetType(e.target.value)}
              className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            >
              {TARGET_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>

          <div className="sm:col-span-2">
            <TargetSearchField
              targetType={targetType}
              value={selectedTarget}
              onChange={setSelectedTarget}
              label="Target (поиск)"
            />
          </div>

          <label className="text-sm">
            scope_type
            <select
              value={scopeType}
              onChange={(e) => setScopeType(e.target.value)}
              className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            >
              {SCOPE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>

          {scopeType === "ORG_UNIT" ? (
            <div>
              <TargetSearchField
                targetType="ORG_UNIT"
                value={scopeTarget}
                onChange={setScopeTarget}
                label="scope org unit"
              />
            </div>
          ) : (
            <div />
          )}

          <label className="text-sm sm:col-span-2">
            reason
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            />
          </label>

          <button
            type="submit"
            disabled={!selectedTarget}
            className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-50 sm:col-span-2"
          >
            Создать grant
          </button>
        </form>
      </section>

      <section>
        <div className="mb-2 flex flex-wrap items-center gap-3">
          <h3 className="font-medium">Grants ({total})</h3>
          <label className="flex items-center gap-1 text-sm">
            <input
              type="checkbox"
              checked={showRevoked}
              onChange={(e) => setShowRevoked(e.target.checked)}
            />
            Показать отозванные
          </label>
          <button type="button" onClick={() => void loadGrants()} className="text-sm underline">
            Обновить
          </button>
        </div>
        {loading ? (
          <p className="text-sm text-zinc-500">Загрузка…</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 dark:bg-zinc-900">
                <tr>
                  <th className="px-3 py-2 text-left">ID</th>
                  <th className="px-3 py-2 text-left">Role</th>
                  <th className="px-3 py-2 text-left">Target</th>
                  <th className="px-3 py-2 text-left">Scope</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-left"></th>
                </tr>
              </thead>
              <tbody>
                {grants.map((g) => {
                  const revoked = g.active_flag === false;
                  return (
                    <tr
                      key={g.grant_id}
                      className={`border-t dark:border-zinc-800 ${revoked ? "opacity-50" : ""}`}
                    >
                      <td className="px-3 py-2">{g.grant_id}</td>
                      <td className="px-3 py-2">
                        {g.access_role_code ?? g.access_role_id} ({g.access_level})
                      </td>
                      <td className="px-3 py-2">
                        {g.target_type}:{g.target_id}
                      </td>
                      <td className="px-3 py-2">
                        {g.scope_type}
                        {g.scope_id != null ? ` #${g.scope_id}` : ""}
                      </td>
                      <td className="px-3 py-2">{revoked ? "revoked" : "active"}</td>
                      <td className="px-3 py-2">
                        {!revoked ? (
                          <button
                            type="button"
                            onClick={() => void handleRevoke(g.grant_id)}
                            className="text-xs text-red-600 underline"
                          >
                            Отозвать
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
