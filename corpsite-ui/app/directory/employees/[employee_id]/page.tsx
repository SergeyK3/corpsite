// corpsite-ui/app/directory/employees/[employee_id]/page.tsx

import Link from "next/link";
import { notFound } from "next/navigation";
import { getEmployeeById } from "../_lib/api.server";

type Props = {
  params: Promise<{
    employee_id: string;
  }>;
};

function fmtDate(v?: string | null): string {
  if (!v) return "—";
  const dt = new Date(v);
  if (Number.isNaN(dt.getTime())) return String(v);
  return dt.toLocaleDateString("ru-RU");
}

function statusRu(v?: string | null): string {
  const s = (v ?? "").toString().toLowerCase();
  if (s === "active") return "Работает";
  if (s === "inactive") return "Не работает";
  return "—";
}

function Field({ label, value }: { label: string; value?: React.ReactNode }) {
  return (
    <div className="bg-white rounded border p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
      <div className="mt-1 text-gray-900 font-medium">{value ?? "—"}</div>
    </div>
  );
}

export default async function EmployeeByIdPage({ params }: Props) {
  const { employee_id } = await params;

  const id = (employee_id ?? "").toString().trim();
  if (!id) notFound();

  // ВАЖНО: employee_id — строковый ключ (с ведущими нулями). НЕ приводить к Number.
  const emp = await getEmployeeById(id);

  if (!emp) {
    notFound();
  }

  const period = `${fmtDate(emp.date_from)} — ${fmtDate(emp.date_to)}`;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/directory/employees"
          className="text-blue-600 hover:text-blue-800 underline text-sm"
        >
          ← К списку сотрудников
        </Link>
      </div>

      <h1 className="text-2xl font-semibold text-gray-900">Сотрудник #{emp.id}</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="ФИО" value={emp.fio} />
        <Field label="Статус" value={statusRu(emp.status)} />

        <Field label="Отдел" value={emp.department?.name} />
        <Field label="Должность" value={emp.position?.name} />

        <Field label="Ставка" value={emp.rate ?? "—"} />
        <Field label="Период" value={period} />
      </div>
    </div>
  );
}
