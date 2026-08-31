"use client";

type WorkspaceSection = {
  id: string;
  label: string;
};

type Props = {
  ariaLabel: string;
  sections: readonly WorkspaceSection[];
  activeSectionId: string;
  onSelect: (sectionId: string) => void;
};

export default function WorkspaceSectionTabs({
  ariaLabel,
  sections,
  activeSectionId,
  onSelect,
}: Props) {
  return (
    <nav aria-label={ariaLabel} className="flex flex-wrap gap-2 px-4 pt-4">
      {sections.map((section) => {
        const active = section.id === activeSectionId;
        return (
          <button
            key={section.id}
            type="button"
            aria-pressed={active}
            onClick={() => onSelect(section.id)}
            className={[
              "rounded-lg px-3 py-1.5 text-sm font-medium transition",
              active
                ? "bg-blue-600 text-white"
                : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800",
            ].join(" ")}
          >
            {section.label}
          </button>
        );
      })}
    </nav>
  );
}
