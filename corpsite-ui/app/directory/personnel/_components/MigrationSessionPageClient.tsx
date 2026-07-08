// PMF-4C / PMF-4D — Migration Wizard session bootstrap + mapping workspace.
"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import * as React from "react";

import { getEmployee, mapApiErrorToMessage } from "@/app/directory/employees/_lib/api.client";
import type { EmployeeDetails } from "@/app/directory/employees/_lib/types";

import MigrationEmployeeContextCard from "./MigrationEmployeeContextCard";
import MigrationPersonBlockerPanel from "./MigrationPersonBlockerPanel";
import MigrationSessionTechnicalDetails from "./MigrationSessionTechnicalDetails";
import MigrationSessionWorkspace from "./MigrationSessionWorkspace";
import MigrationWorkflowStepper from "./MigrationWorkflowStepper";
import MigrationWizardShell, {
  MigrationEmptyPanel,
  MigrationErrorBanner,
  MigrationInfoBanner,
  MigrationLoadingPanel,
} from "./MigrationWizardShell";
import {
  bootstrapMigrationSession,
  MigrationRunNotDraftError,
  parseMigrationEntrySource,
  type MigrationEntrySource,
} from "../_lib/personnelMigrationEntry";
import {
  isMigrationPersonRequiredError,
  isPersonnelMigrationForbiddenError,
  listMigrationDomains,
  mapPersonnelMigrationApiError,
  type MigrationDomainRow,
  type MigrationRun,
} from "../_lib/personnelMigrationApi.client";
import {
  migrationHrDomainDisabled,
  migrationHrDomainNotFound,
  migrationHrEmployeeNotFound,
  migrationHrLoadError,
  migrationHrSessionCommittedMessage,
  migrationHrSessionEntrySourceLabel,
  migrationHrSessionResumeBanner,
  migrationHrSessionTitle,
} from "../_lib/personnelMigrationHrLabels";

type MigrationSessionPageClientProps = {
  domainCode: string;
  employeeIdParam: string;
};

type BootstrapState =
  | { phase: "loading" }
  | { phase: "forbidden" }
  | { phase: "domain_missing"; domainCode: string }
  | { phase: "domain_disabled"; domain: MigrationDomainRow }
  | { phase: "employee_missing" }
  | { phase: "person_blocker"; employee: EmployeeDetails; domain: MigrationDomainRow; source: MigrationEntrySource; candidateId: string | null }
  | { phase: "run_not_draft"; run: MigrationRun; employee: EmployeeDetails; domain: MigrationDomainRow; source: MigrationEntrySource; candidateId: string | null }
  | { phase: "error"; message: string }
  | {
      phase: "ready";
      employee: EmployeeDetails;
      domain: MigrationDomainRow;
      run: MigrationRun;
      source: MigrationEntrySource;
      candidateId: string | null;
      resumed: boolean;
    };

function parsePositiveInt(value: string | null): number | null {
  if (!value) return null;
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function parseEmployeeId(value: string): number | null {
  const n = Number(String(value).trim());
  return Number.isFinite(n) && n > 0 ? n : null;
}

export default function MigrationSessionPageClient({
  domainCode,
  employeeIdParam,
}: MigrationSessionPageClientProps) {
  const searchParams = useSearchParams();
  const [state, setState] = React.useState<BootstrapState>({ phase: "loading" });
  const [technicalError, setTechnicalError] = React.useState<string | null>(null);

  const candidateId = searchParams.get("candidate_id")?.trim() || null;
  const runIdParam = parsePositiveInt(searchParams.get("run_id"));
  const sourceParam = searchParams.get("source");

  const employeeId = parseEmployeeId(employeeIdParam);

  const loadSession = React.useCallback(async () => {
    setState({ phase: "loading" });

    if (!employeeId) {
      setState({ phase: "employee_missing" });
      return;
    }

    try {
      const [domainsResponse, employee] = await Promise.all([
        listMigrationDomains(),
        getEmployee(String(employeeId)),
      ]);

      const domain = (domainsResponse.items ?? []).find((row) => row.domain_code === domainCode) ?? null;
      if (!domain) {
        setState({ phase: "domain_missing", domainCode });
        return;
      }
      if (!domain.is_enabled) {
        setState({ phase: "domain_disabled", domain });
        return;
      }

      const source = parseMigrationEntrySource(sourceParam, candidateId);

      try {
        const boot = await bootstrapMigrationSession({
          domainCode,
          employeeId,
          runIdParam,
          candidateId,
          sourceParam,
        });

        setState({
          phase: "ready",
          employee,
          domain,
          run: boot.run,
          source: boot.source,
          candidateId: boot.candidateId,
          resumed: boot.resumed,
        });
      } catch (e) {
        if (e instanceof MigrationRunNotDraftError) {
          setState({
            phase: "run_not_draft",
            run: e.run,
            employee,
            domain,
            source,
            candidateId,
          });
          return;
        }
        if (isMigrationPersonRequiredError(e)) {
          setState({
            phase: "person_blocker",
            employee,
            domain,
            source,
            candidateId,
          });
          return;
        }
        throw e;
      }
    } catch (e) {
      if (isPersonnelMigrationForbiddenError(e)) {
        setState({ phase: "forbidden" });
        return;
      }
      const employeeMsg = mapApiErrorToMessage(e, "");
      if (employeeMsg.toLowerCase().includes("not found") || employeeMsg.includes("404")) {
        setState({ phase: "employee_missing" });
        return;
      }
      setState({
        phase: "error",
        message: migrationHrLoadError(mapPersonnelMigrationApiError(e, "Не удалось открыть сессию переноса.")),
      });
    }
  }, [candidateId, domainCode, employeeId, runIdParam, sourceParam]);

  React.useEffect(() => {
    void loadSession();
  }, [loadSession]);

  if (state.phase === "loading") {
    return (
      <div className="px-4 py-3">
        <MigrationLoadingPanel label="Подготовка сессии переноса…" />
      </div>
    );
  }

  if (state.phase === "forbidden") {
    return (
      <MigrationWizardShell title="Перенос данных">
        <MigrationEmptyPanel title="Недостаточно прав" description="Перенос доступен только уполномоченным HR-операторам." />
      </MigrationWizardShell>
    );
  }

  if (state.phase === "domain_missing") {
    return (
      <MigrationWizardShell title="Перенос данных">
        <MigrationErrorBanner message={migrationHrDomainNotFound(state.domainCode)} />
        <Link href="/directory/personnel/migration" className="mt-3 inline-flex text-sm font-medium text-blue-700 hover:underline dark:text-blue-300">
          ← К типам кадровых данных
        </Link>
      </MigrationWizardShell>
    );
  }

  if (state.phase === "domain_disabled") {
    return (
      <MigrationWizardShell title={migrationHrSessionTitle(state.domain.display_name)}>
        <MigrationInfoBanner message={migrationHrDomainDisabled(state.domain.display_name)} />
        <Link href="/directory/personnel/migration" className="mt-3 inline-flex text-sm font-medium text-blue-700 hover:underline dark:text-blue-300">
          ← К типам кадровых данных
        </Link>
      </MigrationWizardShell>
    );
  }

  if (state.phase === "employee_missing") {
    return (
      <MigrationWizardShell title="Перенос данных">
        <MigrationErrorBanner message={migrationHrEmployeeNotFound()} />
        <Link href="/directory/personnel/migration" className="mt-3 inline-flex text-sm font-medium text-blue-700 hover:underline dark:text-blue-300">
          ← К типам кадровых данных
        </Link>
      </MigrationWizardShell>
    );
  }

  const sharedShell = (args: {
    domain: MigrationDomainRow;
    employee: EmployeeDetails;
    source: MigrationEntrySource;
    candidateId: string | null;
    run: MigrationRun | null;
    children: React.ReactNode;
  }) => (
    <MigrationWizardShell
      title={migrationHrSessionTitle(args.domain.display_name)}
      breadcrumbTail={[
        { label: args.domain.display_name, href: "/directory/personnel/migration" },
        { label: args.employee.fio?.trim() || `Сотрудник #${employeeId}` },
      ]}
    >
      <div className="space-y-4">
        <MigrationWorkflowStepper activeStepId="employee" />
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Источник входа: <span className="font-medium text-zinc-800 dark:text-zinc-200">{migrationHrSessionEntrySourceLabel(args.source)}</span>
        </p>
        <MigrationEmployeeContextCard employee={args.employee} />
        {args.children}
        <MigrationSessionTechnicalDetails
          domainCode={domainCode}
          employeeId={employeeId!}
          run={args.run}
          source={args.source}
          candidateId={args.candidateId}
        />
      </div>
    </MigrationWizardShell>
  );

  if (state.phase === "person_blocker") {
    return sharedShell({
      domain: state.domain,
      employee: state.employee,
      source: state.source,
      candidateId: state.candidateId,
      run: null,
      children: <MigrationPersonBlockerPanel />,
    });
  }

  if (state.phase === "run_not_draft") {
    return sharedShell({
      domain: state.domain,
      employee: state.employee,
      source: state.source,
      candidateId: state.candidateId,
      run: state.run,
      children: (
        <MigrationInfoBanner message={migrationHrSessionCommittedMessage()} />
      ),
    });
  }

  if (state.phase === "error") {
    return (
      <MigrationWizardShell title="Перенос данных">
        <MigrationErrorBanner message={state.message} />
        <button
          type="button"
          onClick={() => void loadSession()}
          className="mt-3 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-800 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-900"
        >
          Повторить
        </button>
      </MigrationWizardShell>
    );
  }

  const resumeBanner = migrationHrSessionResumeBanner(state.resumed);

  return (
    <MigrationWizardShell
      title={migrationHrSessionTitle(state.domain.display_name)}
      breadcrumbTail={[
        { label: state.domain.display_name, href: "/directory/personnel/migration" },
        { label: state.employee.fio?.trim() || `Сотрудник #${employeeId}` },
      ]}
    >
      <div className="space-y-4">
        {resumeBanner ? <MigrationInfoBanner message={resumeBanner} /> : null}
        <MigrationSessionWorkspace
          domain={state.domain}
          employee={state.employee}
          employeeId={employeeId!}
          run={state.run}
          source={state.source}
          candidateId={state.candidateId}
          onRunUpdated={(run) =>
            setState((prev) => (prev.phase === "ready" ? { ...prev, run } : prev))
          }
          onTechnicalError={setTechnicalError}
        />
        <div className="flex flex-wrap gap-3">
          <Link
            href="/directory/personnel/import/review"
            className="inline-flex rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-900"
          >
            ← Проверка записей
          </Link>
          <Link
            href="/directory/personnel/migration"
            className="inline-flex rounded-lg px-3 py-2 text-sm font-medium text-zinc-700 underline hover:no-underline dark:text-zinc-300"
          >
            К типам кадровых данных
          </Link>
        </div>
        <MigrationSessionTechnicalDetails
          domainCode={domainCode}
          employeeId={employeeId!}
          run={state.run}
          source={state.source}
          candidateId={state.candidateId}
          lastError={technicalError}
        />
      </div>
    </MigrationWizardShell>
  );
}
