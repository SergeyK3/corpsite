"use client";

import {
  personnelOrderStatusBadgeClass,
  personnelOrderStatusLabel,
} from "../_lib/personnelOrderLabels";

type Props = {
  status: string;
};

export default function PersonnelOrderStatusBadge({ status }: Props) {
  return (
    <span
      className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${personnelOrderStatusBadgeClass(status)}`}
    >
      {personnelOrderStatusLabel(status)}
    </span>
  );
}
