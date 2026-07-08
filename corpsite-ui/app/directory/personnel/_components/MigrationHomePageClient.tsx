// PMF-4B — Migration Home (domain list).
"use client";

import * as React from "react";

import MigrationDomainCard from "./MigrationDomainCard";
import MigrationWizardShell, {
  MigrationEmptyPanel,
  MigrationErrorBanner,
  MigrationForbiddenPanel,
  MigrationInfoBanner,
  MigrationLoadingPanel,
} from "./MigrationWizardShell";
import {
  isPersonnelMigrationForbiddenError,
  listMigrationDomains,
  mapPersonnelMigrationApiError,
  type MigrationDomainRow,
} from "../_lib/personnelMigrationApi.client";

export default function MigrationHomePageClient() {
  const [domains, setDomains] = React.useState<MigrationDomainRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [forbidden, setForbidden] = React.useState(false);
  const [startNotice, setStartNotice] = React.useState<string | null>(null);

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
        setError(mapPersonnelMigrationApiError(e, "Не удалось загрузить домены миграции."));
        setDomains([]);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadDomains();
  }, [loadDomains]);

  function handleStartMigration(domain: MigrationDomainRow) {
    setStartNotice(
      `Домен «${domain.display_name}»: выбор сотрудника и создание draft run будут доступны в PMF-4C.`
    );
  }

  return (
    <MigrationWizardShell
      title="Миграция кадровых данных"
      description="Перенос approved staging-данных в постоянные кадровые записи через Commit Engine. Единственная точка фиксации — commit migration run."
    >
      <MigrationInfoBanner message="Commit — единственная точка записи в кадровую карточку. Import Layer остаётся staging-only." />

      {startNotice ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-200">
          {startNotice}
        </div>
      ) : null}

      {forbidden ? <MigrationForbiddenPanel /> : null}

      {!forbidden ? <MigrationErrorBanner message={error} /> : null}

      {!forbidden && error ? (
        <div>
          <button
            type="button"
            onClick={() => void loadDomains()}
            className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-800 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-900"
          >
            Повторить
          </button>
        </div>
      ) : null}

      {forbidden ? null : loading ? (
        <MigrationLoadingPanel label="Загрузка доменов миграции…" />
      ) : domains.length === 0 && !error ? (
        <MigrationEmptyPanel
          title="Домены миграции не найдены"
          description="В реестре PMF нет зарегистрированных domain plugins. Проверьте seed personnel_migration_domains."
        />
      ) : domains.length > 0 ? (
        <section aria-label="Домены миграции">
          <h2 className="mb-3 text-sm font-medium text-zinc-700 dark:text-zinc-300">Доступные домены</h2>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {domains.map((domain) => (
              <MigrationDomainCard key={domain.domain_code} domain={domain} onStartMigration={handleStartMigration} />
            ))}
          </div>
        </section>
      ) : null}
    </MigrationWizardShell>
  );
}
