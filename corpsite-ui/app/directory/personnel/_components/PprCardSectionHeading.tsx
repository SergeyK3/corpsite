import * as React from "react";

/** Shared PPR card section title styling (accent bar + semibold heading). */
export const PPR_CARD_SECTION_HEADING_CLASS =
  "border-l-[3px] border-amber-600 pl-3 text-[15px] font-semibold leading-snug text-amber-950 dark:border-amber-500 dark:text-amber-100";

type PprCardSectionHeadingProps = {
  id: string;
  children: React.ReactNode;
};

export function PprCardSectionHeading({ id, children }: PprCardSectionHeadingProps) {
  return (
    <h2 id={id} className={PPR_CARD_SECTION_HEADING_CLASS}>
      {children}
    </h2>
  );
}
