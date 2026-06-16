import { Suspense } from "react";

import PersonnelImportRowsPageClient from "../../../_components/PersonnelImportRowsPageClient";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ batchId: string }> };

export default async function PersonnelImportRowsPage({ params }: Props) {
  const { batchId } = await params;
  const id = Number(batchId);
  return (
    <Suspense fallback={<div className="p-6 text-sm text-zinc-500">Загрузка…</div>}>
      <PersonnelImportRowsPageClient batchId={Number.isFinite(id) ? id : 0} />
    </Suspense>
  );
}
