"use client";

import { useSearchParams } from "next/navigation";

import PersonnelLkPageClient from "./PersonnelLkPageClient";
import PersonnelLkSubNav from "./PersonnelLkSubNav";
import PersonnelSummaryPageClient from "./PersonnelSummaryPageClient";

export default function PersonnelLkSectionPageClient() {
  const searchParams = useSearchParams();
  const reportsOpen = searchParams.get("view") === "reports";

  return <div className="space-y-3">
    <PersonnelLkSubNav activeTab={reportsOpen ? "reports" : "list"} />
    {reportsOpen ? <PersonnelSummaryPageClient /> : <PersonnelLkPageClient />}
  </div>;
}
