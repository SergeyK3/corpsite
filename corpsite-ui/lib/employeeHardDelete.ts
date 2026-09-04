import type { MeInfo } from "./types";

/**
 * Legacy hard-delete is unconditionally disabled in the web application.
 * There is no environment- or capability-controlled escape hatch.
 */
export function canHardDeleteEmployee(me: MeInfo | null | undefined): boolean {
  void me;
  return false;
}
