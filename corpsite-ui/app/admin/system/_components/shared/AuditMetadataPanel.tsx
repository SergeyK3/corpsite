// FILE: corpsite-ui/app/admin/system/_components/shared/AuditMetadataPanel.tsx
"use client";

import FieldDiffList from "./FieldDiffList";
import { metadataHasSensitiveKeys } from "../../_lib/adminSystemLabels";

type AuditMetadataPanelProps = {
  metadata?: Record<string, unknown> | null;
};

export default function AuditMetadataPanel({ metadata }: AuditMetadataPanelProps) {
  const meta = metadata ?? {};
  const sensitive = metadataHasSensitiveKeys(meta);
  const action = typeof meta.action === "string" ? meta.action : null;
  const changedFields = meta.changed_fields as
    | Record<string, { from?: unknown; to?: unknown }>
    | undefined;

  return (
    <div className="space-y-2 text-sm">
      {sensitive.length ? (
        <p className="text-xs font-medium text-red-600">
          Warning: sensitive keys in metadata: {sensitive.join(", ")}
        </p>
      ) : null}

      {action ? (
        <div>
          <span className="font-medium">action:</span> {action}
        </div>
      ) : null}

      {meta.employee_id != null ? (
        <div>
          <span className="font-medium">employee_id:</span> {String(meta.employee_id)}
        </div>
      ) : null}

      {meta.assignment_id != null ? (
        <div>
          <span className="font-medium">assignment_id:</span> {String(meta.assignment_id)}
        </div>
      ) : null}

      {changedFields && Object.keys(changedFields).length ? (
        <div>
          <div className="font-medium">changed_fields:</div>
          <FieldDiffList changedFields={changedFields} />
        </div>
      ) : null}

      {meta.diff_fields && Array.isArray(meta.diff_fields) && meta.diff_fields.length ? (
        <div className="text-xs text-zinc-500">
          diff_fields: {(meta.diff_fields as string[]).join(", ")}
        </div>
      ) : null}

      {!action && !changedFields ? (
        <pre className="max-h-40 overflow-auto text-xs">{JSON.stringify(meta, null, 2)}</pre>
      ) : null}
    </div>
  );
}
