"use client";
import * as React from "react";
import { getPositions } from "@/app/directory/employees/_lib/api.client";
import type { Position } from "@/app/directory/employees/_lib/types";

export type DocumentPosition = Position & { id: number; name: string };

export async function loadPersonnelOrderPositions(): Promise<DocumentPosition[]> {
  const rows = new Map<number, DocumentPosition>();
  const limit = 1000;
  for (let offset = 0; ; offset += limit) {
    // Document wording is independent of employment/allowed-position scopes.
    const response = await getPositions({ limit, offset });
    const page = Array.isArray(response?.items) ? response.items : [];
    for (const row of page) {
      const id = Number(row.position_id ?? row.id);
      if (!Number.isInteger(id) || id <= 0 || !String(row.name || "").trim()) continue;
      rows.set(id, { ...row, id, name: String(row.name),
        name_kk: row.translation_status === "needs_review" ? null : row.name_kk,
        document_possessive_kk: row.document_form_status === "needs_review" ? null : row.document_possessive_kk,
      });
    }
    if (page.length < limit || (Number.isFinite(response?.total) && offset + page.length >= response.total)) break;
    if (offset >= 100000) throw new Error("Не удалось полностью загрузить справочник должностей.");
  }
  return [...rows.values()];
}

export function usePersonnelOrderPositions(enabled: boolean) {
  const [positions, setPositions] = React.useState<DocumentPosition[]>([]);
  const [error, setError] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  React.useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setLoading(true); setError(false);
    void loadPersonnelOrderPositions().then(items => { if (!cancelled) setPositions(items); })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [enabled]);
  return {positions, error, loading};
}
