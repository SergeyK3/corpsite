"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import MigrationStatusMatrixPageClient from "./MigrationStatusMatrixPageClient";

export default function PersonnelSummaryPageClient() {
  const searchParams = useSearchParams();
  const params = new URLSearchParams(searchParams.toString());
  params.set("view", "reports");
  params.set("report", "cards");
  return <div className="space-y-4">
    <nav aria-label="Отчёты кадровой сводки" className="flex flex-wrap gap-2 px-4 pt-4">
      <Link href={`/directory/personnel/lk?${params.toString()}`} aria-current="page" className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white">Сводка по карточкам</Link>
    </nav>
    <MigrationStatusMatrixPageClient />
  </div>;
}
