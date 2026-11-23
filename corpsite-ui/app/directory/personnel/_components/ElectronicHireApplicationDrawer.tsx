"use client";

import * as React from "react";
import { useOrgUnitScopeOptions } from "@/lib/useOrgUnitScopeOptions";
import { usePersonnelOrderPositionOptions } from "@/lib/usePersonnelOrderPositionOptions";
import { getActiveIntakeLink, issueIntakeLink, reissueIntakeLink } from "../_lib/personnelApplicationsApi.client";
import {
  checkElectronicHire, createElectronicHire, createElectronicHireOrderDraft, getElectronicHire,
  listElectronicHireApplications, printElectronicHire,
  retryElectronicHireNotification, searchFormerCandidates, sendElectronicHireLinkTelegram, updateElectronicHireConditions,
  uploadElectronicHireSignedCopy, type FormerCandidate,
} from "../_lib/electronicHireApi.client";
import PersonnelApplicationIntakeOnBehalfDrawer from "./PersonnelApplicationIntakeOnBehalfDrawer";

type Props = { open: boolean; onClose: () => void };
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const field = "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900";

export default function ElectronicHireApplicationDrawer({ open, onClose }: Props) {
  const [query, setQuery] = React.useState("");
  const [matches, setMatches] = React.useState<FormerCandidate[]>([]);
  const [iin, setIin] = React.useState("");
  const [fullName, setFullName] = React.useState("");
  const [birthDate, setBirthDate] = React.useState("");
  const [received, setReceived] = React.useState(today);
  const [start, setStart] = React.useState(today);
  const [unitId, setUnitId] = React.useState<number | null>(null);
  const [positionId, setPositionId] = React.useState<number | null>(null);
  const [rate, setRate] = React.useState("1");
  const [applicationId, setApplicationId] = React.useState<number | null>(null);
  const [personId, setPersonId] = React.useState<number | null>(null);
  const [printText, setPrintText] = React.useState<{ru: string; kk: string} | null>(null);
  const [locale, setLocale] = React.useState<"ru" | "kk">("ru");
  const [checked, setChecked] = React.useState(false);
  const [link, setLink] = React.useState("");
  const [assist, setAssist] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [uploaded, setUploaded] = React.useState("");
  const [existing, setExisting] = React.useState<Array<{application_id: number; full_name: string; status: string}>>([]);
  const [orderId, setOrderId] = React.useState<number | null>(null);
  const [notification, setNotification] = React.useState("");
  const { options: units } = useOrgUnitScopeOptions(null, open);
  const unit = units.find(row => row.unit_id === unitId);
  const { scopedOptions: positions } = usePersonnelOrderPositionOptions({ enabled: open, orgUnitId: unitId, orgGroupId: unit?.group_id ?? null, allowedOnly: true });

  React.useEffect(() => { if (open) void listElectronicHireApplications().then(result => setExisting(result.items)).catch(() => {}); }, [open]);

  React.useEffect(() => {
    if (!open || query.trim().length < 2) { setMatches([]); return; }
    let active = true;
    const timer = window.setTimeout(() => { void searchFormerCandidates(query).then(result => { if (active) setMatches(result.items); }).catch(() => { if (active) setMatches([]); }); }, 250);
    return () => { active = false; window.clearTimeout(timer); };
  }, [open, query]);

  if (!open) return null;
  const message = (e: unknown) => e instanceof Error ? e.message
    : e && typeof e === "object" && "message" in e && typeof e.message === "string"
      ? e.message : "Не удалось выполнить действие.";

  async function openExisting(id: number) {
    setBusy(true); setError("");
    try {
      const app = await getElectronicHire(id);
      setApplicationId(id); setPersonId(Number(app.person_id));
      setIin(String(app.iin || "")); setFullName(String(app.full_name || ""));
      setReceived(String(app.application_received_at || "")); setStart(String(app.planned_start_date || ""));
      setUnitId(Number(app.intended_org_unit_id) || null); setPositionId(Number(app.intended_position_id) || null);
      setRate(String(app.intended_employment_rate || "1")); setChecked(Boolean(app.candidate_checked_at));
      setOrderId(Number(app.personnel_order_id) || null);
      const note = app.notification as {status?: string; last_error?: string | null} | null;
      setNotification(note?.last_error || note?.status || "");
      setPrintText(await printElectronicHire(id));
      const currentLink = await getActiveIntakeLink(id).catch(() => null);
      setLink(currentLink?.intake_url_path || "");
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (unitId == null || positionId == null) return;
    setBusy(true); setError("");
    try {
      const result = await createElectronicHire({ iin, full_name: fullName, application_received_at: received,
        birth_date: birthDate || undefined,
        planned_start_date: start, org_unit_id: unitId, position_id: positionId,
        employment_rate: Number(rate.replace(",", ".")), org_group_id: unit?.group_id });
      setApplicationId(result.application_id); setPersonId(result.person_id);
      setPrintText(await printElectronicHire(result.application_id));
      try { const issued = await issueIntakeLink(result.application_id); setLink(issued.intake_url_path); } catch { /* HR may issue later. */ }
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  async function issue(reissue: boolean) {
    if (applicationId == null) return;
    setBusy(true); setError("");
    try {
      const result = reissue ? await reissueIntakeLink(applicationId) : await issueIntakeLink(applicationId);
      setLink(result.intake_url_path);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  async function createOrder() {
    if (applicationId == null) return;
    setBusy(true); setError("");
    try {
      const result = await createElectronicHireOrderDraft(applicationId);
      setOrderId(result.personnel_order_id);
      setNotification(result.notification.status);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  async function saveConditions() {
    if (applicationId == null || unitId == null || positionId == null) return;
    setBusy(true); setError("");
    try {
      await updateElectronicHireConditions(applicationId, {org_unit_id: unitId, position_id: positionId,
        employment_rate: Number(rate.replace(",", ".")), planned_start_date: start});
      setPrintText(await printElectronicHire(applicationId)); setChecked(false); setNotification("Ожидает повторного согласования");
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }

  function openPrint() {
    if (!printText) return;
    const popup = window.open("", "_blank");
    if (!popup) return;
    popup.opener = null;
    popup.document.write("<!doctype html><html><head><meta charset='utf-8'><title>Заявление</title><style>body{font:18px/1.7 Georgia,serif;max-width:760px;margin:70px auto;color:#111}pre{white-space:pre-wrap;font:inherit}</style></head><body><pre></pre></body></html>");
    popup.document.querySelector("pre")!.textContent = printText[locale];
    popup.document.close(); popup.focus(); popup.print();
  }

  return <div className="fixed inset-0 z-50 flex justify-end bg-black/30" data-testid="electronic-hire-drawer">
    <aside className="h-full w-full max-w-2xl overflow-y-auto border-l border-zinc-200 bg-white p-6 text-zinc-900 shadow-xl">
      <div className="mb-5 flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold">Заявление о приёме на работу</h2><p className="text-sm text-zinc-600">Электронное заявление и планируемые условия приёма</p></div><button onClick={onClose} className="rounded border px-3 py-1">Закрыть</button></div>
      {error && <p role="alert" className="mb-4 rounded bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {applicationId == null ? <form onSubmit={create} className="space-y-4">
        {existing.length > 0 && <div className="rounded border bg-zinc-50 p-3 text-sm"><h3 className="mb-2 font-medium">Незавершённые заявления</h3><ul className="space-y-1">{existing.map(row => <li key={row.application_id}><button type="button" className="underline" onClick={() => void openExisting(row.application_id)}>№{row.application_id} · {row.full_name}</button></li>)}</ul></div>}
        <label className="block text-sm">Поиск среди ранее уволенных<input className={field} value={query} onChange={e => setQuery(e.target.value)} placeholder="ФИО или ИИН" /></label>
        {matches.length > 0 && <ul className="rounded border p-2">{matches.map(row => <li key={row.person_id}><button type="button" className="w-full rounded px-2 py-1 text-left hover:bg-zinc-100" onClick={() => { setIin(row.iin); setFullName(row.full_name); setMatches([]); setQuery(row.full_name); }}>{row.full_name} · {row.iin}</button></li>)}</ul>}
        <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">ИИН<input required minLength={12} maxLength={12} className={field} value={iin} onChange={e => setIin(e.target.value)} /></label><label className="text-sm">ФИО кандидата<input required className={field} value={fullName} onChange={e => setFullName(e.target.value)} /></label></div>
        <label className="block text-sm">Дата рождения<input type="date" className={field} value={birthDate} onChange={e => setBirthDate(e.target.value)} /></label>
        <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Дата заявления<input type="date" required className={field} value={received} onChange={e => setReceived(e.target.value)} /></label><label className="text-sm">Планируемая дата начала<input type="date" required className={field} value={start} onChange={e => setStart(e.target.value)} /></label></div>
        <label className="block text-sm">Отделение<select required className={field} value={unitId ?? ""} onChange={e => { setUnitId(Number(e.target.value) || null); setPositionId(null); }}><option value="">Выберите отделение</option>{units.map(row => <option key={row.unit_id} value={row.unit_id}>{row.name}</option>)}</select></label>
        <label className="block text-sm">Должность<select required className={field} value={positionId ?? ""} onChange={e => setPositionId(Number(e.target.value) || null)}><option value="">Выберите должность</option>{positions.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
        <label className="block text-sm">Ставка<input required type="number" step="0.01" min="0.01" max="2" className={field} value={rate} onChange={e => setRate(e.target.value)} /></label>
        <button disabled={busy || unitId == null || positionId == null} className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Сформировать заявление</button>
      </form> : <div className="space-y-5">
        <p className="rounded bg-emerald-50 p-3 text-sm text-emerald-800">Заявление №{applicationId} сохранено. Личная карточка: {personId}.</p>
        <details className="rounded border p-3"><summary className="cursor-pointer font-medium">Изменить условия приёма</summary><div className="mt-3 space-y-3">
          <label className="block text-sm">Отделение<select className={field} value={unitId ?? ""} onChange={e => { setUnitId(Number(e.target.value) || null); setPositionId(null); }}><option value="">Выберите отделение</option>{units.map(row => <option key={row.unit_id} value={row.unit_id}>{row.name}</option>)}</select></label>
          <label className="block text-sm">Должность<select className={field} value={positionId ?? ""} onChange={e => setPositionId(Number(e.target.value) || null)}><option value="">Выберите должность</option>{positions.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
          <div className="grid gap-2 sm:grid-cols-2"><label className="text-sm">Ставка<input className={field} type="number" min="0.01" max="2" step="0.01" value={rate} onChange={e => setRate(e.target.value)} /></label><label className="text-sm">Начало работы<input className={field} type="date" value={start} onChange={e => setStart(e.target.value)} /></label></div>
          <button disabled={busy || unitId == null || positionId == null} className="rounded border px-3 py-2 text-sm" onClick={() => void saveConditions()}>Сохранить условия</button>
        </div></details>
        <div className="flex flex-wrap gap-2"><button className="rounded border px-3 py-2" onClick={() => setLocale("ru")}>Русский</button><button className="rounded border px-3 py-2" onClick={() => setLocale("kk")}>Қазақша</button><button className="rounded border px-3 py-2" onClick={openPrint}>Печать</button><button className="rounded border px-3 py-2" onClick={() => { void printElectronicHire(applicationId).then(setPrintText).catch(e => setError(message(e))); }}>Обновить после исправлений в ЛК</button></div>
        {printText && <pre className="whitespace-pre-wrap rounded border bg-zinc-50 p-5 font-serif text-base leading-7">{printText[locale]}</pre>}
        <button disabled={busy || checked} className="rounded border px-3 py-2" onClick={() => { void checkElectronicHire(applicationId).then(() => setChecked(true)).catch(e => setError(message(e))); }}>{checked ? "Данные проверены кандидатом" : "Данные проверены кандидатом"}</button>
        <p className="text-xs text-zinc-600">Эта отметка не является электронной подписью.</p>
        <label className="block text-sm">Подписанное бумажное заявление (PDF или фото)<input type="file" accept="application/pdf,image/jpeg,image/png" className="mt-1 block" onChange={e => { const file = e.target.files?.[0]; if (file) void uploadElectronicHireSignedCopy(applicationId, file).then(r => setUploaded(r.file_name)).catch(err => setError(message(err))); }} /></label>
        {uploaded && <p className="text-sm text-emerald-700">Прикреплено: {uploaded}</p>}
        <div className="flex flex-wrap gap-2"><a className="rounded bg-zinc-900 px-3 py-2 text-sm text-white" href={`/directory/personnel/persons/${personId}/card`} target="_blank" rel="noreferrer">Создать / восстановить ЛК</a><button className="rounded border px-3 py-2 text-sm" onClick={() => setAssist(true)}>Заполнить с кадровиком</button><button className="rounded border px-3 py-2 text-sm" onClick={() => void issue(Boolean(link))}>Выдать ссылку на 24 часа</button></div>
        {link && <div className="rounded border bg-zinc-50 p-3 text-sm"><p>Ссылка для кандидата: <a className="underline" href={link}>{window.location.origin}{link}</a></p><button className="mt-2 underline" onClick={() => void issue(true)}>Перевыпустить ссылку</button></div>}
        {link && <button className="rounded border px-3 py-2 text-sm" onClick={() => { void sendElectronicHireLinkTelegram(applicationId).then(result => setNotification(result.status === "sent" ? "Ссылка отправлена кандидату" : result.last_error || "Доставка не удалась")).catch(e => setError(message(e))); }}>Отправить ссылку через Telegram</button>}
        <div className="border-t pt-4"><button disabled={busy} className="rounded bg-zinc-900 px-4 py-2 text-sm text-white disabled:opacity-50" onClick={() => void createOrder()}>Сформировать приказ</button>
          {orderId && <p className="mt-2 text-sm">Проект приказа №{orderId} · <a className="underline" href={`/directory/personnel/orders?order_id=${orderId}`}>Открыть проект</a></p>}
          {notification && <p className="mt-2 text-sm">Уведомление: {notification}</p>}
          {orderId && notification !== "sent" && <button className="mt-2 text-sm underline" onClick={() => { void retryElectronicHireNotification(applicationId).then(r => setNotification(r.status === "sent" ? "sent" : r.last_error || r.status)).catch(e => setError(message(e))); }}>Повторить отправку руководителю</button>}
        </div>
      </div>}
    </aside>
    <PersonnelApplicationIntakeOnBehalfDrawer applicationId={applicationId} open={assist} onClose={() => setAssist(false)} />
  </div>;
}
