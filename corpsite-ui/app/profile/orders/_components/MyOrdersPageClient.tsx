"use client";

import { useEffect, useMemo, useState } from "react";
import PositionCabinetSectionShell from "@/components/PositionCabinetSectionShell";
import { getMyOrder, getMyOrders, type MyOrder, type MyOrderDetail } from "../_lib/myOrdersApi.client";

const UNCONFIRMED = "Не подтверждено кадровой службой";
const CONFIRMED = "Подтверждено кадровой службой";
const warning = "Приказ ещё не подтверждён кадровой службой. Сведения могут быть уточнены после сверки с оригиналом.";
const dateText = (value: string | null) => value ? new Intl.DateTimeFormat("ru-RU").format(new Date(`${value}T00:00:00`)) : "Дата не указана";
const statusText = (status: MyOrder["confirmation_status"]) => status === "CONFIRMED" ? CONFIRMED : UNCONFIRMED;

export default function MyOrdersPageClient() {
  const [orders, setOrders] = useState<MyOrder[]>([]); const [year, setYear] = useState(""); const [confirmation, setConfirmation] = useState("all");
  const [selected, setSelected] = useState<MyOrderDetail | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  useEffect(() => { let alive = true; setLoading(true); getMyOrders(year || undefined, confirmation).then((r) => { if (alive) setOrders(r.orders); }).catch(() => alive && setError("Не удалось загрузить приказы.")).finally(() => alive && setLoading(false)); return () => { alive = false; }; }, [year, confirmation]);
  const years = useMemo(() => [...new Set(orders.map((o) => o.order_date?.slice(0, 4)).filter(Boolean))] as string[], [orders]);
  const open = async (id: number) => { try { setSelected(await getMyOrder(id)); } catch { setError("Не удалось открыть приказ."); } };
  const draft = selected?.confirmation_status === "UNCONFIRMED";
  return <PositionCabinetSectionShell title="Мои приказы">
    <p className="mb-5 text-zinc-600 dark:text-zinc-400">Кадровые приказы, в которых вы указаны как работник</p>
    <div className="mb-5 flex flex-wrap gap-3" data-testid="my-orders-filters"><label>Год <select value={year} onChange={(e) => setYear(e.target.value)} className="ml-1 rounded border p-2"><option value="">Все</option>{years.map((v) => <option key={v} value={v}>{v}</option>)}</select></label><label>Статус <select value={confirmation} onChange={(e) => setConfirmation(e.target.value)} className="ml-1 rounded border p-2"><option value="all">Все</option><option value="confirmed">Подтверждённые</option><option value="unconfirmed">Неподтверждённые</option></select></label></div>
    {error && <p role="alert">{error}</p>}{loading ? <p>Загрузка приказов…</p> : orders.length === 0 ? <div data-testid="my-orders-empty" className="rounded-xl border p-5">Приказов, связанных с вашей личной карточкой, пока нет.</div> : <div className="space-y-3" data-testid="my-orders-list">{orders.map((order) => <article key={order.order_id} className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold">{order.title}</p><p>{dateText(order.order_date)} · № {order.order_number || "не указан"}</p>{order.item_text && <p className="mt-2 text-zinc-600 dark:text-zinc-400">{order.item_text}</p>}<p className={order.confirmation_status === "CONFIRMED" ? "mt-2 text-green-700" : "mt-2 text-amber-700"}>{statusText(order.confirmation_status)}</p></div><button className="rounded-md border px-3 py-2" onClick={() => open(order.order_id)}>Открыть</button></div></article>)}</div>}
    {selected && <div className="fixed inset-0 z-50 overflow-auto bg-black/40 p-4 print:static print:bg-white print:p-0" role="dialog" aria-modal="true" aria-label="Просмотр приказа"><article className="relative my-8 mx-auto max-w-3xl bg-white p-6 text-zinc-900 shadow dark:bg-zinc-950 dark:text-zinc-100 print:my-0 print:max-w-none print:shadow-none" data-testid="my-order-document"><div className="mb-5 flex justify-end gap-2 print:hidden"><button className="rounded border px-3 py-2" onClick={() => setSelected(null)}>Закрыть</button><button className="rounded border px-3 py-2" onClick={() => window.print()}>{draft ? "Распечатать предварительную версию" : "Распечатать"}</button></div>{draft && <><div className="mb-4 rounded border border-amber-500 bg-amber-50 p-3 text-amber-900">{selected.warning || warning}</div><div className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rotate-[-28deg] text-4xl font-bold text-red-600/25" data-testid="my-order-unconfirmed-watermark">НЕ ПОДТВЕРЖДЕНО</div></>}<p className="text-sm">{dateText(selected.order_date)} · № {selected.order_number || "не указан"}</p><h2 className="mt-2 text-xl font-bold">{selected.title}</h2><p className={draft ? "mt-3 text-amber-700" : "mt-3 text-green-700"}>{statusText(selected.confirmation_status)}</p><p className="mt-6 whitespace-pre-wrap">{selected.item_text || "Текст пункта приказа пока не сформирован."}</p></article></div>}
  </PositionCabinetSectionShell>;
}
