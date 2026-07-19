/** Deep links into the MRD create wizard (frontend-only UX). */
import type { MonthlyReferenceSummary } from "./mrdApi.client";
import { MRD_FORK_WIZARD_HREF } from "./detectedDifferencesWorkspace";
import { collapseMrdJournalRows } from "./mrdPeriodWindow";

export type MrdCreateWizardLinkOptions = {
  sourceMrdId: number;
  targetPeriod?: string | null;
};

export function buildMrdCreateWizardHref(options: MrdCreateWizardLinkOptions): string {
  const params = new URLSearchParams();
  params.set("source_mrd_id", String(options.sourceMrdId));
  if (options.targetPeriod) {
    params.set("target_period", options.targetPeriod.slice(0, 10));
  }
  return `${MRD_FORK_WIZARD_HREF}?${params.toString()}`;
}

/** @deprecated use buildMrdCreateWizardHref */
export function buildMrdForkWizardHref(options: {
  mode?: "version" | "period";
  sourceMrdId?: number | null;
  lockSource?: boolean;
  targetPeriod?: string | null;
}): string {
  if (options.sourceMrdId != null && options.sourceMrdId > 0) {
    return buildMrdCreateWizardHref({
      sourceMrdId: options.sourceMrdId,
      targetPeriod: options.targetPeriod,
    });
  }
  return MRD_FORK_WIZARD_HREF;
}

export function parseMrdCreateWizardSearchParams(searchParams: Pick<URLSearchParams, "get">): {
  sourceMrdId: number | null;
  targetPeriod: string | null;
} {
  const sourceRaw = searchParams.get("source_mrd_id");
  const parsed = sourceRaw ? Number(sourceRaw) : NaN;
  const sourceMrdId = Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  const targetRaw = searchParams.get("target_period");
  const targetPeriod =
    targetRaw && /^\d{4}-\d{2}(-\d{2})?$/.test(targetRaw)
      ? targetRaw.length === 7
        ? `${targetRaw}-01`
        : targetRaw.slice(0, 10)
      : null;
  return { sourceMrdId, targetPeriod };
}

/** @deprecated */
export function parseMrdForkWizardSearchParams(searchParams: Pick<URLSearchParams, "get">) {
  const parsed = parseMrdCreateWizardSearchParams(searchParams);
  return {
    mode: "period" as const,
    sourceMrdId: parsed.sourceMrdId,
    lockSource: parsed.sourceMrdId != null,
    targetPeriod: parsed.targetPeriod,
  };
}

export function resolveInitialCreateWizardState(
  items: MonthlyReferenceSummary[],
  activeByPeriod: Record<string, number>,
  options: ReturnType<typeof parseMrdCreateWizardSearchParams>,
): { sourceMrdId: string; targetPeriod: string | null } {
  const journalRows = collapseMrdJournalRows(items, activeByPeriod);
  if (options.sourceMrdId != null && items.some((item) => item.mrd_id === options.sourceMrdId)) {
    const source = items.find((item) => item.mrd_id === options.sourceMrdId)!;
    return {
      sourceMrdId: String(options.sourceMrdId),
      targetPeriod: options.targetPeriod,
    };
  }
  const suggested = journalRows[0] ?? null;
  return {
    sourceMrdId: suggested ? String(suggested.mrd_id) : "",
    targetPeriod: options.targetPeriod,
  };
}
