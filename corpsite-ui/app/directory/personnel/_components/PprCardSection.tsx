"use client";

import * as React from "react";
import type { PprCardSectionId } from "@/lib/pprCardSections";
import { EmployeeImportCardSection } from "./EmployeeImportCardSection";

type PprCardSectionProps = React.ComponentProps<typeof EmployeeImportCardSection>;
export const ReviewCardSectionContext = React.createContext<PprCardSectionId | null>(null);

/** PPR personal card section shell with unified accent section headings. */
export function PprCardSection(props: PprCardSectionProps) {
  const activeReviewSection = React.useContext(ReviewCardSectionContext);
  if (activeReviewSection && props.id !== activeReviewSection) return null;
  const section = <EmployeeImportCardSection {...props} usePprHeading />;
  return activeReviewSection
    ? <div role="tabpanel" id={`personal-card-panel-${props.id}`}>{section}</div>
    : section;
}
