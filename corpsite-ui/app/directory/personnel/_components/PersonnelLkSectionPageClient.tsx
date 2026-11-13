"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import PersonnelLkPageClient from "./PersonnelLkPageClient";
import PersonnelSummaryPageClient from "./PersonnelSummaryPageClient";

const BASE = "/directory/personnel/lk";

export default function PersonnelLkSectionPageClient() {
  const searchParams = useSearchParams();
  const reportsOpen = searchParams.get("view") === "reports";
  const tabClass = (active: boolean) => `rounded-lg px-3 py-2 text-sm font-medium ${active ? "bg-blue-600 text-white" : "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-100"}`;

  return <div className="space-y-3">
    <nav aria-label="Личные карточки" className="flex flex-wrap gap-2 px-4 pt-4">
      <Link href={BASE} aria-current={!reportsOpen ? "page" : undefined} className={tabClass(!reportsOpen)}>Список карточек</Link>
      <Link href={`${BASE}?view=reports&report=cards`} aria-current={reportsOpen ? "page" : undefined} className={tabClass(reportsOpen)}>Отчёты</Link>
    </nav>
    {reportsOpen ? <PersonnelSummaryPageClient /> : <PersonnelLkPageClient />}
  </div>;
}
