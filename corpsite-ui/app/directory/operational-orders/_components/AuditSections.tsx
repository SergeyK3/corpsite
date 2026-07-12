"use client";

import * as React from "react";

import { auditActionLabel, provenanceActionLabel } from "../_lib/actionLabels";
import { formatDateTime } from "../_lib/mappers";
import type { AuditSummary, ProvenanceSummary } from "../_lib/types";

type Props = {
  audit: AuditSummary[];
  provenance: ProvenanceSummary[];
};

function TechnicalDetails({ data }: { data: unknown }) {
  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-xs text-zinc-500">Технические данные</summary>
      <pre className="mt-1 overflow-x-auto rounded bg-zinc-50 p-2 text-[10px] dark:bg-zinc-900">{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}

export default function AuditSections({ audit, provenance }: Props) {
  return (
    <div className="space-y-4">
      <section className="rounded-xl border p-4 dark:border-zinc-800">
        <h3 className="mb-3 text-sm font-semibold">История рабочего пространства</h3>
        {!audit.length ? (
          <p className="text-sm text-zinc-500" data-testid="audit-empty">
            История пока отсутствует
          </p>
        ) : (
          <ol className="space-y-3">
            {audit.map((entry) => (
              <li key={entry.audit_id} className="rounded-lg border px-3 py-2 dark:border-zinc-700" data-testid={`audit-entry-${entry.audit_id}`}>
                <div className="text-sm font-medium">{auditActionLabel(entry.action)}</div>
                <div className="text-xs text-zinc-500">
                  {formatDateTime(entry.created_at)}
                  {entry.actor_user_id ? ` · user #${entry.actor_user_id}` : ""}
                </div>
                <div className="text-[10px] text-zinc-400">{entry.action}</div>
                <TechnicalDetails data={entry} />
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="rounded-xl border p-4 dark:border-zinc-800">
        <h3 className="mb-3 text-sm font-semibold">Происхождение текста</h3>
        {!provenance.length ? (
          <p className="text-sm text-zinc-500">Записей provenance нет</p>
        ) : (
          <ol className="space-y-3">
            {provenance.map((entry) => (
              <li key={entry.provenance_id} className="rounded-lg border px-3 py-2 dark:border-zinc-700">
                <div className="text-sm font-medium">{provenanceActionLabel(entry.action)}</div>
                <div className="text-xs text-zinc-500">
                  {formatDateTime(entry.created_at)} · {entry.locale.toUpperCase()} · block #{entry.draft_block_id}
                </div>
                <div className="text-[10px] text-zinc-400">{entry.action}</div>
                <TechnicalDetails data={entry} />
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
