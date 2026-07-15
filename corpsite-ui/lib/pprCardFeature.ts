/** Feature gate for PPR «Личная карточка» UI read migration (R9 v1). */

function appEnv(): string {
  return (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
}

function truthy(name: string): boolean {
  const v = (process.env[name] || "").trim().toLowerCase();
  return v === "1" || v === "true" || v === "yes" || v === "on";
}

/**
 * When true: «Открыть» navigates to PPR card; card page uses `/api/ppr/*`.
 * Default ON in dev, OFF in production unless explicitly enabled.
 */
export function isPprCardEnabled(): boolean {
  const explicit = process.env.NEXT_PUBLIC_PPR_CARD_ENABLED;
  if (explicit !== undefined && explicit.trim() !== "") {
    return truthy("NEXT_PUBLIC_PPR_CARD_ENABLED");
  }
  const env = appEnv();
  return env !== "prod" && env !== "production";
}
