"use client";

import { documentStatusBadgeClass, documentStatusLabel } from "../_lib/status";

type Props = { status: string };

export default function DocumentStatusBadge({ status }: Props) {
  return (
    <span
      className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${documentStatusBadgeClass(status)}`}
      data-testid={`document-status-badge-${status}`}
    >
      {documentStatusLabel(status)}
    </span>
  );
}
