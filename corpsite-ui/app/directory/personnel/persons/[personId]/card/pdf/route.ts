import { NextResponse } from "next/server";

import { extractPersonnelOrderPdfAuth, isPersonnelOrderPdfAuthenticated } from "@/app/directory/personnel/_lib/personnelOrderPdfAuth";
import { loadPersonCardPdfDocument } from "@/app/directory/personnel/_lib/personCardPdfData.server";
import { renderHtmlPdfResponse } from "@/app/intake/_lib/intakePdfRouteHandler";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request, context: { params: Promise<{ personId: string }> | { personId: string } }) {
  const auth = extractPersonnelOrderPdfAuth(request);
  if (!isPersonnelOrderPdfAuthenticated(auth)) return NextResponse.json({ error: { code: "UNAUTHORIZED", message: "Требуется авторизация." } }, { status: 401 });
  const params = await Promise.resolve(context.params);
  const personId = Number(params.personId);
  return renderHtmlPdfResponse(() => loadPersonCardPdfDocument(personId, auth));
}
