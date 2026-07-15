"use client";

import * as React from "react";

import { PPR_CARD_SECTIONS, type PprCardSectionDef } from "@/lib/pprCardSections";
import { PERSONAL_CARD_SHORT_TITLE } from "@/lib/personnelCardTerminology";

type NavProps = {
  className?: string;
  sections?: PprCardSectionDef[];
};

export function PprCardSectionNav({ className, sections = PPR_CARD_SECTIONS }: NavProps) {
  return (
    <nav
      aria-label={`Разделы ${PERSONAL_CARD_SHORT_TITLE}`}
      className={`sticky top-0 z-10 -mx-4 mb-5 border-b border-zinc-200 bg-zinc-50/95 px-4 py-2 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/95 sm:-mx-6 sm:px-6 ${className ?? ""}`}
    >
      <ul className="flex flex-wrap gap-2">
        {sections.map((section) => (
          <li key={section.id}>
            <a
              href={`#${section.id}`}
              className="inline-flex rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-medium text-zinc-700 transition hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              {section.title}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
