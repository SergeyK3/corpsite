"use client";

import { EmployeeImportCardSection } from "./EmployeeImportCardSection";

type PprCardSectionProps = React.ComponentProps<typeof EmployeeImportCardSection>;

/** PPR personal card section shell with unified accent section headings. */
export function PprCardSection(props: PprCardSectionProps) {
  return <EmployeeImportCardSection {...props} usePprHeading />;
}
