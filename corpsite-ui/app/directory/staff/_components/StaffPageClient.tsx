"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import WorkspaceSectionTabs from "@/components/WorkspaceSectionTabs";
import EmployeesPageClient from "../../employees/_components/EmployeesPageClient";
import type { EmployeesFilters } from "../../employees/_lib/query";
import type { Department, EmployeesResponse, Position } from "../../employees/_lib/types";
import PersonnelRosterReportPanel from "../../personnel/_components/PersonnelRosterReport";

const SECTIONS = [
  { id: "personnel", label: "Персонал" },
  { id: "reports", label: "Отчёты" },
] as const;

const INITIAL_FILTERS: EmployeesFilters = {
  status: "all",
  limit: 50,
  offset: 0,
};
const INITIAL_DEPARTMENTS: Department[] = [];
const INITIAL_POSITIONS: Position[] = [];
const INITIAL_EMPLOYEES: EmployeesResponse = { items: [], total: 0 };

export default function StaffPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlSection = searchParams.get("view") === "reports" ? "reports" : "personnel";
  const [activeSectionId, setActiveSectionId] = React.useState(urlSection);

  React.useEffect(() => {
    setActiveSectionId(urlSection);
  }, [urlSection]);

  function selectSection(sectionId: string) {
    const nextSectionId = sectionId === "reports" ? "reports" : "personnel";
    const params = new URLSearchParams(searchParams.toString());
    if (nextSectionId === "reports") params.set("view", "reports");
    else params.delete("view");
    const query = params.toString();
    setActiveSectionId(nextSectionId);
    router.replace(`/directory/staff${query ? `?${query}` : ""}`);
  }

  return (
    <div className="bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
          <div className="border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Персонал</h1>
          </div>
          <WorkspaceSectionTabs
            ariaLabel="Подразделы персонала"
            sections={SECTIONS}
            activeSectionId={activeSectionId}
            onSelect={selectSection}
          />
          {activeSectionId === "reports" ? (
            <PersonnelRosterReportPanel />
          ) : (
            <EmployeesPageClient
              pageTitle="Персонал"
              readOnly
              managementView
              initialFilters={INITIAL_FILTERS}
              initialDepartments={INITIAL_DEPARTMENTS}
              initialPositions={INITIAL_POSITIONS}
              initialEmployees={INITIAL_EMPLOYEES}
              initialError={null}
              refreshResetsOrgUnitFilter
              embedded
            />
          )}
        </div>
      </div>
    </div>
  );
}
