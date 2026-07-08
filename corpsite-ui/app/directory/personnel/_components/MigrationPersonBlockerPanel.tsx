// PMF-4C — person_id precondition blocker.
"use client";

import Link from "next/link";

import { MIGRATION_PERSON_BLOCKER_MESSAGE, MIGRATION_PERSON_BLOCKER_TITLE } from "../_lib/personnelMigrationHrLabels";

export default function MigrationPersonBlockerPanel() {
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-5 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
      <p className="font-medium">{MIGRATION_PERSON_BLOCKER_TITLE}</p>
      <p className="mt-2">{MIGRATION_PERSON_BLOCKER_MESSAGE}</p>
      <div className="mt-4 flex flex-wrap gap-3">
        <Link
          href="/directory/personnel/import/review"
          className="inline-flex rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm font-medium text-amber-900 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100 dark:hover:bg-amber-900"
        >
          Перейти к проверке записей
        </Link>
        <Link
          href="/directory/personnel/migration"
          className="inline-flex rounded-lg px-3 py-2 text-sm font-medium text-amber-900 underline hover:no-underline dark:text-amber-100"
        >
          К типам кадровых данных
        </Link>
      </div>
    </div>
  );
}
