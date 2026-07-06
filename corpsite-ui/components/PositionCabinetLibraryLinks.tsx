// FILE: corpsite-ui/components/PositionCabinetLibraryLinks.tsx
"use client";

import { useMemo } from "react";

import { getDepartmentDiLibraryUrl, getSectionDiLibraryUrl } from "@/lib/diLibraries";
import type { MeInfo } from "@/lib/types";

const linkClassName =
  "inline-flex h-10 items-center rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700";

type Props = {
  me: MeInfo | null;
};

export default function PositionCabinetLibraryLinks({ me }: Props) {
  const departmentDiLibraryUrl = useMemo(
    () => getDepartmentDiLibraryUrl(me?.unit_id),
    [me?.unit_id],
  );
  const sectionDiLibraryUrl = useMemo(
    () => getSectionDiLibraryUrl(me?.login),
    [me?.login],
  );

  if (!departmentDiLibraryUrl && !sectionDiLibraryUrl) return null;

  return (
    <div className="flex flex-wrap items-end gap-3">
      {departmentDiLibraryUrl ? (
        <a href={departmentDiLibraryUrl} target="_blank" rel="noreferrer" className={linkClassName}>
          Библиотека отдела
        </a>
      ) : null}

      {sectionDiLibraryUrl ? (
        <a href={sectionDiLibraryUrl} target="_blank" rel="noreferrer" className={linkClassName}>
          Библиотека секции
        </a>
      ) : null}
    </div>
  );
}
