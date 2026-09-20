import { NextResponse } from "next/server";

import {
  extractPersonnelOrderPdfAuth,
  isPersonnelOrderPdfAuthenticated,
} from "@/app/directory/personnel/_lib/personnelOrderPdfAuth";
import { renderHtmlPdfResponse } from "@/app/intake/_lib/intakePdfRouteHandler";
import { loadSelfPersonCardPdfDocument } from "../_lib/selfPersonCardPdfData.server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** ID-free browser route for the caller's own personal-card PDF. */
export async function GET(request: Request) {
  const auth = extractPersonnelOrderPdfAuth(request);
  if (!isPersonnelOrderPdfAuthenticated(auth)) {
    return NextResponse.json(
      { error: { code: "UNAUTHORIZED", message: "Требуется авторизация." } },
      { status: 401 },
    );
  }
  return renderHtmlPdfResponse(() => loadSelfPersonCardPdfDocument(auth));
}
