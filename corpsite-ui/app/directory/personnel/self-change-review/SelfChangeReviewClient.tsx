"use client";

import * as React from "react";
import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";
import { relationshipTypeLabel } from "../_lib/pprCardPresentation";

type Photo = { version_id: string; person_id: number; kind: string; title: string; revision: number; state: string; full_name: string };
type RelativeRequest = { request_id: string; person_id: number; relative_id: number; revision: number; employee_name: string;
  current: Record<string, unknown>; proposed: Record<string, unknown> };
const fields = [["relationship_type", "Степень родства"], ["full_name", "ФИО"], ["birth_date", "Дата рождения"],
  ["birth_place", "Место рождения"], ["organization_name", "Организация"],
  ["residence_address", "Адрес проживания"], ["notes", "Примечание"]] as const;

function relativeValue(key: string, value: unknown): string {
  return key === "relationship_type" ? relationshipTypeLabel(typeof value === "string" ? value : null) : String(value ?? "—");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(resolveApiUrl(path), { ...init, headers: buildHeaders(init.headers as Record<string, string> | undefined), cache: "no-store" });
  if (!response.ok) throw toApiError(response.status, await readJsonSafe(response), { method: init.method ?? "GET", url: path });
  return response.json() as Promise<T>;
}

function decisionError(caught: unknown): string {
  if (caught instanceof TypeError) return "Ответ сервера не получен. Обновите очередь и проверьте статус заявки перед повторной попыткой.";
  if (caught && typeof caught === "object" && "message" in caught && typeof caught.message === "string") {
    const status = "status" in caught && typeof caught.status === "number" ? caught.status : null;
    return status !== null && status < 500 ? `Решение не сохранено: ${caught.message}` : `Не удалось подтвердить решение: ${caught.message}`;
  }
  return "Не удалось подтвердить решение. Обновите очередь и проверьте статус заявки.";
}

function PhotoCompare({ photo, actions }: { photo: Photo; actions: React.ReactNode }) {
  const [current, setCurrent] = React.useState<string | null>(null);
  const [proposed, setProposed] = React.useState<string | null>(null);
  const [largeOpen, setLargeOpen] = React.useState(false);
  const closeRef = React.useRef<HTMLButtonElement>(null);
  React.useEffect(() => {
    let active = true;
    const load = async (path: string, setter: (url: string) => void) => {
      const response = await fetch(resolveApiUrl(path), { headers: buildHeaders(), cache: "no-store" });
      if (!response.ok) return;
      const blob = await response.blob();
      if (active) setter(URL.createObjectURL(blob));
    };
    void load(`/api/personnel-files/persons/${photo.person_id}/current-photo`, setCurrent);
    void load(`/api/personnel-files/versions/${photo.version_id}/preview`, setProposed);
    return () => { active = false; };
  }, [photo.person_id, photo.version_id]);
  React.useEffect(() => () => { if (current) URL.revokeObjectURL(current); }, [current]);
  React.useEffect(() => () => { if (proposed) URL.revokeObjectURL(proposed); }, [proposed]);
  React.useEffect(() => {
    if (!largeOpen) return;
    closeRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setLargeOpen(false); };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [largeOpen]);
  return <div className="mt-3 flex flex-wrap items-start gap-6">
    <div><p className="text-sm font-medium">Текущее фото</p>{current ? <img src={current} alt="Текущее фото" className="mt-2 h-48 w-36 rounded object-contain" /> : <p className="mt-2 text-sm text-zinc-500">Фото отсутствует</p>}</div>
    <div className="flex flex-wrap items-start gap-5">
      <div><p className="text-sm font-medium">Новое фото на проверке</p>{proposed ? <button type="button" onClick={() => setLargeOpen(true)} aria-label="Открыть новое фото крупно" className="mt-2 rounded text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"><img src={proposed} alt="Новое фото на проверке" className="h-48 w-36 rounded object-contain" /><span className="mt-1 block text-sm text-blue-700 underline dark:text-blue-300">Открыть крупно</span></button> : <p className="mt-2 text-sm text-zinc-500">Загрузка фото…</p>}</div>
      <div className="min-w-56"><p className="text-sm font-semibold">Решение по новому фото</p>{actions}</div>
    </div>
    {largeOpen && proposed && <div role="presentation" className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setLargeOpen(false); }}>
      <section role="dialog" aria-modal="true" aria-label={`Новое фото на проверке: ${photo.full_name}`} className="max-h-[95vh] w-full max-w-[700px] overflow-y-auto rounded-xl bg-white p-4 text-zinc-900 shadow-xl dark:bg-zinc-950 dark:text-zinc-50">
        <div className="flex items-start justify-between gap-4"><div><h2 className="text-lg font-semibold">Новое фото на проверке</h2><p className="text-sm text-zinc-500">{photo.full_name} · сохранённый кадр целиком</p></div><button ref={closeRef} type="button" onClick={() => setLargeOpen(false)} className="rounded border px-3 py-1.5 text-sm">Закрыть</button></div>
        <img src={proposed} alt="Полный сохранённый кадр нового фото" className="mx-auto mt-4 max-h-[75vh] max-w-full object-contain" />
      </section>
    </div>}
  </div>;
}

export default function SelfChangeReviewClient() {
  const [photos, setPhotos] = React.useState<Photo[]>([]);
  const [relatives, setRelatives] = React.useState<RelativeRequest[]>([]);
  const [reasons, setReasons] = React.useState<Record<string, string>>({});
  const [error, setError] = React.useState("");
  const [decisionErrors, setDecisionErrors] = React.useState<Record<string, string>>({});
  const [confirmation, setConfirmation] = React.useState("");
  const [busy, setBusy] = React.useState<string | null>(null);
  const load = React.useCallback(async () => {
    const results = await Promise.allSettled([
      request<{ items: Photo[] }>("/api/personnel-files/review-queue"),
      request<{ items: RelativeRequest[] }>("/api/ppr/relative-change-requests/review-queue"),
    ]);
    if (results[0].status === "fulfilled") setPhotos(results[0].value.items.filter((item) => item.kind === "photo"));
    if (results[1].status === "fulfilled") setRelatives(results[1].value.items);
    const unavailable = [results[0].status === "rejected" ? "фото" : null, results[1].status === "rejected" ? "родственников" : null].filter(Boolean);
    setError(unavailable.length ? `Не удалось обновить очередь ${unavailable.join(" и ")}.` : "");
  }, []);
  React.useEffect(() => { void load(); }, [load]);
  async function decide(kind: "photo" | "relative", id: string, revision: number, action: "approve" | "return", employeeName: string) {
    setBusy(id);
    setDecisionErrors((old) => { const updated = { ...old }; delete updated[id]; return updated; });
    try {
      const reason = reasons[id] ?? "";
      const path = kind === "photo" ? `/api/personnel-files/versions/${id}/decision` : `/api/ppr/relative-change-requests/${id}/decision`;
      const result = await request<{ state?: string; status?: string }>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision: revision, action, reason }) });
      const actual = kind === "photo" ? result.state : result.status;
      const expected = action === "approve" ? "approved" : "returned";
      if (actual !== expected) {
        setDecisionErrors((old) => ({ ...old, [id]: `Сервер вернул статус «${actual ?? "неизвестен"}». Обновите очередь перед следующим решением.` }));
        void load();
        return;
      }
      if (kind === "photo") setPhotos((old) => old.filter((item) => item.version_id !== id));
      else setRelatives((old) => old.filter((item) => item.request_id !== id));
      setConfirmation(kind === "photo"
        ? `Новое фото сотрудника ${employeeName} ${action === "approve" ? "одобрено" : "возвращено с пояснением"}. Решение сохранено.`
        : `Исправление родственника сотрудника ${employeeName} ${action === "approve" ? "одобрено" : "возвращено с пояснением"}. Решение сохранено.`);
      void load();
    } catch (caught) { setDecisionErrors((old) => ({ ...old, [id]: decisionError(caught) })); }
    finally { setBusy(null); }
  }
  const actions = (kind: "photo" | "relative", id: string, revision: number, employeeName: string) => <div className={kind === "photo" ? "mt-2 flex flex-col items-start gap-2" : "mt-4 flex flex-wrap items-end gap-2"}><button type="button" disabled={busy === id} onClick={() => void decide(kind, id, revision, "approve", employeeName)} className="rounded bg-emerald-700 px-3 py-2 text-sm text-white disabled:opacity-50">{kind === "photo" ? "Одобрить новое фото" : "Одобрить"}</button><label className="text-sm">Пояснение для возврата<input className="mt-1 block rounded border px-2 py-2 dark:bg-zinc-950" value={reasons[id] ?? ""} onChange={(event) => setReasons((old) => ({ ...old, [id]: event.target.value }))} /></label><button type="button" disabled={busy === id || !(reasons[id] ?? "").trim()} onClick={() => void decide(kind, id, revision, "return", employeeName)} className="rounded border border-amber-600 px-3 py-2 text-sm disabled:opacity-50">{kind === "photo" ? "Вернуть новое фото с пояснением" : "Вернуть с пояснением"}</button>{decisionErrors[id] && <p role="alert" className="text-sm text-red-700 dark:text-red-300">{decisionErrors[id]}</p>}</div>;
  return <div className="space-y-5 p-4"><h1 className="text-2xl font-semibold">Изменения личных карточек на проверке</h1>{confirmation && <p role="status" className="rounded border border-emerald-400 bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">{confirmation}</p>}{error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    <section><h2 className="text-lg font-semibold">Фото</h2>{photos.length === 0 && <p className="text-sm text-zinc-500">Нет заявок.</p>}{photos.map((photo) => <article key={photo.version_id} className="my-3 rounded-lg border p-4"><h3 className="font-medium">{photo.full_name} · фото</h3><PhotoCompare photo={photo} actions={actions("photo", photo.version_id, photo.revision, photo.full_name)} /></article>)}</section>
    <section><h2 className="text-lg font-semibold">Родственники</h2>{relatives.length === 0 && <p className="text-sm text-zinc-500">Нет заявок.</p>}{relatives.map((item) => <article key={item.request_id} className="my-3 rounded-lg border p-4"><h3 className="font-medium">{item.employee_name} · запись #{item.relative_id}</h3><div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>Поле</th><th>Сейчас</th><th>Предложено</th></tr></thead><tbody>{fields.map(([key, label]) => <tr key={key} className="border-t"><th className="py-2">{label}</th><td className="py-2">{relativeValue(key, item.current[key])}</td><td className="py-2">{relativeValue(key, item.proposed[key])}</td></tr>)}</tbody></table></div>{actions("relative", item.request_id, item.revision, item.employee_name)}</article>)}</section>
  </div>;
}
