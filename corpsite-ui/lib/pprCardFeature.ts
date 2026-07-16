/** Feature gate for PPR «Личная карточка» UI read migration (R9 v1). */

function appEnv(): string {
  return (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
}

function truthy(name: string): boolean {
  const v = (process.env[name] || "").trim().toLowerCase();
  return v === "1" || v === "true" || v === "yes" || v === "on";
}

function falsy(name: string): boolean {
  const v = (process.env[name] || "").trim().toLowerCase();
  return v === "0" || v === "false" || v === "no" || v === "off";
}

function isProductionEnv(): boolean {
  const env = appEnv();
  return env === "prod" || env === "production";
}

/**
 * When true: «Открыть» navigates to PPR card; card page uses `/api/ppr/*`.
 * Explicit NEXT_PUBLIC_PPR_CARD_ENABLED overrides defaults.
 * Default ON in local Next dev and non-production APP_ENV.
 */
export function isPprCardEnabled(): boolean {
  const explicit = process.env.NEXT_PUBLIC_PPR_CARD_ENABLED;
  if (explicit !== undefined && explicit.trim() !== "") {
    if (falsy("NEXT_PUBLIC_PPR_CARD_ENABLED")) return false;
    return truthy("NEXT_PUBLIC_PPR_CARD_ENABLED");
  }
  if (process.env.NODE_ENV === "development") return true;
  return !isProductionEnv();
}

/** Staff list route used as return target from the personal card. */
export const PPR_CARD_RETURN_HREF = "/directory/staff";
