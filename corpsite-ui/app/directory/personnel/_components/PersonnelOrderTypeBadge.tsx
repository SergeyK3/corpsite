"use client";
import { usePersonnelSectionLanguage } from "../_lib/personnelSectionLanguage";

import {
  personnelOrderTypeBadgeClass,
  personnelOrderTypeLabel,
} from "../_lib/personnelOrderLabels";

type Props = {
  typeCode: string;
};

export default function PersonnelOrderTypeBadge({ typeCode }: Props) {
  const { language } = usePersonnelSectionLanguage();
  return (
    <span
      className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${personnelOrderTypeBadgeClass(typeCode)}`}
    >
      {personnelOrderTypeLabel(typeCode, language)}
    </span>
  );
}
