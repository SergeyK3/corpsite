"use client";

import * as React from "react";
import { getHireApplicationForOrder } from "../_lib/electronicHireApi.client";

export default function ElectronicHireVisaPanel({ orderId }: {orderId: number}) {
  const [data, setData] = React.useState<Awaited<ReturnType<typeof getHireApplicationForOrder>> | null>(null);
  React.useEffect(() => { let active = true; void getHireApplicationForOrder(orderId).then(value => { if (active) setData(value); }).catch(() => {}); return () => { active = false; }; }, [orderId]);
  if (!data) return null;
  return <section className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 text-sm">
    <h3 className="font-semibold">Заявление №{data.application_id} · {data.full_name}</h3>
    <p className="mt-1">Виза: {data.current_visa?.is_current ? data.current_visa.decision === "approved" ? "согласовано" : "отказ" : "требуется актуальное согласование"}</p>
    {data.visas.length > 0 && <details className="mt-2"><summary className="cursor-pointer">История виз ({data.visas.length})</summary><ul className="mt-2 space-y-1">{data.visas.map(visa => <li key={visa.visa_id}>#{visa.visa_id}: {visa.decision === "approved" ? "Согласен" : "Не согласен"} · {new Date(visa.decided_at).toLocaleString("ru-RU")} · пользователь {visa.decided_by_user_id}{visa.explanation ? ` · ${visa.explanation}` : ""}{visa.is_current ? " · текущие условия" : " · прежние условия"}</li>)}</ul></details>}
  </section>;
}
