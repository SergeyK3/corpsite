"use client";

import {
  PERSONNEL_ORDER_APPLIED_LABEL,
  personnelOrderAppliedBadgeClass,
} from "../_lib/personnelOrderLabels";

export default function PersonnelOrderAppliedBadge() {
  return (
    <span
      data-testid="personnel-order-applied-badge"
      className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${personnelOrderAppliedBadgeClass()}`}
    >
      {PERSONNEL_ORDER_APPLIED_LABEL}
    </span>
  );
}
