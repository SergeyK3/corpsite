import { NextResponse } from "next/server";

import { IntakePdfDataError } from "./intakePdfData.server";
import { buildIntakePdfContentDisposition } from "./intakePdfFilename";
import { getIntakePdfRenderer } from "./intakePdfRenderer";
import type { IntakePdfLoadedModel } from "./intakePdfData.server";

export const INTAKE_PDF_MAX_BYTES = 15 * 1024 * 1024;

function jsonError(status: number, code: string, message: string): NextResponse {
  return NextResponse.json({ error: { code, message } }, { status });
}

export async function renderIntakePdfResponse(
  loadModel: () => Promise<IntakePdfLoadedModel>,
  opts?: { format?: string | null },
): Promise<NextResponse> {
  const started = Date.now();
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
      return jsonError(err.status, err.code, err.message);
    }

    const code =
      err && typeof err === "object" && "code" in err && String((err as { code?: unknown }).code) === "PDF_TIMEOUT"
        ? "PDF_TIMEOUT"
        : "PDF_RENDER_ERROR";
    return jsonError(
      500,
      code,
      code === "PDF_TIMEOUT"
        ? "Превышено время формирования PDF."
        : "Не удалось сформировать PDF.",
    );
  }
}
