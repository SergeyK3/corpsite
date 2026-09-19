"use client";

import { buildHeaders } from "@/lib/api";

import {
  buildIntakePdfHrefByApplicationId,
  buildIntakePdfHrefByToken,
} from "./intakePdfFilename";

export type OpenIntakePdfResult =
  | { ok: true; href: string }
  | { ok: false; error: string; blocked?: boolean; status?: number; code?: string };

type PdfErrorBody = {
  error?: { code?: unknown; message?: unknown };
  detail?: { code?: unknown; message?: unknown } | unknown;
};

function messageForPdfStatus(status: number): string {
  if (status === 401) return "Требуется авторизация для скачивания PDF.";
  if (status === 403) return "Недостаточно прав для скачивания PDF.";
  if (status === 404) return "Анкета не найдена.";
  if (status === 409 || status === 422) return "PDF временно невозможно сформировать из-за ошибки данных.";
  if (status >= 500) return "Сервер формирования PDF недоступен.";
  return `Не удалось скачать PDF (HTTP ${status}).`;
}

async function readPdfError(res: Response): Promise<{ code?: string; message: string }> {
  const fallback = messageForPdfStatus(res.status);
  try {
    const body = (await res.json()) as PdfErrorBody;
    const error = body?.error ?? (typeof body?.detail === "object" && body.detail ? body.detail : null);
    const rawCode = error && typeof error === "object" ? (error as { code?: unknown }).code : undefined;
    const rawMessage = error && typeof error === "object" ? (error as { message?: unknown }).message : undefined;
    return {
      code: typeof rawCode === "string" && rawCode.trim() ? rawCode.trim() : undefined,
      // Backend messages are already safe, but do not expose arbitrary HTML/plain-text proxy bodies.
      message: typeof rawMessage === "string" && rawMessage.trim() ? rawMessage.trim() : fallback,
    };
  } catch {
    return { message: fallback };
  }
}

function filenameFromContentDisposition(value: string | null, fallback: string): string {
  if (!value) return fallback;
  const utf8 = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const quoted = value.match(/filename="([^"\\]*(?:\\.[^"\\]*)*)"/i)?.[1];
  const plain = value.match(/filename=([^;]+)/i)?.[1];
  let decoded = "";
  if (utf8) {
    try {
      decoded = decodeURIComponent(utf8);
    } catch {
      decoded = "";
    }
  }
  const candidate = decoded || (quoted ?? plain ?? "").trim();
  // A response header must not be able to choose a path or an empty browser filename.
  const safe = candidate.replace(/[\\/:*?"<>|\x00-\x1F]/g, "_").trim();
  return safe || fallback;
}

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
      credentials: "same-origin",
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

/** Downloads an HR-facing intake PDF without navigating away from the journal. */
export async function downloadIntakePdfByApplicationId(applicationId: number): Promise<OpenIntakePdfResult> {
  if (!Number.isFinite(applicationId) || applicationId <= 0) {
    return { ok: false, error: "\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 \u0438\u0434\u0435\u043d\u0442\u0438\u0444\u0438\u043a\u0430\u0442\u043e\u0440 \u043e\u0431\u0440\u0430\u0449\u0435\u043d\u0438\u044f." };
  }
  const href = buildIntakePdfHrefByApplicationId(applicationId);
  try {
    const res = await fetch(href, {
      method: "GET",
      headers: buildHeaders({ Accept: "application/pdf" }) as Record<string, string>,
      cache: "no-store",
      credentials: "same-origin",
    });
    if (!res.ok) {
      const error = await readPdfError(res);
      console.warn("Intake PDF download failed", { status: res.status, code: error.code ?? "HTTP_ERROR" });
      return { ok: false, error: error.message, status: res.status, code: error.code };
    }
    const contentType = res.headers.get("content-type") ?? "";
    if (!/^application\/pdf(?:;|$)/i.test(contentType)) {
      console.warn("Intake PDF download returned an unexpected content type", { contentType });
      return {
        ok: false,
        error: "Сервер вернул некорректный формат PDF.",
        status: res.status,
        code: "UNEXPECTED_CONTENT_TYPE",
      };
    }
    const blob = await res.blob();
    if (blob.size === 0) {
      return { ok: false, error: "Сервер вернул пустой PDF.", status: res.status, code: "EMPTY_PDF" };
    }
    const blobUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = blobUrl;
    anchor.download = filenameFromContentDisposition(
      res.headers.get("content-disposition"),
      `Анкета_${applicationId}.pdf`,
    );
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    return { ok: true, href };
  } catch {
    console.warn("Intake PDF download request failed", { code: "NETWORK_ERROR" });
    return { ok: false, error: "Сервер формирования PDF недоступен.", code: "NETWORK_ERROR" };
  }
}
