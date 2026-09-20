/**
 * Presentation-only helpers for the employee's operational assignment.
 * The API values remain canonical; these functions never feed a write path.
 */
const STATUS_LABELS: Record<string, string> = {
  active: "Работает",
};

export function displayOperationalStatus(value: string | null): string | null {
  if (value === null) return null;
  return STATUS_LABELS[value] ?? value;
}

export function displayEmploymentRate(value: number | null): string | null {
  if (value === null || !Number.isFinite(value)) return null;
  return value.toFixed(2);
}
