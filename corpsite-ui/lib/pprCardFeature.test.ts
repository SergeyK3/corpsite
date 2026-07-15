import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { isPprCardEnabled } from "./pprCardFeature";

describe("isPprCardEnabled", () => {
  const env = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...env };
    delete process.env.NEXT_PUBLIC_PPR_CARD_ENABLED;
    delete process.env.NEXT_PUBLIC_APP_ENV;
  });

  afterEach(() => {
    process.env = env;
  });

  it("returns true in dev when flag is unset", async () => {
    process.env.NEXT_PUBLIC_APP_ENV = "dev";
    const { isPprCardEnabled: enabled } = await import("./pprCardFeature");
    expect(enabled()).toBe(true);
  });

  it("returns false in production when flag is unset", async () => {
    process.env.NEXT_PUBLIC_APP_ENV = "production";
    const { isPprCardEnabled: enabled } = await import("./pprCardFeature");
    expect(enabled()).toBe(false);
  });

  it("respects explicit NEXT_PUBLIC_PPR_CARD_ENABLED=true in production", async () => {
    process.env.NEXT_PUBLIC_APP_ENV = "production";
    process.env.NEXT_PUBLIC_PPR_CARD_ENABLED = "true";
    const { isPprCardEnabled: enabled } = await import("./pprCardFeature");
    expect(enabled()).toBe(true);
  });

  it("respects explicit NEXT_PUBLIC_PPR_CARD_ENABLED=false in dev", async () => {
    process.env.NEXT_PUBLIC_APP_ENV = "dev";
    process.env.NEXT_PUBLIC_PPR_CARD_ENABLED = "false";
    const { isPprCardEnabled: enabled } = await import("./pprCardFeature");
    expect(enabled()).toBe(false);
  });
});

describe("isPprCardEnabled (static import)", () => {
  it("is exported", () => {
    expect(typeof isPprCardEnabled).toBe("function");
  });
});
