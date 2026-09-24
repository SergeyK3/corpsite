// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelSectionHeader.tsx
"use client";

import { Suspense } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import PersonnelSubNav from "./PersonnelSubNav";
import PersonnelControlListSubNav from "./PersonnelControlListSubNav";

export default function PersonnelSectionHeader() {
  const pathname = usePathname() || "";
  const isHiringDocumentChecklist = pathname === "/directory/personnel/hiring-document-checklist";

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Кадровые процессы</h1>
      <div className="mt-3">
        <Suspense fallback={<div className="h-8" aria-hidden="true" />}>
          <PersonnelSubNav />
        </Suspense>
      </div>
      <Suspense fallback={null}>
        <PersonnelControlListSubNav />
      </Suspense>
      {isHiringDocumentChecklist ? (
        <nav aria-label="Разное" className="mt-3 flex flex-wrap gap-2">
          <Link
            href="/directory/personnel/hiring-document-checklist"
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white"
            aria-current="page"
          >
            Перечень документов при приеме на работу
          </Link>
        </nav>
      ) : null}
    </div>
  );
}
