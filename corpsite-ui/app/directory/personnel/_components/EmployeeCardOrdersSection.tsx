"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  buildPersonnelOrdersHref,
  formatPersonnelOrderDate,
  listPersonnelOrders,
  mapPersonnelOrdersApiError,
  personnelOrderStatusLabel,
  type PersonnelOrderListItem,
} from "../_lib/personnelOrdersApi.client";

type Props = {
  employeeId: string;
};

function orderTypeLabel(code: string | null | undefined): string {
  const map: Record<string, string> = {
    HIRE: "Приём",
    TRANSFER: "Перевод",
    TERMINATION: "Увольнение",
    CONCURRENT_DUTY_START: "Совмещение (начало)",
    CONCURRENT_DUTY_END: "Совмещение (окончание)",
    COMPOSITE: "Составной",
  };
  const key = String(code || "").trim().toUpperCase();
  return map[key] || key || "Приказ";
}

export default function EmployeeCardOrdersSection({ employeeId }: Props) {
  const [items, setItems] = useState<PersonnelOrderListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const employeeNumericId = Number(employeeId);
  const ordersHref = buildPersonnelOrdersHref(
    Number.isFinite(employeeNumericId) && employeeNumericId > 0
      ? { employee_id: employeeNumericId }
      : {},
  );

  useEffect(() => {
    if (!Number.isFinite(employeeNumericId) || employeeNumericId <= 0) {
      setItems([]);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    void listPersonnelOrders({ employee_id: employeeNumericId, limit: 10, offset: 0 })
      .then((body) => {
        if (cancelled) return;
        setItems(Array.isArray(body.items) ? body.items : []);
      })
      .catch((e) => {
        if (cancelled) return;
        setItems([]);
        setError(mapPersonnelOrdersApiError(e, "Не удалось загрузить приказы сотрудника"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [employeeId, employeeNumericId]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Link
          href={ordersHref}
          className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-blue-500"
        >
          Журнал приказов сотрудника
        </Link>
        <Link
          href={ordersHref}
          className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm text-zinc-800 transition hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
        >
          Создать приказ
        </Link>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="text-sm text-zinc-500">Загрузка приказов…</div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-zinc-200 bg-zinc-50/80 px-3 py-3 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
          Приказов по этому сотруднику пока нет. Юридически значимые кадровые действия оформляются через
          кадровый приказ.
        </div>
      ) : (
        <ul className="divide-y divide-zinc-200 rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
          {items.map((row) => {
            const href = buildPersonnelOrdersHref({
              order_id: row.order_id,
              employee_id: employeeNumericId,
            });
            return (
              <li key={row.order_id}>
                <Link
                  href={href}
                  className="flex flex-wrap items-baseline justify-between gap-2 px-3 py-2.5 text-sm transition hover:bg-zinc-50 dark:hover:bg-zinc-900/50"
                >
                  <span className="font-medium text-zinc-900 dark:text-zinc-50">
                    {row.order_number ? `№ ${row.order_number}` : `Приказ #${row.order_id}`}
                    {row.order_date ? ` от ${formatPersonnelOrderDate(row.order_date)}` : ""}
                    {" · "}
                    {orderTypeLabel(row.order_type_code)}
                  </span>
                  <span className="text-xs text-zinc-500">{personnelOrderStatusLabel(row.status)}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}

      <p className="text-xs text-zinc-500">
        Кадровые действия (перевод, увольнение, совмещение) выполняются через приказ и не изменяют данные
        сотрудника напрямую из этого досье.
      </p>
    </div>
  );
}
