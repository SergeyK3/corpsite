// PMF-4D / PMF-4E — post-bootstrap mapping workspace orchestration.
"use client";

import * as React from "react";

import type { EmployeeDetails } from "@/app/directory/employees/_lib/types";

import MigrationCandidateList from "./MigrationCandidateList";
import MigrationCandidateSourcePanel from "./MigrationCandidateSourcePanel";
import MigrationCommitConfirmDialog from "./MigrationCommitConfirmDialog";
import MigrationCommitSuccessPanel from "./MigrationCommitSuccessPanel";
import MigrationEmployeeContextCard from "./MigrationEmployeeContextCard";
import MigrationReviewSummaryPanel from "./MigrationReviewSummaryPanel";
import MigrationWorkflowStepper from "./MigrationWorkflowStepper";
import { MigrationErrorBanner } from "./MigrationWizardShell";
import type { MigrationEntrySource } from "../_lib/personnelMigrationEntry";
import {
  listNormalizedRecords,
  type NormalizedRecord,
} from "../_lib/importApi.client";
import {
  addMigrationDraftItem,
  commitMigrationRun,
  getMigrationRun,
  mapPersonnelMigrationApiError,
  type MigrationDomainRow,
  type MigrationRun,
  type MigrationRunItem,
} from "../_lib/personnelMigrationApi.client";
import {
  buildAddDraftItemPayloadFromNormalizedRecord,
  findNormalizedRecordByCandidateId,
  normalizedRecordKindsForDomain,
} from "../_lib/personnelMigrationCandidates";
import { displayNormalizedRecordIin } from "../_lib/normalizedRecordIin";
import { clearStoredDraftRunId } from "../_lib/personnelMigrationSessionStorage";
import {
  MIGRATION_COMMIT_CTA_LABEL,
  migrationHrCommitError,
  migrationHrCommitUnavailableReason,
  migrationHrLoadError,
  migrationHrSessionAddItemError,
  type MigrationSessionWorkflowStepId,
} from "../_lib/personnelMigrationHrLabels";

type WorkspacePhase = "select" | "review" | "success";

type MigrationSessionWorkspaceProps = {
  domain: MigrationDomainRow;
  employee: EmployeeDetails;
  employeeId: number;
  run: MigrationRun;
  source: MigrationEntrySource;
  candidateId: string | null;
  onRunUpdated: (run: MigrationRun) => void;
  onTechnicalError?: (error: string | null) => void;
};

function findItemForRecord(run: MigrationRun, record: NormalizedRecord): MigrationRunItem | null {
  const sourceId = String(record.normalized_record_id);
  return (
    run.items.find(
      (item) =>
        item.source_kind === "normalized_record" && item.source_record_id === sourceId,
    ) ?? null
  );
}

function resolveActiveItem(run: MigrationRun): MigrationRunItem | null {
  const draftItems = run.items.filter((item) => item.item_status === "draft");
  return draftItems[draftItems.length - 1] ?? run.items[run.items.length - 1] ?? null;
}

function resolveInitialPhase(run: MigrationRun): WorkspacePhase {
  if (run.run_status === "committed") return "success";
  if (resolveActiveItem(run)) return "review";
  return "select";
}

function resolveActiveStepId(phase: WorkspacePhase, adding: boolean): MigrationSessionWorkflowStepId {
  if (adding) return "records";
  switch (phase) {
    case "select":
      return "employee";
    case "review":
      return "review";
    case "success":
      return "commit";
    default:
      return "employee";
  }
}

function resolveDisabledSteps(phase: WorkspacePhase): MigrationSessionWorkflowStepId[] {
  switch (phase) {
    case "select":
      return ["review", "commit"];
    case "review":
      return ["commit"];
    default:
      return [];
  }
}

export default function MigrationSessionWorkspace({
  domain,
  employee,
  employeeId,
  run: initialRun,
  source,
  candidateId,
  onRunUpdated,
  onTechnicalError,
}: MigrationSessionWorkspaceProps) {
  const [run, setRun] = React.useState(initialRun);
  const [phase, setPhase] = React.useState<WorkspacePhase>(() => resolveInitialPhase(initialRun));
  const [records, setRecords] = React.useState<NormalizedRecord[]>([]);
  const [recordsLoading, setRecordsLoading] = React.useState(true);
  const [recordsError, setRecordsError] = React.useState<string | null>(null);
  const [selectedRecord, setSelectedRecord] = React.useState<NormalizedRecord | null>(null);
  const [activeItem, setActiveItem] = React.useState<MigrationRunItem | null>(() =>
    resolveActiveItem(initialRun),
  );
  const [adding, setAdding] = React.useState(false);
  const [addError, setAddError] = React.useState<string | null>(null);
  const [commitError, setCommitError] = React.useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [committing, setCommitting] = React.useState(false);
  const autoAddAttemptedRef = React.useRef(false);
  const runRef = React.useRef(initialRun);

  React.useEffect(() => {
    runRef.current = run;
  }, [run]);

  const activeStepId = resolveActiveStepId(phase, adding);
  const disabledStepIds = resolveDisabledSteps(phase);
  const hasPersonLink = run.person_id != null;
  const isDraft = run.run_status === "draft";
  const canCommit =
    phase === "review" &&
    activeItem != null &&
    isDraft &&
    hasPersonLink &&
    migrationHrCommitUnavailableReason({
      hasItem: activeItem != null,
      isDraft,
      hasPersonLink,
    }) == null;

  const commitUnavailableReason =
    phase === "review"
      ? migrationHrCommitUnavailableReason({
          hasItem: activeItem != null,
          isDraft,
          hasPersonLink,
        })
      : null;

  const iinOverride = React.useMemo(() => {
    if (source !== "review") return null;
    const record = selectedRecord ?? findNormalizedRecordByCandidateId(records, candidateId);
    if (!record) return null;
    const iin = displayNormalizedRecordIin(record);
    return iin === "—" ? null : iin;
  }, [candidateId, records, selectedRecord, source]);

  React.useEffect(() => {
    setRun(initialRun);
    const item = resolveActiveItem(initialRun);
    if (item) {
      setActiveItem(item);
    }
    setPhase(resolveInitialPhase(initialRun));
  }, [initialRun]);

  React.useEffect(() => {
    onTechnicalError?.(commitError);
  }, [commitError, onTechnicalError]);

  React.useEffect(() => {
    let cancelled = false;

    async function loadCandidates() {
      setRecordsLoading(true);
      setRecordsError(null);
      try {
        const kinds = normalizedRecordKindsForDomain(domain.domain_code);
        const responses = await Promise.all(
          kinds.map((recordKind) =>
            listNormalizedRecords({
              employee_id: employeeId,
              review_status: "approved",
              record_kind: recordKind,
              limit: 100,
            }),
          ),
        );
        if (cancelled) return;

        const merged = responses
          .flatMap((response) => response.items ?? [])
          .sort((a, b) => b.normalized_record_id - a.normalized_record_id);

        setRecords(merged);

        const existingItem = resolveActiveItem(initialRun);
        if (existingItem?.source_record_id) {
          const matched = merged.find(
            (row) => String(row.normalized_record_id) === existingItem.source_record_id,
          );
          if (matched) {
            setSelectedRecord(matched);
            return;
          }
        }

        if (candidateId) {
          const matched = findNormalizedRecordByCandidateId(merged, candidateId);
          if (matched) {
            setSelectedRecord(matched);
          }
        }
      } catch (e) {
        if (!cancelled) {
          setRecordsError(
            migrationHrLoadError(
              mapPersonnelMigrationApiError(e, "Не удалось загрузить список записей."),
            ),
          );
        }
      } finally {
        if (!cancelled) {
          setRecordsLoading(false);
        }
      }
    }

    void loadCandidates();
    return () => {
      cancelled = true;
    };
  }, [candidateId, domain.domain_code, employeeId, initialRun]);

  const addRecordToRun = React.useCallback(
    async (record: NormalizedRecord) => {
      const existing = findItemForRecord(runRef.current, record);
      if (existing) {
        setSelectedRecord(record);
        setActiveItem(existing);
        setPhase("review");
        setAddError(null);
        return;
      }

      setAdding(true);
      setAddError(null);
      setSelectedRecord(record);

      try {
        const response = await addMigrationDraftItem(
          runRef.current.run_id,
          buildAddDraftItemPayloadFromNormalizedRecord(record),
        );
        setRun(response.run);
        runRef.current = response.run;
        setActiveItem(response.item);
        setPhase("review");
        onRunUpdated(response.run);
      } catch (e) {
        setAddError(
          migrationHrSessionAddItemError(
            mapPersonnelMigrationApiError(e, "Не удалось добавить запись в сессию переноса."),
          ),
        );
      } finally {
        setAdding(false);
      }
    },
    [onRunUpdated],
  );

  React.useEffect(() => {
    if (phase !== "select") return;
    if (!selectedRecord || recordsLoading || adding || activeItem) return;
    if (autoAddAttemptedRef.current) return;

    autoAddAttemptedRef.current = true;
    void addRecordToRun(selectedRecord);
  }, [activeItem, addRecordToRun, adding, phase, recordsLoading, selectedRecord]);

  const handleSelect = React.useCallback(
    (record: NormalizedRecord) => {
      autoAddAttemptedRef.current = true;
      void addRecordToRun(record);
    },
    [addRecordToRun],
  );

  const handleCommit = React.useCallback(async () => {
    setCommitting(true);
    setCommitError(null);
    onTechnicalError?.(null);

    try {
      await commitMigrationRun(runRef.current.run_id);
      const refreshed = await getMigrationRun(runRef.current.run_id);
      setRun(refreshed);
      runRef.current = refreshed;
      setPhase("success");
      onRunUpdated(refreshed);
      clearStoredDraftRunId(domain.domain_code, employeeId);
      setConfirmOpen(false);
    } catch (e) {
      const raw = mapPersonnelMigrationApiError(e, "Не удалось выполнить перенос.");
      const friendly = migrationHrCommitError(raw);
      setCommitError(friendly);
      onTechnicalError?.(raw);
      setConfirmOpen(false);
    } finally {
      setCommitting(false);
    }
  }, [domain.domain_code, employeeId, onRunUpdated, onTechnicalError]);

  const contextRecord = selectedRecord ?? findNormalizedRecordByCandidateId(records, candidateId);

  return (
    <div className="space-y-4">
      <MigrationWorkflowStepper activeStepId={activeStepId} disabledStepIds={disabledStepIds} />

      {phase === "success" ? (
        <MigrationCommitSuccessPanel
          employee={employee}
          employeeId={employeeId}
          domain={domain}
          record={contextRecord}
        />
      ) : (
        <>
          <MigrationCandidateSourcePanel
            candidateId={candidateId}
            source={source}
            record={contextRecord}
          />

          <MigrationEmployeeContextCard employee={employee} iinOverride={iinOverride} />

          {phase === "select" ? (
            <>
              {recordsError ? <MigrationErrorBanner message={recordsError} /> : null}
              <MigrationCandidateList
                records={records}
                selectedRecordId={selectedRecord?.normalized_record_id ?? null}
                loading={recordsLoading}
                adding={adding}
                error={addError}
                onSelect={handleSelect}
              />
            </>
          ) : (
            <>
              {addError ? <MigrationErrorBanner message={addError} /> : null}
              {commitError ? <MigrationErrorBanner message={commitError} /> : null}
              <MigrationReviewSummaryPanel
                employee={employee}
                domain={domain}
                source={source}
                record={contextRecord}
                isDraft={isDraft}
                hasPersonLink={hasPersonLink}
              />
              <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
                {canCommit ? (
                  <button
                    type="button"
                    onClick={() => setConfirmOpen(true)}
                    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                  >
                    {MIGRATION_COMMIT_CTA_LABEL}
                  </button>
                ) : (
                  <p className="text-sm text-zinc-600 dark:text-zinc-400">
                    {commitUnavailableReason ?? "Перенос временно недоступен."}
                  </p>
                )}
              </div>
            </>
          )}
        </>
      )}

      <MigrationCommitConfirmDialog
        open={confirmOpen}
        committing={committing}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void handleCommit()}
      />
    </div>
  );
}
