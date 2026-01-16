// corpsite-ui/app/directory/employees/[employee_id]/page.tsx

import Link from "next/link";
import { getEmployeeById } from "../_lib/api.server";

type EmployeeDetail = {
  id: string;
  full_name: string;
  department?: { id: number; name: string };
  position?: { id: number; name: string };
  date_from: string | null;
  date_to: string | null;
  employment_rate: number | null;
  is_active: boolean;
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="text-gray-600 text-sm">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}

function fmt(v: string | null) {
  return v ?? "—";
}

export default async function EmployeeCardPage({
  params,
}: {
  params: { employee_id: string };
}) {
  const e = (await getEmployeeById(params.employee_id)) as EmployeeDetail;

  return (
    <main className="p-4 space-y-4">
      <div>
        <Link
          href="/directory/employees"
          className="underline text-blue-700 hover:text-blue-900"
        >
          ← Назад к списку
        </Link>
      </div>

      <h1 className="text-xl font-semibold">Карточка сотрудника</h1>

      <div className="border rounded bg-white p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Row label="Таб. №" value={e.id} />
          <Row label="Статус" value={e.is_active ? "Работает" : "Уволен"} />
          <div className="md:col-span-2">
            <Row label="ФИО" value={e.full_name} />
          </div>
          <Row label="Отдел" value={e.department?.name ?? "—"} />
          <Row label="Должность" value={e.position?.name ?? "—"} />
          <Row
            label="Ставка"
            value={e.employment_rate != null ? String(e.employment_rate) : "—"}
          />
          <Row label="Дата с" value={fmt(e.date_from)} />
          <Row label="Дата по" value={fmt(e.date_to)} />
        </div>
      </div>
    </main>
  );
}
