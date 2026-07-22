"use client";

import * as React from "react";

import type { PprRelativeRecordResponse } from "../_lib/pprQueryTypes";
import { formatPprDate, relationshipTypeLabel } from "../_lib/pprCardPresentation";

type Props = {
  active: PprRelativeRecordResponse[];
  superseded: PprRelativeRecordResponse[];
  voided: PprRelativeRecordResponse[];
};

function RelativeRecordCard({ record }: { record: PprRelativeRecordResponse }) {
  const relationshipLabel =
    record.relationship_label || relationshipTypeLabel(record.relationship_type);

  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800">
      <div className="font-medium text-zinc-900 dark:text-zinc-50">{record.full_name}</div>
      <dl className="mt-2 grid gap-1 text-xs text-zinc-600 dark:text-zinc-400 sm:grid-cols-2">
        <div>
          <dt className="inline">Степень родства: </dt>
          <dd className="inline">{relationshipLabel}</dd>
        </div>
        {record.birth_date ? (
          <div>
            <dt className="inline">Дата рождения: </dt>
            <dd className="inline">{formatPprDate(record.birth_date, "day")}</dd>
          </div>
        ) : null}
        {record.birth_place ? (
          <div>
            <dt className="inline">Место рождения: </dt>
            <dd className="inline">{record.birth_place}</dd>
          </div>
        ) : null}
        {record.organization_name ? (
          <div>
            <dt className="inline">Организация: </dt>
            <dd className="inline">{record.organization_name}</dd>
          </div>
        ) : null}
        {record.residence_address ? (
          <div className="sm:col-span-2">
            <dt className="inline">Адрес: </dt>
            <dd className="inline">{record.residence_address}</dd>
          </div>
        ) : null}
        {record.notes ? (
          <div className="sm:col-span-2">
            <dt className="inline">Примечание: </dt>
            <dd className="inline">{record.notes}</dd>
          </div>
        ) : null}
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
  defaultOpen = false,
}: {
  title: string;
  records: PprRelativeRecordResponse[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
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
            <RelativeRecordCard
              key={record.record_id ?? `${record.relationship_type}-${record.full_name}`}
              record={record}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function PprCardFamilySection({ active, superseded, voided }: Props) {
  if (active.length === 0 && superseded.length === 0 && voided.length === 0) {
    return <p className="text-sm text-zinc-500">Сведения о родственниках отсутствуют.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Действующие записи</h3>
        {active.length === 0 ? (
          <p className="text-sm text-zinc-500">Нет действующих записей.</p>
        ) : (
          active.map((record) => (
            <RelativeRecordCard
              key={record.record_id ?? `${record.relationship_type}-${record.full_name}`}
              record={record}
            />
          ))
        )}
      </div>
      <CollapsibleGroup title="Заменённые записи" records={superseded} />
      <CollapsibleGroup title="Аннулированные записи" records={voided} />
    </div>
  );
}
