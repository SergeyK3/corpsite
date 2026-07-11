"use client";

import { buildHeaders } from "@/lib/api";

import type { PersonnelOrderPrintLanguage } from "./personnelOrderPrintLanguage";
import { buildPersonnelOrderPdfHref } from "./personnelOrderPdfFilename";

export type OpenPersonnelOrderPdfResult =
  | { ok: true; href: string }
  | { ok: false; error: string; blocked?: boolean };

/**
 * Open official PDF in a new tab.
 * Auth is Bearer-in-localStorage, so the browser cannot send credentials via bare window.open(url).
 * Flow: authenticated fetch → blob URL → window.open(blob).
 */
export async function openPersonnelOrderPdf(
  orderId: number,
  language: PersonnelOrderPrintLanguage,
): Promise<OpenPersonnelOrderPdfResult> {
  const href = buildPersonnelOrderPdfHref(orderId, language);
  try {
    const res = await fetch(href, {
      method: "GET",
      headers: buildHeaders({ Accept: "application/pdf" }) as Record<string, string>,
      cache: "no-store",
    });

    if (!res.ok) {
      let message = `Не удалось открыть PDF (HTTP ${res.status}).`;
      try {
        const body = (await res.json()) as { error?: { message?: string } };
        if (body?.error?.message) message = body.error.message;
      } catch {
        // keep default
      }
      return { ok: false, error: message };
    }

    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    const opened = window.open(blobUrl, "_blank", "noopener,noreferrer");
    if (!opened) {
      URL.revokeObjectURL(blobUrl);
      return {
        ok: false,
        blocked: true,
        error:
          "Браузер заблокировал всплывающее окно. Разрешите всплывающие окна для этого сайта и повторите.",
      };
    }
    // Revoke after the viewer has a chance to load the blob.
    window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    return { ok: true, href };
  } catch {
    return { ok: false, error: "Не удалось открыть PDF." };
  }
}
