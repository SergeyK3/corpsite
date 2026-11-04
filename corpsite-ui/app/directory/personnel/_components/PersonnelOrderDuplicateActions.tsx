import { buildPersonnelOrdersHref, personnelOrderTypeLabel, personnelOrderStatusLabel, type PersonnelOrderHeaderDuplicatePreview } from "../_lib/personnelOrdersApi.client";

export default function PersonnelOrderDuplicateActions({duplicate, day}: {duplicate: PersonnelOrderHeaderDuplicatePreview; day: string}) {
  const conflicts = duplicate.candidates.filter(row => row.is_conflict ?? row.order_date === day);
  return <div className="space-y-2 text-sm" data-testid="personnel-order-duplicate-actions">
    <p>Номер и дата проверяются среди всех неудалённых приказов, независимо от типа и фильтров журнала.</p>
    {conflicts.map(row => <div key={row.order_id} className="space-y-1">
      <p>№ {row.order_number || "—"} · ID {row.order_id} · {personnelOrderTypeLabel(row.order_type_code)} · {personnelOrderStatusLabel(row.status)}{row.record_quality ? ` · ${row.record_quality === "WORKING" ? "Рабочая запись" : "Техническая запись"}` : ""}</p>
      {row.can_open === true ? <a className="block text-blue-700 underline dark:text-blue-300"
        href={buildPersonnelOrdersHref({order_id: row.order_id, record_quality: "ALL", include_closed: true})}>
        Открыть существующий приказ
      </a> : null}
    </div>)}
  </div>;
}
