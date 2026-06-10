// FILE: corpsite-ui/app/directory/employees/_components/EmployeeCreateForm.tsx
"use client";

import * as React from "react";

import { getEmployees } from "../_lib/api.client";

export type OrgUnitOption = {
  id: number;
  label: string;
};

export type PositionOption = {
  id: number;
  label: string;
};

export type EmployeeCreateFormValues = {
  full_name: string;
  org_unit_id: string;
  position_id: string;
  date_from: string;
  employment_rate: string;
};

type EmployeeCreateFormProps = {
  initialValues: EmployeeCreateFormValues;
  orgUnitOptions: OrgUnitOption[];
  /** Полный справочник должностей; фильтрация по отделению — внутри формы. */
  positionOptions: PositionOption[];
  saving?: boolean;
  error?: string | null;
  onSubmit: (values: EmployeeCreateFormValues) => Promise<void> | void;
  onCancel: () => void;
};

function employeePositionId(item: { position?: { id?: number | null } | null }): number {
  const id = Number(item?.position?.id ?? 0);
  return Number.isFinite(id) && id > 0 ? id : 0;
}

function sortPositionOptions(opts: PositionOption[]): PositionOption[] {
  return [...opts].sort((a, b) => a.label.localeCompare(b.label, "ru"));
}

export default function EmployeeCreateForm({
  initialValues,
  orgUnitOptions,
  positionOptions,
  saving = false,
  error = null,
  onSubmit,
  onCancel,
}: EmployeeCreateFormProps) {
  const [values, setValues] = React.useState<EmployeeCreateFormValues>(initialValues);
  const [unitPositionIds, setUnitPositionIds] = React.useState<Set<number> | null>(null);
  const [unitPositionsLoading, setUnitPositionsLoading] = React.useState(false);
  const [showAllPositions, setShowAllPositions] = React.useState(false);

  React.useEffect(() => {
    setValues(initialValues);
  }, [initialValues]);

  React.useEffect(() => {
    setShowAllPositions(false);
  }, [values.org_unit_id]);

  // Должности, уже используемые сотрудниками выбранного отделения (org_unit_id).
  React.useEffect(() => {
    const unitId = String(values.org_unit_id ?? "").trim();
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
  }, [values.org_unit_id]);

  const sortedAllPositions = React.useMemo(
    () => sortPositionOptions(positionOptions),
    [positionOptions]
  );

  const unitPositionGroups = React.useMemo(() => {
    const unitId = String(values.org_unit_id ?? "").trim();
    if (!unitId || !unitPositionIds || unitPositionIds.size === 0) {
      return {
        matched: [] as PositionOption[],
        rest: sortedAllPositions,
        hasMatches: false,
      };
    }

    const matched = sortedAllPositions.filter((o) => unitPositionIds.has(o.id));
    const rest = sortedAllPositions.filter((o) => !unitPositionIds.has(o.id));
    return {
      matched,
      rest,
      hasMatches: matched.length > 0,
    };
  }, [sortedAllPositions, values.org_unit_id, unitPositionIds]);

  const showFilteredOnly = unitPositionGroups.hasMatches && !showAllPositions;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await onSubmit(values);
  }

  function handleOrgUnitChange(orgUnitId: string) {
    setShowAllPositions(false);
    setValues((prev) => ({ ...prev, org_unit_id: orgUnitId, position_id: "" }));
  }

  function renderPositionOptions() {
    if (showFilteredOnly) {
      return unitPositionGroups.matched.map((opt) => (
        <option
          key={opt.id}
          value={String(opt.id)}
          className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50"
        >
          {opt.label}
        </option>
      ));
    }

    if (unitPositionGroups.hasMatches && showAllPositions) {
      return (
        <>
          <optgroup label="В выбранном отделении">
            {unitPositionGroups.matched.map((opt) => (
              <option
                key={`unit-${opt.id}`}
                value={String(opt.id)}
                className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50"
              >
                {opt.label}
              </option>
            ))}
          </optgroup>
          {unitPositionGroups.rest.length > 0 && (
            <optgroup label="Прочие должности">
              {unitPositionGroups.rest.map((opt) => (
                <option
                  key={`all-${opt.id}`}
                  value={String(opt.id)}
                  className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50"
                >
                  {opt.label}
                </option>
              ))}
            </optgroup>
          )}
        </>
      );
    }

    return sortedAllPositions.map((opt) => (
      <option
        key={opt.id}
        value={String(opt.id)}
        className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50"
      >
        {opt.label}
      </option>
    ));
  }

  return (
    <form onSubmit={handleSubmit} className="flex h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="flex items-start justify-between border-b border-zinc-200 dark:border-zinc-800 px-6 py-5">
        <div>
          <h2 className="text-2xl font-semibold leading-tight text-zinc-900 dark:text-zinc-50">
            Создание записи
          </h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Персонал</p>
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
            <label htmlFor="employee-full-name" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              ФИО <span className="text-red-400">*</span>
            </label>
            <input
              id="employee-full-name"
              name="full_name"
              type="text"
              value={values.full_name}
              onChange={(e) => setValues((prev) => ({ ...prev, full_name: e.target.value }))}
              placeholder="Например: Сапарбаева Жайна"
              autoComplete="off"
              spellCheck={false}
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="employee-org-unit" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Отделение <span className="text-red-400">*</span>
            </label>
            <select
              id="employee-org-unit"
              name="org_unit_id"
              value={values.org_unit_id}
              onChange={(e) => handleOrgUnitChange(e.target.value)}
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
              required
            >
              <option value="" className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                Выберите отделение
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
            <label htmlFor="employee-position" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Должность <span className="text-red-400">*</span>
            </label>
            <select
              id="employee-position"
              name="position_id"
              value={values.position_id}
              onChange={(e) => setValues((prev) => ({ ...prev, position_id: e.target.value }))}
              disabled={unitPositionsLoading && Boolean(values.org_unit_id)}
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400 disabled:cursor-wait disabled:opacity-70"
              required
            >
              <option value="" className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                {unitPositionsLoading && values.org_unit_id
                  ? "Загрузка должностей отделения…"
                  : "Выберите должность"}
              </option>
              {renderPositionOptions()}
            </select>
            {unitPositionGroups.hasMatches && !showAllPositions && (
              <button
                type="button"
                onClick={() => setShowAllPositions(true)}
                className="self-start text-xs text-blue-600 transition hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300"
              >
                Показать все должности ({sortedAllPositions.length})
              </button>
            )}
            {unitPositionGroups.hasMatches && showAllPositions && (
              <button
                type="button"
                onClick={() => setShowAllPositions(false)}
                className="self-start text-xs text-blue-600 transition hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300"
              >
                Только должности отделения ({unitPositionGroups.matched.length})
              </button>
            )}
            {showFilteredOnly && (
              <p className="text-xs text-zinc-600 dark:text-zinc-400">
                Показаны должности, уже используемые в выбранном отделении ({unitPositionGroups.matched.length}).
              </p>
            )}
          </div>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <label htmlFor="employee-date-from" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                Дата приёма
              </label>
              <input
                id="employee-date-from"
                name="date_from"
                type="date"
                value={values.date_from}
                onChange={(e) => setValues((prev) => ({ ...prev, date_from: e.target.value }))}
                className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
              />
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="employee-rate" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                Ставка
              </label>
              <input
                id="employee-rate"
                name="employment_rate"
                type="number"
                min="0.01"
                max="2"
                step="0.01"
                value={values.employment_rate}
                onChange={(e) => setValues((prev) => ({ ...prev, employment_rate: e.target.value }))}
                className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
              />
            </div>
          </div>
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
          {saving ? "Сохранение..." : "Сохранить"}
        </button>
      </div>
    </form>
  );
}
