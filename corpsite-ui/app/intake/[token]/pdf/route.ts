import { loadIntakePdfModelByToken } from "../../_lib/intakePdfData.server";
import { renderIntakePdfResponse } from "../../_lib/intakePdfRouteHandler";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteParams = {
  params: Promise<{ token: string }> | { token: string };
};

export async function GET(request: Request, context: RouteParams) {
  const resolved = await Promise.resolve(context.params);
  const token = String(resolved.token || "").trim();
  const format = new URL(request.url).searchParams.get("format");
  return renderIntakePdfResponse(() => loadIntakePdfModelByToken(token), { format });
}
