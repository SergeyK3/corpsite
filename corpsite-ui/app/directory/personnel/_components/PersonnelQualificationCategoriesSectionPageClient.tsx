"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import * as React from "react";

import { apiFetchJson } from "@/lib/api";
import PersonnelQualificationCategoriesReport, { type QualificationCategoriesReportData } from "./PersonnelQualificationCategoriesReport";
import PersonnelQualificationCategoriesSummary from "./PersonnelQualificationCategoriesSummary";

const BASE = "/directory/personnel/qualification-categories";

export default function PersonnelQualificationCategoriesSectionPageClient() {
  const searchParams = useSearchParams();
  const reportsOpen = searchParams.get("view") === "reports";
  const [report, setReport] = React.useState<QualificationCategoriesReportData | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [unitId, setUnitId] = React.useState("");

  React.useEffect(() => {
    let active = true;
    void apiFetchJson<QualificationCategoriesReportData>("/directory/personnel/reports/qualification-categories")
      .then((value) => { if (active) setReport(value); })
      .catch((reason: { status?: number }) => {
        if (active) setError(reason?.status === 403 ? "Недостаточно прав для просмотра отчёта." : "Не удалось загрузить отчёт.");
      });
    return () => { active = false; };
  }, []);

  const tabClass = (active: boolean) => `rounded-lg px-3 py-2 text-sm font-medium ${active ? "bg-blue-600 text-white" : "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-100"}`;
  return <div className="space-y-4" data-testid="qualification-categories-section">
    <nav aria-label="Квалификационные категории" className="flex flex-wrap gap-2 px-4 pt-4">
      <Link href={BASE} aria-current={!reportsOpen ? "page" : undefined} className={tabClass(!reportsOpen)}>Список</Link>
      <Link href={`${BASE}?view=reports`} aria-current={reportsOpen ? "page" : undefined} className={tabClass(reportsOpen)}>Отчёты</Link>
    </nav>
    {reportsOpen
      ? <PersonnelQualificationCategoriesSummary report={report} error={error} unitId={unitId} onUnitIdChange={setUnitId} />
      : <div className="px-4 pb-4"><PersonnelQualificationCategoriesReport report={report} error={error} unitId={unitId} onUnitIdChange={setUnitId} /></div>}
  </div>;
}
