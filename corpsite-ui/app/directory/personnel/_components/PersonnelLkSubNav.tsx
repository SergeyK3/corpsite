"use client";

import Link from "next/link";

import { useCurrentUser } from "@/lib/currentUser";
import { canSeeHrProcessesNav, canSeePersonnelFileReviewNav, PERSONNEL_FILE_REVIEW_HREF } from "@/lib/personnelNav";

type Tab = "list" | "review" | "reports";
const BASE = "/directory/personnel/lk";

function tabClass(active: boolean): string {
  return `rounded-lg px-3 py-2 text-sm font-medium ${active ? "bg-blue-600 text-white" : "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-100"}`;
}

export default function PersonnelLkSubNav({ activeTab }: { activeTab: Tab }) {
  const me = useCurrentUser();
  const showCardSection = activeTab !== "review" || canSeeHrProcessesNav(me);

  return (
    <nav aria-label="Личные карточки" className="flex flex-wrap gap-2 px-4 pt-4">
      {showCardSection ? <Link href={BASE} aria-current={activeTab === "list" ? "page" : undefined} className={tabClass(activeTab === "list")}>Список карточек</Link> : null}
      {canSeePersonnelFileReviewNav(me) ? <Link href={PERSONNEL_FILE_REVIEW_HREF} aria-current={activeTab === "review" ? "page" : undefined} className={tabClass(activeTab === "review")}>Проверка карточек</Link> : null}
      {showCardSection ? <Link href={`${BASE}?view=reports&report=cards`} aria-current={activeTab === "reports" ? "page" : undefined} className={tabClass(activeTab === "reports")}>Отчёты</Link> : null}
    </nav>
  );
}
