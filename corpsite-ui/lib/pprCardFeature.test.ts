import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

describe("isPprCardEnabled", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubEnv("NEXT_PUBLIC_PPR_CARD_ENABLED", undefined);
    vi.stubEnv("NEXT_PUBLIC_APP_ENV", undefined);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("returns true in Next development when flag is unset", async () => {
    vi.stubEnv("NODE_ENV", "development");
    const { isPprCardEnabled: enabled } = await import("./pprCardFeature");
    expect(enabled()).toBe(true);
  });

  it("returns true in dev APP_ENV when flag is unset", async () => {
    process.env.NEXT_PUBLIC_APP_ENV = "dev";
    vi.stubEnv("NODE_ENV", "test");
    const { isPprCardEnabled: enabled } = await import("./pprCardFeature");
    expect(enabled()).toBe(true);
  });

  it("returns false in production when flag is unset", async () => {
    process.env.NEXT_PUBLIC_APP_ENV = "production";
    vi.stubEnv("NODE_ENV", "production");
    const { isPprCardEnabled: enabled } = await import("./pprCardFeature");
    expect(enabled()).toBe(false);
  });

  it("respects explicit NEXT_PUBLIC_PPR_CARD_ENABLED=true in production", async () => {
    process.env.NEXT_PUBLIC_APP_ENV = "production";
    vi.stubEnv("NODE_ENV", "production");
    process.env.NEXT_PUBLIC_PPR_CARD_ENABLED = "true";
    const { isPprCardEnabled: enabled } = await import("./pprCardFeature");
    expect(enabled()).toBe(true);
  });

  it("respects explicit NEXT_PUBLIC_PPR_CARD_ENABLED=false in development", async () => {
    vi.stubEnv("NODE_ENV", "development");
    process.env.NEXT_PUBLIC_PPR_CARD_ENABLED = "false";
    const { isPprCardEnabled: enabled } = await import("./pprCardFeature");
    expect(enabled()).toBe(false);
  });
});

describe("isPprCardEnabled (static import)", () => {
  it("is exported", async () => {
    const { isPprCardEnabled } = await import("./pprCardFeature");
    expect(typeof isPprCardEnabled).toBe("function");
  });
});
