"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import ImportHrReviewPageClient from "./ImportHrReviewPageClient";
import ImportInitialBaselinePageClient from "./ImportInitialBaselinePageClient";
import PersonnelImportNormalizedRecordsReviewPageClient from "./PersonnelImportNormalizedRecordsReviewPageClient";

function ImportReviewRouter() {
  const searchParams = useSearchParams();
  const mode = searchParams.get("mode");

  if (mode === "initial") {
    return <ImportInitialBaselinePageClient />;
  }

  if (mode === "hr") {
    return <ImportHrReviewPageClient />;
  }

  const batchParam = searchParams.get("batch");
  const initialBatchId =
    batchParam && /^\d+$/.test(batchParam) ? Number(batchParam) : undefined;

  return <PersonnelImportNormalizedRecordsReviewPageClient initialBatchId={initialBatchId} />;
}

export default function ImportReviewPageRouter() {
  return (
    <Suspense fallback={<div className="py-8 text-center text-zinc-500">Загрузка…</div>}>
      <ImportReviewRouter />
    </Suspense>
  );
}
