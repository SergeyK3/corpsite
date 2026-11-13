"use client";

import { useRouter, useSearchParams } from "next/navigation";

import WorkspaceSectionTabs from "@/components/WorkspaceSectionTabs";
import { useCurrentUser } from "@/lib/currentUser";
import { canSeeHrProcessesNav } from "@/lib/personnelNav";
import PersonnelJournalPageClient from "./PersonnelJournalPageClient";
import PersonnelTypeHeadcountReport from "./PersonnelTypeHeadcountReport";

const SECTIONS = [
  { id: "journal", label: "Журнал" },
  { id: "reports", label: "Отчёты" },
] as const;

export default function PersonnelJournalSectionPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const canSeeReport = canSeeHrProcessesNav(useCurrentUser());
  const activeSection = canSeeReport && searchParams.get("view") === "reports" ? "reports" : "journal";

  function selectSection(sectionId: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (sectionId === "reports") params.set("view", "reports");
    else params.delete("view");
    const query = params.toString();
    router.replace(`/directory/personnel/journal${query ? `?${query}` : ""}`);
  }

  return <div>
    {canSeeReport ? <WorkspaceSectionTabs
      ariaLabel="Подразделы кадрового журнала"
      sections={SECTIONS}
      activeSectionId={activeSection}
      onSelect={selectSection}
    /> : null}
    {activeSection === "reports"
      ? <PersonnelTypeHeadcountReport />
      : <PersonnelJournalPageClient />}
  </div>;
}
