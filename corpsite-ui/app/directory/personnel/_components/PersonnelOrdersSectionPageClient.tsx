"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import WorkspaceSectionTabs from "@/components/WorkspaceSectionTabs";

import PersonnelOrdersPageClient from "./PersonnelOrdersPageClient";
import PersonnelOrdersSummaryReportPanel from "./PersonnelOrdersSummaryReport";

const SECTIONS = [
  { id: "orders", label: "Кадровые приказы" },
  { id: "reports", label: "Отчёты" },
] as const;

export default function PersonnelOrdersSectionPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlSection = searchParams.get("view") === "reports" ? "reports" : "orders";
  const [activeSectionId, setActiveSectionId] = React.useState(urlSection);

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
        <PersonnelOrdersSummaryReportPanel />
      ) : (
        <PersonnelOrdersPageClient />
      )}
    </div>
  );
}
