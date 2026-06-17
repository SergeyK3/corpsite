// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelSectionHeader.tsx
"use client";

import { Suspense } from "react";

import PersonnelSubNav from "./PersonnelSubNav";

export default function PersonnelSectionHeader() {
  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Персонал</h1>
      <div className="mt-3">
        <Suspense fallback={<div className="h-8" aria-hidden="true" />}>
          <PersonnelSubNav />
        </Suspense>
      </div>
    </div>
  );
}
