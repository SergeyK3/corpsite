"use client";

import {
  personnelOrderTypeBadgeClass,
  personnelOrderTypeLabel,
} from "../_lib/personnelOrderLabels";

type Props = {
  typeCode: string;
};

export default function PersonnelOrderTypeBadge({ typeCode }: Props) {
  return (
    <span
      className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${personnelOrderTypeBadgeClass(typeCode)}`}
    >
      {personnelOrderTypeLabel(typeCode)}
    </span>
  );
}
