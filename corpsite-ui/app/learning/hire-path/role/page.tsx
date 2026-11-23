"use client";

import { useEffect, useState } from "react";
import { apiFetchJson } from "@/lib/api";
import PersonnelOrderDocumentView from "@/app/directory/personnel/_components/PersonnelOrderDocumentView";
import type { PersonnelOrderDetailResponse, PersonnelOrderEditorialState } from "@/app/directory/personnel/_lib/personnelOrdersApi.client";

type Me = { role_code: string; full_name: string };
type InboxItem = { id: string; kind: "intake_link" | "order_notice"; root_attempt_id: string; application_id: number; intake_url_path?: string | null; order_id?: number; number?: string; date?: string; status?: string; acknowledged_at?: string | null };
type Approval = { root_attempt_id: string; application_id: number; order_id: number; candidate: string };
type Signature = { root_attempt_id: string; application_id: number; order_id: number; order_number: string | null; status: string };
type OrderPack = { detail: PersonnelOrderDetailResponse; editorial: PersonnelOrderEditorialState };
const button = "rounded border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100";
const panel = "rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-700 dark:bg-zinc-900";
const evidence = "Подтверждаю ознакомление с приказом";

export default function HireRolePage() {
  const [me, setMe] = useState<Me | null>(null);
  const [inbox, setInbox] = useState<InboxItem[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [signatures, setSignatures] = useState<Signature[]>([]);
  const [order, setOrder] = useState<OrderPack | null>(null);
  const [locale, setLocale] = useState<"ru" | "kk">("ru");
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState("");
  async function load() {
    const user = await apiFetchJson<Me>("/auth/me"); setMe(user);
    if (user.role_code === "LEARN_CANDIDATE") setInbox((await apiFetchJson<{ items: InboxItem[] }>("/learning/hire-path/inbox")).items);
    if (user.role_code === "TRAINING_HEAD_LOCAL") setApprovals((await apiFetchJson<{ items: Approval[] }>("/learning/hire-path/approvals")).items);
    if (user.role_code === "LEARN_SIGNATORY") setSignatures((await apiFetchJson<{ items: Signature[] }>("/learning/hire-path/signatures")).items);
  }
  useEffect(() => { void load().catch(error => setMessage(error instanceof Error ? error.message : "Кабинет недоступен")); }, []);
  async function act(rootId: string, action: string, body?: unknown) {
    setMessage("");
    try {
      await apiFetchJson(`/learning/hire-path/${rootId}/${action}`, { method: "POST", ...(body === undefined ? {} : { body }) });
      await load(); setMessage("Действие сохранено в учебной истории.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Действие не выполнено"); }
  }
  async function openOrder(rootId: string) {
    try { setOrder(await apiFetchJson<OrderPack>(`/learning/hire-path/${rootId}/role-order`)); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Приказ недоступен"); }
  }
  return <main className="min-h-screen bg-zinc-50 px-4 py-8 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100"><div className="mx-auto max-w-4xl space-y-5">
    <header className={panel}><a href="/learning" className="text-sm text-blue-700 underline dark:text-blue-300">← Обучение</a><h1 className="mt-2 text-2xl font-semibold">Учебный кабинет приёма</h1><p>{me?.full_name || "Загрузка…"}</p><button className={`${button} mt-2`} onClick={() => void load()}>Обновить</button></header>
    {message && <p role="status" className="rounded border border-blue-300 bg-blue-50 p-3 dark:bg-blue-950">{message}</p>}
    {me?.role_code === "LEARN_CANDIDATE" && <section className={panel}><h2 className="text-xl font-semibold">Мои сообщения</h2>
      {inbox.length === 0 && <p className="mt-2">Учебных сообщений пока нет.</p>}
      {inbox.map(item => <article key={item.id} className="mt-4 rounded border p-4">
        {item.kind === "intake_link" ? <><h3 className="font-semibold">Запрос заполнения личной карточки</h3><p>Заявление № {item.application_id}</p>
          {item.intake_url_path ? <a className="text-blue-700 underline dark:text-blue-300" href={item.intake_url_path}>Открыть личную карточку</a> : <p>Ссылка недействительна или уже использована.</p>}</>
        : <><h3 className="font-semibold">Уведомление о приказе</h3><p>Приказ № {item.number || "—"} от {item.date || "—"} · {item.status}</p>
          <button className={`${button} mt-2`} onClick={() => void openOrder(item.root_attempt_id)}>Прочитать приказ RU/KK</button>
          {item.acknowledged_at ? <p className="mt-2">Ознакомление подтверждено: {item.acknowledged_at}</p> : <div className="mt-3 space-y-2"><label className="block text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> {evidence}</label><button className={button} disabled={!confirmed || !order} onClick={() => void act(item.root_attempt_id, "acknowledge", { method: "training_cabinet", evidence })}>Ознакомился</button><p className="text-xs">Сначала откройте и прочитайте приказ.</p></div>}</>}
      </article>)}
    </section>}
    {me?.role_code === "TRAINING_HEAD_LOCAL" && <section className={panel}><h2 className="text-xl font-semibold">Согласование заявления</h2>
      {approvals.length === 0 && <p>Заявлений пока нет.</p>}
      {approvals.map(item => <article className="mt-3 rounded border p-4" key={item.root_attempt_id}><p>Заявление № {item.application_id} · {item.candidate} · приказ № {item.order_id}</p><button className={`${button} mt-2`} onClick={() => void act(item.root_attempt_id, "approve")}>Согласовать условия приёма</button></article>)}
    </section>}
    {me?.role_code === "LEARN_SIGNATORY" && <section className={panel}><h2 className="text-xl font-semibold">Приказы на подпись</h2>
      {signatures.length === 0 && <p>Приказов пока нет.</p>}
      {signatures.map(item => <article className="mt-3 rounded border p-4" key={item.root_attempt_id}><p>Приказ № {item.order_number || "без номера"} · {item.status}</p><div className="mt-2 flex gap-2"><button className={button} onClick={() => void openOrder(item.root_attempt_id)}>Прочитать RU/KK</button><button className={button} disabled={item.status !== "READY_FOR_SIGNATURE" || !order} onClick={() => void act(item.root_attempt_id, "sign")}>Подписать</button></div></article>)}
    </section>}
    {order && <section className={panel}><div className="mb-3 flex gap-2"><button className={button} onClick={() => setLocale("ru")}>Русский</button><button className={button} onClick={() => setLocale("kk")}>Қазақша</button><button className={button} onClick={() => window.print()}>Печать</button></div><PersonnelOrderDocumentView detail={order.detail} editorial={order.editorial} language={locale} /></section>}
  </div></main>;
}
