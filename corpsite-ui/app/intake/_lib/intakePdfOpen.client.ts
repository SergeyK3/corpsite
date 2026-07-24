"use client";

import { buildHeaders } from "@/lib/api";

import {
  buildIntakePdfHrefByApplicationId,
  buildIntakePdfHrefByToken,
} from "./intakePdfFilename";

export type OpenIntakePdfResult =
  | { ok: true; href: string }
  | { ok: false; error: string; blocked?: boolean };

async function openPdfFromHref(href: string, withAuth: boolean): Promise<OpenIntakePdfResult> {
  try {
    const headers: Record<string, string> = { Accept: "application/pdf" };
    if (withAuth) {
      Object.assign(headers, buildHeaders({ Accept: "application/pdf" }) as Record<string, string>);
    }

    const res = await fetch(href, {
      method: "GET",
      headers,
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
    window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    return { ok: true, href };
  } catch {
    return { ok: false, error: "Не удалось открыть PDF." };
  }
}

export async function openIntakePdfByToken(token: string): Promise<OpenIntakePdfResult> {
  const trimmed = String(token ?? "").trim();
  if (!trimmed) {
    return { ok: false, error: "Ссылка анкеты недействительна." };
  }
  return openPdfFromHref(buildIntakePdfHrefByToken(trimmed), false);
}

export async function openIntakePdfByApplicationId(applicationId: number): Promise<OpenIntakePdfResult> {
  if (!Number.isFinite(applicationId) || applicationId <= 0) {
    return { ok: false, error: "Некорректный идентификатор обращения." };
  }
  return openPdfFromHref(buildIntakePdfHrefByApplicationId(applicationId), true);
}
