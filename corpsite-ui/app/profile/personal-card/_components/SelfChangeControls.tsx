"use client";

import * as React from "react";
import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";
import { relationshipTypeLabel, relationshipTypeOptions } from "@/app/directory/personnel/_lib/pprCardPresentation";
import PhotoCropEditor from "./PhotoCropEditor";

type Relative = { record_id: number; updated_at: string; relationship_type: string; full_name: string;
  birth_date?: string | null; birth_place?: string | null; organization_name?: string | null;
  residence_address?: string | null; notes?: string | null };
type Request = { request_id: string; relative_id: number; expected_updated_at: string; proposed: Omit<Relative, "record_id" | "updated_at">;
  status: "pending" | "returned" | "approved"; revision: number; reason: string; approved_relative_id: number | null };
type PhotoVersion = { version_id: string; set_id: string; kind: string; state: string; revision: number; reason: string; created_at: string };

const buttonClass = "rounded-md border border-blue-600 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50 dark:text-blue-300";
const fieldClass = "mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950";
const statusLabel: Record<string, string> = { pending: "На проверке", approved: "Одобрено", returned: "Возвращено" };
const statusClass: Record<string, string> = { pending: "bg-amber-100 text-amber-900", approved: "bg-emerald-100 text-emerald-900", returned: "bg-rose-100 text-rose-900" };

export function ChangeStatus({ state, reason }: { state: string; reason?: string }) {
  if (!statusLabel[state]) return null;
  return <span><span className={`rounded-full px-2 py-1 text-xs font-medium ${statusClass[state]}`}>{statusLabel[state]}</span>{state === "returned" && reason ? <span className="ml-2 text-sm">{reason}</span> : null}</span>;
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(resolveApiUrl(path), { ...init, headers: buildHeaders(init.headers as Record<string, string> | undefined), cache: "no-store" });
  if (!response.ok) throw toApiError(response.status, await readJsonSafe(response), { method: init.method ?? "GET", url: path });
  return response.json() as Promise<T>;
}

function changeError(caught: unknown, fallback: string): string {
  if (caught && typeof caught === "object" && "message" in caught && typeof caught.message === "string" && !(caught instanceof TypeError)) {
    return caught.message;
  }
  if (caught instanceof TypeError) return "Не удалось связаться с сервером. Проверьте подключение и повторите попытку.";
  return fallback;
}

export function ChangeButton({ onClick, disabled = false }: { onClick: () => void; disabled?: boolean }) {
  return <button type="button" className={`${buttonClass} disabled:cursor-not-allowed disabled:opacity-50`} onClick={onClick} disabled={disabled}>Внести изменения</button>;
}

export function ChangeModal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return <div role="presentation" className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section role="dialog" aria-modal="true" aria-label={title} className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-xl bg-white p-5 shadow-xl dark:bg-zinc-950">
      <div className="flex items-start justify-between gap-3"><h2 className="text-lg font-semibold">{title}</h2><button type="button" onClick={onClose} aria-label="Закрыть" className="text-xl">×</button></div>
      {children}
    </section>
  </div>;
}

export function SelfPhotoChanges() {
  const [open, setOpen] = React.useState(false);
  const [current, setCurrent] = React.useState<string | null>(null);
  const [preview, setPreview] = React.useState<string | null>(null);
  const [file, setFile] = React.useState<File | null>(null);
  const [source, setSource] = React.useState<File | null>(null);
  const [sourceKey, setSourceKey] = React.useState(0);
  const [latest, setLatest] = React.useState<PhotoVersion | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  React.useEffect(() => {
    let alive = true;
    void (async () => {
      const [photo, files] = await Promise.all([
        fetch(resolveApiUrl("/api/ppr/me/photo"), { headers: buildHeaders(), cache: "no-store" }),
        api<{ items: PhotoVersion[] }>("/api/personnel-files/me"),
      ]);
      if (!alive) return;
      if (photo.ok) setCurrent(URL.createObjectURL(await photo.blob()));
      setLatest(files.items.filter((item) => item.kind === "photo").sort((a, b) => b.created_at.localeCompare(a.created_at))[0] ?? null);
    })().catch(() => { if (alive) setError("Не удалось загрузить состояние фото."); });
    return () => { alive = false; };
  }, []);
  React.useEffect(() => () => { if (current) URL.revokeObjectURL(current); }, [current]);
  React.useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const cropReady = React.useCallback((cropped: File | null, url: string | null) => { setFile(cropped); setPreview(url); }, []);
  const cropError = React.useCallback((message: string) => { setFile(null); setPreview(null); setError(message); }, []);

  async function send() {
    if (!file) return;
    setBusy(true); setError("");
    try {
      const body = new FormData();
      body.append("file", file); body.append("kind", "photo"); body.append("title", "Фото лица");
      if (latest) { body.append("set_id", latest.set_id); body.append("expected_revision", String(latest.revision)); body.append("expected_version_id", latest.version_id); }
      const result = await api<PhotoVersion>("/api/personnel-files/me", { method: "POST", body });
      setLatest(result); setFile(null); setSource(null); setPreview(null); setOpen(false);
    } catch (caught) { setError(changeError(caught, "Не удалось отправить фото.")); }
    finally { setBusy(false); }
  }
  return <div className="space-y-2" data-testid="self-photo-changes">
    <div className="flex items-center gap-3">{current ? <img src={current} alt="Текущее фото" className="h-24 w-24 rounded-lg object-cover" /> : <div className="flex h-24 w-24 items-center justify-center rounded-lg bg-zinc-100 text-xs text-zinc-500">Фото отсутствует</div>}<ChangeButton onClick={() => setOpen(true)} /></div>
    {latest && statusLabel[latest.state] && <p className="text-sm">Заявка на фото: <ChangeStatus state={latest.state} reason={latest.reason} /></p>}
    {open && <ChangeModal title="Замена фото" onClose={() => setOpen(false)}>
      <p className="mt-3 text-sm text-zinc-600">Новое фото уйдёт кадровику на проверку. Действующее фото останется в карточке до одобрения.</p>
      <p className="mt-2 text-sm text-zinc-600">Выберите JPEG, из которого можно выделить кадр не меньше 480 × 640 пикселей. Итоговый файл будет JPEG 600 × 800 пикселей, не более 500 КБ.</p>
      <div className="mt-4 flex gap-4">{current && <div><p className="text-xs">Сейчас</p><img src={current} alt="Действующее фото" className="mt-1 h-32 w-32 rounded object-cover" /></div>}{preview && <div><p className="text-xs">Итоговый JPEG 600 × 800</p><img src={preview} alt="Итоговое фото 600 на 800" className="mt-1 h-32 w-24 rounded object-cover" /></div>}</div>
      <label className="mt-4 block text-sm">Выберите исходный JPEG<input type="file" accept="image/jpeg" className={fieldClass} onChange={(event) => { setFile(null); setPreview(null); setError(""); setSource(event.target.files?.[0] ?? null); setSourceKey((value) => value + 1); }} /></label>
      {source && <PhotoCropEditor key={sourceKey} source={source} onReady={cropReady} onError={cropError} />}
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      <button type="button" disabled={!file || busy} onClick={() => void send()} className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50">Отправить на проверку</button>
    </ChangeModal>}
  </div>;
}

const relativeFields = [
  ["relationship_type", "Степень родства"], ["full_name", "ФИО"], ["birth_date", "Дата рождения"],
  ["birth_place", "Место рождения"], ["organization_name", "Организация"],
  ["residence_address", "Адрес проживания"], ["notes", "Примечание"],
] as const;
const pendingRelativeMessage = "Исправление уже отправлено кадровику. Дождитесь решения, прежде чем подавать новое.";
function values(record: Relative | Request["proposed"]): Request["proposed"] {
  return Object.fromEntries(relativeFields.map(([key]) => [key, record[key] ?? null])) as Request["proposed"];
}

export function SelfRelativeChanges({ records }: { records: Relative[] }) {
  const [requests, setRequests] = React.useState<Request[]>([]);
  const [open, setOpen] = React.useState(false);
  const [selected, setSelected] = React.useState<Relative | null>(null);
  const [returnRequest, setReturnRequest] = React.useState<Request | null>(null);
  const [draft, setDraft] = React.useState<Request["proposed"] | null>(null);
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => { void api<{ items: Request[] }>("/api/ppr/me/relative-change-requests").then((data) => setRequests(data.items)).catch(() => setError("Не удалось загрузить заявки.")); }, []);
  const latestFor = (record: Relative) => requests.find((item) => item.relative_id === record.record_id || item.approved_relative_id === record.record_id);
  const editableRecords = records.filter((record) => latestFor(record)?.status !== "pending");
  function edit(record: Relative, previous?: Request) { setSelected(record); setReturnRequest(previous ?? null); setDraft(values(previous?.proposed ?? record)); setError(""); setOpen(true); }
  async function send() {
    if (!selected || !draft) return;
    setBusy(true); setError("");
    try {
      const path = returnRequest ? `/api/ppr/me/relative-change-requests/${returnRequest.request_id}/resubmit` : `/api/ppr/me/relatives/${selected.record_id}/change-requests`;
      const body = { expected_updated_at: selected.updated_at, proposed: draft, ...(returnRequest ? { expected_revision: returnRequest.revision } : {}) };
      const updated = await api<Request>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      setRequests((old) => [updated, ...old.filter((item) => item.request_id !== updated.request_id)]);
      setOpen(false);
    } catch (caught) { setError(changeError(caught, "Не удалось отправить заявку.")); }
    finally { setBusy(false); }
  }
  return <div className="mt-3 space-y-3" data-testid="self-relative-changes">
    <div className="flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">Родственники</h2>{records.length > 0 && <ChangeButton disabled={editableRecords.length === 0} onClick={() => { if (editableRecords.length === 1) edit(editableRecords[0], latestFor(editableRecords[0])?.status === "returned" ? latestFor(editableRecords[0]) : undefined); else { setSelected(null); setDraft(null); setOpen(true); } }} />}</div>
    <p className="text-sm text-zinc-600">Исправление действующей записи будет проверено кадровиком.</p>
    {records.length === 0 && <p className="text-sm text-zinc-500">Записей о родственниках пока нет. Исправлять пока нечего.</p>}
    {records.map((record) => { const request = latestFor(record); const pending = request?.status === "pending"; return <div key={record.record_id} className="rounded-lg border p-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><strong>{record.full_name}</strong><button type="button" className={`${buttonClass} disabled:cursor-not-allowed disabled:opacity-50`} onClick={() => edit(record, request?.status === "returned" ? request : undefined)} disabled={pending} aria-describedby={pending ? `relative-pending-${record.record_id}` : undefined}>Исправить</button></div><p>Степень родства: {relationshipTypeLabel(record.relationship_type)}</p>{pending && <p id={`relative-pending-${record.record_id}`} className="mt-2 text-sm text-amber-800 dark:text-amber-300">{pendingRelativeMessage}</p>}{request && <p className="mt-2"><ChangeStatus state={request.status} reason={request.reason} /></p>}{request?.status === "returned" && <button type="button" className="mt-2 text-blue-700 underline" onClick={() => edit(record, request)}>Открыть предложенные значения</button>}</div>; })}
    {error && !open && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {open && <ChangeModal title="Исправление записи о родственнике" onClose={() => setOpen(false)}>
      <p className="mt-3 text-sm text-zinc-600">Выберите действующую запись и укажите исправления. Заявка уйдёт кадровику; текущие данные сохранятся до одобрения.</p>
      <label className="mt-4 block text-sm">Запись<select className={fieldClass} value={selected?.record_id ?? ""} onChange={(event) => { const record = editableRecords.find((item) => item.record_id === Number(event.target.value)); if (record) edit(record, latestFor(record)?.status === "returned" ? latestFor(record) : undefined); else { setSelected(null); setReturnRequest(null); setDraft(null); } }}><option value="">Выберите родственника</option>{editableRecords.map((record) => <option key={record.record_id} value={record.record_id}>{record.full_name}</option>)}</select></label>
      {selected && draft && <div className="mt-3 grid gap-3 sm:grid-cols-2">{relativeFields.map(([key, label]) => <label key={key} className="text-sm">{label}{key === "relationship_type" ? <select className={fieldClass} value={draft.relationship_type ?? ""} onChange={(event) => setDraft((old) => old ? { ...old, relationship_type: event.target.value } : old)}>{relationshipTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select> : <input className={fieldClass} type={key === "birth_date" ? "date" : "text"} value={draft[key] ?? ""} onChange={(event) => setDraft((old) => old ? { ...old, [key]: event.target.value || null } : old)} />}</label>)}</div>}
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      <button type="button" disabled={!selected || !draft?.full_name || !draft?.relationship_type || busy} className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50" onClick={() => void send()}>Отправить на проверку</button>
    </ChangeModal>}
  </div>;
}
