"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import { canSeeHrProcessesNav } from "@/lib/personnelNav";
import type { MeInfo } from "@/lib/types";

import {
  createMrdCommandId,
  forkMonthlyReferencePeriod,
  listMonthlyReferenceForkSources,
  mapMrdApiError,
  type MonthlyReferenceSummary,
} from "../_lib/mrdApi.client";
import {
  buildForkPeriodWarnings,
  formatMrdPeriodHeadline,
  formatMrdReportPeriod,
} from "../_lib/mrdDisplay";
import { buildDetectedDifferencesHref } from "../_lib/detectedDifferencesWorkspace";
import {
  parseMrdCreateWizardSearchParams,
  resolveInitialCreateWizardState,
} from "../_lib/mrdForkNavigation";
import {
  collectExistingReportPeriods,
  listAllowedTargetPeriodOptions,
  monthInputFromIso,
  validateCreateTargetPeriod,
} from "../_lib/mrdPeriodWindow";
import { MRD_UI } from "../_lib/mrdUiLabels";

function monthInputToIsoDate(value: string): string {
  return `${value}-01`;
}

export default function MrdForkWizardPageClient() {
  const searchParams = useSearchParams();
  const urlOptions = React.useMemo(() => parseMrdCreateWizardSearchParams(searchParams), [searchParams]);

  const [me, setMe] = React.useState<MeInfo | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [success, setSuccess] = React.useState<string | null>(null);
  const [sources, setSources] = React.useState<MonthlyReferenceSummary[]>([]);
  const [activeByPeriod, setActiveByPeriod] = React.useState<Record<string, number>>({});
  const [sourceMrdId, setSourceMrdId] = React.useState("");
  const [targetPeriodInput, setTargetPeriodInput] = React.useState("");
  const [notes, setNotes] = React.useState("");
  const [initialized, setInitialized] = React.useState(false);

  const selectedSource = React.useMemo(
    () => sources.find((item) => String(item.mrd_id) === sourceMrdId) ?? null,
    [sourceMrdId, sources],
  );

  const existingPeriods = React.useMemo(() => collectExistingReportPeriods(sources), [sources]);

  const targetOptions = React.useMemo(() => {
    if (!selectedSource) return [];
    return listAllowedTargetPeriodOptions(selectedSource.report_period, existingPeriods);
  }, [existingPeriods, selectedSource]);

  const periodValidationError = React.useMemo(() => {
    if (!selectedSource || !targetPeriodInput) return null;
    return validateCreateTargetPeriod(
      targetPeriodInput,
      selectedSource.report_period,
      existingPeriods,
    );
  }, [existingPeriods, selectedSource, targetPeriodInput]);

  const warnings = React.useMemo(() => buildForkPeriodWarnings(selectedSource), [selectedSource]);

  const loadSources = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await listMonthlyReferenceForkSources();
      setSources(data.items);
      setActiveByPeriod(data.active_by_period);
      setError(null);
    } catch (e) {
      setError(mapMrdApiError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void apiAuthMe()
      .then((data) => setMe(data))
      .catch(() => setMe(null));
  }, []);

  React.useEffect(() => {
    if (!canSeeHrProcessesNav(me)) return;
    void loadSources();
  }, [loadSources, me]);

  React.useEffect(() => {
    setInitialized(false);
    setSourceMrdId("");
    setTargetPeriodInput("");
    setSuccess(null);
    setError(null);
  }, [urlOptions.sourceMrdId, urlOptions.targetPeriod]);

  React.useEffect(() => {
    if (loading || initialized || !sources.length) return;
    const initial = resolveInitialCreateWizardState(sources, activeByPeriod, urlOptions);
    setSourceMrdId(initial.sourceMrdId);
    if (urlOptions.targetPeriod) {
      setTargetPeriodInput(monthInputFromIso(urlOptions.targetPeriod));
    } else if (initial.sourceMrdId) {
      const source = sources.find((item) => String(item.mrd_id) === initial.sourceMrdId);
      if (source) {
        const options = listAllowedTargetPeriodOptions(source.report_period, existingPeriods);
        if (options[0]) setTargetPeriodInput(options[0].monthInput);
      }
    }
    setInitialized(true);
  }, [activeByPeriod, existingPeriods, initialized, loading, sources, urlOptions]);

  React.useEffect(() => {
    if (!selectedSource) return;
    const options = listAllowedTargetPeriodOptions(selectedSource.report_period, existingPeriods);
    if (options.length === 1) {
      setTargetPeriodInput(options[0].monthInput);
    }
  }, [existingPeriods, selectedSource]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!selectedSource) {
      setError(MRD_UI.selectSourceError);
      return;
    }
    const validationError = validateCreateTargetPeriod(
      targetPeriodInput,
      selectedSource.report_period,
      existingPeriods,
    );
    if (validationError) {
      setError(validationError);
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await forkMonthlyReferencePeriod({
        command_id: createMrdCommandId("mrd-create-period"),
        source_mrd_id: selectedSource.mrd_id,
        target_report_period: monthInputToIsoDate(targetPeriodInput),
        notes: notes.trim() || null,
      });
      setSuccess(
        `${MRD_UI.successCreatedPeriod(formatMrdReportPeriod(response.result.target_report_period))} ` +
          MRD_UI.successCopiedEntries(response.result.copied_entry_count),
      );
      await loadSources();
    } catch (e) {
      setError(mapMrdApiError(e));
    } finally {
      setSubmitting(false);
    }
  }

  if (me && !canSeeHrProcessesNav(me)) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {MRD_UI.insufficientPermissions}
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="mrd-fork-wizard">
      <div>
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">{MRD_UI.createWizardTitle}</h1>
        <p className="mt-1 max-w-3xl text-sm text-zinc-600 dark:text-zinc-400">{MRD_UI.createWizardLead}</p>
        <p className="mt-1 text-xs text-zinc-500">{MRD_UI.creationWindowHint}</p>
      </div>

      <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-950 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-100">
        <div className="font-medium">{MRD_UI.detectedDifferencesTitle}</div>
        <p className="mt-1">{MRD_UI.detectedDifferencesLead}</p>
        <Link
          href={buildDetectedDifferencesHref({
            reportPeriod: selectedSource ? monthInputFromIso(selectedSource.report_period) : null,
          })}
          className="mt-2 inline-flex text-sm font-medium underline"
        >
          {MRD_UI.detectedDifferencesLink}
        </Link>
      </div>

      {loading ? (
        <div className="rounded-xl border border-zinc-200 px-4 py-8 text-center text-sm text-zinc-500">Загрузка…</div>
      ) : !selectedSource ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-6 text-sm text-amber-950">
          {MRD_UI.selectSourceError}{" "}
          <Link href="/directory/personnel/import#baselines" className="font-medium underline">
            {MRD_UI.journalLink}
          </Link>
        </div>
      ) : (
        <form onSubmit={(event) => void handleSubmit(event)} className="space-y-5 rounded-xl border border-zinc-200 p-5 dark:border-zinc-800">
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-3 text-sm dark:border-zinc-700 dark:bg-zinc-900">
            <div className="font-medium text-zinc-900 dark:text-zinc-100">{MRD_UI.lockedSourceLabel}</div>
            <p className="mt-1 text-zinc-700 dark:text-zinc-300">{formatMrdPeriodHeadline(selectedSource.report_period)}</p>
          </div>

          <label className="block text-sm text-zinc-700 dark:text-zinc-300">
            <span className="mb-1 block font-medium">{MRD_UI.targetPeriodLabel}</span>
            {targetOptions.length <= 1 ? (
              <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950">
                {targetPeriodInput ? formatMrdReportPeriod(monthInputToIsoDate(targetPeriodInput)) : "—"}
              </div>
            ) : (
              <select
                value={targetPeriodInput}
                onChange={(event) => setTargetPeriodInput(event.target.value)}
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                required
              >
                <option value="">Выберите период…</option>
                {targetOptions.map((option) => (
                  <option key={option.iso} value={option.monthInput}>
                    {formatMrdReportPeriod(option.iso)}
                  </option>
                ))}
              </select>
            )}
            {periodValidationError && targetPeriodInput ? (
              <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">{periodValidationError}</span>
            ) : null}
          </label>

          <label className="block text-sm text-zinc-700 dark:text-zinc-300">
            <span className="mb-1 block font-medium">
              {MRD_UI.notesLabel} <span className="font-normal text-zinc-500">({MRD_UI.notesOptional})</span>
            </span>
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={2}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>

          {warnings.length ? (
            <ul className="list-disc space-y-1 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100">
              {warnings.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : null}

          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div>
          ) : null}
          {success ? (
            <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900">{success}</div>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <button
              type="submit"
              disabled={
                submitting ||
                !targetPeriodInput ||
                !!validateCreateTargetPeriod(targetPeriodInput, selectedSource.report_period, existingPeriods)
              }
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? MRD_UI.submitting : MRD_UI.submitCreate}
            </button>
            <Link
              href="/directory/personnel/import#baselines"
              className="rounded-lg border border-zinc-300 px-4 py-2 text-sm hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
            >
              {MRD_UI.journalLink}
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}
