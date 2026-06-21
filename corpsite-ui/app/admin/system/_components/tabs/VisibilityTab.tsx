// FILE: corpsite-ui/app/admin/system/_components/tabs/VisibilityTab.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { getEmployees } from "@/app/directory/employees/_lib/api.client";
import { getOrgUnitsTree } from "@/app/directory/org-units/_lib/api.client";
import { apiFetchJson } from "@/lib/api";

import {
  createPersonnelVisibilityAssignment,
  fetchAdminUsers,
  fetchEffectivePersonnelVisibility,
  fetchPersonnelVisibilityAssignments,
  mapAdminSystemApiError,
  revokePersonnelVisibilityAssignment,
  searchAccessTargets,
  type AccessTargetSearchItem,
  type EffectivePersonnelVisibility,
  type PersonnelVisibilityAssignment,
} from "../../_lib/adminSystemApi.client";
import {
  buildBulkDepartmentVisibilityPayloads,
  buildDepartmentUserOptions,
  canSubmitVisibilityAssignment,
  classifyBulkVisibilityCreateError,
  clearDepartmentTargetSelection,
  countEmployeesWithoutUserAccount,
  departmentPrefilterOptional,
  departmentPrefilterRequired,
  extractPositionIdsFromEmployees,
  filterOrgUnitsByGroupAndQuery,
  filterPositionsByDepartmentContext,
  filterUserOptionsByQuery,
  flattenOrgUnitTree,
  formatDepartmentOptionLabel,
  formatUserOptionLabel,
  parseDepartmentGroupFilterValue,
  pruneDepartmentTargetSelectionByGroup,
  selectAllVisibleDepartmentTargets,
  sortDepartmentGroupOptions,
  summarizeBulkVisibilityCreateResults,
  toggleDepartmentTargetSelection,
  toAccessTargetFromUser,
  VISIBILITY_MODE_OPTIONS,
  type BulkVisibilityCreateItemResult,
  type DepartmentGroupOption,
  type OrgUnitOption,
  type VisibilityAssignmentMode,
  type EmployeeLike,
  type VisibilityUserOption,
} from "../../_lib/visibilityTabLogic";
import ErrorBanner, { InfoBanner, SuccessBanner } from "../shared/ErrorBanner";
import TargetSearchField from "../shared/TargetSearchField";

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

function indentStyle(depth: number): React.CSSProperties {
  return { paddingLeft: `${Math.min(depth, 6) * 12 + 8}px` };
}

export default function VisibilityTab() {
  const [items, setItems] = useState<PersonnelVisibilityAssignment[]>([]);
  const [total, setTotal] = useState(0);
  const [showRevoked, setShowRevoked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [mode, setMode] = useState<VisibilityAssignmentMode>("USER");
  const [orgUnits, setOrgUnits] = useState<OrgUnitOption[]>([]);
  const [departmentGroups, setDepartmentGroups] = useState<DepartmentGroupOption[]>([]);
  const [referenceLoading, setReferenceLoading] = useState(true);

  const [prefilterGroupId, setPrefilterGroupId] = useState("");
  const [prefilterDepartment, setPrefilterDepartment] = useState<OrgUnitOption | null>(null);
  const [departmentQuery, setDepartmentQuery] = useState("");
  const [userQuery, setUserQuery] = useState("");
  const [departmentTargetQuery, setDepartmentTargetQuery] = useState("");

  const [departmentEmployees, setDepartmentEmployees] = useState<EmployeeLike[]>([]);
  const [employeesLoading, setEmployeesLoading] = useState(false);
  const [employeesWithoutAccount, setEmployeesWithoutAccount] = useState(0);
  const [adminUsers, setAdminUsers] = useState<Awaited<ReturnType<typeof fetchAdminUsers>>>([]);

  const [selectedUser, setSelectedUser] = useState<VisibilityUserOption | null>(null);
  const [selectedDepartmentTargetIds, setSelectedDepartmentTargetIds] = useState<Set<number>>(
    () => new Set(),
  );
  const [selectedPosition, setSelectedPosition] = useState<AccessTargetSearchItem | null>(null);
  const [positionResults, setPositionResults] = useState<AccessTargetSearchItem[]>([]);
  const [positionQuery, setPositionQuery] = useState("");
  const [positionLoading, setPositionLoading] = useState(false);

  const [scopeType, setScopeType] = useState<(typeof SCOPE_TYPES)[number]>("ORGANIZATION");
  const [scopeTarget, setScopeTarget] = useState<AccessTargetSearchItem | null>(null);
  const [scopeGroupId, setScopeGroupId] = useState("");
  const [canViewTasks, setCanViewTasks] = useState(false);

  const [effectiveUserId, setEffectiveUserId] = useState("");
  const [effective, setEffective] = useState<EffectivePersonnelVisibility | null>(null);

  const scopeTargetType = scopeType === "DEPARTMENT" ? "ORG_UNIT" : null;

  const selectedGroupId = useMemo(
    () => parseDepartmentGroupFilterValue(prefilterGroupId),
    [prefilterGroupId],
  );

  const filteredPrefilterDepartments = useMemo(
    () => filterOrgUnitsByGroupAndQuery(orgUnits, selectedGroupId, departmentQuery),
    [orgUnits, selectedGroupId, departmentQuery],
  );

  const filteredDepartmentTargets = useMemo(
    () => filterOrgUnitsByGroupAndQuery(orgUnits, selectedGroupId, departmentTargetQuery),
    [orgUnits, selectedGroupId, departmentTargetQuery],
  );

  const orgUnitsById = useMemo(
    () => new Map(orgUnits.map((dept) => [dept.unitId, dept])),
    [orgUnits],
  );

  const displayedDepartmentTargets = useMemo(
    () => filteredDepartmentTargets.slice(0, 40),
    [filteredDepartmentTargets],
  );

  const departmentUserOptions = useMemo(() => {
    if (!prefilterDepartment) return [];
    return buildDepartmentUserOptions(departmentEmployees, adminUsers, prefilterDepartment);
  }, [adminUsers, departmentEmployees, prefilterDepartment]);

  const filteredUsers = useMemo(
    () => filterUserOptionsByQuery(departmentUserOptions, userQuery),
    [departmentUserOptions, userQuery],
  );

  const staffedPositionIds = useMemo(
    () => extractPositionIdsFromEmployees(departmentEmployees),
    [departmentEmployees],
  );

  const filteredPositionResults = useMemo(
    () =>
      filterPositionsByDepartmentContext(
        positionResults,
        staffedPositionIds,
        Boolean(prefilterDepartment),
      ),
    [positionResults, prefilterDepartment, staffedPositionIds],
  );

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

  useEffect(() => {
    void (async () => {
      setReferenceLoading(true);
      try {
        const [tree, groupsBody, users] = await Promise.all([
          getOrgUnitsTree({ include_inactive: false }),
          apiFetchJson<{ items?: { group_id: number; group_name?: string }[] }>(
            "/directory/department-groups",
          ).catch(() => ({ items: [] })),
          fetchAdminUsers({ limit: 500 }),
        ]);

        const groupNames = new Map<number, string>();
        const groups: DepartmentGroupOption[] = [];
        for (const g of groupsBody.items ?? []) {
          const gid = Number(g.group_id);
          if (Number.isFinite(gid) && gid >= 1) {
            const groupName = String(g.group_name || "").trim() || `Группа #${gid}`;
            groupNames.set(gid, groupName);
            groups.push({ groupId: gid, groupName });
          }
        }

        setOrgUnits(flattenOrgUnitTree(tree.items, 0, groupNames));
        setDepartmentGroups(sortDepartmentGroupOptions(groups));
        setAdminUsers(users);
      } catch (err) {
        setError(mapAdminSystemApiError(err, "Не удалось загрузить справочник отделений"));
      } finally {
        setReferenceLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!prefilterDepartment || (mode !== "USER" && mode !== "POSITION")) {
      setDepartmentEmployees([]);
      setEmployeesWithoutAccount(0);
      return;
    }

    void (async () => {
      setEmployeesLoading(true);
      try {
        const res = await getEmployees({
          org_unit_id: prefilterDepartment.unitId,
          include_children: true,
          status: "active",
          limit: 200,
        });
        setDepartmentEmployees(res.items);
        setEmployeesWithoutAccount(countEmployeesWithoutUserAccount(res.items));
      } catch {
        setDepartmentEmployees([]);
        setEmployeesWithoutAccount(0);
      } finally {
        setEmployeesLoading(false);
      }
    })();
  }, [mode, prefilterDepartment]);

  useEffect(() => {
    if (mode !== "POSITION") return;
    const timer = window.setTimeout(() => {
      void (async () => {
        setPositionLoading(true);
        try {
          const res = await searchAccessTargets({
            target_type: "POSITION",
            q: positionQuery,
            limit: 30,
          });
          setPositionResults(res.items);
        } catch {
          setPositionResults([]);
        } finally {
          setPositionLoading(false);
        }
      })();
    }, 300);
    return () => window.clearTimeout(timer);
  }, [mode, positionQuery]);

  function resetTargetSelection(): void {
    setSelectedUser(null);
    setSelectedDepartmentTargetIds(clearDepartmentTargetSelection());
    setSelectedPosition(null);
    setUserQuery("");
    setDepartmentTargetQuery("");
    setPositionQuery("");
  }

  function handlePrefilterGroupChange(nextGroupId: string): void {
    setPrefilterGroupId(nextGroupId);
    const nextSelectedGroupId = parseDepartmentGroupFilterValue(nextGroupId);
    if (
      prefilterDepartment &&
      nextSelectedGroupId != null &&
      prefilterDepartment.groupId !== nextSelectedGroupId
    ) {
      setPrefilterDepartment(null);
      setSelectedUser(null);
      setUserQuery("");
      setSelectedPosition(null);
      setPositionQuery("");
    }
    setSelectedDepartmentTargetIds((current) =>
      pruneDepartmentTargetSelectionByGroup(current, nextSelectedGroupId, orgUnitsById),
    );
  }

  function handleModeChange(next: VisibilityAssignmentMode): void {
    setMode(next);
    setPrefilterGroupId("");
    setPrefilterDepartment(null);
    setDepartmentQuery("");
    resetTargetSelection();
  }

  async function handleCreate(e: React.FormEvent): Promise<void> {
    e.preventDefault();

    if (
      !canSubmitVisibilityAssignment({
        mode,
        selectedDepartment: prefilterDepartment,
        selectedUser,
        selectedDepartmentTargetIds,
        selectedPosition,
      })
    ) {
      setError(
        mode === "DEPARTMENT"
          ? "Выберите хотя бы одно отделение"
          : "Заполните обязательные поля назначения",
      );
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

    if (mode === "DEPARTMENT") {
      const scopeDepartmentGroupId =
        scopeType === "DEPARTMENT_GROUP" ? Number(scopeGroupId) : null;
      const payloads = buildBulkDepartmentVisibilityPayloads({
        departmentIds: selectedDepartmentTargetIds,
        scopeType,
        scopeDepartmentId: scopeType === "DEPARTMENT" ? scopeTarget?.target_id ?? null : null,
        scopeDepartmentGroupId,
        canViewTasks,
      });

      const results: BulkVisibilityCreateItemResult[] = [];
      for (const item of payloads) {
        try {
          await createPersonnelVisibilityAssignment(item.payload);
          results.push({ departmentId: item.departmentId, outcome: "success" });
        } catch (err) {
          results.push({
            departmentId: item.departmentId,
            outcome: classifyBulkVisibilityCreateError(err),
            errorMessage: mapAdminSystemApiError(err, "Не удалось создать назначение"),
          });
        }
      }

      const summary = summarizeBulkVisibilityCreateResults(results);
      if (summary.successCount > 0) {
        setSuccess(summary.message);
        setSelectedDepartmentTargetIds(clearDepartmentTargetSelection());
        await load();
      } else {
        setError(summary.message);
      }
      return;
    }

    let target: AccessTargetSearchItem | null = null;
    if (mode === "USER" && selectedUser) target = toAccessTargetFromUser(selectedUser);
    if (mode === "POSITION" && selectedPosition) target = selectedPosition;
    if (!target) {
      setError("Выберите target");
      return;
    }

    const targetTypeApi = target.target_type as "USER" | "POSITION";

    try {
      await createPersonnelVisibilityAssignment({
        target_type: targetTypeApi,
        target_user_id: targetTypeApi === "USER" ? target.target_id : null,
        target_position_id: targetTypeApi === "POSITION" ? target.target_id : null,
        target_department_id: null,
        scope_type: scopeType,
        scope_department_id: scopeType === "DEPARTMENT" ? scopeTarget?.target_id ?? null : null,
        scope_department_group_id: scopeType === "DEPARTMENT_GROUP" ? Number(scopeGroupId) : null,
        can_view_personnel: true,
        can_view_tasks: canViewTasks,
      });
      setSuccess("Назначение создано");
      resetTargetSelection();
      setPrefilterGroupId("");
      setPrefilterDepartment(null);
      setDepartmentQuery("");
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
      <InfoBanner message="Видимость персонала (ADR-042 E1) открывает правый сайдбар и справочник без выдачи admin-функций. Роль отвечает за действия; visibility scope — за просмотр." />

      {error ? <ErrorBanner message={error} /> : null}
      {success ? <SuccessBanner message={success} /> : null}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Создать назначение</h2>

        <div className="flex flex-wrap gap-2">
          {VISIBILITY_MODE_OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => handleModeChange(option.id)}
              className={[
                "rounded-lg px-3 py-1.5 text-sm font-medium transition",
                mode === option.id
                  ? "bg-blue-600 text-white"
                  : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
              ].join(" ")}
            >
              {option.label}
            </button>
          ))}
        </div>

        <form onSubmit={handleCreate} className="grid gap-4 md:grid-cols-2">
          {(departmentPrefilterRequired(mode) || departmentPrefilterOptional(mode)) && (
            <div className="md:col-span-2 space-y-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
              <div className="text-sm font-medium">
                {departmentPrefilterRequired(mode)
                  ? "Отделение (обязательно)"
                  : "Отделение (опционально — фильтр должностей)"}
              </div>
              {prefilterDepartment ? (
                <div className="flex items-center justify-between rounded border border-green-300 bg-green-50 px-2 py-1 text-sm dark:border-green-800 dark:bg-green-950/30">
                  <span>{formatDepartmentOptionLabel(prefilterDepartment)}</span>
                  <button
                    type="button"
                    className="text-xs underline"
                    onClick={() => {
                      setPrefilterDepartment(null);
                      setDepartmentQuery("");
                      resetTargetSelection();
                    }}
                  >
                    сменить
                  </button>
                </div>
              ) : (
                <>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                    <label className="block shrink-0 sm:w-52">
                      <span className="mb-1 block text-xs text-zinc-500">Группа отделений</span>
                      <select
                        value={prefilterGroupId}
                        onChange={(e) => handlePrefilterGroupChange(e.target.value)}
                        disabled={referenceLoading}
                        className="w-full rounded border px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900"
                      >
                        <option value="">Все группы</option>
                        {departmentGroups.map((group) => (
                          <option key={group.groupId} value={String(group.groupId)}>
                            {group.groupName}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="min-w-0 flex-1">
                      <input
                        type="search"
                        placeholder="Поиск отделения…"
                        value={departmentQuery}
                        onChange={(e) => setDepartmentQuery(e.target.value)}
                        className="w-full rounded border px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900"
                        disabled={referenceLoading}
                      />
                    </div>
                  </div>
                  {referenceLoading ? (
                    <p className="text-xs text-zinc-500">Загрузка отделений…</p>
                  ) : filteredPrefilterDepartments.length === 0 ? (
                    <p className="text-xs text-zinc-500">Отделения не найдены</p>
                  ) : (
                    <ul className="max-h-44 overflow-auto rounded border dark:border-zinc-700">
                      {filteredPrefilterDepartments.slice(0, 40).map((dept) => (
                        <li key={dept.unitId}>
                          <button
                            type="button"
                            className="block w-full px-2 py-1.5 text-left text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800"
                            style={indentStyle(dept.depth)}
                            onClick={() => {
                              setPrefilterDepartment(dept);
                              setDepartmentQuery("");
                              resetTargetSelection();
                            }}
                          >
                            {formatDepartmentOptionLabel(dept)}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
              {mode === "POSITION" && !prefilterDepartment ? (
                <p className="text-xs text-zinc-500">
                  Без выбора отделения поиск должностей выполняется по всей организации. Фильтр по
                  отделению основан на активных сотрудниках отделения и может быть неполным.
                </p>
              ) : null}
            </div>
          )}

          {mode === "USER" ? (
            <div className="md:col-span-2 space-y-2">
              <div className="text-sm font-medium">Сотрудник с учётной записью</div>
              {!prefilterDepartment ? (
                <p className="rounded border border-dashed border-zinc-300 px-3 py-2 text-sm text-zinc-500 dark:border-zinc-600">
                  Выберите отделение, чтобы увидеть сотрудников с учётной записью.
                </p>
              ) : selectedUser ? (
                <div className="flex items-center justify-between rounded border border-green-300 bg-green-50 px-2 py-1 text-sm dark:border-green-800 dark:bg-green-950/30">
                  <span>{formatUserOptionLabel(selectedUser)}</span>
                  <button
                    type="button"
                    className="text-xs underline"
                    onClick={() => setSelectedUser(null)}
                  >
                    сменить
                  </button>
                </div>
              ) : (
                <>
                  <input
                    type="search"
                    placeholder="Поиск по ФИО, login, должности…"
                    value={userQuery}
                    onChange={(e) => setUserQuery(e.target.value)}
                    className="w-full rounded border px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900"
                    disabled={employeesLoading}
                  />
                  {employeesLoading ? (
                    <p className="text-xs text-zinc-500">Загрузка сотрудников…</p>
                  ) : filteredUsers.length === 0 ? (
                    <p className="rounded border border-dashed border-zinc-300 px-3 py-2 text-sm text-zinc-500 dark:border-zinc-600">
                      {departmentUserOptions.length === 0
                        ? "В выбранном отделении нет активных пользователей с учётной записью."
                        : "Сотрудники не найдены по запросу."}
                    </p>
                  ) : (
                    <ul className="max-h-52 overflow-auto rounded border dark:border-zinc-700">
                      {filteredUsers.map((user) => (
                        <li key={user.userId}>
                          <button
                            type="button"
                            className="block w-full px-2 py-1.5 text-left text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800"
                            onClick={() => setSelectedUser(user)}
                          >
                            <div className="font-medium">{user.fullName}</div>
                            <div className="text-zinc-500">
                              {[
                                user.login ? `login: ${user.login}` : null,
                                user.positionName,
                                user.departmentName,
                              ]
                                .filter(Boolean)
                                .join(" · ")}
                            </div>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  {!employeesLoading && employeesWithoutAccount > 0 ? (
                    <p className="text-xs text-amber-700 dark:text-amber-300">
                      {employeesWithoutAccount} сотрудник(ов) без учётной записи — назначение USER
                      для них недоступно.
                    </p>
                  ) : null}
                </>
              )}
            </div>
          ) : null}

          {mode === "DEPARTMENT" ? (
            <div className="md:col-span-2 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium">Отделения-получатели visibility</div>
                {selectedDepartmentTargetIds.size > 0 ? (
                  <span className="text-xs text-zinc-500">
                    Выбрано: {selectedDepartmentTargetIds.size}
                  </span>
                ) : null}
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                <label className="block shrink-0 sm:w-52">
                  <span className="mb-1 block text-xs text-zinc-500">Группа отделений</span>
                  <select
                    value={prefilterGroupId}
                    onChange={(e) => handlePrefilterGroupChange(e.target.value)}
                    disabled={referenceLoading}
                    className="w-full rounded border px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900"
                  >
                    <option value="">Все группы</option>
                    {departmentGroups.map((group) => (
                      <option key={group.groupId} value={String(group.groupId)}>
                        {group.groupName}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="min-w-0 flex-1">
                  <input
                    type="search"
                    placeholder="Поиск отделения…"
                    value={departmentTargetQuery}
                    onChange={(e) => setDepartmentTargetQuery(e.target.value)}
                    className="w-full rounded border px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900"
                    disabled={referenceLoading}
                  />
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-800"
                  disabled={referenceLoading || filteredDepartmentTargets.length === 0}
                  onClick={() =>
                    setSelectedDepartmentTargetIds((current) =>
                      selectAllVisibleDepartmentTargets(current, filteredDepartmentTargets),
                    )
                  }
                >
                  Выбрать все видимые
                </button>
                <button
                  type="button"
                  className="rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-800"
                  disabled={selectedDepartmentTargetIds.size === 0}
                  onClick={() => setSelectedDepartmentTargetIds(clearDepartmentTargetSelection())}
                >
                  Снять выбор
                </button>
              </div>
              {referenceLoading ? (
                <p className="text-xs text-zinc-500">Загрузка отделений…</p>
              ) : filteredDepartmentTargets.length === 0 ? (
                <p className="text-xs text-zinc-500">Отделения не найдены</p>
              ) : (
                <ul className="max-h-52 overflow-auto rounded border dark:border-zinc-700">
                  {displayedDepartmentTargets.map((dept) => {
                    const checked = selectedDepartmentTargetIds.has(dept.unitId);
                    return (
                      <li key={dept.unitId}>
                        <label
                          className="flex cursor-pointer items-start gap-2 px-2 py-1.5 text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800"
                          style={indentStyle(dept.depth)}
                        >
                          <input
                            type="checkbox"
                            className="mt-0.5"
                            checked={checked}
                            onChange={() =>
                              setSelectedDepartmentTargetIds((current) =>
                                toggleDepartmentTargetSelection(current, dept.unitId),
                              )
                            }
                          />
                          <span>
                            <span className="font-medium">{dept.name}</span>
                            <span className="block text-zinc-500">
                              {[dept.groupName ? `группа: ${dept.groupName}` : null, dept.code]
                                .filter(Boolean)
                                .join(" · ")}
                            </span>
                          </span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              )}
              {filteredDepartmentTargets.length > displayedDepartmentTargets.length ? (
                <p className="text-xs text-zinc-500">
                  Показаны первые {displayedDepartmentTargets.length} из{" "}
                  {filteredDepartmentTargets.length}. «Выбрать все видимые» отметит все по текущему
                  фильтру.
                </p>
              ) : null}
            </div>
          ) : null}

          {mode === "POSITION" ? (
            <div className="md:col-span-2 space-y-2">
              <div className="text-sm font-medium">Должность</div>
              {selectedPosition ? (
                <div className="flex items-center justify-between rounded border border-green-300 bg-green-50 px-2 py-1 text-sm dark:border-green-800 dark:bg-green-950/30">
                  <span>
                    #{selectedPosition.target_id} — {selectedPosition.label}
                    {selectedPosition.subtitle ? ` (${selectedPosition.subtitle})` : ""}
                  </span>
                  <button
                    type="button"
                    className="text-xs underline"
                    onClick={() => setSelectedPosition(null)}
                  >
                    сменить
                  </button>
                </div>
              ) : (
                <>
                  <input
                    type="search"
                    placeholder="Поиск должности…"
                    value={positionQuery}
                    onChange={(e) => setPositionQuery(e.target.value)}
                    className="w-full rounded border px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900"
                  />
                  {positionLoading ? <p className="text-xs text-zinc-500">Поиск…</p> : null}
                  {filteredPositionResults.length > 0 ? (
                    <ul className="max-h-44 overflow-auto rounded border dark:border-zinc-700">
                      {filteredPositionResults.map((item) => (
                        <li key={item.target_id}>
                          <button
                            type="button"
                            className="block w-full px-2 py-1 text-left text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800"
                            onClick={() => setSelectedPosition(item)}
                          >
                            <strong>#{item.target_id}</strong> {item.label}
                            {item.subtitle ? ` — ${item.subtitle}` : ""}
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : prefilterDepartment && !positionLoading ? (
                    <p className="text-xs text-zinc-500">
                      В выбранном отделении нет должностей по текущему фильтру.
                    </p>
                  ) : null}
                </>
              )}
            </div>
          ) : null}

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
            <div className="self-end pb-2 text-sm text-zinc-500 dark:text-zinc-400">
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
