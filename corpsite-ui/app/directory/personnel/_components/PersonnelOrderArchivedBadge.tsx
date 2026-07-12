"use client";

import {
  PERSONNEL_ORDER_ARCHIVED_LABEL,
  personnelOrderArchivedBadgeClass,
} from "../_lib/personnelOrderLabels";

export default function PersonnelOrderArchivedBadge() {
  return (
    <span
      data-testid="personnel-order-archived-badge"
      className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${personnelOrderArchivedBadgeClass()}`}
    >
      {PERSONNEL_ORDER_ARCHIVED_LABEL}
    </span>
  );
}
