// FILE: corpsite-ui/app/directory/personnel/page.tsx
import EmployeesPageClient from "../employees/_components/EmployeesPageClient";
import type { EmployeesFilters } from "../employees/_lib/query";
import type { Department, Position, EmployeesResponse } from "../employees/_lib/types";

export const dynamic = "force-dynamic";

export default function PersonnelPage() {
  const initialFilters: EmployeesFilters = {
    status: "all",
    limit: 50,
    offset: 0,
  };

  const initialDepartments: Department[] = [];
  const initialPositions: Position[] = [];
  const initialEmployees: EmployeesResponse = { items: [], total: 0 };

  return (
    <EmployeesPageClient
      pageTitle="Персонал"
      initialFilters={initialFilters}
      initialDepartments={initialDepartments}
      initialPositions={initialPositions}
      initialEmployees={initialEmployees}
      initialError={null}
    />
  );
}