import { NextResponse } from "next/server";

import {
  extractPersonnelOrderPdfAuth,
  isPersonnelOrderPdfAuthenticated,
} from "@/app/directory/personnel/_lib/personnelOrderPdfAuth";
import { loadIntakePdfModelByApplicationId } from "@/app/intake/_lib/intakePdfData.server";
import { renderIntakePdfResponse } from "@/app/intake/_lib/intakePdfRouteHandler";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteParams = {
  params: Promise<{ applicationId: string }> | { applicationId: string };
};

function jsonError(status: number, code: string, message: string): NextResponse {
  return NextResponse.json({ error: { code, message } }, { status });
}

function parseApplicationId(raw: string): number | null {
  const applicationId = Number(raw);
  if (!Number.isFinite(applicationId) || applicationId <= 0 || !Number.isInteger(applicationId)) {
    return null;
  }
  return applicationId;
}

export async function GET(request: Request, context: RouteParams) {
  const auth = extractPersonnelOrderPdfAuth(request);
  if (!isPersonnelOrderPdfAuthenticated(auth)) {
    return jsonError(401, "UNAUTHORIZED", "Требуется авторизация.");
  }

  const resolved = await Promise.resolve(context.params);
  const applicationId = parseApplicationId(String(resolved.applicationId || ""));
  if (applicationId == null) {
    return jsonError(422, "INVALID_APPLICATION_ID", "Некорректный идентификатор обращения.");
  }

  return renderIntakePdfResponse(() => loadIntakePdfModelByApplicationId(applicationId, auth));
}
