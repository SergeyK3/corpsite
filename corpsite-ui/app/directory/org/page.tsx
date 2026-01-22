// corpsite-ui/app/directory/org/page.tsx
import * as React from "react";
import OrgPageClient from "./_components/OrgPageClient";

export default function OrgPage() {
  return (
    <div className="space-y-4">
      <div className="bg-white rounded border p-4">
        <div className="text-lg font-semibold">Оргструктура</div>
        <div className="text-sm text-gray-600">
          Выберите подразделение слева, чтобы увидеть сотрудников справа.
        </div>
      </div>

      <React.Suspense fallback={<div className="rounded border bg-white p-4 text-sm text-gray-700">Загрузка…</div>}>
        <OrgPageClient />
      </React.Suspense>
    </div>
  );
}
