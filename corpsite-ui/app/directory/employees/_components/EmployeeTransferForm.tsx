// FILE: corpsite-ui/app/directory/employees/_components/EmployeeTransferForm.tsx
"use client";

import * as React from "react";

import type { EmployeeDetails } from "../_lib/types";
import { getEmployees, getPositions } from "../_lib/api.client";
import { getOrgUnitsTree, type TreeNode } from "../../org-units/_lib/api.client";

export type OrgUnitOption = {
  id: number;
  label: string;
};

export type PositionOption = {
  id: number;
  label: string;
};

export type EmployeeTransferFormValues = {
  to_org_unit_id: string;
  to_position_id: string;
  effective_date: string;
  order_ref: string;
  comment: string;
};

type EmployeeTransferFormProps = {
  details: EmployeeDetails;
  initialToOrgUnitId?: string;
  saving?: boolean;
  error?: string | null;
  onSubmit: (values: EmployeeTransferFormValues) => Promise<void> | void;
  onCancel: () => void;
};

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function flattenOrgUnits(nodes: TreeNode[], depth = 0): OrgUnitOption[] {
  const out: OrgUnitOption[] = [];
  for (const node of nodes) {
    const unitId = Number(node.unit_id ?? node.id);
    if (Number.isFinite(unitId) && unitId > 0) {
      const name = String(node.name ?? node.name_ru ?? `#${unitId}`).trim();
      out.push({ id: unitId, label: `${"— ".repeat(depth)}${name}` });
    }
    if (Array.isArray(node.children) && node.children.length > 0) {
      out.push(...flattenOrgUnits(node.children, depth + 1));
    }
  }
  return out;
}

function currentOrgUnitLabel(details: EmployeeDetails): string {
  const d = details as Record<string, unknown>;
  const orgUnit = d.org_unit as { name?: string } | null | undefined;
  const department = d.department as { name?: string } | null | undefined;
  return (
    String(orgUnit?.name ?? d.org_unit_name ?? department?.name ?? d.department_name ?? "").trim() || "—"
  );
}

function currentPositionId(details: EmployeeDetails): string {
  const d = details as Record<string, unknown>;
  const position = d.position as { id?: number | null } | null | undefined;
  const id = Number(position?.id ?? d.position_id ?? 0);
  return Number.isFinite(id) && id > 0 ? String(id) : "";
}

function currentPositionLabel(details: EmployeeDetails): string {
  const d = details as Record<string, unknown>;
  const position = d.position as { name?: string } | null | undefined;
  return String(position?.name ?? d.position_name ?? "").trim() || "—";
}

function employeePositionId(item: { position?: { id?: number | null } | null }): number {
  const id = Number(item?.position?.id ?? 0);
  return Number.isFinite(id) && id > 0 ? id : 0;
}

function normalizePositionOptions(raw: unknown): PositionOption[] {
  const items = Array.isArray(raw)
    ? raw
    : raw && typeof raw === "object" && Array.isArray((raw as { items?: unknown[] }).items)
      ? (raw as { items: unknown[] }).items
      : [];

  return items
    .map((p: Record<string, unknown>) => {
      const id = Number(p?.position_id ?? p?.id ?? 0);
      const label = String(p?.name ?? `#${id}`).trim();
      return { id, label } as PositionOption;
    })
    .filter((p) => Number.isFinite(p.id) && p.id > 0)
    .sort((a, b) => a.label.localeCompare(b.label, "ru"));
}

function buildInitialValues(details: EmployeeDetails, initialToOrgUnitId?: string): EmployeeTransferFormValues {
  return {
    to_org_unit_id: String(initialToOrgUnitId ?? "").trim(),
    to_position_id: currentPositionId(details),
    effective_date: todayIsoDate(),
    order_ref: "",
    comment: "",
  };
}

export default function EmployeeTransferForm({
  details,
  initialToOrgUnitId,
  saving = false,
  error = null,
  onSubmit,
  onCancel,
}: EmployeeTransferFormProps) {
  const [values, setValues] = React.useState<EmployeeTransferFormValues>(() =>
    buildInitialValues(details, initialToOrgUnitId)
  );
  const [orgUnitOptions, setOrgUnitOptions] = React.useState<OrgUnitOption[]>([]);
  const [orgUnitsLoading, setOrgUnitsLoading] = React.useState(false);
  const [allPositionOptions, setAllPositionOptions] = React.useState<PositionOption[]>([]);
  const [unitPositionIds, setUnitPositionIds] = React.useState<Set<number> | null>(null);
  const [unitPositionsLoading, setUnitPositionsLoading] = React.useState(false);
  const [showAllPositions, setShowAllPositions] = React.useState(false);

  const displayFio = String(
    (details as Record<string, unknown>)?.fio ??
      (details as Record<string, unknown>)?.full_name ??
      "Сотрудник"
  ).trim();

  React.useEffect(() => {
    setValues(buildInitialValues(details, initialToOrgUnitId));
    setShowAllPositions(false);
  }, [details, initialToOrgUnitId]);

  React.useEffect(() => {
    let cancelled = false;
    setOrgUnitsLoading(true);

    void (async () => {
      try {
        const tree = await getOrgUnitsTree({});
        if (cancelled) return;
        setOrgUnitOptions(flattenOrgUnits(tree.items ?? []));
      } catch {
        if (!cancelled) setOrgUnitOptions([]);
      } finally {
        if (!cancelled) setOrgUnitsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const raw = await getPositions({ limit: 1000, offset: 0 });
        if (cancelled) return;
        setAllPositionOptions(normalizePositionOptions(raw));
      } catch {
        if (!cancelled) setAllPositionOptions([]);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    setShowAllPositions(false);
  }, [values.to_org_unit_id]);

  React.useEffect(() => {
    const unitId = String(values.to_org_unit_id ?? "").trim();
    if (!unitId) {
      setUnitPositionIds(null);
      setUnitPositionsLoading(false);
      return;
    }

    let cancelled = false;
    setUnitPositionsLoading(true);

    void (async () => {
      try {
        const res = await getEmployees({
          status: "all",
          org_unit_id: unitId,
          include_children: false,
          limit: 200,
          offset: 0,
        });
        if (cancelled) return;

        const ids = new Set<number>();
        for (const item of res.items ?? []) {
          const pid = employeePositionId(item);
          if (pid > 0) ids.add(pid);
        }
        setUnitPositionIds(ids);
      } catch {
        if (!cancelled) setUnitPositionIds(new Set());
      } finally {
        if (!cancelled) setUnitPositionsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [values.to_org_unit_id]);

  const sortedAllPositions = React.useMemo(
    () => [...allPositionOptions].sort((a, b) => a.label.localeCompare(b.label, "ru")),
    [allPositionOptions]
  );

  const unitPositionGroups = React.useMemo(() => {
    const unitId = String(values.to_org_unit_id ?? "").trim();
    if (!unitId || !unitPositionIds || unitPositionIds.size === 0) {
      return { matched: [] as PositionOption[], rest: sortedAllPositions, hasMatches: false };
    }

    const matched = sortedAllPositions.filter((o) => unitPositionIds.has(o.id));
    const rest = sortedAllPositions.filter((o) => !unitPositionIds.has(o.id));
    return { matched, rest, hasMatches: matched.length > 0 };
  }, [sortedAllPositions, values.to_org_unit_id, unitPositionIds]);

  const showFilteredOnly = unitPositionGroups.hasMatches && !showAllPositions;

  const positionSelectOptions = React.useMemo(() => {
    if (!values.to_org_unit_id) return sortedAllPositions;

    if (showFilteredOnly) return unitPositionGroups.matched;
    if (unitPositionGroups.hasMatches && showAllPositions) return sortedAllPositions;
    if (unitPositionIds !== null && unitPositionIds.size === 0) return sortedAllPositions;
    return sortedAllPositions;
  }, [
    values.to_org_unit_id,
    showFilteredOnly,
    unitPositionGroups,
    sortedAllPositions,
    showAllPositions,
    unitPositionIds,
  ]);

  function handleOrgUnitChange(orgUnitId: string) {
    setShowAllPositions(false);
    setValues((prev) => ({ ...prev, to_org_unit_id: orgUnitId }));
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await onSubmit(values);
  }

  const readOnlyClass =
    "h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 px-4 py-2 text-sm text-zinc-700 dark:text-zinc-300 outline-none";
  const fieldClass =
    "h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400";

  return (
    <form onSubmit={handleSubmit} className="flex h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="flex items-start justify-between border-b border-zinc-200 dark:border-zinc-800 px-6 py-5">
        <div>
          <h2 className="text-2xl font-semibold leading-tight text-zinc-900 dark:text-zinc-50">Кадровый перевод</h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{displayFio}</p>
        </div>

        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-60"
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

          <section>
            <h3 className="mb-3 text-sm font-medium text-zinc-900 dark:text-zinc-50">Текущее место работы</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Отделение</label>
                <input type="text" readOnly value={currentOrgUnitLabel(details)} className={readOnlyClass} />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Должность</label>
                <input type="text" readOnly value={currentPositionLabel(details)} className={readOnlyClass} />
              </div>
            </div>
          </section>

          <section>
            <h3 className="mb-3 text-sm font-medium text-zinc-900 dark:text-zinc-50">Новое место работы</h3>
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <label htmlFor="transfer-to-org-unit" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                  Целевое отделение <span className="text-red-400">*</span>
                </label>
                <select
                  id="transfer-to-org-unit"
                  name="to_org_unit_id"
                  value={values.to_org_unit_id}
                  onChange={(e) => handleOrgUnitChange(e.target.value)}
                  disabled={orgUnitsLoading || saving}
                  className={fieldClass}
                  required
                >
                  <option value="" className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                    {orgUnitsLoading ? "Загрузка отделений…" : "Выберите отделение"}
                  </option>
                  {orgUnitOptions.map((opt) => (
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

              <div className="flex flex-col gap-2">
                <label htmlFor="transfer-to-position" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                  Целевая должность
                </label>
                <select
                  id="transfer-to-position"
                  name="to_position_id"
                  value={values.to_position_id}
                  onChange={(e) => setValues((prev) => ({ ...prev, to_position_id: e.target.value }))}
                  disabled={!values.to_org_unit_id || unitPositionsLoading || saving}
                  className={fieldClass}
                >
                  <option value="" className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                    {unitPositionsLoading && values.to_org_unit_id
                      ? "Загрузка должностей…"
                      : "Текущая должность (по умолчанию)"}
                  </option>
                  {positionSelectOptions.map((opt) => (
                    <option
                      key={opt.id}
                      value={String(opt.id)}
                      className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50"
                    >
                      {opt.label}
                    </option>
                  ))}
                </select>
                {unitPositionGroups.hasMatches && !showAllPositions && values.to_org_unit_id ? (
                  <button
                    type="button"
                    onClick={() => setShowAllPositions(true)}
                    className="self-start text-xs text-blue-600 transition hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300"
                  >
                    Показать все должности ({sortedAllPositions.length})
                  </button>
                ) : null}
                {unitPositionGroups.hasMatches && showAllPositions && values.to_org_unit_id ? (
                  <button
                    type="button"
                    onClick={() => setShowAllPositions(false)}
                    className="self-start text-xs text-blue-600 transition hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300"
                  >
                    Только должности отделения ({unitPositionGroups.matched.length})
                  </button>
                ) : null}
              </div>
            </div>
          </section>

          <section>
            <h3 className="mb-3 text-sm font-medium text-zinc-900 dark:text-zinc-50">Данные приказа</h3>
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <label htmlFor="transfer-effective-date" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                  Дата перевода <span className="text-red-400">*</span>
                </label>
                <input
                  id="transfer-effective-date"
                  name="effective_date"
                  type="date"
                  value={values.effective_date}
                  onChange={(e) => setValues((prev) => ({ ...prev, effective_date: e.target.value }))}
                  className={fieldClass}
                  required
                  disabled={saving}
                />
              </div>

              <div className="flex flex-col gap-2">
                <label htmlFor="transfer-order-ref" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                  Номер приказа
                </label>
                <input
                  id="transfer-order-ref"
                  name="order_ref"
                  type="text"
                  value={values.order_ref}
                  onChange={(e) => setValues((prev) => ({ ...prev, order_ref: e.target.value }))}
                  placeholder="Необязательно"
                  className={fieldClass}
                  disabled={saving}
                  autoComplete="off"
                />
              </div>

              <div className="flex flex-col gap-2">
                <label htmlFor="transfer-comment" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                  Комментарий
                </label>
                <textarea
                  id="transfer-comment"
                  name="comment"
                  value={values.comment}
                  onChange={(e) => setValues((prev) => ({ ...prev, comment: e.target.value }))}
                  placeholder="Необязательно"
                  rows={3}
                  className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400 disabled:opacity-60"
                  disabled={saving}
                />
              </div>
            </div>
          </section>
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Отмена
        </button>

        <button
          type="submit"
          disabled={saving || orgUnitsLoading}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? "Перевод…" : "Перевести"}
        </button>
      </div>
    </form>
  );
}
