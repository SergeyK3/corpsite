"use client";

import { buildHeaders } from "@/lib/api";

export async function downloadPersonCardPdf(personId: number): Promise<{ ok: true } | { ok: false; error: string }> {
  if (!Number.isSafeInteger(personId) || personId <= 0) return { ok: false, error: "Некорректный идентификатор сотрудника." };
  try {
    const response = await fetch(`/directory/personnel/persons/${personId}/card/pdf`, { headers: buildHeaders({ Accept: "application/pdf" }) as Record<string, string>, cache: "no-store", credentials: "same-origin" });
    if (!response.ok) return { ok: false, error: response.status === 403 ? "Недостаточно прав для просмотра карточки." : "Не удалось сформировать PDF." };
    const blob = await response.blob();
    if (!blob.size) return { ok: false, error: "Сервер вернул пустой PDF." };
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `personal-card-${personId}.pdf`; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    return { ok: true };
  } catch { return { ok: false, error: "Сервер формирования PDF недоступен." }; }
}
