"use client";

import type { PprCompositeReadResponse } from "../_lib/pprQueryTypes";
import {
  formatPprDate,
  hrRelationshipLabel,
  lifecycleStatusLabel,
} from "../_lib/pprCardPresentation";

type Props = {
  ppr: PprCompositeReadResponse;
};

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-0.5 text-sm font-medium text-zinc-900 dark:text-zinc-50">{value || "—"}</div>
    </div>
  );
}

export default function PprCardGeneralSection({ ppr }: Props) {
  const g = ppr.general;
  const mat = ppr.materialization;

  return (
    <div className="space-y-4">
      <p className="text-xs text-zinc-500">
        Раздел доступен только для просмотра. Редактирование будет подключено на следующем этапе.
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="ФИО" value={g.full_name} />
        <Field label="Фамилия" value={g.last_name ?? ""} />
        <Field label="Имя" value={g.first_name ?? ""} />
        <Field label="Отчество" value={g.middle_name ?? ""} />
        <Field label="ИИН" value={g.iin ?? ""} />
        <Field label="Дата рождения" value={formatPprDate(g.birth_date)} />
        <Field
          label="Статус личной карточки"
          value={lifecycleStatusLabel(mat.materialized, mat.lifecycle_state)}
        />
        <Field label="Кадровая связь" value={hrRelationshipLabel(mat.hr_relationship_context)} />
      </div>
    </div>
  );
}
