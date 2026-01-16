"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import type { Department, Position, EmployeeDetails, EmployeeListResponse } from "../_lib/types";
import type { EmployeesFilters } from "../_lib/query";
import { normalizeFilters, filtersToSearchParams } from "../_lib/query";
import { getEmployees } from "../_lib/api.client";

import EmployeesToolbar from "./EmployeesToolbar";
import EmployeesTable from "./EmployeesTable";
import EmployeeDrawer from "./EmployeeDrawer";
import TerminateEmployeeDialog from "./TerminateEmployeeDialog";

type Props = {
  initialFilters: EmployeesFilters;
  initialDepartments: Department[];
  initialPositions: Position[];
  initialEmployees: EmployeeListResponse;
};

export default function EmployeesPageClient({
  initialFilters,
  initialDepartments,
  initialPositions,
  initialEmployees,
}: Props) {
  const router = useRouter();
  const sp = useSearchParams();

  const [filters, setFilters] = useState<EmployeesFilters>(initialFilters);
  const [data, setData] = useState<EmployeeListResponse>(initialEmployees);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [terminateOpen, setTerminateOpen] = useState(false);
  const [terminateEmployee, setTerminateEmployee] = useState<EmployeeDetails | null>(null);

  const [isPending, startTransition] = useTransition();
  const [loadError, setLoadError] = useState<string | null>(null);

  const paging = useMemo(
    () => ({ limit: filters.limit ?? 50, offset: filters.offset ?? 0 }),
    [filters.limit, filters.offset]
  );

  // Sync local filters when URL changes (back/forward)
  useEffect(() => {
    const next = normalizeFilters({
      q: sp.get("q") ?? undefined,
      department_id: sp.get("department_id") ? Number(sp.get("department_id")) : undefined,
      position_id: sp.get("position_id") ? Number(sp.get("position_id")) : undefined,
      status: (sp.get("status") as any) ?? undefined,
      limit: sp.get("limit") ? Number(sp.get("limit")) : undefined,
      offset: sp.get("offset") ? Number(sp.get("offset")) : undefined,
    });
    setFilters(next);
    // Не подгружаем тут автоматически — обновление идёт через refreshList() при изменении фильтров пользователем.
    // Back/forward будет сопровождаться сменой URL, но данные могут отличаться — это допустимо, если вы не хотите
    // двойных запросов. Если нужно строго — снимем ограничение.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sp.toString()]);

  async function refreshList(nextFilters: EmployeesFilters) {
    setLoadError(null);
    startTransition(async () => {
      try {
        const resp = await getEmployees(nextFilters);
        setData(resp);
      } catch (e) {
        setLoadError("Не удалось загрузить список сотрудников.");
      }
    });
  }

  function pushFilters(next: EmployeesFilters) {
    const n = normalizeFilters(next);
    setFilters(n);
    const params = filtersToSearchParams(n);
    router.push(`/directory/employees?${params.toString()}`);
    refreshList(n);
  }

  function onChangeFilters(partial: Partial<EmployeesFilters>) {
    pushFilters({
      ...filters,
      ...partial,
      offset: 0, // при смене фильтров сбрасываем пагинацию
    });
  }

  function onReset() {
    pushFilters({ status: "active", limit: 50, offset: 0 });
  }

  function onOpenEmployee(employee_id: string) {
    setSelectedId(employee_id);
  }

  function onCloseDrawer() {
    setSelectedId(null);
  }

  function onOpenTerminate(details: EmployeeDetails) {
    setTerminateEmployee(details);
    setTerminateOpen(true);
  }

  function onCloseTerminate() {
    setTerminateOpen(false);
  }

  async function onTerminated() {
    setTerminateOpen(false);
    // обновляем список после успешного PATCH
    await refreshList(filters);
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Сотрудники</h1>
        <div className="text-sm text-gray-500">
          {isPending ? "Обновление…" : `Всего: ${data.total}`}
        </div>
      </div>

      <EmployeesToolbar
        filters={filters}
        departments={initialDepartments}
        positions={initialPositions}
        onChange={onChangeFilters}
        onReset={onReset}
      />

      {loadError ? (
        <div className="border rounded p-3 bg-white text-sm text-red-700">{loadError}</div>
      ) : null}

      <EmployeesTable
        items={data.items}
        total={data.total}
        limit={paging.limit}
        offset={paging.offset}
        loading={isPending}
        onOpenEmployee={onOpenEmployee}
        onChangePage={(nextOffset) => pushFilters({ ...filters, offset: nextOffset })}
      />

      <EmployeeDrawer
        employeeId={selectedId}
        open={!!selectedId}
        onClose={onCloseDrawer}
        onTerminate={onOpenTerminate}
      />

      <TerminateEmployeeDialog
        employee={terminateEmployee}
        open={terminateOpen}
        onClose={onCloseTerminate}
        onSubmitted={onTerminated}
      />
    </div>
  );
}
