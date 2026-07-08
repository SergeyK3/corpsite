// PMF-4C — entry context resolver + auto draft run policy.

import {
  createDraftRun,
  getMigrationRun,
  type MigrationRun,
} from "./personnelMigrationApi.client";
import {
  clearStoredDraftRunId,
  readStoredDraftRunId,
  writeStoredDraftRunId,
} from "./personnelMigrationSessionStorage";

export type MigrationEntrySource = "review" | "migration_home" | "deep_link";

const ENTRY_SOURCES: MigrationEntrySource[] = ["review", "migration_home", "deep_link"];

export type SessionBootstrapInput = {
  domainCode: string;
  employeeId: number;
  runIdParam: number | null;
  candidateId: string | null;
  sourceParam: string | null;
};

export type SessionBootstrapResult = {
  run: MigrationRun;
  source: MigrationEntrySource;
  candidateId: string | null;
  resumed: boolean;
};

export class MigrationRunNotDraftError extends Error {
  readonly run: MigrationRun;

  constructor(run: MigrationRun) {
    super(`Migration run ${run.run_id} is not draft (${run.run_status}).`);
    this.name = "MigrationRunNotDraftError";
    this.run = run;
  }
}

export function parseMigrationEntrySource(
  sourceParam: string | null,
  candidateId: string | null,
): MigrationEntrySource {
  const normalized = (sourceParam ?? "").trim().toLowerCase();
  if (ENTRY_SOURCES.includes(normalized as MigrationEntrySource)) {
    return normalized as MigrationEntrySource;
  }
  if (candidateId) return "review";
  return "deep_link";
}

function runMatchesScope(run: MigrationRun, domainCode: string, employeeId: number): boolean {
  return run.domain_code === domainCode && run.employee_context_id === employeeId;
}

async function loadDraftRunIfValid(
  runId: number,
  domainCode: string,
  employeeId: number,
): Promise<MigrationRun | null> {
  try {
    const run = await getMigrationRun(runId);
    if (!runMatchesScope(run, domainCode, employeeId)) {
      return null;
    }
    if (run.run_status !== "draft") {
      throw new MigrationRunNotDraftError(run);
    }
    return run;
  } catch (e) {
    if (e instanceof MigrationRunNotDraftError) throw e;
    return null;
  }
}

/** Auto Draft Run Policy — PMF-4C §5. */
export async function bootstrapMigrationSession(
  input: SessionBootstrapInput,
): Promise<SessionBootstrapResult> {
  const source = parseMigrationEntrySource(input.sourceParam, input.candidateId);
  const metadata: Record<string, unknown> = { source };
  if (input.candidateId) metadata.candidate_id = input.candidateId;

  if (input.runIdParam != null) {
    const fromQuery = await loadDraftRunIfValid(input.runIdParam, input.domainCode, input.employeeId);
    if (fromQuery) {
      writeStoredDraftRunId(input.domainCode, input.employeeId, fromQuery.run_id);
      return {
        run: fromQuery,
        source,
        candidateId: input.candidateId,
        resumed: true,
      };
    }
    clearStoredDraftRunId(input.domainCode, input.employeeId);
  }

  const storedRunId = readStoredDraftRunId(input.domainCode, input.employeeId);
  if (storedRunId != null && storedRunId !== input.runIdParam) {
    const fromStorage = await loadDraftRunIfValid(storedRunId, input.domainCode, input.employeeId);
    if (fromStorage) {
      return {
        run: fromStorage,
        source,
        candidateId: input.candidateId,
        resumed: true,
      };
    }
    clearStoredDraftRunId(input.domainCode, input.employeeId);
  }

  const created = await createDraftRun({
    domain_code: input.domainCode,
    employee_context_id: input.employeeId,
    metadata,
  });
  writeStoredDraftRunId(input.domainCode, input.employeeId, created.run_id);
  return {
    run: created,
    source,
    candidateId: input.candidateId,
    resumed: false,
  };
}
