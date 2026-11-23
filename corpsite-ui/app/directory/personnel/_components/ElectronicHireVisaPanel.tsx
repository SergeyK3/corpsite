"use client";

import * as React from "react";
import { getHireApplicationForOrder, requestPositionReview } from "../_lib/electronicHireApi.client";

export default function ElectronicHireVisaPanel({ orderId }: {orderId: number}) {
  const [data, setData] = React.useState<Awaited<ReturnType<typeof getHireApplicationForOrder>> | null>(null);
  const [explanation, setExplanation] = React.useState("");
  const [error, setError] = React.useState("");
  React.useEffect(() => { let active = true; void getHireApplicationForOrder(orderId).then(value => { if (active) setData(value); }).catch(() => {}); return () => { active = false; }; }, [orderId]);
  if (!data) return null;
  return <section className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 text-sm">
    <h3 className="font-semibold">Заявление №{data.application_id} · {data.full_name}</h3>
    {data.position_resolution === "unmatched_manual" && <div className="my-3 rounded border-2 border-amber-500 bg-amber-50 p-3 text-amber-950" role="status"><b>Должность требует сопоставления со справочником</b><p>Исходное название: {data.manual_position_name}. До решения подписание, регистрация и применение приказа заблокированы.</p>{data.position_request ? <p>Запрос №{data.position_request.request_id}: {data.position_request.status === "open" ? "ожидает решения" : "решён"}.</p> : <div className="mt-2"><label>Пояснение<textarea className="mt-1 block w-full rounded border bg-white p-2" value={explanation} onChange={e => setExplanation(e.target.value)} /></label><button className="mt-2 rounded bg-amber-800 px-3 py-2 text-white" disabled={!explanation.trim()} onClick={() => {void requestPositionReview(data.application_id, explanation.trim()).then(request => setData({...data, position_request: request})).catch(e => setError(String(e)));}}>Отправить на уточнение</button></div>}{error && <p role="alert">{error}</p>}</div>}
    {data.position_resolution === "matched_manual" && data.position_request && <p className="my-2 rounded border border-emerald-400 bg-emerald-50 p-3">Исходное название: {data.manual_position_name}. Сопоставлено с «{data.position_request.resolved_position_name}». <a className="underline" href={`/directory/personnel/position-reconciliation?request_id=${data.position_request.request_id}`}>Решение и изменения RU/KK</a></p>}
    <p className="mt-1">Виза: {data.current_visa?.is_current ? data.current_visa.decision === "approved" ? "согласовано" : "отказ" : "требуется актуальное согласование"}</p>
    {data.visas.length > 0 && <details className="mt-2"><summary className="cursor-pointer">История виз ({data.visas.length})</summary><ul className="mt-2 space-y-1">{data.visas.map(visa => <li key={visa.visa_id}>#{visa.visa_id}: {visa.decision === "approved" ? "Согласен" : "Не согласен"} · {new Date(visa.decided_at).toLocaleString("ru-RU")} · пользователь {visa.decided_by_user_id}{visa.explanation ? ` · ${visa.explanation}` : ""}{visa.is_current ? " · текущие условия" : " · прежние условия"}</li>)}</ul></details>}
  </section>;
}
