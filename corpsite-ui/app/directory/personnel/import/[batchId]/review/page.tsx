import { Suspense } from "react";

import PersonnelImportReviewPageClient from "../../../_components/PersonnelImportReviewPageClient";

export const dynamic = "force-dynamic";

export default async function PersonnelImportReviewPage({
  params,
}: {
  params: Promise<{ batchId: string }>;
}) {
  const { batchId } = await params;
  return (
    <Suspense fallback={<div className="px-4 py-8 text-center text-zinc-500">Загрузка…</div>}>
      <PersonnelImportReviewPageClient batchId={Number(batchId)} />
    </Suspense>
  );
}
