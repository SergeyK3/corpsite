// corpsite-ui/app/directory/org/page.tsx
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

      <OrgPageClient />
    </div>
  );
}
