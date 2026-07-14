"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { getPositions, listEmployeeEvents, mapApiErrorToMessage } from "../../employees/_lib/api.client";
import type { EmployeeEventDTO } from "../../employees/_lib/types";
import { getOrgUnitsTree, type TreeNode } from "../../org-units/_lib/api.client";
import {
  buildPersonnelOrdersHref,
  formatPersonnelOrderDate,
  personnelOrderStatusLabel,
} from "../_lib/personnelOrdersApi.client";
import {
  correctionDomainLabel,
  describeCorrectionEvent,
} from "../_lib/correctionHistory";

type Props = {
  employeeId: string;
  refreshToken?: number;
};

type LabelMaps = {
  orgUnits: Map<number, string>;
  positions: Map<number, string>;
};

type PeriodGroup = {
  periodKey: string;
  periodLabel: string;
  events: EmployeeEventDTO[];
};

const EVENT_TYPE_META: Record<string, { label: string; badgeClass: string }> = {
  HIRE: {
    label: "Приём",
    badgeClass: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-200",
  },
  TRANSFER: {
    label: "Перевод",
    badgeClass: "bg-blue-100 text-blue-900 dark:bg-blue-950/50 dark:text-blue-200",
  },
  POSITION_CHANGE: {
    label: "Смена должности",
    badgeClass: "bg-violet-100 text-violet-900 dark:bg-violet-950/50 dark:text-violet-200",
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

  if (type === "CORRECTION") {
    return describeCorrectionEvent(event, maps).join(" · ");
  }

  if (type === "HIRE") {
    return [
      orgLabel(maps, event.to_org_unit_id),
      positionLabel(maps, event.to_position_id),
      rateLabel(event.to_rate),
    ]
      .filter(Boolean)
      .join(" · ");
  }

  if (type === "TERMINATION") {
    const parts = [
      orgLabel(maps, event.from_org_unit_id),
      positionLabel(maps, event.from_position_id),
    ].filter((part) => part !== "—");
    return parts.length ? parts.join(" · ") : "—";
  }

  const orgPart =
    event.from_org_unit_id === event.to_org_unit_id
      ? orgLabel(maps, event.to_org_unit_id)
      : `${orgLabel(maps, event.from_org_unit_id)} → ${orgLabel(maps, event.to_org_unit_id)}`;

  const posPart =
    event.from_position_id === event.to_position_id
      ? positionLabel(maps, event.to_position_id)
      : `${positionLabel(maps, event.from_position_id)} → ${positionLabel(maps, event.to_position_id)}`;

  return [orgPart, posPart !== "—" ? posPart : null, rateLabel(event.to_rate)].filter(Boolean).join(" · ");
}

function eventTypeMeta(event: EmployeeEventDTO) {
  const fromApi = String(event.event_label ?? "").trim();
  const key = String(event.event_type || "").toUpperCase();
  const correctionLabel = key === "CORRECTION" ? correctionDomainLabel(event) : null;
  const fallback =
    EVENT_TYPE_META[key] ?? {
      label: key || "Событие",
      badgeClass: "bg-zinc-100 text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200",
    };
  return {
    label: correctionLabel || fromApi || fallback.label,
    badgeClass: fallback.badgeClass,
  };
}

function renderCorrectionDetails(event: EmployeeEventDTO, maps: LabelMaps) {
  const lines = describeCorrectionEvent(event, maps);
  return (
    <div className="mt-1 space-y-0.5 text-sm text-zinc-800 dark:text-zinc-200">
      {lines.map((line) => (
        <div key={line}>{line}</div>
      ))}
    </div>
  );
}

function periodKeyFromDate(value: string | null | undefined): string {
  const raw = String(value || "").trim();
  if (/^\d{4}-\d{2}/.test(raw)) return raw.slice(0, 7);
  return "unknown";
}

function periodLabelFromKey(key: string): string {
  if (key === "unknown") return "Без даты";
  const dt = new Date(`${key}-01T00:00:00`);
  if (Number.isNaN(dt.getTime())) return key;
  return dt.toLocaleDateString("ru-RU", { month: "long", year: "numeric" });
}

function groupEventsByPeriod(items: EmployeeEventDTO[]): PeriodGroup[] {
  const groups = new Map<string, EmployeeEventDTO[]>();
  for (const event of items) {
    const key = periodKeyFromDate(event.effective_date);
    const bucket = groups.get(key);
    if (bucket) bucket.push(event);
    else groups.set(key, [event]);
  }

  return Array.from(groups.entries()).map(([periodKey, events]) => ({
    periodKey,
    periodLabel: periodLabelFromKey(periodKey),
    events,
  }));
}

function orderLinkLabel(event: EmployeeEventDTO): string {
  if (event.order_number) {
    const datePart = event.order_date ? ` от ${formatPersonnelOrderDate(event.order_date)}` : "";
    const itemPart =
      event.order_item_number != null && event.order_item_number > 0
        ? `, п. ${event.order_item_number}`
        : "";
    return `Приказ №${event.order_number}${datePart}${itemPart}`;
  }
  if (event.order_ref) return `Приказ ${event.order_ref}`;
  if (event.order_id) return `Приказ #${event.order_id}`;
  return "Приказ";
}

function EventOrderLink({
  event,
  employeeId,
}: {
  event: EmployeeEventDTO;
  employeeId: string;
}) {
  if (event.order_id) {
    const employeeNumericId = Number(employeeId);
    const href = buildPersonnelOrdersHref({
      order_id: event.order_id,
      ...(Number.isFinite(employeeNumericId) && employeeNumericId > 0
        ? { employee_id: employeeNumericId }
        : {}),
    });
    return (
      <Link
        href={href}
        className="text-xs font-medium text-blue-700 hover:underline dark:text-blue-300"
      >
        {orderLinkLabel(event)}
      </Link>
    );
  }

  if (event.order_ref) {
    return <span className="text-xs text-zinc-500 dark:text-zinc-400">приказ {event.order_ref}</span>;
  }

  return null;
}

function lifecycleBadge(status: string | null | undefined) {
  const normalized = String(status || "APPROVED").trim().toUpperCase();
  if (normalized === "APPROVED") return null;
  if (normalized === "VOIDED") {
    return (
      <span className="inline-flex rounded-md bg-zinc-200 px-2 py-0.5 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200">
        Аннулировано
      </span>
    );
  }
  return (
    <span className="inline-flex rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900 dark:bg-amber-950/50 dark:text-amber-200">
      {normalized}
    </span>
  );
}

export default function EmployeePersonnelHistorySection({ employeeId, refreshToken = 0 }: Props) {
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
        for (const position of positionItems) {
          const id = Number(
            (position as { position_id?: number; id?: number }).position_id ??
              (position as { id?: number }).id,
          );
          if (!Number.isFinite(id) || id <= 0) continue;
          const name = String((position as { name?: string }).name ?? `#${id}`).trim();
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
        const body = await listEmployeeEvents(employeeId, { limit: 100, offset: 0 });
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

  const groups = useMemo(() => groupEventsByPeriod(items), [items]);
  const linkedOrderCount = useMemo(
    () => items.filter((event) => event.order_id != null).length,
    [items],
  );
  const ordersHref = buildPersonnelOrdersHref(
    Number.isFinite(Number(employeeId)) && Number(employeeId) > 0
      ? { employee_id: Number(employeeId) }
      : {},
  );

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
        {error}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
        Загрузка истории…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400">
        Кадровые события появятся после приёма, перевода, увольнения или исполнения приказа.
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="employee-personnel-history">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          {items.length === 1 ? "1 событие" : `${items.length} событий`}
          {linkedOrderCount > 0
            ? ` · ${linkedOrderCount} ${linkedOrderCount === 1 ? "с приказом" : "с приказами"}`
            : null}
        </p>
        <Link href={ordersHref} className="text-xs font-medium text-blue-700 hover:underline dark:text-blue-300">
          Журнал приказов
        </Link>
      </div>

      <div className="space-y-6">
        {groups.map((group) => (
          <section key={group.periodKey} aria-labelledby={`history-period-${group.periodKey}`}>
            <h3
              id={`history-period-${group.periodKey}`}
              className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400"
            >
              {group.periodLabel}
            </h3>
            <ol className="relative ml-2 space-y-0 border-l border-zinc-200 dark:border-zinc-800">
              {group.events.map((event) => {
                const meta = eventTypeMeta(event);
                const typeKey = String(event.event_type || "").toUpperCase();
                const isCorrection = typeKey === "CORRECTION";
                const summary = isCorrection ? null : describeEvent(event, labelMaps);
                const orderStatus = event.order_status
                  ? personnelOrderStatusLabel(event.order_status)
                  : null;

                return (
                  <li key={event.event_id} className="relative pb-5 pl-5 last:pb-0">
                    <span
                      className="absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-zinc-400 dark:border-zinc-950 dark:bg-zinc-500"
                      aria-hidden
                    />
                    <div className="rounded-xl border border-zinc-200 bg-zinc-50/80 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/40">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
                          {formatPersonnelOrderDate(event.effective_date)}
                        </span>
                        <span
                          className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${meta.badgeClass}`}
                        >
                          {meta.label}
                        </span>
                        {lifecycleBadge(event.lifecycle_status)}
                        <EventOrderLink event={event} employeeId={employeeId} />
                        {orderStatus ? (
                          <span className="text-xs text-zinc-500 dark:text-zinc-400">{orderStatus}</span>
                        ) : null}
                      </div>
                      {isCorrection ? (
                        renderCorrectionDetails(event, labelMaps)
                      ) : (
                        <div className="mt-1 text-sm text-zinc-800 dark:text-zinc-200">{summary}</div>
                      )}
                      {!isCorrection && event.comment ? (
                        <div className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">{event.comment}</div>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
        ))}
      </div>
    </div>
  );
}
