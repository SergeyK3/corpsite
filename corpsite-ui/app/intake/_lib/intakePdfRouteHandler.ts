import { NextResponse } from "next/server";

import { IntakePdfDataError } from "./intakePdfData.server";
import { buildIntakePdfContentDisposition } from "./intakePdfFilename";
import { getIntakePdfRenderer } from "./intakePdfRenderer";
import type { IntakePdfLoadedModel } from "./intakePdfData.server";
import { withPersonnelOrderPdfPage } from "@/app/directory/personnel/_lib/personnelOrderPdfBrowser";
import { PERSONNEL_ORDER_PDF_OPTIONS } from "@/app/directory/personnel/_lib/personnelOrderPdfRenderer";

export const INTAKE_PDF_MAX_BYTES = 15 * 1024 * 1024;

export type HtmlPdfLoadedDocument = { html: string; filename: string };

function jsonError(status: number, code: string, message: string): NextResponse {
  return NextResponse.json({ error: { code, message } }, { status });
}

/** Shared protected HTML-to-PDF response path for non-intake documents. */
export async function renderHtmlPdfResponse(
  loadDocument: () => Promise<HtmlPdfLoadedDocument>,
): Promise<NextResponse> {
  const started = Date.now();
  let stage = "load_model";
  try {
    const document = await loadDocument();
    stage = "render_pdf";
    const pdf = await withPersonnelOrderPdfPage(async (page) => {
      await page.setContent(document.html, { waitUntil: "load" });
      return Buffer.from(await page.pdf(PERSONNEL_ORDER_PDF_OPTIONS));
    });
    if (!pdf?.length) return jsonError(500, "EMPTY_PDF", "Не удалось сформировать PDF.");
    if (pdf.byteLength > INTAKE_PDF_MAX_BYTES) return jsonError(500, "PDF_TOO_LARGE", "PDF превышает допустимый размер.");
    return new NextResponse(new Uint8Array(pdf), {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": buildIntakePdfContentDisposition(document.filename),
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Intake-Pdf-Duration-Ms": String(Date.now() - started),
      },
    });
  } catch (err) {
    if (err && typeof err === "object" && "status" in err && "code" in err) {
      const typed = err as { status?: unknown; code?: unknown; message?: unknown };
      if (typeof typed.status === "number" && typeof typed.code === "string") {
        return jsonError(typed.status, typed.code, typeof typed.message === "string" ? typed.message : "PDF временно недоступен.");
      }
    }
    console.error("Protected PDF rendering failed", { stage, message: err instanceof Error ? err.message : "Unknown PDF error" });
    return jsonError(500, stage === "load_model" ? "PDF_MODEL_ERROR" : "PDF_RENDER_ERROR", "Не удалось сформировать PDF.");
  }
}

export async function renderIntakePdfResponse(
  loadModel: () => Promise<IntakePdfLoadedModel>,
  opts?: { format?: string | null },
): Promise<NextResponse> {
  const started = Date.now();
  let stage = "load_model";
  try {
    const loaded = await loadModel();
    if (opts?.format === "html") {
      const { buildIntakePdfHtmlDocument } = await import("./intakePdfDocumentHtml");
      return new NextResponse(buildIntakePdfHtmlDocument(loaded.model), {
        status: 200,
        headers: {
          "Content-Type": "text/html; charset=utf-8",
          "Cache-Control": "private, no-store",
        },
      });
    }

    stage = "render_pdf";
    const renderer = getIntakePdfRenderer();
    const pdf = await renderer.render(loaded.model);

    if (!pdf?.length) {
      return jsonError(500, "EMPTY_PDF", "Не удалось сформировать PDF.");
    }
    if (pdf.byteLength > INTAKE_PDF_MAX_BYTES) {
      return jsonError(500, "PDF_TOO_LARGE", "PDF превышает допустимый размер.");
    }

    return new NextResponse(new Uint8Array(pdf), {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": buildIntakePdfContentDisposition(loaded.filename),
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Intake-Pdf-Duration-Ms": String(Date.now() - started),
      },
    });
  } catch (err) {
    if (err instanceof IntakePdfDataError) {
      console.warn("Intake PDF data request failed", {
        status: err.status,
        code: err.code,
      });
      return jsonError(err.status, err.code, err.message);
    }

    const code =
      err && typeof err === "object" && "code" in err && String((err as { code?: unknown }).code) === "PDF_TIMEOUT"
        ? "PDF_TIMEOUT"
        : stage === "load_model"
          ? "PDF_MODEL_ERROR"
          : "PDF_RENDER_ERROR";
    // Keep diagnostics in server logs without serializing a stack trace or request data to the browser.
    console.error("Intake PDF rendering failed", {
      code,
      stage,
      message: err instanceof Error ? err.message : "Unknown PDF renderer error",
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
