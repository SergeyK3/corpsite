"use client";

import Link from "next/link";

import { buildPersonalCardHref } from "@/lib/employeeCardNav";
import type { PersonnelLkRegistryItem } from "../_lib/personnelLkApi.client";
import {
  formatPersonnelLkRate,
  personnelLkRecordKindLabel,
  personnelLkStatusLabel,
} from "../_lib/personnelLkLabels";

type Props = {
  items: PersonnelLkRegistryItem[];
  loading: boolean;
  registryReturnHref: string;
  onOpenApplicant: (applicationId: number) => void;
};

const actionClass =
  "rounded-md border border-zinc-200 bg-zinc-100 px-2.5 py-1 text-[12px] leading-4 text-zinc-900 transition hover:bg-zinc-200 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-50 dark:hover:bg-zinc-700";

export default function PersonnelLkTable({
  items,
  loading,
  registryReturnHref,
  onOpenApplicant,
}: Props) {
  return (
    <div
      className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800"
      data-testid="personnel-lk-table"
    >
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr className="bg-zinc-100 text-left dark:bg-zinc-900">
              <th className="min-w-[260px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                ФИО
              </th>
              <th className="min-w-[140px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                ИИН
              </th>
              <th className="w-[140px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Тип
              </th>
              <th className="w-[100px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Ставка
              </th>
              <th className="min-w-[180px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Статус
              </th>
              <th className="w-[120px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Действие
              </th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-sm text-zinc-500">
                  {loading ? "Загрузка…" : "Записи не найдены."}
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr
                  key={`${item.record_kind}-${item.person_id}`}
                  data-testid={`personnel-lk-row-${item.record_kind}-${item.person_id}`}
                >
                  <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-900 dark:text-zinc-50">
                    {item.fio || "—"}
                  </td>
                  <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                    {item.iin || "—"}
                  </td>
                  <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                    {personnelLkRecordKindLabel(item.record_kind)}
                  </td>
                  <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                    {formatPersonnelLkRate(item.rate)}
                  </td>
                  <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                    {personnelLkStatusLabel(item)}
                  </td>
                  <td className="px-3 py-1.5">
                    {item.record_kind === "employee" ? (
                      <Link
                        href={buildPersonalCardHref({ personId: item.person_id }, { returnTo: registryReturnHref })}
                        className={actionClass}
                        data-testid={`personnel-lk-open-card-${item.person_id}`}
                      >
                        Открыть
                      </Link>
                    ) : item.active_application_id != null ? (
                      <button
                        type="button"
                        onClick={() => onOpenApplicant(item.active_application_id!)}
                        className={actionClass}
                        data-testid={`personnel-lk-open-application-${item.active_application_id}`}
                      >
                        Открыть
                      </button>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
