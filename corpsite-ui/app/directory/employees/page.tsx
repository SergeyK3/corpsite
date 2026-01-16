// corpsite-ui/app/directory/employees/page.tsx

import EmployeesPageClient from "./_components/EmployeesPageClient";
import { normalizeFilters, type EmployeesFilters } from "./_lib/query";
import { getEmployees, getDepartments, getPositions } from "./_lib/api.server";

type SearchParams = Record<string, string | string[] | undefined>;

function toStr(v: string | string[] | undefined): string | undefined {
  if (Array.isArray(v)) return v[0];
  return v;
}

function toInt(v: string | string[] | undefined): number | undefined {
  const s = toStr(v);
  if (!s) return undefined;
  const n = Number(s);
  return Number.isFinite(n) ? n : undefined;
}

export default async function EmployeesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;

  const rawFilters: Partial<EmployeesFilters> = {
    q: toStr(sp.q),
    department_id: toInt(sp.department_id),
    position_id: toInt(sp.position_id),
    status: (toStr(sp.status) as any) ?? undefined,
    limit: toInt(sp.limit),
    offset: toInt(sp.offset),
  };

  const filters = normalizeFilters(rawFilters);

  try {
    const [initialDepartments, initialPositions, initialEmployees] =
      await Promise.all([
        getDepartments(),
        getPositions(),
        getEmployees({
          q: filters.q,
          department_id: filters.department_id,
          position_id: filters.position_id,
          status: filters.status,
          limit: filters.limit,
          offset: filters.offset,
          sort: "full_name",
          order: "asc",
        }),
      ]);

    return (
      <EmployeesPageClient
        initialFilters={filters}
        initialDepartments={initialDepartments}
        initialPositions={initialPositions}
        initialEmployees={initialEmployees}
      />
    );
  } catch (e: any) {
    const msg = e?.message ? String(e.message) : "Directory SSR fetch failed";

    return (
      <EmployeesPageClient
        initialFilters={filters}
        initialDepartments={[]}
        initialPositions={[]}
        initialEmployees={{ items: [], total: 0 }}
        initialError={msg as any}
      />
    );
  }
}
