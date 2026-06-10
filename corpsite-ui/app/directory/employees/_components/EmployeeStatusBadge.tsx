"use client";

import { employeeStatusBadgeClass, employeeStatusMeta } from "../_lib/employeeStatus";

type Props = {
  item: unknown;
  className?: string;
};

export default function EmployeeStatusBadge({ item, className = "" }: Props) {
  const meta = employeeStatusMeta(item);

  return (
    <span className={`${employeeStatusBadgeClass(meta.variant)} ${className}`.trim()}>{meta.label}</span>
  );
}
