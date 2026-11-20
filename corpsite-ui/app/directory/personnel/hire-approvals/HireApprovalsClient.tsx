"use client";

import * as React from "react";
import { listHireApprovals, recordHireVisa, type HireApprovalItem } from "../_lib/electronicHireApi.client";

function formatRate(value: number | string): string {
  const rate = Number(value);
  return Number.isFinite(rate)
    ? rate.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : String(value);
}

function formatDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[3]}.${match[2]}.${match[1]}` : value;
}

function formatDecisionTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Asia/Qyzylorda", day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(parsed);
}

export default function HireApprovalsClient() {
  const [items, setItems] = React.useState<HireApprovalItem[]>([]);
  const [notes, setNotes] = React.useState<Record<number, string>>({});
  const [error, setError] = React.useState("");
  const [success, setSuccess] = React.useState<{ applicationId: number; message: string } | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [tab, setTab] = React.useState<"pending" | "worked">("pending");
  const [busy, setBusy] = React.useState<number | null>(null);
  const busyRef = React.useRef<number | null>(null);
  const deepLinkHandled = React.useRef(false);

  const load = React.useCallback(async () => {
    try {
      const target = Number(new URLSearchParams(window.location.search).get("application_id"));
      const result = await listHireApprovals(target > 0 ? target : undefined);
      setItems(result.items);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить заявления.");
    } finally {
      setLoading(false);
    }
  }, []);
  React.useEffect(() => { void load(); }, [load]);
  React.useEffect(() => {
    if (loading || deepLinkHandled.current) return;
    const target = Number(new URLSearchParams(window.location.search).get("application_id"));
    const item = items.find(candidate => candidate.application_id === target);
    deepLinkHandled.current = true;
    if (item) setTab(item.current_visa?.is_current ? "worked" : "pending");
  }, [items, loading]);
  React.useEffect(() => {
    const target = Number(new URLSearchParams(window.location.search).get("application_id"));
    if (target > 0 && items.some(item => item.application_id === target &&
        Boolean(item.current_visa?.is_current) === (tab === "worked"))) {
      document.getElementById(`hire-approval-${target}`)?.scrollIntoView?.({ block: "center" });
    }
  }, [items, tab]);

  const visibleItems = items.filter(item => Boolean(item.current_visa?.is_current) === (tab === "worked"));

  async function decide(id: number, decision: "approved" | "rejected") {
    if (busyRef.current !== null) return;
    busyRef.current = id;
    setBusy(id);
    setError("");
    setSuccess(null);
    try {
      await recordHireVisa(id, decision, notes[id]);
      setSuccess({ applicationId: id, message: decision === "approved"
        ? `Заявление №${id} согласовано` : `По заявлению №${id} сохранён отказ` });
      setTab("worked");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить визу.");
    } finally {
      busyRef.current = null;
      setBusy(null);
    }
  }

  return <main className="mx-auto max-w-5xl space-y-5 p-6 text-zinc-900">
    <h1 className="text-2xl font-semibold">Согласование заявлений о приёме</h1>
    <p className="text-sm text-zinc-600">Показаны заявления только вашего отделения. Решение сохраняет условия приёма и время визы.</p>
    <nav aria-label="Состояние согласований" className="flex gap-2 border-b border-zinc-200">
      <button type="button" aria-current={tab === "pending" ? "page" : undefined} onClick={() => setTab("pending")}
        className={`px-4 py-2 text-sm font-medium ${tab === "pending" ? "border-b-2 border-blue-700 text-blue-800" : "text-zinc-600"}`}>
        На согласовании
      </button>
      <button type="button" aria-current={tab === "worked" ? "page" : undefined} onClick={() => setTab("worked")}
        className={`px-4 py-2 text-sm font-medium ${tab === "worked" ? "border-b-2 border-blue-700 text-blue-800" : "text-zinc-600"}`}>
        Отработано
      </button>
    </nav>
    {error && <p role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-sm font-medium text-red-800">{error}</p>}
    {success && <div role="status" aria-live="polite"
      className="space-y-3 rounded-lg border border-emerald-500 bg-emerald-100 px-4 py-3 font-semibold text-emerald-900">
      <p>{success.message}</p>
      <button type="button" onClick={() => { setSuccess(null); setTab("pending"); }}
        className="rounded bg-emerald-800 px-3 py-2 text-sm text-white">Вернуться к ожидающим согласования</button>
    </div>}
    {loading && <p className="rounded border p-4 text-sm">Загрузка заявлений…</p>}
    {!loading && visibleItems.length === 0 && <p className="rounded border p-4 text-sm">
      {tab === "pending" ? "Заявлений на согласование нет." : "Отработанных заявлений нет."}
    </p>}
    {visibleItems.map(item => {
      const visa = item.current_visa;
      const hasCurrentVisa = Boolean(visa?.is_current);
      const history = (item.visa_history || []).filter(previous => !hasCurrentVisa || previous.visa_id !== visa?.visa_id);
      return <section id={`hire-approval-${item.application_id}`} key={item.application_id}
        className="scroll-mt-6 space-y-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h2 className="font-semibold">Заявление №{item.application_id} · {item.full_name}</h2>
          <span className="rounded bg-zinc-100 px-2 py-1 text-sm text-zinc-700">
            {hasCurrentVisa ? visa?.decision === "approved" ? "Согласовано" : "Отказ" : "Ожидает решения"}
          </span>
        </div>

        <dl className="grid gap-3 rounded-lg bg-zinc-50 p-4 text-sm sm:grid-cols-2">
          <div><dt className="text-zinc-600">Отделение</dt><dd className="mt-1 font-medium">{item.org_unit}</dd></div>
          <div><dt className="text-zinc-600">Должность</dt><dd className="mt-1 font-medium">{item.position}</dd></div>
          <div><dt className="text-zinc-600">Ставка</dt><dd className="mt-1 font-medium">{formatRate(item.employment_rate)}</dd></div>
          <div><dt className="text-zinc-600">Дата начала</dt><dd className="mt-1 font-medium">{formatDate(item.planned_start_date)}</dd></div>
        </dl>

        {visa && <div className="space-y-1 rounded-lg border border-zinc-200 p-4 text-sm">
          <p><span className="text-zinc-600">Решение:</span> <strong>{visa.decision === "approved" ? "Согласовано" : "Отказ"}</strong></p>
          <p><span className="text-zinc-600">Автор:</span> {visa.decided_by_name || `Пользователь №${visa.decided_by_user_id}`}</p>
          <p><span className="text-zinc-600">Дата и время:</span> {formatDecisionTime(visa.decided_at)} (Кызылорда)</p>
          <p><span className="text-zinc-600">Пояснение:</span> {visa.explanation || "—"}</p>
          {!visa.is_current && <p className="font-medium text-amber-700">Условия изменились. Требуется новая виза.</p>}
        </div>}

        {history.length > 0 && <details className="rounded-lg border border-zinc-200 p-4 text-sm">
          <summary className="cursor-pointer font-medium">История виз ({history.length})</summary>
          <ol className="mt-3 space-y-3">
            {history.map(previous =>
              <li key={previous.visa_id} className="border-t border-zinc-200 pt-3">
                <p>Решение: {previous.decision === "approved" ? "Согласовано" : "Отказ"}</p>
                <p>Автор: {previous.decided_by_name || `Пользователь №${previous.decided_by_user_id}`}</p>
                <p>Дата и время: {formatDecisionTime(previous.decided_at)} (Кызылорда)</p>
                <p>Пояснение: {previous.explanation || "—"}</p>
              </li>) }
          </ol>
        </details>}

        {!hasCurrentVisa && <>
          <label className="block text-sm">Пояснение при отказе
            <textarea className="mt-1 w-full rounded border border-zinc-300 p-2 disabled:opacity-60"
              disabled={busy !== null} value={notes[item.application_id] || ""}
              onChange={e => setNotes({ ...notes, [item.application_id]: e.target.value })} />
          </label>
          <div className="flex gap-2">
            <button disabled={busy !== null} onClick={() => void decide(item.application_id, "approved")}
              className="rounded bg-emerald-700 px-3 py-2 text-sm text-white disabled:opacity-50">
              {busy === item.application_id ? "Сохранение…" : "Согласен"}
            </button>
            <button disabled={busy !== null || !notes[item.application_id]?.trim()}
              onClick={() => void decide(item.application_id, "rejected")}
              className="rounded border border-red-300 px-3 py-2 text-sm text-red-700 disabled:opacity-50">Не согласен</button>
          </div>
        </>}
      </section>;
    })}
  </main>;
}
