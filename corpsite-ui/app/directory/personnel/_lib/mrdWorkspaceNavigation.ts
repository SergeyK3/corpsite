/** Deep links into the MRD baseline records workspace. */
export const MRD_WORKSPACE_BASE_HREF = "/directory/personnel/monthly-references";

export function buildMrdWorkspaceHref(mrdId: number): string {
  return `${MRD_WORKSPACE_BASE_HREF}/${mrdId}`;
}

export function buildMrdWorkspaceHrefByPeriod(reportPeriod: string, mrdId: number): string {
  const params = new URLSearchParams();
  params.set("report_period", reportPeriod.slice(0, 10));
  return `${buildMrdWorkspaceHref(mrdId)}?${params.toString()}`;
}
