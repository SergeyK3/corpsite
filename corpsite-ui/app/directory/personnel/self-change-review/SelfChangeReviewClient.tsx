"use client";

import * as React from "react";
import PersonnelSubNav from "../_components/PersonnelSubNav";
import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";

type Photo = { version_id: string; person_id: number; kind: string; title: string; revision: number; state: string; full_name: string };
type RelativeRequest = { request_id: string; person_id: number; relative_id: number; revision: number; employee_name: string;
  current: Record<string, unknown>; proposed: Record<string, unknown> };
const fields = [["relationship_type", "Степень родства"], ["full_name", "ФИО"], ["birth_date", "Дата рождения"],
  ["birth_place", "Место рождения"], ["organization_name", "Организация"],
  ["residence_address", "Адрес проживания"], ["notes", "Примечание"]] as const;

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(resolveApiUrl(path), { ...init, headers: buildHeaders(init.headers as Record<string, string> | undefined), cache: "no-store" });
  if (!response.ok) throw toApiError(response.status, await readJsonSafe(response), { method: init.method ?? "GET", url: path });
  return response.json() as Promise<T>;
}

function PhotoCompare({ photo }: { photo: Photo }) {
  const [current, setCurrent] = React.useState<string | null>(null);
  const [proposed, setProposed] = React.useState<string | null>(null);
  React.useEffect(() => {
    let active = true;
    const load = async (path: string, setter: (url: string) => void) => {
      const response = await fetch(resolveApiUrl(path), { headers: buildHeaders(), cache: "no-store" });
      if (response.ok && active) setter(URL.createObjectURL(await response.blob()));
    };
    void load(`/api/personnel-files/persons/${photo.person_id}/current-photo`, setCurrent);
    void load(`/api/personnel-files/versions/${photo.version_id}/preview`, setProposed);
    return () => { active = false; };
  }, [photo.person_id, photo.version_id]);
  React.useEffect(() => () => { if (current) URL.revokeObjectURL(current); }, [current]);
  React.useEffect(() => () => { if (proposed) URL.revokeObjectURL(proposed); }, [proposed]);
  return <div className="mt-3 flex gap-4"><div><p className="text-xs">Действующее фото</p>{current ? <img src={current} alt="Действующее фото" className="mt-1 h-32 w-32 rounded object-cover" /> : <p className="text-xs">Нет фото</p>}</div><div><p className="text-xs">Предложено</p>{proposed && <img src={proposed} alt="Предложенное фото" className="mt-1 h-32 w-32 rounded object-cover" />}</div></div>;
}

export default function SelfChangeReviewClient() {
  const [photos, setPhotos] = React.useState<Photo[]>([]);
  const [relatives, setRelatives] = React.useState<RelativeRequest[]>([]);
  const [reasons, setReasons] = React.useState<Record<string, string>>({});
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState<string | null>(null);
  const load = React.useCallback(async () => {
    const results = await Promise.allSettled([
      request<{ items: Photo[] }>("/api/personnel-files/review-queue"),
      request<{ items: RelativeRequest[] }>("/api/ppr/relative-change-requests/review-queue"),
    ]);
    if (results[0].status === "fulfilled") setPhotos(results[0].value.items.filter((item) => item.kind === "photo"));
    if (results[1].status === "fulfilled") setRelatives(results[1].value.items);
    if (results.every((item) => item.status === "rejected")) setError("Нет доступа к очереди заявок.");
  }, []);
  React.useEffect(() => { void load(); }, [load]);
  async function decide(kind: "photo" | "relative", id: string, revision: number, action: "approve" | "return") {
    setBusy(id); setError("");
    try {
      const reason = reasons[id] ?? "";
      const path = kind === "photo" ? `/api/personnel-files/versions/${id}/decision` : `/api/ppr/relative-change-requests/${id}/decision`;
      await request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision: revision, action, reason }) });
      await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось принять решение."); }
    finally { setBusy(null); }
  }
  const actions = (kind: "photo" | "relative", id: string, revision: number) => <div className="mt-4 flex flex-wrap items-end gap-2"><button type="button" disabled={busy === id} onClick={() => void decide(kind, id, revision, "approve")} className="rounded bg-emerald-700 px-3 py-2 text-sm text-white disabled:opacity-50">Одобрить</button><label className="text-sm">Пояснение для возврата<input className="mt-1 block rounded border px-2 py-2 dark:bg-zinc-950" value={reasons[id] ?? ""} onChange={(event) => setReasons((old) => ({ ...old, [id]: event.target.value }))} /></label><button type="button" disabled={busy === id || !(reasons[id] ?? "").trim()} onClick={() => void decide(kind, id, revision, "return")} className="rounded border border-amber-600 px-3 py-2 text-sm disabled:opacity-50">Вернуть с пояснением</button></div>;
  return <div className="space-y-5 p-4"><PersonnelSubNav /><h1 className="text-2xl font-semibold">Изменения личных карточек на проверке</h1>{error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    <section><h2 className="text-lg font-semibold">Фото</h2>{photos.length === 0 && <p className="text-sm text-zinc-500">Нет заявок.</p>}{photos.map((photo) => <article key={photo.version_id} className="my-3 rounded-lg border p-4"><h3 className="font-medium">{photo.full_name} · фото</h3><PhotoCompare photo={photo} />{actions("photo", photo.version_id, photo.revision)}</article>)}</section>
    <section><h2 className="text-lg font-semibold">Родственники</h2>{relatives.length === 0 && <p className="text-sm text-zinc-500">Нет заявок.</p>}{relatives.map((item) => <article key={item.request_id} className="my-3 rounded-lg border p-4"><h3 className="font-medium">{item.employee_name} · запись #{item.relative_id}</h3><div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>Поле</th><th>Сейчас</th><th>Предложено</th></tr></thead><tbody>{fields.map(([key, label]) => <tr key={key} className="border-t"><th className="py-2">{label}</th><td className="py-2">{String(item.current[key] ?? "—")}</td><td className="py-2">{String(item.proposed[key] ?? "—")}</td></tr>)}</tbody></table></div>{actions("relative", item.request_id, item.revision)}</article>)}</section>
  </div>;
}
