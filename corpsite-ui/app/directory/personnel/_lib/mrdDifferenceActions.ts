/**
 * Planned API contracts for difference decisions (foundation — not wired yet).
 * Confirm/reject must go through backend commands, not local optimistic UI state.
 */
export type ConfirmDifferencePayload = {
  command_id: string;
  difference_id: number;
  expected_row_version: number;
  basis?: string | null;
};

export type ModifyAndConfirmDifferencePayload = ConfirmDifferencePayload & {
  corrected_new_value: unknown;
};

export type RejectDifferencePayload = {
  command_id: string;
  difference_id: number;
  expected_row_version: number;
  basis?: string | null;
};

export const DIFFERENCE_ACTIONS_FOUNDATION_NOTE =
  "Сохранение решений будет доступно на следующем этапе после подключения команд подтверждения и отклонения.";
