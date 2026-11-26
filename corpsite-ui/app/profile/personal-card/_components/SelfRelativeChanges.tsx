"use client";

import * as React from "react";
import { relationshipTypeLabel, relationshipTypeOptions } from "@/app/directory/personnel/_lib/pprCardPresentation";
import { api, changeError, ChangeButton, ChangeModal, ChangeStatus } from "./SelfChangeControls";

type Relative = { record_id: number; updated_at: string; relationship_type: string; full_name: string;
  birth_date?: string | null; birth_place?: string | null; organization_name?: string | null;
  residence_address?: string | null; notes?: string | null };
type Proposal = Omit<Relative, "record_id" | "updated_at">;
type Request = { request_id: string; request_kind: "correction" | "addition"; relative_id: number | null;
  expected_updated_at: string | null; proposed: Proposal; status: "pending" | "returned" | "approved";
  revision: number; reason: string; approved_relative_id: number | null };

const buttonClass = "rounded-md border border-blue-600 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50 dark:text-blue-300";
const fieldClass = "mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950";
const sameAddressValue = "Проживает со мной";
const fields = ["relationship_type", "full_name", "birth_date", "birth_place", "organization_name", "residence_address", "notes"] as const;
const blank: Proposal = { relationship_type: "", full_name: "", birth_date: null, birth_place: null,
  organization_name: null, residence_address: null, notes: null };

function values(record: Relative | Proposal): Proposal {
  return Object.fromEntries(fields.map((key) => [key, record[key] ?? null])) as Proposal;
}

export default function SelfRelativeChanges({ records }: { records: Relative[] }) {
  const [requests, setRequests] = React.useState<Request[]>([]);
  const [open, setOpen] = React.useState(false);
  const [mode, setMode] = React.useState<"addition" | "correction">("correction");
  const [selected, setSelected] = React.useState<Relative | null>(null);
  const [returned, setReturned] = React.useState<Request | null>(null);
  const [draft, setDraft] = React.useState<Proposal | null>(null);
  const [sameAddress, setSameAddress] = React.useState(false);
  const [detailsOpen, setDetailsOpen] = React.useState(false);
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    void api<{ items: Request[] }>("/api/ppr/me/relative-change-requests")
      .then((data) => setRequests(data.items)).catch(() => setError("Не удалось загрузить заявки."));
  }, []);

  const latestFor = (record: Relative) => requests.find((item) =>
    item.relative_id === record.record_id || item.approved_relative_id === record.record_id);
  const editableRecords = records.filter((record) => latestFor(record)?.status !== "pending");
  const pendingAddition = requests.find((item) => item.request_kind === "addition" && item.status === "pending");
  const additions = requests.filter((item) => item.request_kind === "addition" &&
    (item.status !== "approved" || !records.some((record) => record.record_id === item.approved_relative_id)));

  function edit(record: Relative, previous?: Request) {
    const initial = values(previous?.proposed ?? record);
    setMode("correction"); setSelected(record); setReturned(previous ?? null); setDraft(initial);
    setSameAddress(initial.residence_address === sameAddressValue);
    setDetailsOpen(false); setError(""); setOpen(true);
  }

  function add(previous?: Request) {
    const initial = values(previous?.proposed ?? blank);
    setMode("addition"); setSelected(null); setReturned(previous ?? null); setDraft(initial);
    setSameAddress(initial.residence_address === sameAddressValue);
    setDetailsOpen(false); setError(""); setOpen(true);
  }

  function update(key: keyof Proposal, value: string | null) {
    setDraft((old) => old ? { ...old, [key]: value } : old);
  }

  function relationship(value: string) {
    if (!draft) return;
    if (value === "son" || value === "daughter") {
      const together = !draft.residence_address || draft.residence_address === sameAddressValue;
      setSameAddress(together);
      setDraft({ ...draft, relationship_type: value,
        residence_address: together ? sameAddressValue : draft.residence_address });
    } else {
      setSameAddress(false);
      setDraft({ ...draft, relationship_type: value,
        residence_address: draft.residence_address === sameAddressValue ? null : draft.residence_address });
    }
  }

  async function send() {
    if (!draft || (mode === "correction" && !selected) || busy) return;
    setBusy(true); setError("");
    try {
      const path = returned ? `/api/ppr/me/relative-change-requests/${returned.request_id}/resubmit`
        : mode === "addition" ? "/api/ppr/me/relatives/change-requests"
        : `/api/ppr/me/relatives/${selected!.record_id}/change-requests`;
      const body = { proposed: draft,
        ...(mode === "correction" ? { expected_updated_at: selected!.updated_at } : {}),
        ...(returned ? { expected_revision: returned.revision } : {}) };
      const updated = await api<Request>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      setRequests((old) => [updated, ...old.filter((item) => item.request_id !== updated.request_id)]);
      setOpen(false);
    } catch (caught) { setError(changeError(caught, "Не удалось отправить заявку.")); }
    finally { setBusy(false); }
  }

  const child = draft?.relationship_type === "son" || draft?.relationship_type === "daughter";
  return <div className="mt-3 space-y-3" data-testid="self-relative-changes">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-lg font-semibold">Родственники</h2>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={`${buttonClass} disabled:opacity-50`} disabled={!!pendingAddition} onClick={() => add()}>Добавить родственника</button>
        {records.length > 0 && <ChangeButton disabled={editableRecords.length === 0} onClick={() => {
          if (editableRecords.length === 1) edit(editableRecords[0], latestFor(editableRecords[0])?.status === "returned" ? latestFor(editableRecords[0]) : undefined);
          else { setMode("correction"); setSelected(null); setDraft(null); setReturned(null); setError(""); setOpen(true); }
        }} />}
      </div>
    </div>
    <p className="text-sm text-zinc-600">Новая запись или исправление действующей записи поступят кадровику на проверку.</p>
    {pendingAddition && <p className="text-sm text-amber-800">Новый родственник уже на проверке. Дождитесь решения кадровика.</p>}
    {records.length === 0 && <p className="text-sm text-zinc-500">Записей о родственниках пока нет. Добавьте первого родственника.</p>}
    {records.map((record) => {
      const request = latestFor(record);
      const pending = request?.status === "pending";
      return <div key={record.record_id} className="rounded-lg border p-3 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-2"><strong>{record.full_name}</strong>
          <button type="button" className={`${buttonClass} disabled:cursor-not-allowed disabled:opacity-50`}
            onClick={() => edit(record, request?.status === "returned" ? request : undefined)} disabled={pending}
            aria-describedby={pending ? `relative-pending-${record.record_id}` : undefined}>Исправить</button></div>
        <p>Степень родства: {relationshipTypeLabel(record.relationship_type)}</p>
        {pending && <p id={`relative-pending-${record.record_id}`} className="mt-2 text-sm text-amber-800">Исправление уже отправлено кадровику. Дождитесь решения.</p>}
        {request && <p className="mt-2"><ChangeStatus state={request.status} reason={request.reason} /></p>}
        {request?.status === "returned" && <button type="button" className="mt-2 text-blue-700 underline" onClick={() => edit(record, request)}>Открыть предложенные значения</button>}
      </div>;
    })}
    {additions.map((request) => <div key={request.request_id} className="rounded-lg border p-3 text-sm">
      <strong>Новый родственник: {request.proposed.full_name}</strong>
      <p className="mt-2"><ChangeStatus state={request.status} reason={request.reason} /></p>
      {request.status === "returned" && <button type="button" className="mt-2 text-blue-700 underline" onClick={() => add(request)}>Исправить и отправить повторно</button>}
    </div>)}
    {error && !open && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {open && <ChangeModal title={mode === "addition" ? "Добавление родственника" : "Исправление записи о родственнике"} onClose={() => setOpen(false)}>
      <p className="mt-3 text-sm text-zinc-600">{mode === "addition" ? "Новая запись появится в карточке после одобрения кадровиком." : "Исправление уйдёт кадровику; текущие данные сохранятся до одобрения."}</p>
      {mode === "correction" && <label className="mt-4 block text-sm">Запись
        <select className={fieldClass} value={selected?.record_id ?? ""} onChange={(event) => {
          const record = editableRecords.find((item) => item.record_id === Number(event.target.value));
          if (record) edit(record, latestFor(record)?.status === "returned" ? latestFor(record) : undefined);
          else { setSelected(null); setReturned(null); setDraft(null); }
        }}><option value="">Выберите родственника</option>{editableRecords.map((record) => <option key={record.record_id} value={record.record_id}>{record.full_name}</option>)}</select>
      </label>}
      {draft && <div className="mt-3 space-y-3">
        <label className="block text-sm">ФИО<input autoFocus className={fieldClass} value={draft.full_name ?? ""} onChange={(event) => update("full_name", event.target.value)} /></label>
        <label className="block text-sm">Степень родства<select className={fieldClass} value={draft.relationship_type ?? ""} onChange={(event) => relationship(event.target.value)}><option value="">Выберите степень родства</option>{relationshipTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        <label className="block text-sm">Дата рождения<input type="date" className={fieldClass} value={draft.birth_date ?? ""} onChange={(event) => update("birth_date", event.target.value || null)} /></label>
        {child && <fieldset className="text-sm"><legend className="font-medium">Место проживания ребёнка</legend><div className="mt-2 flex flex-wrap gap-4">
          <label><input type="radio" name="child-residence" checked={sameAddress} onChange={() => { setSameAddress(true); update("residence_address", sameAddressValue); }} /> Проживает со мной</label>
          <label><input type="radio" name="child-residence" checked={!sameAddress} onChange={() => { setSameAddress(false); update("residence_address", null); setDetailsOpen(true); }} /> Другой адрес</label>
        </div></fieldset>}
        <details open={detailsOpen} onToggle={(event) => setDetailsOpen(event.currentTarget.open)} className="rounded border p-3"><summary className="cursor-pointer font-medium">Дополнительные сведения</summary><div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-sm">Место рождения<input className={fieldClass} value={draft.birth_place ?? ""} onChange={(event) => update("birth_place", event.target.value || null)} /></label>
          <label className="text-sm">Организация<input className={fieldClass} value={draft.organization_name ?? ""} onChange={(event) => update("organization_name", event.target.value || null)} /></label>
          {(!child || !sameAddress) && <label className="text-sm">Адрес проживания<input className={fieldClass} value={draft.residence_address ?? ""} onChange={(event) => update("residence_address", event.target.value || null)} /></label>}
          <label className="text-sm">Примечание<input className={fieldClass} value={draft.notes ?? ""} onChange={(event) => update("notes", event.target.value || null)} /></label>
        </div></details>
      </div>}
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      <button type="button" disabled={(mode === "correction" && !selected) || !draft?.full_name.trim() || !draft?.relationship_type || busy}
        className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50" onClick={() => void send()}>{busy ? "Отправляем заявку…" : "Отправить на проверку"}</button>
    </ChangeModal>}
  </div>;
}
