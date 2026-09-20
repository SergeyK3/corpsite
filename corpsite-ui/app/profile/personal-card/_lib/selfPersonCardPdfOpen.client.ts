"use client";

import { buildHeaders } from "@/lib/api";

/** Download the protected self PDF; the URL intentionally has no subject ID. */
export async function downloadMyPersonalCardPdf(): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    const response = await fetch("/profile/personal-card/pdf", {
      method: "GET",
      headers: buildHeaders({ Accept: "application/pdf" }) as Record<string, string>,
      cache: "no-store",
      credentials: "same-origin",
    });
    if (!response.ok) {
      return { ok: false, error: response.status === 409 ? "Личная карточка ещё не создана." : "Не удалось сформировать PDF." };
    }
    const blob = await response.blob();
    if (!blob.size) return { ok: false, error: "Сервер вернул пустой PDF." };
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "personal-card.pdf";
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    return { ok: true };
  } catch {
    return { ok: false, error: "Сервер формирования PDF недоступен." };
  }
}
