// FILE: corpsite-ui/app/directory/employees/_components/EmployeeEventsTimeline.tsx
"use client";

import { useEffect, useMemo, useState } from "react";

import { getPositions, listEmployeeEvents, mapApiErrorToMessage } from "../_lib/api.client";
import type { EmployeeEventDTO } from "../_lib/types";
import { getOrgUnitsTree, type TreeNode } from "../../org-units/_lib/api.client";

type Props = {
  employeeId: string;
  refreshToken?: number;
};

type LabelMaps = {
  orgUnits: Map<number, string>;
  positions: Map<number, string>;
};

const EVENT_TYPE_META: Record<
  string,
  { label: string; badgeClass: string }
> = {
  HIRE: {
    label: "Приём",
    badgeClass:
      "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-200",
  },
  TRANSFER: {
    label: "Перевод",
    badgeClass: "bg-blue-100 text-blue-900 dark:bg-blue-950/50 dark:text-blue-200",
  },
  POSITION_CHANGE: {
    label: "Смена должности",
    badgeClass:
      "bg-violet-100 text-violet-900 dark:bg-violet-950/50 dark:text-violet-200",
  },
  RATE_CHANGE: {
    label: "Изменение ставки",
    badgeClass: "bg-cyan-100 text-cyan-900 dark:bg-cyan-950/50 dark:text-cyan-200",
  },
  CORRECTION: {
    label: "Исправление",
    badgeClass: "bg-amber-100 text-amber-900 dark:bg-amber-950/50 dark:text-amber-200",
  },
  TERMINATION: {
    label: "Увольнение",
    badgeClass: "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200",
  },
};

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const dt = new Date(v);
  if (Number.isNaN(dt.getTime())) return String(v);
  return dt.toLocaleDateString("ru-RU");
}

function flattenOrgUnitNames(nodes: TreeNode[], out: Map<number, string>) {
  for (const node of nodes) {
    const unitId = Number(node.unit_id ?? node.id);
    if (Number.isFinite(unitId) && unitId > 0) {
      const name = String(node.name ?? node.name_ru ?? `#${unitId}`).trim();
      out.set(unitId, name || `#${unitId}`);
    }
    if (Array.isArray(node.children) && node.children.length > 0) {
      flattenOrgUnitNames(node.children, out);
    }
  }
}

function orgLabel(maps: LabelMaps, id: number | null | undefined): string {
  if (id == null) return "—";
  return maps.orgUnits.get(id) ?? `#${id}`;
}

function positionLabel(maps: LabelMaps, id: number | null | undefined): string {
  if (id == null) return "—";
  return maps.positions.get(id) ?? `#${id}`;
}

function rateLabel(rate: number | null | undefined): string | null {
  if (rate == null) return null;
  return `ставка ${rate}`;
}

function describeEvent(event: EmployeeEventDTO, maps: LabelMaps): string {
  const type = String(event.event_type || "").toUpperCase();

  if (type === "HIRE") {
    const parts = [
      orgLabel(maps, event.to_org_unit_id),
      positionLabel(maps, event.to_position_id),
      rateLabel(event.to_rate),
    ].filter(Boolean);
    return parts.join(" · ");
  }

  if (type === "TERMINATION") {
    const parts = [
      orgLabel(maps, event.from_org_unit_id),
      positionLabel(maps, event.from_position_id),
    ].filter((p) => p !== "—");
    return parts.length ? parts.join(" · ") : "—";
  }

  const orgPart =
    event.from_org_unit_id === event.to_org_unit_id
      ? orgLabel(maps, event.to_org_unit_id)
      : `${orgLabel(maps, event.from_org_unit_id)} → ${orgLabel(maps, event.to_org_unit_id)}`;

  const fromPos = event.from_position_id;
  const toPos = event.to_position_id;
  const posPart =
    fromPos === toPos
      ? positionLabel(maps, toPos)
      : `${positionLabel(maps, fromPos)} → ${positionLabel(maps, toPos)}`;

  const parts = [orgPart, posPart !== "—" ? posPart : null, rateLabel(event.to_rate)].filter(Boolean);
  return parts.join(" · ");
}

function eventTypeMeta(event: EmployeeEventDTO) {
  const fromApi = String(event.event_label ?? "").trim();
  const key = String(event.event_type || "").toUpperCase();
  const fallback =
    EVENT_TYPE_META[key] ?? {
      label: key || "Событие",
      badgeClass: "bg-zinc-100 text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200",
    };
  return {
    label: fromApi || fallback.label,
    badgeClass: fallback.badgeClass,
  };
}

export default function EmployeeEventsTimeline({ employeeId, refreshToken = 0 }: Props) {
  const [items, setItems] = useState<EmployeeEventDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [labelMaps, setLabelMaps] = useState<LabelMaps>({
    orgUnits: new Map(),
    positions: new Map(),
  });

  useEffect(() => {
    let cancelled = false;

    async function loadLabels() {
      const orgUnits = new Map<number, string>();
      const positions = new Map<number, string>();

      try {
        const tree = await getOrgUnitsTree();
        flattenOrgUnitNames(Array.isArray(tree?.items) ? tree.items : [], orgUnits);
      } catch {
        // labels fall back to #id
      }

      try {
        const rawPositions = await getPositions({ limit: 1000, offset: 0 });
        const positionItems = Array.isArray(rawPositions)
          ? rawPositions
          : Array.isArray(rawPositions?.items)
            ? rawPositions.items
            : [];
        for (const p of positionItems) {
          const id = Number((p as { position_id?: number; id?: number }).position_id ?? (p as { id?: number }).id);
          if (!Number.isFinite(id) || id <= 0) continue;
          const name = String((p as { name?: string }).name ?? `#${id}`).trim();
          positions.set(id, name || `#${id}`);
        }
      } catch {
        // labels fall back to #id
      }

      if (!cancelled) {
        setLabelMaps({ orgUnits, positions });
      }
    }

    void loadLabels();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!employeeId) {
      setItems([]);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const body = await listEmployeeEvents(employeeId, { limit: 50, offset: 0 });
        if (cancelled) return;
        setItems(Array.isArray(body.items) ? body.items : []);
      } catch (e) {
        if (cancelled) return;
        setItems([]);
        setError(mapApiErrorToMessage(e, "Не удалось загрузить кадровую историю"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [employeeId, refreshToken]);

  const totalLabel = useMemo(() => {
    if (loading) return "";
    const n = items.length;
    if (n === 0) return "Событий пока нет";
    return n === 1 ? "1 событие" : `${n} событий`;
  }, [items.length, loading]);

  return (
    <section>
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-50">Кадровая история</h3>
        {totalLabel ? (
          <span className="text-xs text-zinc-500 dark:text-zinc-400">{totalLabel}</span>
        ) : null}
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
          {error}
        </div>
      ) : loading ? (
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/40 px-4 py-3 text-sm text-zinc-600 dark:text-zinc-400">
          Загрузка истории…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/40 px-4 py-3 text-sm text-zinc-600 dark:text-zinc-400">
          Кадровые события появятся после приёма, перевода или увольнения.
        </div>
      ) : (
        <ol className="relative space-y-0 border-l border-zinc-200 dark:border-zinc-800 ml-2">
          {items.map((event) => {
            const meta = eventTypeMeta(event);
            const summary = describeEvent(event, labelMaps);

            return (
              <li key={event.event_id} className="relative pb-5 pl-5 last:pb-0">
                <span
                  className="absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white dark:border-zinc-950 bg-zinc-400 dark:bg-zinc-500"
                  aria-hidden
                />
                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/40 px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
                      {fmtDate(event.effective_date)}
                    </span>
                    <span
                      className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${meta.badgeClass}`}
                    >
                      {meta.label}
                    </span>
                    {event.order_ref ? (
                      <span className="text-xs text-zinc-500 dark:text-zinc-400">
                        приказ {event.order_ref}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-1 text-sm text-zinc-800 dark:text-zinc-200">{summary}</div>
                  {event.comment ? (
                    <div className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">{event.comment}</div>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
