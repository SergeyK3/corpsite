"use client";

import * as React from "react";

import type { PprTrainingRecordResponse } from "../_lib/pprQueryTypes";
import { formatPersonnelDateRange } from "@/lib/personnelDateFormat";

type Props = {
  active: PprTrainingRecordResponse[];
  superseded: PprTrainingRecordResponse[];
  voided: PprTrainingRecordResponse[];
};

function TrainingRecordCard({ record }: { record: PprTrainingRecordResponse }) {
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800">
      <div className="font-medium text-zinc-900 dark:text-zinc-50">
        {record.title || "Обучение без названия"}
      </div>
      <dl className="mt-2 grid gap-1 text-xs text-zinc-600 dark:text-zinc-400 sm:grid-cols-2">
        <div>
          <dt className="inline">Вид: </dt>
          <dd className="inline">{record.training_kind}</dd>
        </div>
        {record.organization_name ? (
          <div>
            <dt className="inline">Организация: </dt>
            <dd className="inline">{record.organization_name}</dd>
          </div>
        ) : null}
        <div>
          <dt className="inline">Период: </dt>
          <dd className="inline">
            {formatPersonnelDateRange(record.started_at, record.completed_at, { precision: "year" })}
          </dd>
        </div>
        <div>
          <dt className="inline">Статус: </dt>
          <dd className="inline">{record.lifecycle_status}</dd>
        </div>
      </dl>
    </div>
  );
}

function CollapsibleGroup({
  title,
  records,
}: {
  title: string;
  records: PprTrainingRecordResponse[];
}) {
  const [open, setOpen] = React.useState(false);
  if (records.length === 0) return null;
  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-sm font-medium text-zinc-700 underline-offset-2 hover:underline dark:text-zinc-300"
        aria-expanded={open}
      >
        {title} ({records.length})
      </button>
      {open ? (
        <div className="space-y-2">
          {records.map((record) => (
            <TrainingRecordCard key={record.record_id ?? record.title} record={record} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function PprCardTrainingSection({ active, superseded, voided }: Props) {
  if (active.length === 0 && superseded.length === 0 && voided.length === 0) {
    return <p className="text-sm text-zinc-500">Записи об обучении отсутствуют.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Действующие записи</h3>
        {active.length === 0 ? (
          <p className="text-sm text-zinc-500">Нет действующих записей.</p>
        ) : (
          active.map((record) => <TrainingRecordCard key={record.record_id ?? record.title} record={record} />)
        )}
      </div>
      <CollapsibleGroup title="Заменённые записи" records={superseded} />
      <CollapsibleGroup title="Аннулированные записи" records={voided} />
    </div>
  );
}
