"use client";

import * as React from "react";
import Link from "next/link";

import EmployeeAccountSections from "../../employees/_components/EmployeeAccountSections";
import { buildEmployeeCardAccessHref } from "@/lib/employeeCardNav";
import type { EnrollEmployeeResponse, NormalizedRecord } from "../_lib/importApi.client";

type Props = {
  employeeId: number;
  enrollResult: EnrollEmployeeResponse;
  record: NormalizedRecord;
  batchFileName?: string;
};

function ProvenanceChain({
  record,
  batchFileName,
  employeeId,
  linkedRecordIds,
}: {
  record: NormalizedRecord;
  batchFileName?: string;
  employeeId: number;
  linkedRecordIds?: number[];
}) {
  const batchLabel = batchFileName
    ? `${batchFileName} (#${record.batch_id})`
    : `Batch #${record.batch_id}`;
  return (
    <div className="space-y-1 font-mono text-xs text-zinc-600 dark:text-zinc-400">
      <div>{batchLabel}</div>
      <div className="pl-3">└─ Row #{record.row_id}</div>
      <div className="pl-6">└─ Normalized #{record.record_id} ← текущая</div>
      {(linkedRecordIds ?? [])
        .filter((id) => id !== record.record_id)
        .map((id) => (
          <div key={id} className="pl-6">
            └─ Normalized #{id} (тот же ИИН)
          </div>
        ))}
      <div className="pl-9 text-green-700 dark:text-green-300">└─ Employee #{employeeId} ✓</div>
    </div>
  );
}

function CompletedItem({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2 text-sm text-green-900 dark:text-green-100">
      <span aria-hidden="true" className="font-semibold">
        ✓
      </span>
      <span>{children}</span>
    </li>
  );
}

/** @deprecated Use buildEmployeeCardAccessHref from @/lib/employeeCardNav */
export function buildImportCardAccountHref(employeeId: number | string): string {
  return buildEmployeeCardAccessHref(employeeId);
}

export default function EnrollmentCompletionPanel({
  employeeId,
  enrollResult,
  record,
  batchFileName,
}: Props) {
  const linkedCount = enrollResult.linked_records_count ?? 0;
  const employeeIdStr = String(employeeId);

  return (
    <section className="space-y-4 rounded-lg border border-green-200 bg-green-50/60 p-4 dark:border-green-900 dark:bg-green-950/30">
      <div>
        <h3 className="text-sm font-semibold text-green-900 dark:text-green-100">
          ✓ Сотрудник создан · ID {employeeId}
        </h3>
        <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
          Импорт → Зачисление → Добавление в персонал завершены. Следующий шаг жизненного цикла — доступ к
          Corpsite.
        </p>
      </div>

      <div className="rounded-lg border border-green-200/80 bg-white/70 p-3 dark:border-green-900/60 dark:bg-zinc-950/40">
        <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">Выполнено</div>
        <ul className="mt-2 space-y-1">
          <CompletedItem>Сотрудник добавлен в персонал</CompletedItem>
          <CompletedItem>
            Привязка HR-записей
            {linkedCount > 0 ? ` (${linkedCount})` : ""}
          </CompletedItem>
          <CompletedItem>Контакт сотрудника</CompletedItem>
        </ul>
      </div>

      <div className="rounded-lg border border-amber-200 bg-amber-50/80 p-3 dark:border-amber-900/60 dark:bg-amber-950/20">
        <div className="text-xs font-medium uppercase tracking-wide text-amber-800 dark:text-amber-200">
          Следующий шаг
        </div>
        <p className="mt-1 text-sm text-amber-950 dark:text-amber-100">
          Учётная запись Corpsite создаётся отдельно и нужна для входа в систему.
        </p>
        <div className="mt-4 border-t border-amber-200/80 pt-4 dark:border-amber-900/50">
          <EmployeeAccountSections employeeId={employeeIdStr} showEvents={false} showTelegram={false} />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Link
          href={buildEmployeeCardAccessHref(employeeId)}
          className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          Открыть карточку сотрудника
        </Link>
        <Link
          href={`/directory/staff?employeeId=${employeeId}`}
          className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
        >
          Быстрый просмотр в «Персонал»
        </Link>
      </div>

      <ProvenanceChain
        record={record}
        batchFileName={batchFileName}
        employeeId={employeeId}
        linkedRecordIds={enrollResult.linked_record_ids}
      />
    </section>
  );
}
