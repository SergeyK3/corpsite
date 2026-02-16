// FILE: corpsite-ui/app/directory/employees/page.tsx

import EmployeesPageClient from "./_components/EmployeesPageClient";
import type { EmployeesFilters } from "./_lib/query";
import type { Department, Position, EmployeesResponse } from "./_lib/types";

export const dynamic = "force-dynamic";

export default function EmployeesPage() {
  const initialFilters: EmployeesFilters = {
    status: "all",
    limit: 50,
    offset: 0,
    // department_id / position_id / q не задаём (будут undefined)
  };

  const initialDepartments: Department[] = [];
  const initialPositions: Position[] = [];
  const initialEmployees: EmployeesResponse = { items: [], total: 0 };

  return (
    <EmployeesPageClient
      initialFilters={initialFilters}
      initialDepartments={initialDepartments}
      initialPositions={initialPositions}
      initialEmployees={initialEmployees}
      initialError={null}
    />
  );
}
