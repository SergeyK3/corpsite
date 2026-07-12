export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("ru-RU");
}

export function formatPartyReference(type: string, reference: string, displayName?: string | null): string {
  if (displayName?.trim()) return displayName.trim();
  return `${type}: ${reference}`;
}

export function languageCoverageLabel(ruPresent?: boolean | null, kkPresent?: boolean | null): string {
  const parts: string[] = [];
  if (ruPresent) parts.push("RU");
  if (kkPresent) parts.push("KK");
  return parts.length ? parts.join(" / ") : "—";
}

export function fingerprintShort(value: string | null | undefined): string {
  if (!value) return "—";
  return value.length > 12 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;
}
