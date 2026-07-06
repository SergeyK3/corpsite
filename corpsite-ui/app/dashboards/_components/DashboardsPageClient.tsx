// FILE: corpsite-ui/app/dashboards/_components/DashboardsPageClient.tsx
"use client";

import PositionCabinetSectionShell from "@/components/PositionCabinetSectionShell";

export default function DashboardsPageClient() {
  return (
    <PositionCabinetSectionShell title="Дашборды">
      <div className="rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900/40 px-4 py-6 text-sm text-zinc-700 dark:text-zinc-300">
        <p className="font-medium text-zinc-900 dark:text-zinc-100">Раздел в подготовке</p>
        <p className="mt-2">
          Здесь будут дашборды должности. Содержимое относится к Position Cabinet и сохраняется при
          смене сотрудника, занимающего эту должность.
        </p>
      </div>
    </PositionCabinetSectionShell>
  );
}
