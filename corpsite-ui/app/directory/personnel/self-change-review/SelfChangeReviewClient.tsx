"use client";

import * as React from "react";
import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";
import type { PprCardSectionId } from "@/lib/pprCardSections";
import { relationshipTypeLabel } from "../_lib/pprCardPresentation";
import PprPersonalCardPageClient from "../_components/PprPersonalCardPageClient";

type Photo = { version_id: string; person_id: number; kind: string; title: string; revision: number; state: string; full_name: string };
type RelativeRequest = { request_id: string; request_kind: "correction" | "addition"; person_id: number; relative_id: number | null; revision: number; employee_name: string;
  current: Record<string, unknown>; proposed: Record<string, unknown> };
const fields = [["relationship_type", "Степень родства"], ["full_name", "ФИО"], ["birth_date", "Дата рождения"],
  ["birth_place", "Место рождения"], ["organization_name", "Организация"],
  ["residence_address", "Адрес проживания"], ["notes", "Примечание"]] as const;

function relativeValue(key: string, value: unknown): string {
  return key === "relationship_type" ? relationshipTypeLabel(typeof value === "string" ? value : null) : String(value ?? "—");
}

function requestWord(count: number): string {
  if (count % 10 === 1 && count % 100 !== 11) return "заявка";
  if (count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 12 || count % 100 > 14)) return "заявки";
  return "заявок";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(resolveApiUrl(path), { ...init, headers: buildHeaders(init.headers as Record<string, string> | undefined), cache: "no-store" });
  if (!response.ok) throw toApiError(response.status, await readJsonSafe(response), { method: init.method ?? "GET", url: path });
  return response.json() as Promise<T>;
}

function decisionError(caught: unknown): string {
  if (caught instanceof TypeError) return "Ответ сервера не получен. Обновите очередь и проверьте статус заявки перед повторной попыткой.";
  if (caught && typeof caught === "object" && "message" in caught && typeof caught.message === "string") {
    if (/PPR envelope not materialized|person_id\s*=\s*\d+/i.test(caught.message)) {
      return "Решение не сохранено: личная карточка не подготовлена для изменения. Обновите очередь и повторите попытку.";
    }
    const status = "status" in caught && typeof caught.status === "number" ? caught.status : null;
    return status !== null && status < 500 ? `Решение не сохранено: ${caught.message}` : `Не удалось подтвердить решение: ${caught.message}`;
  }
  return "Не удалось подтвердить решение. Обновите очередь и проверьте статус заявки.";
}

function PhotoCompare({ photo, actions }: { photo: Photo; actions: React.ReactNode }) {
  const [current, setCurrent] = React.useState<string | null>(null);
  const [proposed, setProposed] = React.useState<string | null>(null);
  const [currentLoaded, setCurrentLoaded] = React.useState(false);
  const [proposedLoaded, setProposedLoaded] = React.useState(false);
  const [largeOpen, setLargeOpen] = React.useState(false);
  const closeRef = React.useRef<HTMLButtonElement>(null);
  React.useEffect(() => {
    let active = true;
    const load = async (path: string, setter: (url: string) => void, onSettled: () => void) => {
      try {
        const response = await fetch(resolveApiUrl(path), { headers: buildHeaders(), cache: "no-store" });
        if (!response.ok) return;
        const blob = await response.blob();
        if (active) setter(URL.createObjectURL(blob));
      } finally { if (active) onSettled(); }
    };
    void load(`/api/personnel-files/persons/${photo.person_id}/current-photo`, setCurrent, () => setCurrentLoaded(true)).catch(() => {});
    void load(`/api/personnel-files/versions/${photo.version_id}/preview`, setProposed, () => setProposedLoaded(true)).catch(() => {});
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
    <div><p className="text-sm font-medium">Текущее фото</p>{current ? <img src={current} alt="Текущее фото" className="mt-2 h-48 w-36 rounded object-contain" /> : <p className="mt-2 text-sm text-zinc-500">{currentLoaded ? "Фото отсутствует" : "Загрузка фото…"}</p>}</div>
    <div className="flex flex-wrap items-start gap-5">
      <div><p className="text-sm font-medium">Новое фото на проверке</p>{proposed ? <button type="button" onClick={() => setLargeOpen(true)} aria-label="Открыть новое фото крупно" className="mt-2 rounded text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"><img src={proposed} alt="Новое фото на проверке" className="h-48 w-36 rounded object-contain" /><span className="mt-1 block text-sm text-blue-700 underline dark:text-blue-300">Открыть крупно</span></button> : <p className="mt-2 text-sm text-zinc-500">{proposedLoaded ? "Не удалось загрузить новое фото. Обновите карточку." : "Загрузка фото…"}</p>}</div>
      <div className="min-w-56">{proposed && currentLoaded ? actions : <p className="text-sm text-zinc-500">Решение доступно после загрузки фото для сравнения.</p>}</div>
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
  const [selectedPersonId, setSelectedPersonId] = React.useState<number | null>(null);
  const [decisions, setDecisions] = React.useState<Record<string, "approve" | "return">>({});
  const [reasons, setReasons] = React.useState<Record<string, string>>({});
  const [error, setError] = React.useState("");
  const [confirmation, setConfirmation] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [stale, setStale] = React.useState(false);
  const [reviewEpoch, setReviewEpoch] = React.useState(0);
  const load = React.useCallback(async () => {
    const results = await Promise.allSettled([
      request<{ items: Photo[] }>("/api/personnel-files/review-queue"),
      request<{ items: RelativeRequest[] }>("/api/ppr/relative-change-requests/review-queue"),
    ]);
    const unavailable = [results[0].status === "rejected" ? "фото" : null, results[1].status === "rejected" ? "родственников" : null].filter(Boolean);
    if (unavailable.length) {
      setError(`Не удалось обновить очередь ${unavailable.join(" и ")}.`);
      setStale(true);
      return false;
    }
    setPhotos((results[0] as PromiseFulfilledResult<{ items: Photo[] }>).value.items.filter((item) => item.kind === "photo"));
    setRelatives((results[1] as PromiseFulfilledResult<{ items: RelativeRequest[] }>).value.items);
    setError("");
    return true;
  }, []);
  React.useEffect(() => { void load(); }, [load]);
  const people = new Map<number, { name: string; photos: Photo[]; relatives: RelativeRequest[] }>();
  for (const photo of photos) {
    const person = people.get(photo.person_id) ?? { name: photo.full_name, photos: [], relatives: [] };
    person.photos.push(photo); people.set(photo.person_id, person);
  }
  for (const relative of relatives) {
    const person = people.get(relative.person_id) ?? { name: relative.employee_name, photos: [], relatives: [] };
    person.relatives.push(relative); people.set(relative.person_id, person);
  }
  const selected = selectedPersonId === null ? null : people.get(selectedPersonId);
  const items = selected ? [
    ...selected.photos.map((item) => ({ kind: "photo" as const, id: item.version_id, revision: item.revision })),
    ...selected.relatives.map((item) => ({ kind: "relative" as const, id: item.request_id, revision: item.revision })),
  ] : [];
  const ready = items.length > 0 && items.every((item) => decisions[item.id] &&
    (decisions[item.id] !== "return" || (reasons[item.id] ?? "").trim()));

  async function refreshForReview() {
    if (await load()) {
      setDecisions({}); setReasons({}); setStale(false); setConfirmation(""); setReviewEpoch((value) => value + 1);
    }
  }
  async function complete() {
    if (selectedPersonId === null || !ready || busy || stale) return;
    setBusy(true); setError("");
    try {
      const result = await request<{ results: { kind: string; id: string; status: string }[] }>(
        `/api/ppr/self-change-review/persons/${selectedPersonId}/complete`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decisions: items.map((item) => ({ kind: item.kind, id: item.id,
            expected_revision: item.revision, action: decisions[item.id], reason: reasons[item.id] ?? "" })) }),
        });
      if (result.results.length !== items.length || result.results.some((item) =>
        item.status !== (decisions[item.id] === "approve" ? "approved" : "returned"))) {
        throw new Error("Сервер вернул неполный результат. Обновите очередь и проверьте решения.");
      }
      setConfirmation(`Проверка сотрудника ${selected?.name ?? ""} завершена. Все решения сохранены вместе.`);
      setPhotos((old) => old.filter((item) => item.person_id !== selectedPersonId));
      setRelatives((old) => old.filter((item) => item.person_id !== selectedPersonId));
      setSelectedPersonId(null); setDecisions({}); setReasons({});
      void load();
    } catch (caught) {
      const conflict = caught && typeof caught === "object" && "status" in caught && caught.status === 409;
      if (conflict) {
        setStale(true);
        setError("Заявки сотрудника изменились. Ни одно решение не применено. Обновите карточку и перепроверьте все заявки.");
      } else setError(decisionError(caught));
    } finally { setBusy(false); }
  }
  const actions = (id: string) => <fieldset className="mt-4 flex flex-wrap items-center gap-3 text-sm" disabled={busy || stale}>
    <legend className="font-medium">Решение по заявке</legend>
    <label><input type="radio" name={`decision-${id}`} checked={decisions[id] === "approve"} onChange={() => setDecisions((old) => ({ ...old, [id]: "approve" }))} /> Одобрить</label>
    <label><input type="radio" name={`decision-${id}`} checked={decisions[id] === "return"} onChange={() => setDecisions((old) => ({ ...old, [id]: "return" }))} /> Вернуть с пояснением</label>
    {decisions[id] === "return" && <label>Пояснение для возврата<input className="ml-2 rounded border px-2 py-2 dark:bg-zinc-950" value={reasons[id] ?? ""} onChange={(event) => setReasons((old) => ({ ...old, [id]: event.target.value }))} /></label>}
  </fieldset>;
  const pendingSections: PprCardSectionId[] = selected ? [
    ...(selected.photos.length ? ["general" as const] : []),
    ...(selected.relatives.length ? ["family" as const] : []),
  ] : [];
  const generalPanel = selected?.photos.length ? <section className="mt-5 border-t pt-4">
    <h3 className="text-lg font-semibold">Фото на проверке</h3>
    {selected.photos.map((photo) => <article key={photo.version_id} className="my-3 rounded-lg border p-4">
      <PhotoCompare photo={photo} actions={actions(photo.version_id)} />
    </article>)}
  </section> : null;
  const familyPanel = selected?.relatives.length ? <section className="mt-5 border-t pt-4">
    <h3 className="text-lg font-semibold">Предложенные изменения</h3>
    {selected.relatives.map((item) => <article key={item.request_id} className="my-3 rounded-lg border p-4">
      <h4 className="font-medium">{item.request_kind === "addition" ? "Новый родственник" : `Исправление записи #${item.relative_id}`}</h4>
      <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>Поле</th><th>Сейчас</th><th>Предложено</th></tr></thead><tbody>{fields.map(([key, label]) => <tr key={key} className="border-t"><th className="py-2">{label}</th><td className="py-2">{relativeValue(key, item.current[key])}</td><td className="py-2">{relativeValue(key, item.proposed[key])}</td></tr>)}</tbody></table></div>
      {actions(item.request_id)}
    </article>)}
  </section> : null;
  const reviewFooter = <div className="mt-5 border-t pt-4">
    <p className="mb-3 text-sm text-zinc-600">{items.length} {requestWord(items.length)} на проверке. Решения применятся вместе после завершения проверки.</p>
    {stale && <button type="button" className="mb-3 rounded border px-4 py-2 text-sm" onClick={() => void refreshForReview()}>Обновить карточку и перепроверить</button>}
    <button type="button" disabled={!ready || busy || stale} className="block rounded bg-blue-700 px-4 py-2 text-white disabled:opacity-50" onClick={() => void complete()}>{busy ? "Завершаем проверку…" : "Завершить проверку"}</button>
  </div>;
  return <div className="space-y-5 p-4">{!selected && <h1 className="text-2xl font-semibold">Изменения личных карточек на проверке</h1>}
    {confirmation && <p role="status" className="rounded border border-emerald-400 bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">{confirmation}</p>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {error && !selected && <button type="button" className="rounded border px-3 py-1.5 text-sm" onClick={() => void refreshForReview()}>Обновить очередь</button>}
    {!selected && <section><h2 className="text-lg font-semibold">Очередь сотрудников</h2>
      {people.size === 0 && <p className="mt-3 text-sm text-zinc-500">Нет заявок на проверке.</p>}
      <div className="mt-3 space-y-2">{[...people.entries()].map(([personId, person]) => {
        const count = person.photos.length + person.relatives.length;
        return <button key={personId} type="button" className="block w-full rounded-lg border p-3 text-left hover:bg-zinc-50 dark:hover:bg-zinc-900" onClick={() => { setSelectedPersonId(personId); setDecisions({}); setReasons({}); setStale(false); setError(""); }}>
          {person.name} · {count} {requestWord(count)} · {[person.photos.length && "Фото", person.relatives.length && "Родственники"].filter(Boolean).join(", ")}
        </button>;
      })}</div>
    </section>}
    {selected && selectedPersonId !== null && <PprPersonalCardPageClient key={`${selectedPersonId}-${reviewEpoch}`}
      personId={String(selectedPersonId)} canEditPprSections={false}
      review={{ pendingSections, generalPanel, familyPanel, footer: reviewFooter,
        onBack: () => { setSelectedPersonId(null); setStale(false); setError(""); } }} />}
  </div>;
}
