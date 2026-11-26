"use client";

import * as React from "react";
import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";
import PhotoCropEditor from "./PhotoCropEditor";

type PhotoVersion = { version_id: string; set_id: string; kind: string; state: string; revision: number; reason: string; created_at: string };

const buttonClass = "rounded-md border border-blue-600 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50 dark:text-blue-300";
const fieldClass = "mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950";
const statusLabel: Record<string, string> = { pending: "Отправлено кадровику на проверку", approved: "Одобрено кадровиком", returned: "Возвращено кадровиком" };
const statusClass: Record<string, string> = { pending: "bg-amber-100 text-amber-900", approved: "bg-emerald-100 text-emerald-900", returned: "bg-rose-100 text-rose-900" };

export function ChangeStatus({ state, reason, subject }: { state: string; reason?: string; subject: string }) {
  if (!statusLabel[state]) return null;
  return <div role="status" className="mt-2 space-y-2 text-sm">
    <p className="font-medium">{subject}{state === "returned" ? " возвращена кадровиком" : ""}</p>
    <span className={`inline-block rounded-full px-2 py-1 text-xs font-medium ${statusClass[state]}`}>{statusLabel[state]}</span>
    {state === "returned" && reason ? <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-rose-950 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-100"><strong>Причина возврата</strong><p className="mt-1">{reason}</p></div> : null}
  </div>;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(resolveApiUrl(path), { ...init, headers: buildHeaders(init.headers as Record<string, string> | undefined), cache: "no-store" });
  if (!response.ok) throw toApiError(response.status, await readJsonSafe(response), { method: init.method ?? "GET", url: path });
  return response.json() as Promise<T>;
}

export function changeError(caught: unknown, fallback: string): string {
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
  const [pendingPhoto, setPendingPhoto] = React.useState<{ versionId: string; url: string } | null>(null);
  const [pendingPhotoError, setPendingPhotoError] = React.useState<string | null>(null);
  const [preview, setPreview] = React.useState<string | null>(null);
  const [file, setFile] = React.useState<File | null>(null);
  const [source, setSource] = React.useState<File | null>(null);
  const [sourceKey, setSourceKey] = React.useState(0);
  const [latest, setLatest] = React.useState<PhotoVersion | null>(null);
  const [latestLoaded, setLatestLoaded] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const busyRef = React.useRef(false);
  const [error, setError] = React.useState("");
  const [confirmation, setConfirmation] = React.useState("");
  const [retryNeedsConfirmation, setRetryNeedsConfirmation] = React.useState(false);
  const [retryConfirmed, setRetryConfirmed] = React.useState(false);
  const photoLoadSequence = React.useRef(0);
  const loadLatest = React.useCallback(async (silent = false) => {
    if (!silent) setLatestLoaded(false);
    const files = await api<{ items: PhotoVersion[] }>("/api/personnel-files/me");
    const newest = files.items.filter((item) => item.kind === "photo").sort((a, b) => b.created_at.localeCompare(a.created_at))[0] ?? null;
    setLatest(newest);
    setLatestLoaded(true);
    return newest;
  }, []);
  const loadCurrent = React.useCallback(async () => {
    const sequence = ++photoLoadSequence.current;
    const response = await fetch(resolveApiUrl("/api/ppr/me/photo"), { headers: buildHeaders(), cache: "no-store" });
    if (sequence !== photoLoadSequence.current) return;
    if (response.ok) {
      const blob = await response.blob();
      if (sequence === photoLoadSequence.current) setCurrent(URL.createObjectURL(blob));
    } else if (response.status === 404) setCurrent(null);
    else throw new Error("Не удалось загрузить текущее фото.");
  }, []);
  React.useEffect(() => {
    let alive = true;
    void Promise.all([loadCurrent(), loadLatest()]).catch(() => { if (alive) setError("Не удалось загрузить состояние фото."); });
    return () => { alive = false; photoLoadSequence.current += 1; };
  }, [loadCurrent, loadLatest]);
  React.useEffect(() => {
    let active = true;
    let checking = false;
    const refresh = async () => {
      if (!active || checking) return;
      checking = true;
      try {
        const newest = await loadLatest(true);
        if (active && (newest?.version_id !== latest?.version_id || newest?.revision !== latest?.revision || newest?.state !== latest?.state)) {
          if (newest?.state !== "pending") setConfirmation("");
          await loadCurrent();
        }
      } catch { if (active) setError("Не удалось обновить статус фото. Обновите карточку."); }
      finally { checking = false; }
    };
    const onVisibility = () => { if (document.visibilityState === "visible") void refresh(); };
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", onVisibility);
    const timer = latest?.state === "pending" ? window.setInterval(() => void refresh(), 15000) : null;
    return () => { active = false; window.removeEventListener("focus", refresh); document.removeEventListener("visibilitychange", onVisibility); if (timer !== null) window.clearInterval(timer); };
  }, [latest?.revision, latest?.state, latest?.version_id, loadCurrent, loadLatest]);
  React.useEffect(() => () => { if (current) URL.revokeObjectURL(current); }, [current]);
  React.useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  React.useEffect(() => {
    if (latest?.state !== "pending") return;
    let active = true;
    void fetch(resolveApiUrl(`/api/personnel-files/versions/${latest.version_id}/preview`), {
      headers: buildHeaders(), cache: "no-store",
    }).then(async (response) => {
      if (!response.ok) throw new Error("preview unavailable");
      const blob = await response.blob();
      if (active) setPendingPhoto({ versionId: latest.version_id, url: URL.createObjectURL(blob) });
    }).catch(() => { if (active) setPendingPhotoError(latest.version_id); });
    return () => { active = false; };
  }, [latest?.state, latest?.version_id]);
  React.useEffect(() => () => { if (pendingPhoto) URL.revokeObjectURL(pendingPhoto.url); }, [pendingPhoto]);
  const cropReady = React.useCallback((cropped: File | null, url: string | null) => { setFile(cropped); setPreview(url); }, []);
  const cropError = React.useCallback((message: string) => { setFile(null); setPreview(null); setError(message); }, []);

  async function send() {
    if (!file || !latestLoaded || busyRef.current || latest?.state === "pending" || (retryNeedsConfirmation && !retryConfirmed)) return;
    busyRef.current = true;
    setBusy(true); setError("");
    try {
      const body = new FormData();
      body.append("file", file); body.append("kind", "photo"); body.append("title", "Фото лица");
      if (latest) { body.append("set_id", latest.set_id); body.append("expected_revision", String(latest.revision)); body.append("expected_version_id", latest.version_id); }
      const result = await api<PhotoVersion>("/api/personnel-files/me", { method: "POST", body });
      setLatest(result); setFile(null); setSource(null); setPreview(null); setOpen(false);
      setRetryNeedsConfirmation(false); setRetryConfirmed(false);
      setConfirmation("Новое фото отправлено кадровику");
    } catch (caught) {
      const conflict = caught && typeof caught === "object" && "status" in caught && caught.status === 409;
      if (conflict) {
        setRetryNeedsConfirmation(true); setRetryConfirmed(false);
        try {
          const newest = await loadLatest();
          setError(newest?.state === "pending"
            ? "Текущий кадр не отправлен: другое фото уже на проверке. Дождитесь решения кадровика."
            : "Версия фото изменилась. Текущий кадр не отправлен. Проверьте его и подтвердите повторную отправку.");
        } catch { setError("Версия фото изменилась. Текущий кадр не отправлен. Не удалось обновить статус заявки; повторите проверку позже."); }
      } else setError(changeError(caught, "Не удалось отправить фото."));
    } finally { busyRef.current = false; setBusy(false); }
  }
  return <div className="space-y-2" data-testid="self-photo-changes">
    <div className="flex flex-wrap items-start gap-5">
      <div><p className="mb-2 text-sm font-medium">Текущее фото</p>{current ? <img src={current} alt="Текущее фото" className="h-32 w-24 rounded-lg object-contain" /> : <div className="flex h-32 w-24 items-center justify-center rounded-lg bg-zinc-100 px-2 text-center text-xs text-zinc-500">Фото отсутствует</div>}</div>
      {latest?.state === "pending" && <div><p className="mb-2 text-sm font-medium">Новое фото на проверке</p>
        {pendingPhoto?.versionId === latest.version_id ? <img src={pendingPhoto.url} alt="Новое фото на проверке" className="h-32 w-24 rounded-lg object-contain" />
          : <div className="flex h-32 w-24 items-center rounded-lg border px-2 text-center text-xs text-zinc-500">{pendingPhotoError === latest.version_id ? "Не удалось загрузить отправленный кадр. Обновите карточку." : "Загружаем отправленный кадр…"}</div>}
      </div>}
      <div className="pt-7"><ChangeButton disabled={!latestLoaded} onClick={() => setOpen(true)} /></div>
    </div>
    {!latestLoaded && !error && <p className="text-sm text-zinc-500">Загружаем состояние фото…</p>}
    {error && !open && <p role="alert" className="text-sm text-red-700">{error} <button type="button" className="underline" onClick={() => { setError(""); void loadLatest().catch(() => setError("Не удалось загрузить состояние фото.")); }}>Обновить статус фото</button></p>}
    {confirmation && <p role="status" className="text-sm text-emerald-700">{confirmation}</p>}
    {latest && statusLabel[latest.state] && <ChangeStatus subject="Заявка на новое фото" state={latest.state} reason={latest.reason} />}
    {open && <ChangeModal title="Замена фото" onClose={() => { if (!busyRef.current) setOpen(false); }}>
      <p className="mt-3 text-sm text-zinc-600">Новое фото уйдёт кадровику на проверку. Действующее фото останется в карточке до одобрения.</p>
      <p className="mt-2 text-sm text-zinc-600">Выберите JPEG, из которого можно выделить кадр не меньше 360 × 480 пикселей. При приближении кадра меньше 480 × 640 пикселей фото может потерять чёткость. Итоговый файл будет JPEG 600 × 800 пикселей, не более 500 КБ.</p>
      <div className="mt-4 flex gap-4">{current && <div><p className="text-xs">Текущее фото</p><img src={current} alt="Действующее фото" className="mt-1 h-32 w-24 rounded object-contain" /></div>}{preview && <div><p className="text-xs">Итоговый JPEG 600 × 800</p><img src={preview} alt="Итоговое фото 600 на 800" className="mt-1 h-32 w-24 rounded object-contain" /></div>}</div>
      <label className="mt-4 block text-sm">Выберите исходный JPEG<input type="file" accept="image/jpeg" className={fieldClass} onChange={(event) => { setFile(null); setPreview(null); setError(""); setRetryConfirmed(false); setSource(event.target.files?.[0] ?? null); setSourceKey((value) => value + 1); }} /></label>
      {source && <PhotoCropEditor key={sourceKey} source={source} onReady={cropReady} onError={cropError} />}
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      {latest?.state === "pending" && <p className="mt-3 text-sm text-amber-700">Другое фото уже на проверке. Этот кадр пока нельзя отправить.</p>}
      {(retryNeedsConfirmation || latest?.state === "pending") && <button type="button" className={`${buttonClass} mt-3`} disabled={busy} onClick={() => { void loadLatest().catch(() => setError("Не удалось обновить статус заявки.")); }}>Обновить статус заявки</button>}
      {retryNeedsConfirmation && latest?.state !== "pending" && !retryConfirmed && <button type="button" className={`${buttonClass} mt-3 block`} onClick={() => setRetryConfirmed(true)}>Подтвердить повторную отправку</button>}
      {retryConfirmed && <p className="mt-3 text-sm text-amber-700">Повторная отправка подтверждена. Проверьте кадр перед отправкой.</p>}
      <button type="button" disabled={!file || !latestLoaded || busy || latest?.state === "pending" || (retryNeedsConfirmation && !retryConfirmed)} onClick={() => void send()} className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50">{busy ? "Отправляем фото…" : retryNeedsConfirmation ? "Отправить повторно на проверку" : "Отправить на проверку"}</button>
    </ChangeModal>}
  </div>;
}
