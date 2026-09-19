const UUID_V4_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isIntakeRecordId(value: unknown): value is string {
  return typeof value === "string" && UUID_V4_PATTERN.test(value);
}

/** Creates an RFC 4122 v4 identifier for a new repeatable intake row. */
export function createIntakeRecordId(): string {
  return crypto.randomUUID();
}

/** Preserves an existing valid id; legacy or malformed identifiers are upgraded once on normalization. */
export function normalizeIntakeRecordId(value: unknown): string {
  return isIntakeRecordId(value) ? value : createIntakeRecordId();
}
