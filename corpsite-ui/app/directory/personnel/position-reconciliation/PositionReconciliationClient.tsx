"use client";

import * as React from "react";
import { apiFetchJson } from "@/lib/api";
import { listPositionReviews, resolvePositionReview, type PositionReview, type PositionReviewAudit } from "../_lib/electronicHireApi.client";

type Candidate = {position_id: number; name: string; name_kk: string | null; allowed: boolean;
  document_nominative_ru: string | null; document_possessive_kk: string | null};
type Detail = {request: PositionReview; history: PositionReviewAudit[]};
const field = "w-full rounded border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900";

export default function PositionReconciliationClient() {
  const [items, setItems] = React.useState<PositionReview[]>([]);
  const [selected, setSelected] = React.useState<Detail | null>(null);
  const [query, setQuery] = React.useState("");
  const [candidates, setCandidates] = React.useState<Candidate[]>([]);
  const [mode, setMode] = React.useState<"existing" | "link" | "new">("existing");
  const [positionId, setPositionId] = React.useState<number | null>(null);
  const [newPosition, setNewPosition] = React.useState({name: "", category: "other", name_kk: "",
    document_nominative_ru: "", document_possessive_kk: ""});
  const [note, setNote] = React.useState("");
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [canResolve, setCanResolve] = React.useState(false);
  const selectedId = selected?.request.request_id;

  async function refresh() {
    const result = await listPositionReviews();
    setItems(result.items);
    const wanted = Number(new URLSearchParams(window.location.search).get("request_id")) || selectedId || result.items[0]?.request_id;
    if (wanted) await openRequest(wanted);
  }
  async function openRequest(id: number) {
    const result = await apiFetchJson<Detail>(`/directory/electronic-hire/position-requests/${id}`);
    setSelected(result); setPositionId(null); setError("");
    window.history.replaceState(null, "", `?request_id=${id}`);
  }
  React.useEffect(() => {
    void apiFetchJson<{can_resolve: boolean}>("/directory/electronic-hire/position-reconciliation/capabilities")
      .then(result => { setCanResolve(result.can_resolve); if (result.can_resolve) void refresh().catch(e => setError(String(e))); })
      .catch(e => setError(String(e)));
  // Initial permission check only.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  React.useEffect(() => {
    if (!selected || !canResolve) return;
    let active = true;
    void apiFetchJson<{items: Candidate[]}>(`/directory/electronic-hire/position-reconciliation/positions?org_unit_id=${selected.request.org_unit_id}&q=${encodeURIComponent(query)}`)
      .then(result => { if (active) setCandidates(result.items); })
      .catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [selected?.request.request_id, selected?.request.org_unit_id, query, canResolve]);

  async function decide() {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      await resolvePositionReview(selected.request.request_id, {
        mode, ...(mode === "new" ? {new_position: newPosition} : {position_id: positionId || undefined}),
        decision_note: note,
      });
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  if (!canResolve) return <main className="mx-auto max-w-5xl p-6 text-zinc-900"><h1 className="text-2xl font-semibold">Должности требуют сопоставления</h1><p className="mt-4">{error || "Проверка разрешения…"}</p></main>;
  const request = selected?.request;
  const latestDecision = selected?.history.findLast(entry => entry.action === "resolved")?.details;
  return <main className="mx-auto max-w-6xl space-y-5 bg-white p-6 text-zinc-900">
    <header><h1 className="text-2xl font-semibold">Должности требуют сопоставления</h1><p className="text-sm text-zinc-600">Решение сохраняет исходное название заявления и обновляет связанный черновик приказа.</p><a className="text-sm underline" href="/directory/personnel/position-reconciliation/historical">Отчёт о ранее подписанных и зарегистрированных документах</a></header>
    {error && <p role="alert" className="rounded bg-red-50 p-3 text-red-800">{error}</p>}
    <div className="grid gap-5 lg:grid-cols-[minmax(260px,1fr)_minmax(0,2fr)]">
      <nav aria-label="Очередь уточнений" className="space-y-2">{items.map(item => <button key={item.request_id} type="button" onClick={() => void openRequest(item.request_id)} className={`w-full rounded border p-3 text-left text-sm ${selectedId === item.request_id ? "border-blue-600 bg-blue-50" : "bg-white"}`}><b>Запрос №{item.request_id}</b> · {item.status === "open" ? "Ожидает решения" : "Решён"}<br />{item.source_title}<br /><span className="text-zinc-600">{item.org_unit_name}</span></button>)}{items.length === 0 && <p className="text-sm">Запросов пока нет.</p>}</nav>
      {request && <article className="space-y-4 rounded border p-4 text-sm">
        <div><h2 className="text-lg font-semibold">Запрос №{request.request_id} · {request.status === "open" ? "ожидает решения" : "решён"}</h2><p><b>Исходное название:</b> {request.source_title}</p><p><b>Отделение:</b> {request.org_unit_name}</p><p><b>Заявление:</b> №{request.application_id}; <b>черновик:</b> {request.personnel_order_id ? <a className="underline" href={`/directory/personnel/orders?order_id=${request.personnel_order_id}`}>№{request.personnel_order_id}</a> : "ещё не создан"}</p><p><b>Автор и дата:</b> {request.requester_name}, {new Date(request.requested_at).toLocaleString("ru-RU")}</p><p><b>Пояснение:</b> {request.explanation}</p></div>
        {request.status === "open" && <div className="space-y-3 border-t pt-4"><h3 className="font-semibold">Принять решение</h3><div className="flex flex-wrap gap-3">{(["existing", "link", "new"] as const).map((value, index) => <label key={value}><input type="radio" checked={mode === value} onChange={() => {setMode(value); setPositionId(null);}} /> {(["Выбрать существующую", "Связать с отделением", "Добавить новую"] as const)[index]}</label>)}</div>
          {mode !== "new" ? <><label className="block">Поиск должности<input className={field} value={query} onChange={e => setQuery(e.target.value)} /></label><label className="block">Должность<select className={field} value={positionId ?? ""} onChange={e => setPositionId(Number(e.target.value) || null)}><option value="">Выберите должность</option>{candidates.filter(row => mode === "link" ? !row.allowed : row.allowed).map(row => <option key={row.position_id} value={row.position_id}>{row.name} / {row.name_kk || "нет KK"}{!row.document_nominative_ru || !row.document_possessive_kk ? " · неполные формы" : ""}</option>)}</select></label></>
            : <div className="grid gap-2 sm:grid-cols-2"><label>Название RU<input className={field} value={newPosition.name} onChange={e => setNewPosition({...newPosition, name: e.target.value})} /></label><label>Название KK<input className={field} value={newPosition.name_kk} onChange={e => setNewPosition({...newPosition, name_kk: e.target.value})} /></label><label>Форма RU для документа<input className={field} value={newPosition.document_nominative_ru} onChange={e => setNewPosition({...newPosition, document_nominative_ru: e.target.value})} /></label><label>Форма KK для документа<input className={field} value={newPosition.document_possessive_kk} onChange={e => setNewPosition({...newPosition, document_possessive_kk: e.target.value})} /></label><label>Категория<select className={field} value={newPosition.category} onChange={e => setNewPosition({...newPosition, category: e.target.value})}>{["leaders","medical","admin","technical","other"].map(value => <option key={value} value={value}>{value}</option>)}</select></label></div>}
          <label className="block">Комментарий к решению<textarea className={field} value={note} onChange={e => setNote(e.target.value)} /></label><button disabled={busy || (mode !== "new" && !positionId)} className="rounded bg-blue-700 px-4 py-2 text-white disabled:opacity-50" onClick={() => void decide()}>Принять решение</button>
        </div>}
        {request.status === "resolved" && <div className="rounded border border-emerald-300 bg-emerald-50 p-3"><b>Принятое решение:</b> {request.resolved_position_name} / {request.resolved_position_name_kk}; {request.decider_name}, {request.decided_at ? new Date(request.decided_at).toLocaleString("ru-RU") : ""}.<p>После изменения должности требуется повторное согласование проекта.</p></div>}
        {latestDecision && <details className="rounded border p-3" open><summary className="cursor-pointer font-semibold">Изменения RU/KK и печати</summary>{(["ru", "kk"] as const).map(locale => <div key={locale} className="mt-3 grid gap-2 sm:grid-cols-2"><div><b>Заявление {locale.toUpperCase()} · до</b><pre className="whitespace-pre-wrap bg-zinc-50 p-2">{String((latestDecision.before_print as Record<string,string> | undefined)?.[locale] || "")}</pre></div><div><b>Заявление {locale.toUpperCase()} · после</b><pre className="whitespace-pre-wrap bg-zinc-50 p-2">{String((latestDecision.after_print as Record<string,string> | undefined)?.[locale] || "")}</pre></div><div><b>Приказ {locale.toUpperCase()} · до</b><pre className="whitespace-pre-wrap bg-zinc-50 p-2">{String((latestDecision.before_order_text as Record<string,string> | undefined)?.[locale] || "")}</pre></div><div><b>Приказ {locale.toUpperCase()} · после</b><pre className="whitespace-pre-wrap bg-zinc-50 p-2">{String((latestDecision.after_order_text as Record<string,string> | undefined)?.[locale] || "")}</pre></div></div>)}</details>}
        <details><summary className="cursor-pointer font-semibold">История запроса</summary><ul className="mt-2 list-disc pl-5">{selected?.history.map(entry => <li key={entry.audit_id}>{new Date(entry.recorded_at).toLocaleString("ru-RU")} · {entry.action === "requested" ? "отправлен" : "решён"} · пользователь №{entry.actor_user_id}</li>)}</ul></details>
      </article>}
    </div>
  </main>;
}
