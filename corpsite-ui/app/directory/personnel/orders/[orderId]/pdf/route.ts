import { NextResponse } from "next/server";

import {
  extractPersonnelOrderPdfAuth,
  isPersonnelOrderPdfAuthenticated,
} from "../../../_lib/personnelOrderPdfAuth";
import { logPersonnelOrderPdfAudit } from "../../../_lib/personnelOrderPdfAudit";
import {
  PersonnelOrderPdfDataError,
  loadPersonnelOrderPrintViewModelForPdf,
} from "../../../_lib/personnelOrderPdfData.server";
import {
  buildPersonnelOrderPdfContentDisposition,
  buildPersonnelOrderPdfFilename,
} from "../../../_lib/personnelOrderPdfFilename";
import { getPersonnelOrderPdfRenderer } from "../../../_lib/personnelOrderPdfRenderer";
import { parsePersonnelOrderPrintLanguage } from "../../../_lib/personnelOrderPrintLanguage";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_PDF_BYTES = 15 * 1024 * 1024;

type RouteParams = {
  params: Promise<{ orderId: string }> | { orderId: string };
};

function jsonError(status: number, code: string, message: string): NextResponse {
  return NextResponse.json({ error: { code, message } }, { status });
}

function parseOrderId(raw: string): number | null {
  const orderId = Number(raw);
  if (!Number.isFinite(orderId) || orderId <= 0 || !Number.isInteger(orderId)) return null;
  return orderId;
}

export async function GET(request: Request, context: RouteParams) {
  const started = Date.now();
  const auth = extractPersonnelOrderPdfAuth(request);
  const resolved = await Promise.resolve(context.params);
  const orderId = parseOrderId(String(resolved.orderId || ""));
  const languageParam = new URL(request.url).searchParams.get("language");
  const language = parsePersonnelOrderPrintLanguage(languageParam, { fallbackToDefault: false });

  const auditBase = {
    order_id: orderId,
    language: languageParam,
    requesting_user_id: auth.requestingUserId,
  };

  try {
    if (!isPersonnelOrderPdfAuthenticated(auth)) {
      logPersonnelOrderPdfAudit({
        ...auditBase,
        result: "error",
        duration_ms: Date.now() - started,
        error_code: "UNAUTHORIZED",
      });
      return jsonError(401, "UNAUTHORIZED", "Требуется авторизация.");
    }

    if (orderId == null) {
      logPersonnelOrderPdfAudit({
        ...auditBase,
        result: "error",
        duration_ms: Date.now() - started,
        error_code: "INVALID_ORDER_ID",
      });
      return jsonError(422, "INVALID_ORDER_ID", "Некорректный идентификатор приказа.");
    }

    if (!language) {
      logPersonnelOrderPdfAudit({
        ...auditBase,
        order_id: orderId,
        result: "error",
        duration_ms: Date.now() - started,
        error_code: "INVALID_LANGUAGE",
      });
      return jsonError(422, "INVALID_LANGUAGE", "Некорректный язык печатной формы.");
    }

    const model = await loadPersonnelOrderPrintViewModelForPdf(orderId, auth);
    const renderer = getPersonnelOrderPdfRenderer();
    const pdf = await renderer.render({ model, language });

    if (!pdf?.length) {
      logPersonnelOrderPdfAudit({
        ...auditBase,
        order_id: orderId,
        language,
        result: "error",
        duration_ms: Date.now() - started,
        error_code: "EMPTY_PDF",
      });
      return jsonError(500, "EMPTY_PDF", "Не удалось сформировать PDF.");
    }

    if (pdf.byteLength > MAX_PDF_BYTES) {
      logPersonnelOrderPdfAudit({
        ...auditBase,
        order_id: orderId,
        language,
        result: "error",
        duration_ms: Date.now() - started,
        error_code: "PDF_TOO_LARGE",
      });
      return jsonError(500, "PDF_TOO_LARGE", "PDF превышает допустимый размер.");
    }

    const filename = buildPersonnelOrderPdfFilename(model.orderNumber, orderId, language);
    logPersonnelOrderPdfAudit({
      ...auditBase,
      order_id: orderId,
      language,
      result: "ok",
      duration_ms: Date.now() - started,
    });

    return new NextResponse(new Uint8Array(pdf), {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": buildPersonnelOrderPdfContentDisposition(filename),
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch (err) {
    const duration_ms = Date.now() - started;
    if (err instanceof PersonnelOrderPdfDataError) {
      logPersonnelOrderPdfAudit({
        ...auditBase,
        result: "error",
        duration_ms,
        error_code: err.code,
      });
      return jsonError(err.status, err.code, err.message);
    }

    const code =
      err && typeof err === "object" && "code" in err && String((err as { code?: unknown }).code) === "PDF_TIMEOUT"
        ? "PDF_TIMEOUT"
        : "PDF_RENDER_ERROR";
    logPersonnelOrderPdfAudit({
      ...auditBase,
      result: "error",
      duration_ms,
      error_code: code,
    });
    return jsonError(
      500,
      code,
      code === "PDF_TIMEOUT"
        ? "Превышено время формирования PDF."
        : "Не удалось сформировать PDF.",
    );
  }
}
