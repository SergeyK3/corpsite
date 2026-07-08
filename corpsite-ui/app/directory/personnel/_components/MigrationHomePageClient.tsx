// PMF-4B.1 — Migration Home (HR-first).
"use client";

import Link from "next/link";
import * as React from "react";

import MigrationDomainCard from "./MigrationDomainCard";
import MigrationNextSteps from "./MigrationNextSteps";
import MigrationProcessChain from "./MigrationProcessChain";
import MigrationRoadmapPanel from "./MigrationRoadmapPanel";
import MigrationWizardShell, {
  MigrationEmptyPanel,
  MigrationErrorBanner,
  MigrationForbiddenPanel,
  MigrationLoadingPanel,
} from "./MigrationWizardShell";
import {
  isPersonnelMigrationForbiddenError,
  listMigrationDomains,
  mapPersonnelMigrationApiError,
  type MigrationDomainRow,
} from "../_lib/personnelMigrationApi.client";
import {
  MIGRATION_HERO_DESCRIPTION,
  MIGRATION_HERO_TITLE,
  MIGRATION_REVIEW_LINK_HREF,
  MIGRATION_REVIEW_LINK_LABEL,
  migrationHrEmptyStateDescription,
  migrationHrEmptyStateTitle,
  migrationHrLoadError,
} from "../_lib/personnelMigrationHrLabels";

export default function MigrationHomePageClient() {
  const [domains, setDomains] = React.useState<MigrationDomainRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [forbidden, setForbidden] = React.useState(false);

  const loadDomains = React.useCallback(async () => {
    setLoading(true);
    setForbidden(false);
    try {
      const data = await listMigrationDomains();
      setDomains(data.items ?? []);
      setError(null);
    } catch (e) {
      if (isPersonnelMigrationForbiddenError(e)) {
        setForbidden(true);
        setError(null);
        setDomains([]);
      } else {
        setError(
          migrationHrLoadError(mapPersonnelMigrationApiError(e, "Не удалось загрузить типы кадровых данных."))
        );
        setDomains([]);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadDomains();
  }, [loadDomains]);

  return (
    <MigrationWizardShell title={MIGRATION_HERO_TITLE} description={MIGRATION_HERO_DESCRIPTION}>
      <MigrationProcessChain />

      <div className="flex flex-wrap items-center gap-3">
        <Link
          href={MIGRATION_REVIEW_LINK_HREF}
          className="inline-flex items-center rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-900"
        >
          ← {MIGRATION_REVIEW_LINK_LABEL}
        </Link>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Если записи ещё не проверены, начните с проверки импортированных данных.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <div className="space-y-4">
          {forbidden ? <MigrationForbiddenPanel /> : null}

          {!forbidden ? <MigrationErrorBanner message={error} /> : null}

          {!forbidden && error ? (
            <button
              type="button"
              onClick={() => void loadDomains()}
              className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-800 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-900"
            >
              Повторить
            </button>
          ) : null}

          {forbidden ? null : loading ? (
            <MigrationLoadingPanel label="Загрузка типов кадровых данных…" />
          ) : domains.length === 0 && !error ? (
            <MigrationEmptyPanel
              title={migrationHrEmptyStateTitle()}
              description={migrationHrEmptyStateDescription()}
            />
          ) : domains.length > 0 ? (
            <section aria-label="Типы кадровых данных">
              <h2 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Тип кадровых данных</h2>
              <div className="grid gap-4 lg:grid-cols-2">
                {domains.map((domain) => (
                  <MigrationDomainCard key={domain.domain_code} domain={domain} />
                ))}
              </div>
            </section>
          ) : null}

          <MigrationRoadmapPanel />
        </div>

        <aside className="space-y-4">
          <MigrationNextSteps />
        </aside>
      </div>
    </MigrationWizardShell>
  );
}
