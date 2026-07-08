import { Suspense } from "react";

import MigrationSessionRouteClient from "../../../_components/MigrationSessionRouteClient";
import { MigrationLoadingPanel } from "../../../_components/MigrationWizardShell";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ domainCode: string; employeeId: string }>;
};

export default async function PersonnelMigrationSessionPage({ params }: PageProps) {
  const { domainCode, employeeId } = await params;

  return (
    <Suspense
      fallback={
        <div className="px-4 py-3">
          <MigrationLoadingPanel label="Загрузка сессии переноса…" />
        </div>
      }
    >
      <MigrationSessionRouteClient domainCode={domainCode} employeeId={employeeId} />
    </Suspense>
  );
}
