// corpsite-ui/app/directory/employees/[employee_id]/page.tsx

import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { getEmployeeById } from "../_lib/api.server";

type Props = {
  params: Promise<{
    employee_id: string;
  }>;
};

function dash(v: unknown): string {
  const s = (v ?? "").toString().trim();
  return s ? s : "—";
}

function fmtStatusRu(v?: string | null): string {
  const s = (v ?? "").toString().trim().toLowerCase();
  if (s === "active") return "Работает";
  if (s === "inactive") return "Не работает";
  return "Неизвестно";
}

function fmtDateRu(v?: string | null): string {
  const s = (v ?? "").toString().trim();
  if (!s) return "—";

  // Берём только дату, даже если прилетел datetime
  const d = s.slice(0, 10); // YYYY-MM-DD
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d);
  if (!m) return s;
  return `${m[3]}.${m[2]}.${m[1]}`;
}

function fmtDateToRu(v?: string | null): string {
  const s = (v ?? "").toString().trim();
  return s ? fmtDateRu(s) : "по настоящее время";
}

function fmtRate(v: unknown): string {
  if (v === null || v === undefined) return "—";
  const s = v.toString().trim();
  if (!s) return "—";
  const n = Number(s.replace(",", "."));
  if (Number.isFinite(n)) return n.toString().replace(".", ",");
  return s;
}

function CardSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border bg-white p-4">
      <h2 className="text-base font-semibold text-gray-900 mb-3">{title}</h2>
      {children}
    </section>
  );
}

function Field({ label, value }: { label: string; value?: ReactNode }) {
  return (
    <div className="rounded-xl border p-4">
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
  if (!emp) notFound();

  const deptName = emp.department?.name ?? null;
  const deptId = emp.department?.id ?? null;

  const posName = emp.position?.name ?? null;
  const posId = emp.position?.id ?? null;

  const fio = emp.fio ? emp.fio.toString().trim() : "";
  const title = fio ? fio : `Сотрудник ${dash(emp.id)}`;

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

      {/* Заголовок */}
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold text-gray-900">{title}</h1>
        <div className="text-sm text-gray-600">
          Табельный №: <span className="font-mono text-gray-900">{dash(emp.id)}</span> · Статус:{" "}
          <span className="text-gray-900">{fmtStatusRu(emp.status)}</span>
        </div>
      </div>

      {/* Организация */}
      <CardSection title="Организация">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field
            label="Отдел / подразделение"
            value={
              <span>
                {dash(deptName)}
                {deptId !== null && deptId !== undefined ? (
                  <span className="text-gray-500"> (id: {deptId})</span>
                ) : null}
              </span>
            }
          />
          <Field
            label="Должность"
            value={
              <span>
                {dash(posName)}
                {posId !== null && posId !== undefined ? (
                  <span className="text-gray-500"> (id: {posId})</span>
                ) : null}
              </span>
            }
          />
        </div>
      </CardSection>

      {/* Занятость */}
      <CardSection title="Занятость">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Ставка" value={fmtRate(emp.rate)} />
          <Field label="Период" value={`${fmtDateRu(emp.date_from)} — ${fmtDateToRu(emp.date_to)}`} />
          <Field label="Дата приёма" value={fmtDateRu(emp.date_from)} />
          <Field label="Дата увольнения / до" value={fmtDateToRu(emp.date_to)} />
        </div>
      </CardSection>

      {/* Идентификаторы */}
      <CardSection title="Идентификаторы">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Employee ID" value={<span className="font-mono">{dash(emp.id)}</span>} />
          <Field
            label="Источник данных"
            value={<span className="font-mono">{dash(emp.source?.relation)}</span>}
          />
        </div>
      </CardSection>
    </div>
  );
}
