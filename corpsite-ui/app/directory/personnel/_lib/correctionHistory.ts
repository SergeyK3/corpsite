import type { EmployeeEventDTO } from "../../employees/_lib/types";

export type CorrectionLabelMaps = {
  orgUnits: Map<number, string>;
  positions: Map<number, string>;
};

const FIELD_LABELS: Record<string, string> = {
  full_name: "ФИО",
  org_unit_id: "Подразделение",
  position_id: "Должность",
  employment_rate: "Ставка",
  date_from: "Дата начала",
  date_to: "Дата окончания",
};

function formatCorrectionScalar(
  field: string,
  value: unknown,
  maps: CorrectionLabelMaps,
): string {
  if (value == null || value === "") return "—";

  if (field === "org_unit_id") {
    const id = Number(value);
    if (Number.isFinite(id) && id > 0) {
      return maps.orgUnits.get(id) ?? `#${id}`;
    }
  }

  if (field === "position_id") {
    const id = Number(value);
    if (Number.isFinite(id) && id > 0) {
      return maps.positions.get(id) ?? `#${id}`;
    }
  }

  if (field === "employment_rate") {
    const num = Number(value);
    if (Number.isFinite(num)) return String(num);
  }

  if (field === "date_from" || field === "date_to") {
    const raw = String(value).trim();
    if (!raw) return "—";
    const dt = new Date(raw);
    if (!Number.isNaN(dt.getTime())) return dt.toLocaleDateString("ru-RU");
    return raw;
  }

  return String(value);
}

export function describeCorrectionEvent(
  event: EmployeeEventDTO,
  maps: CorrectionLabelMaps,
): string[] {
  const metadata = event.metadata;
  if (!metadata || typeof metadata !== "object") {
    return ["Исправление данных"];
  }

  const reason = String(metadata.reason ?? "").trim();
  const changesRaw = metadata.changes;
  const lines: string[] = [];

  if (changesRaw && typeof changesRaw === "object" && !Array.isArray(changesRaw)) {
    for (const [field, delta] of Object.entries(changesRaw)) {
      if (!delta || typeof delta !== "object" || Array.isArray(delta)) continue;
      const fromVal = (delta as { from?: unknown }).from;
      const toVal = (delta as { to?: unknown }).to;
      const label = FIELD_LABELS[field] ?? field;
      lines.push(
        `${label}: ${formatCorrectionScalar(field, fromVal, maps)} → ${formatCorrectionScalar(field, toVal, maps)}`,
      );
    }
  }

  if (reason) {
    lines.push(`Причина: ${reason}`);
  }

  if (event.comment) {
    lines.push(`Комментарий: ${event.comment}`);
  }

  if (lines.length === 0) {
    return ["Исправление данных"];
  }

  return lines;
}

export function correctionDomainLabel(event: EmployeeEventDTO): string | null {
  const domain = String(event.metadata?.domain ?? "").trim().toLowerCase();
  if (domain === "general") return "Исправление общих сведений";
  if (domain === "assignment") return "Исправление назначения";
  return null;
}
