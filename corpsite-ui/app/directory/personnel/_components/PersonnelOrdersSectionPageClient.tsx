"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import WorkspaceSectionTabs from "@/components/WorkspaceSectionTabs";

import PersonnelOrdersPageClient from "./PersonnelOrdersPageClient";
import PersonnelOrdersSummaryReportPanel from "./PersonnelOrdersSummaryReport";
import PersonnelEmployeeActionsReport from "./PersonnelEmployeeActionsReport";

const SECTIONS = [
  { id: "orders", label: "Кадровые приказы" },
  { id: "reports", label: "Отчёты" },
] as const;
const REPORTS = [
  { id: "categories", label: "По категориям" },
  { id: "statuses", label: "По статусам" },
  { id: "employees", label: "По сотрудникам" },
] as const;
type ReportTab = (typeof REPORTS)[number]["id"];

export default function PersonnelOrdersSectionPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlSection = searchParams.get("view") === "reports" ? "reports" : "orders";
  const [activeSectionId, setActiveSectionId] = React.useState(urlSection);
  const [activeReport, setActiveReport] = React.useState<ReportTab>("categories");

  React.useEffect(() => {
    setActiveSectionId(urlSection);
  }, [urlSection]);

  function selectSection(sectionId: string) {
    const nextSectionId = sectionId === "reports" ? "reports" : "orders";
    const params = new URLSearchParams(searchParams.toString());
    if (nextSectionId === "reports") params.set("view", "reports");
    else params.delete("view");
    const query = params.toString();
    setActiveSectionId(nextSectionId);
    router.replace(`/directory/personnel/orders${query ? `?${query}` : ""}`);
  }

  return (
    <div>
      <WorkspaceSectionTabs
        ariaLabel="Подразделы приказов"
        sections={SECTIONS}
        activeSectionId={activeSectionId}
        onSelect={selectSection}
      />
      {activeSectionId === "reports" ? (
        <>
          <WorkspaceSectionTabs
            ariaLabel="Отчёты по кадровым приказам"
            sections={REPORTS}
            activeSectionId={activeReport}
            onSelect={(reportId) => setActiveReport(reportId as ReportTab)}
          />
          {activeReport === "employees" ? <PersonnelEmployeeActionsReport /> :
            <PersonnelOrdersSummaryReportPanel mode={activeReport} />}
        </>
      ) : (
        <PersonnelOrdersPageClient />
      )}
    </div>
  );
}
