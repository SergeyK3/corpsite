// FILE: corpsite-ui/app/directory/org/page.tsx
import * as React from "react";
import OrgPageClient from "./_components/OrgPageClient";

export default function OrgPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6">
        <div className="text-2xl font-semibold text-zinc-100">Оргструктура</div>
        <div className="mt-1 text-sm text-zinc-400">
          Выберите подразделение, чтобы увидеть список сотрудников.
        </div>
      </div>

      <React.Suspense
        fallback={
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-400">
            Загрузка…
          </div>
        }
      >
        <OrgPageClient />
      </React.Suspense>
    </div>
  );
}
