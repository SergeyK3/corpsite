"use client";

import type { PprCardSectionDef, PprCardSectionId } from "@/lib/pprCardSections";

export default function PersonalCardSectionTabs({ sections, active, onSelect, pending = [] }: {
  sections: PprCardSectionDef[];
  active: PprCardSectionId;
  onSelect: (id: PprCardSectionId) => void;
  pending?: PprCardSectionId[];
}) {
  return <div role="tablist" aria-label="Разделы личной карточки" className="-mx-1 flex flex-wrap gap-2 px-1 pb-1">
    {sections.map((section) => <button key={section.id} type="button" role="tab"
      aria-selected={active === section.id} aria-controls={`personal-card-panel-${section.id}`}
      onClick={() => onSelect(section.id)}
      className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${active === section.id
        ? "bg-blue-600 text-white"
        : "border border-zinc-300 bg-white text-zinc-800 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-900"}`}>
      {section.title}
      {pending.includes(section.id) && <span role="img" aria-label="Есть изменения на проверке"
        title="Есть изменения на проверке" className="inline-block h-2.5 w-2.5 rounded-full bg-red-500 ring-1 ring-white" />}
    </button>)}
  </div>;
}
