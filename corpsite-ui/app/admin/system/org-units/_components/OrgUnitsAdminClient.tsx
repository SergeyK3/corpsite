// FILE: corpsite-ui/app/admin/system/org-units/_components/OrgUnitsAdminClient.tsx
"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import ConfirmDialog from "../../_components/shared/ConfirmDialog";
import ErrorBanner, { SuccessBanner } from "../../_components/shared/ErrorBanner";
import {
  activateAdminOrgUnit,
  bulkDeleteAdminOrgUnits,
  buildBulkDeleteConfirmMessage,
  buildBulkDeleteResultRows,
  canOfferNoParentOption,
  collectDescendantIds,
  createAdminOrgUnit,
  deactivateAdminOrgUnit,
  deleteAdminOrgUnit,
  fetchAdminOrgUnitDependencies,
  fetchAdminOrgUnits,
  findRootUnits,
  formatBulkDeleteSummary,
  formatDependencyList,
  isOrgUnitHasDependenciesError,
  mapAdminOrgUnitsApiError,
  previewBulkDeleteAdminOrgUnits,
  resolveGroupLabel,
  updateAdminOrgUnit,
  type AdminOrgUnit,
  type AdminOrgUnitListParams,
  type BulkDeletePreviewResponse,
  type BulkDeleteResultRow,
  type OrgUnitDependencySummary,
} from "../_lib/adminOrgUnitsApi.client";
import { fetchDepartmentGroups, type DepartmentGroupRow } from "@/lib/orgScope";
import { recordStatusLabel } from "@/lib/i18n";

type DrawerMode = "create" | "edit" | "view" | null;

type FormState = {
  name: string;
  code: string;
  group_id: string;
  parent_unit_id: string;
  is_active: boolean;
  allow_duplicate: boolean;
};

const EMPTY_FORM: FormState = {
  name: "",
  code: "",
  group_id: "",
  parent_unit_id: "",
  is_active: true,
  allow_duplicate: false,
};

const ACTION_BTN =
  "rounded-md border border-zinc-300 px-2 py-0.5 text-xs font-medium hover:bg-zinc-50 dark:border-zinc-600 dark:hover:bg-zinc-800";
const ACTION_BTN_DANGER =
  "rounded-md border border-red-300 px-2 py-0.5 text-xs font-medium text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/40";

const PAGE_SIZE = 50;

export default function OrgUnitsAdminClient() {
  const [items, setItems] = useState<AdminOrgUnit[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"all" | "active" | "inactive">("active");
  const [orgGroupId, setOrgGroupId] = useState("");
  const [parentFilter, setParentFilter] = useState("");
  const [rootsOnly, setRootsOnly] = useState(false);
  const [withoutEmployees, setWithoutEmployees] = useState(false);
  const [deletableOnly, setDeletableOnly] = useState(false);
  const [offset, setOffset] = useState(0);

  const [groups, setGroups] = useState<DepartmentGroupRow[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const [drawerMode, setDrawerMode] = useState<DrawerMode>(null);
  const [activeUnit, setActiveUnit] = useState<AdminOrgUnit | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [dependencyDialog, setDependencyDialog] = useState<{
    unit: AdminOrgUnit;
    deps: OrgUnitDependencySummary;
  } | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<AdminOrgUnit | null>(null);
  const [bulkConfirm, setBulkConfirm] = useState(false);
  const [bulkPreview, setBulkPreview] = useState<BulkDeletePreviewResponse | null>(null);
  const [bulkPreviewLoading, setBulkPreviewLoading] = useState(false);
  const [bulkResults, setBulkResults] = useState<{
    deleted: BulkDeleteResultRow[];
    failed: BulkDeleteResultRow[];
  } | null>(null);

  const listParams = useMemo((): AdminOrgUnitListParams => {
    const params: AdminOrgUnitListParams = {
      status,
      roots_only: rootsOnly,
      without_employees: withoutEmployees,
      deletable_only: deletableOnly,
      limit: PAGE_SIZE,
      offset,
    };
    const trimmed = q.trim();
    if (trimmed) params.q = trimmed;
    if (orgGroupId) params.org_group_id = Number(orgGroupId);
    if (parentFilter) params.parent_unit_id = Number(parentFilter);
    return params;
  }, [q, status, orgGroupId, parentFilter, rootsOnly, withoutEmployees, deletableOnly, offset]);

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAdminOrgUnits(listParams);
      setItems(data.items ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      setError(mapAdminOrgUnitsApiError(err, "Не удалось загрузить подразделения."));
    } finally {
      setLoading(false);
    }
  }, [listParams]);

  useEffect(() => {
    const timer = window.setTimeout(() => setQ(qInput), 300);
    return () => window.clearTimeout(timer);
  }, [qInput]);

  useEffect(() => {
    setOffset(0);
  }, [q, status, orgGroupId, parentFilter, rootsOnly, withoutEmployees, deletableOnly]);

  useEffect(() => {
    void loadItems();
  }, [loadItems]);

  useEffect(() => {
    void (async () => {
      try {
        const rows = await fetchDepartmentGroups();
        setGroups(rows);
      } catch {
        setGroups([]);
      }
    })();
  }, []);

  const groupLabelById = useMemo(
    () => new Map(groups.map((g) => [g.group_id, g.group_name])),
    [groups],
  );

  const rootUnits = useMemo(() => findRootUnits(items), [items]);
  const rootExists = rootUnits.length > 0;

  const allowNoParent = useMemo(
    () =>
      canOfferNoParentOption({
        mode: drawerMode === "create" ? "create" : "edit",
        rootExists,
        activeUnit,
      }),
    [drawerMode, rootExists, activeUnit],
  );

  const groupInheritedFromParent = useMemo(() => {
    const parentId = Number(form.parent_unit_id);
    if (!Number.isFinite(parentId) || parentId <= 0) return null;
    const parent = items.find((u) => u.unit_id === parentId);
    return parent?.group_id ?? null;
  }, [form.parent_unit_id, items]);

  const unitNameById = useMemo(() => new Map(items.map((u) => [u.unit_id, u.name])), [items]);

  const currentPageIds = useMemo(() => items.map((unit) => unit.unit_id), [items]);
  const allCurrentPageSelected =
    currentPageIds.length > 0 && currentPageIds.every((id) => selectedIds.has(id));
  const someCurrentPageSelected =
    currentPageIds.some((id) => selectedIds.has(id)) && !allCurrentPageSelected;

  const selectedUnitsForConfirm = useMemo(() => {
    const byId = new Map(items.map((unit) => [unit.unit_id, unit]));
    return Array.from(selectedIds)
      .map((id) => byId.get(id) ?? { unit_id: id, name: `ID ${id}` })
      .sort((a, b) => a.unit_id - b.unit_id);
  }, [items, selectedIds]);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const parentOptions = useMemo(() => {
    if (!activeUnit) return items;
    const blocked = collectDescendantIds(items, activeUnit.unit_id);
    blocked.add(activeUnit.unit_id);
    return items.filter((u) => !blocked.has(u.unit_id));
  }, [items, activeUnit]);

  function openCreate() {
    setActiveUnit(null);
    const defaultGroupId = groups[0] ? String(groups[0].group_id) : "";
    setForm({
      ...EMPTY_FORM,
      group_id: defaultGroupId,
      parent_unit_id: "",
    });
    setDrawerMode("create");
    setError(null);
    setFormError(null);
    setSuccess(null);
  }

  function openEdit(unit: AdminOrgUnit) {
    setActiveUnit(unit);
    setForm({
      name: unit.name,
      code: unit.code ?? "",
      group_id: unit.group_id != null ? String(unit.group_id) : groups[0] ? String(groups[0].group_id) : "",
      parent_unit_id: unit.parent_unit_id != null ? String(unit.parent_unit_id) : "",
      is_active: unit.is_active,
      allow_duplicate: false,
    });
    setDrawerMode("edit");
    setFormError(null);
  }

  function handleParentChange(parentUnitId: string) {
    setForm((prev) => {
      const next = { ...prev, parent_unit_id: parentUnitId };
      const parentId = Number(parentUnitId);
      if (Number.isFinite(parentId) && parentId > 0) {
        const parent = items.find((u) => u.unit_id === parentId);
        if (parent?.group_id != null) {
          next.group_id = String(parent.group_id);
        }
      }
      return next;
    });
  }

  function validateFormBeforeSave(): string | null {
    if (drawerMode === "edit" && activeUnit && activeUnit.parent_unit_id != null && !form.parent_unit_id.trim()) {
      return "Выберите родительское подразделение.";
    }
    if (!form.group_id.trim()) {
      return "Выберите группу отделений.";
    }
    return null;
  }

  function openView(unit: AdminOrgUnit) {
    setActiveUnit(unit);
    setDrawerMode("view");
  }

  async function handleSave() {
    const validationError = validateFormBeforeSave();
    if (validationError) {
      setFormError(validationError);
      return;
    }

    setSaving(true);
    setError(null);
    setFormError(null);
    try {
      if (drawerMode === "create") {
        const parentRaw = form.parent_unit_id.trim();
        await createAdminOrgUnit({
          name: form.name.trim(),
          code: form.code.trim() || null,
          group_id: Number(form.group_id),
          parent_unit_id: parentRaw ? Number(parentRaw) : null,
          is_active: form.is_active,
          allow_duplicate: form.allow_duplicate,
        });
        setSuccess("Подразделение создано.");
      } else if (drawerMode === "edit" && activeUnit) {
        const parentRaw = form.parent_unit_id.trim();
        const isCurrentRoot = activeUnit.parent_unit_id == null;
        await updateAdminOrgUnit(activeUnit.unit_id, {
          name: form.name.trim(),
          code: form.code.trim() || null,
          group_id: Number(form.group_id),
          is_active: form.is_active,
          allow_duplicate: form.allow_duplicate,
          ...(isCurrentRoot
            ? {}
            : parentRaw
              ? { parent_unit_id: Number(parentRaw) }
              : { clear_parent: true }),
        });
        setSuccess("Подразделение обновлено.");
      }
      setDrawerMode(null);
      await loadItems();
    } catch (err) {
      const message = mapAdminOrgUnitsApiError(err, "Не удалось сохранить подразделение.");
      setFormError(message);
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteAttempt(unit: AdminOrgUnit) {
    setError(null);
    try {
      const deps = await fetchAdminOrgUnitDependencies(unit.unit_id);
      if (!deps.can_delete) {
        setDependencyDialog({ unit, deps });
        return;
      }
      setDeleteConfirm(unit);
    } catch (err) {
      setError(mapAdminOrgUnitsApiError(err, "Не удалось проверить зависимости."));
    }
  }

  async function confirmDelete() {
    if (!deleteConfirm) return;
    setError(null);
    try {
      await deleteAdminOrgUnit(deleteConfirm.unit_id);
      setSuccess(`Подразделение «${deleteConfirm.name}» (ID ${deleteConfirm.unit_id}) удалено.`);
      setDeleteConfirm(null);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(deleteConfirm.unit_id);
        return next;
      });
      await loadItems();
    } catch (err) {
      if (isOrgUnitHasDependenciesError(err)) {
        const detail = err.body?.detail;
        setDependencyDialog({
          unit: deleteConfirm,
          deps: {
            can_delete: false,
            dependencies: detail?.dependencies ?? {},
          },
        });
        setDeleteConfirm(null);
        return;
      }
      setError(mapAdminOrgUnitsApiError(err, "Не удалось удалить подразделение."));
    }
  }

  async function handleDeactivateFromDialog() {
    if (!dependencyDialog) return;
    try {
      await deactivateAdminOrgUnit(dependencyDialog.unit.unit_id);
      setSuccess(`Подразделение «${dependencyDialog.unit.name}» деактивировано.`);
      setDependencyDialog(null);
      await loadItems();
    } catch (err) {
      setError(mapAdminOrgUnitsApiError(err, "Не удалось деактивировать подразделение."));
    }
  }

  async function toggleActive(unit: AdminOrgUnit) {
    setError(null);
    try {
      if (unit.is_active) {
        await deactivateAdminOrgUnit(unit.unit_id);
        setSuccess(`Подразделение «${unit.name}» деактивировано.`);
      } else {
        await activateAdminOrgUnit(unit.unit_id);
        setSuccess(`Подразделение «${unit.name}» активировано.`);
      }
      await loadItems();
    } catch (err) {
      setError(mapAdminOrgUnitsApiError(err, "Не удалось изменить статус."));
    }
  }

  function toggleSelected(unitId: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(unitId)) next.delete(unitId);
      else next.add(unitId);
      return next;
    });
  }

  function toggleSelectAllCurrentPage() {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allCurrentPageSelected) {
        for (const id of currentPageIds) next.delete(id);
      } else {
        for (const id of currentPageIds) next.add(id);
      }
      return next;
    });
  }

  async function openBulkConfirm() {
    const ids = Array.from(selectedIds);
    if (!ids.length) return;
    setBulkConfirm(true);
    setBulkPreview(null);
    setBulkPreviewLoading(true);
    setError(null);
    try {
      const preview = await previewBulkDeleteAdminOrgUnits(ids);
      setBulkPreview(preview);
    } catch (err) {
      setBulkConfirm(false);
      setError(mapAdminOrgUnitsApiError(err, "Не удалось подготовить массовое удаление."));
    } finally {
      setBulkPreviewLoading(false);
    }
  }

  function closeBulkConfirm() {
    setBulkConfirm(false);
    setBulkPreview(null);
    setBulkPreviewLoading(false);
  }

  async function confirmBulkDelete() {
    const ids = Array.from(selectedIds);
    if (!ids.length) return;
    closeBulkConfirm();
    setError(null);
    try {
      const result = await bulkDeleteAdminOrgUnits(ids);
      const rows = buildBulkDeleteResultRows(result, unitNameById);
      setBulkResults(rows);
      setSuccess(formatBulkDeleteSummary(result));
      setSelectedIds((prev) => {
        const next = new Set(prev);
        for (const deletedId of result.deleted_ids) next.delete(deletedId);
        return next;
      });
      await loadItems();
    } catch (err) {
      setError(mapAdminOrgUnitsApiError(err, "Массовое удаление не выполнено."));
    }
  }

  function closeBulkResults() {
    setBulkResults(null);
    void loadItems();
  }

  return (
    <div className="space-y-4" data-testid="org-units-admin-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Справочник подразделений</h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Административный CRUD с контролем зависимостей.{" "}
            <Link href="/admin/system" className="underline">
              Кабинет системного администратора
            </Link>
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
          data-testid="org-units-create-btn"
        >
          Создать
        </button>
      </div>

      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      <div className="grid gap-3 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 md:grid-cols-2 lg:grid-cols-4">
        <label className="text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Поиск</span>
          <input
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            className="w-full rounded-lg border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
            placeholder="Название, код или ID"
            data-testid="org-units-filter-search"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Статус</span>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as typeof status)}
            className="w-full rounded-lg border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
            data-testid="org-units-filter-status"
          >
            <option value="all">Все</option>
            <option value="active">Активные</option>
            <option value="inactive">Неактивные</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Группа отделений</span>
          <select
            value={orgGroupId}
            onChange={(e) => setOrgGroupId(e.target.value)}
            className="w-full rounded-lg border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">Все</option>
            {groups.map((g) => (
              <option key={g.group_id} value={String(g.group_id)}>
                {g.group_name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Родитель</span>
          <select
            value={parentFilter}
            onChange={(e) => setParentFilter(e.target.value)}
            className="w-full rounded-lg border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">Все</option>
            {items.map((u) => (
              <option key={u.unit_id} value={String(u.unit_id)}>
                {u.name} (#{u.unit_id})
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={rootsOnly} onChange={(e) => setRootsOnly(e.target.checked)} />
          Только корневые
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={withoutEmployees}
            onChange={(e) => setWithoutEmployees(e.target.checked)}
          />
          Без сотрудников
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={deletableOnly}
            onChange={(e) => setDeletableOnly(e.target.checked)}
            data-testid="org-units-filter-deletable"
          />
          Только удаляемые
        </label>
        <div className="flex items-end gap-2">
          <button
            type="button"
            onClick={() => void loadItems()}
            className="rounded-lg border border-zinc-300 px-3 py-1 text-sm dark:border-zinc-600"
          >
            Обновить
          </button>
          <span className="text-sm text-zinc-600 dark:text-zinc-400" data-testid="org-units-selected-count">
            Выбрано: {selectedIds.size}
          </span>
          <button
            type="button"
            onClick={() => void openBulkConfirm()}
            disabled={selectedIds.size === 0}
            className="rounded-lg bg-red-600 px-3 py-1 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="org-units-bulk-delete-btn"
          >
            Удалить выбранные ({selectedIds.size})
          </button>
        </div>
      </div>

      {bulkResults ? (
        <div
          className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950"
          data-testid="org-units-bulk-results"
          role="dialog"
          aria-modal="true"
        >
          <div className="flex items-start justify-between gap-3">
            <h3 className="text-base font-semibold">Результаты массового удаления</h3>
            <button
              type="button"
              onClick={closeBulkResults}
              className="rounded-lg border border-zinc-300 px-3 py-1 text-sm dark:border-zinc-600"
              data-testid="org-units-bulk-results-close"
            >
              Закрыть
            </button>
          </div>

          {bulkResults.deleted.length > 0 ? (
            <section className="mt-4">
              <h4 className="text-sm font-medium text-emerald-700 dark:text-emerald-400">Удалено</h4>
              <ul className="mt-2 space-y-2 text-sm">
                {bulkResults.deleted.map((row) => (
                  <li
                    key={`deleted-${row.unit_id}`}
                    className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 dark:border-emerald-900 dark:bg-emerald-950/30"
                    data-testid={`bulk-result-deleted-${row.unit_id}`}
                  >
                    <div className="font-medium">
                      {row.name} <span className="text-zinc-500">(ID {row.unit_id})</span>
                    </div>
                    <div className="text-emerald-700 dark:text-emerald-300">Удалено</div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {bulkResults.failed.length > 0 ? (
            <section className="mt-4">
              <h4 className="text-sm font-medium text-amber-700 dark:text-amber-400">Не удалено</h4>
              <ul className="mt-2 space-y-2 text-sm">
                {bulkResults.failed.map((row) => (
                  <li
                    key={`failed-${row.unit_id}`}
                    className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 dark:border-amber-900 dark:bg-amber-950/30"
                    data-testid={`bulk-result-failed-${row.unit_id}`}
                  >
                    <div className="font-medium">
                      {row.name} <span className="text-zinc-500">(ID {row.unit_id})</span>
                    </div>
                    <div className="text-amber-800 dark:text-amber-200">
                      {row.message ??
                        (row.reason_code === "ORG_UNIT_HAS_DEPENDENCIES"
                          ? "Заблокировано: есть зависимости"
                          : row.reason_code === "SUBTREE_HAS_DEPENDENCIES"
                            ? "Заблокировано: есть зависимости в поддереве"
                            : `Ошибка: ${row.reason_code ?? "неизвестная ошибка"}`)}
                    </div>
                    {row.dependencies && Object.keys(row.dependencies).length > 0 ? (
                      <ul className="mt-1 list-disc pl-5 text-zinc-700 dark:text-zinc-300">
                        {formatDependencyList(row.dependencies).map((line) => (
                          <li key={line}>{line}</li>
                        ))}
                      </ul>
                    ) : null}
                    {row.blocked_units && row.blocked_units.length > 0 ? (
                      <ul className="mt-2 space-y-2 text-xs">
                        {row.blocked_units.map((blocked) => (
                          <li key={`blocked-${row.unit_id}-${blocked.id}`}>
                            <div className="font-medium">
                              {blocked.name} <span className="text-zinc-500">(ID {blocked.id})</span>
                            </div>
                            <ul className="mt-1 list-disc pl-5">
                              {formatDependencyList(blocked.dependencies).map((line) => (
                                <li key={`${blocked.id}-${line}`}>{line}</li>
                              ))}
                            </ul>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full text-sm" data-testid="org-units-table">
          <thead className="bg-zinc-100 text-left dark:bg-zinc-900">
            <tr>
              <th className="px-2 py-2">
                <input
                  type="checkbox"
                  checked={allCurrentPageSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = someCurrentPageSelected;
                  }}
                  onChange={toggleSelectAllCurrentPage}
                  aria-label="Выбрать все на текущей странице"
                  data-testid="org-units-select-all-page"
                />
              </th>
              <th className="px-2 py-2">ID</th>
              <th className="px-2 py-2">Наименование</th>
              <th className="px-2 py-2">Код</th>
              <th className="px-2 py-2">Группа</th>
              <th className="px-2 py-2">Родитель</th>
              <th className="px-2 py-2">Статус</th>
              <th className="px-2 py-2">Дети</th>
              <th className="px-2 py-2">Сотрудники</th>
              <th className="px-2 py-2">Действия</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={10} className="px-3 py-4 text-zinc-500">
                  Загрузка…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-3 py-4 text-zinc-500">
                  Нет записей ({total})
                </td>
              </tr>
            ) : (
              items.map((unit) => (
                <tr key={unit.unit_id} className="border-t border-zinc-200 dark:border-zinc-800">
                  <td className="px-2 py-2">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(unit.unit_id)}
                      onChange={() => toggleSelected(unit.unit_id)}
                      data-testid={`org-unit-select-${unit.unit_id}`}
                    />
                  </td>
                  <td className="px-2 py-2">{unit.unit_id}</td>
                  <td className="px-2 py-2">{unit.name}</td>
                  <td className="px-2 py-2">{unit.code ?? "—"}</td>
                  <td className="px-2 py-2">
                    {resolveGroupLabel(unit.group_id, unit.group_name, groupLabelById)}
                  </td>
                  <td className="px-2 py-2">
                    {unit.parent_name ? `${unit.parent_name} (#${unit.parent_unit_id})` : "—"}
                  </td>
                  <td className="px-2 py-2">
                    {unit.is_active ? recordStatusLabel("active") : recordStatusLabel("inactive")}
                  </td>
                  <td className="px-2 py-2">{unit.child_count ?? 0}</td>
                  <td className="px-2 py-2">{unit.active_employee_count ?? 0}</td>
                  <td className="px-2 py-2">
                    <div className="flex flex-wrap items-center gap-2" data-testid={`org-unit-actions-${unit.unit_id}`}>
                      <button
                        type="button"
                        className={ACTION_BTN}
                        onClick={() => openView(unit)}
                        data-testid={`org-unit-view-${unit.unit_id}`}
                      >
                        Просмотр
                      </button>
                      <button
                        type="button"
                        className={ACTION_BTN}
                        onClick={() => openEdit(unit)}
                        data-testid={`org-unit-edit-${unit.unit_id}`}
                      >
                        Редактировать
                      </button>
                      <button
                        type="button"
                        className={ACTION_BTN}
                        onClick={() => void toggleActive(unit)}
                        data-testid={`org-unit-toggle-active-${unit.unit_id}`}
                      >
                        {unit.is_active ? "Деактивировать" : "Активировать"}
                      </button>
                      <button
                        type="button"
                        className={ACTION_BTN_DANGER}
                        onClick={() => void handleDeleteAttempt(unit)}
                        data-testid={`org-unit-delete-${unit.unit_id}`}
                      >
                        Удалить
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between gap-3 text-sm">
        <span data-testid="org-units-pagination-info">
          Страница {page} из {totalPages} (всего {total})
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={offset === 0 || loading}
            onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
            className="rounded-lg border border-zinc-300 px-3 py-1 disabled:opacity-50 dark:border-zinc-600"
            data-testid="org-units-page-prev"
          >
            Назад
          </button>
          <button
            type="button"
            disabled={offset + PAGE_SIZE >= total || loading}
            onClick={() => setOffset((value) => value + PAGE_SIZE)}
            className="rounded-lg border border-zinc-300 px-3 py-1 disabled:opacity-50 dark:border-zinc-600"
            data-testid="org-units-page-next"
          >
            Вперёд
          </button>
        </div>
      </div>

      {drawerMode ? (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/30">
          <div className="h-full w-full max-w-md overflow-y-auto border-l border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                {drawerMode === "create"
                  ? "Создание подразделения"
                  : drawerMode === "edit"
                    ? "Редактирование"
                    : "Просмотр"}
              </h2>
              <button type="button" onClick={() => setDrawerMode(null)} className="text-sm underline">
                Закрыть
              </button>
            </div>

            {drawerMode === "view" && activeUnit ? (
              <dl className="space-y-2 text-sm">
                <div>
                  <dt className="text-zinc-500">ID</dt>
                  <dd>{activeUnit.unit_id}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Наименование</dt>
                  <dd>{activeUnit.name}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Код</dt>
                  <dd>{activeUnit.code ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Группа</dt>
                  <dd>
                    {resolveGroupLabel(activeUnit.group_id, activeUnit.group_name, groupLabelById)}
                  </dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Родитель</dt>
                  <dd>{activeUnit.parent_name ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Статус</dt>
                  <dd>{activeUnit.is_active ? recordStatusLabel("active") : recordStatusLabel("inactive")}</dd>
                </div>
              </dl>
            ) : (
              <form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  void handleSave();
                }}
              >
                {formError ? (
                  <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200" data-testid="org-unit-form-error">
                    {formError}
                  </p>
                ) : null}
                <label className="block text-sm">
                  <span className="mb-1 block">Наименование *</span>
                  <input
                    required
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    className="w-full rounded-lg border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
                    data-testid="org-unit-form-name"
                  />
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block">Код</span>
                  <input
                    value={form.code}
                    onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
                    className="w-full rounded-lg border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
                  />
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block">Группа отделений *</span>
                  <select
                    required
                    value={form.group_id}
                    onChange={(e) => setForm((f) => ({ ...f, group_id: e.target.value }))}
                    disabled={groupInheritedFromParent != null}
                    className="w-full rounded-lg border border-zinc-300 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-900"
                    data-testid="org-unit-form-group"
                  >
                    {groups.map((g) => (
                      <option key={g.group_id} value={String(g.group_id)}>
                        {g.group_name}
                      </option>
                    ))}
                  </select>
                  {groupInheritedFromParent != null ? (
                    <span className="mt-1 block text-xs text-zinc-500">
                      Группа наследуется от родительского подразделения.
                    </span>
                  ) : null}
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block">Родительское подразделение</span>
                  <select
                    required={drawerMode === "edit" && activeUnit?.parent_unit_id != null}
                    value={form.parent_unit_id}
                    onChange={(e) => handleParentChange(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
                    data-testid="org-unit-form-parent"
                  >
                    {allowNoParent ? (
                      <option value="">
                        {drawerMode === "create" ? "— выберите родителя —" : "— корень / без родителя —"}
                      </option>
                    ) : (
                      <option value="" disabled>
                        — выберите родителя —
                      </option>
                    )}
                    {parentOptions.map((u) => (
                      <option key={u.unit_id} value={String(u.unit_id)}>
                        {u.name} (#{u.unit_id})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                  />
                  Активное подразделение
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.allow_duplicate}
                    onChange={(e) => setForm((f) => ({ ...f, allow_duplicate: e.target.checked }))}
                  />
                  Разрешить дубль имени у того же родителя
                </label>
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
                  data-testid="org-unit-form-save"
                >
                  {saving ? "Сохранение…" : "Сохранить"}
                </button>
              </form>
            )}
          </div>
        </div>
      ) : null}

      {dependencyDialog ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
          data-testid="org-unit-dependency-dialog"
        >
          <div className="w-full max-w-lg rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-700 dark:bg-zinc-900">
            <h3 className="text-lg font-semibold">Удаление невозможно</h3>
            <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
              Подразделение «{dependencyDialog.unit.name}» (ID {dependencyDialog.unit.unit_id}) используется в
              системе.
            </p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
              {formatDependencyList(dependencyDialog.deps.dependencies).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="rounded-lg border px-3 py-1 text-sm" onClick={() => setDependencyDialog(null)}>
                Закрыть
              </button>
              <button
                type="button"
                className="rounded-lg bg-amber-600 px-3 py-1 text-sm text-white"
                onClick={() => void handleDeactivateFromDialog()}
                data-testid="org-unit-deactivate-instead-btn"
              >
                Деактивировать
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        open={deleteConfirm != null}
        title="Подтвердите удаление"
        message={
          deleteConfirm
            ? `Удалить подразделение «${deleteConfirm.name}» (ID ${deleteConfirm.unit_id})? Действие необратимо.`
            : ""
        }
        confirmLabel="Удалить"
        onConfirm={() => void confirmDelete()}
        onCancel={() => setDeleteConfirm(null)}
      />

      <ConfirmDialog
        open={bulkConfirm}
        title="Массовое удаление"
        message={
          bulkPreviewLoading
            ? "Подготовка списка подразделений для удаления…"
            : bulkPreview
              ? buildBulkDeleteConfirmMessage(bulkPreview)
              : `Удалить ${selectedIds.size} выбранных подразделений? Действие необратимо.`
        }
        details={
          bulkPreview && !bulkPreviewLoading ? (
            <div className="space-y-3">
              <div>
                <h4 className="font-medium text-zinc-800 dark:text-zinc-200">Выбранные подразделения</h4>
                <ul
                  className="mt-1 max-h-32 list-disc space-y-1 overflow-y-auto pl-5 text-zinc-700 dark:text-zinc-300"
                  data-testid="org-units-bulk-confirm-list"
                >
                  {bulkPreview.roots.map((root) => (
                    <li key={root.id}>
                      {root.name} <span className="text-zinc-500">(ID {root.id})</span>
                    </li>
                  ))}
                </ul>
              </div>
              {bulkPreview.roots.some((root) => root.descendants.length > 0) ? (
                <div>
                  <h4 className="font-medium text-red-700 dark:text-red-400">
                    Также будут удалены дочерние подразделения
                  </h4>
                  <ul
                    className="mt-1 max-h-40 list-disc space-y-1 overflow-y-auto pl-5 text-zinc-700 dark:text-zinc-300"
                    data-testid="org-units-bulk-confirm-descendants"
                  >
                    {bulkPreview.roots.flatMap((root) =>
                      root.descendants.map((child) => (
                        <li key={`${root.id}-${child.id}`}>
                          {child.name} <span className="text-zinc-500">(ID {child.id})</span>
                        </li>
                      )),
                    )}
                  </ul>
                </div>
              ) : null}
              {bulkPreview.skipped_as_covered.length > 0 ? (
                <p className="text-xs text-zinc-500" data-testid="org-units-bulk-confirm-covered-note">
                  {bulkPreview.skipped_as_covered.length} подразделений будут удалены вместе с выбранным
                  родителем и не обрабатываются отдельно.
                </p>
              ) : null}
            </div>
          ) : selectedUnitsForConfirm.length > 0 && !bulkPreviewLoading ? (
            <ul
              className="max-h-48 list-disc space-y-1 overflow-y-auto pl-5 text-zinc-700 dark:text-zinc-300"
              data-testid="org-units-bulk-confirm-list"
            >
              {selectedUnitsForConfirm.map((unit) => (
                <li key={unit.unit_id}>
                  {unit.name} <span className="text-zinc-500">(ID {unit.unit_id})</span>
                </li>
              ))}
            </ul>
          ) : null
        }
        confirmLabel="Удалить выбранные"
        confirmDisabled={bulkPreviewLoading || bulkPreview == null}
        onConfirm={() => void confirmBulkDelete()}
        onCancel={closeBulkConfirm}
      />
    </div>
  );
}
