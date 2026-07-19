/**
 * Integration anchors for the future Detected Differences workspace (WP-MRD-004 foundation).
 * Legacy import review pages remain until WP-MRD-006 cutover.
 */
export const DETECTED_DIFFERENCES_WORKSPACE_HREF = "/directory/personnel/differences";

export const MRD_FORK_WIZARD_HREF = "/directory/personnel/monthly-references/fork";

export const MRD_ACTIVE_CONTEXT_QUERY_KEY = "report_period";

/** Placeholder until differences API is wired in WP-MRD-004+. */
export function buildDetectedDifferencesHref(options?: {
  reportPeriod?: string | null;
  batchId?: number | null;
}): string {
  const params = new URLSearchParams();
  if (options?.reportPeriod) params.set("report_period", options.reportPeriod);
  if (options?.batchId) params.set("batch_id", String(options.batchId));
  const qs = params.toString();
  return qs ? `${DETECTED_DIFFERENCES_WORKSPACE_HREF}?${qs}` : DETECTED_DIFFERENCES_WORKSPACE_HREF;
}
