import { describe, expect, it } from "vitest";
import { candidateIntakePublicUrl } from "./candidateIntakePublicUrl";

describe("candidateIntakePublicUrl", () => {
  it("uses the public origin of the same stand for a candidate link", () => {
    expect(candidateIntakePublicUrl("/intake/token-123", "https://test.mmc.004.kz", "http://127.0.0.1:3000"))
      .toBe("https://test.mmc.004.kz/intake/token-123");
    expect(candidateIntakePublicUrl("/intake/token-123", undefined, "https://test.mmc.004.kz"))
      .toBe("https://test.mmc.004.kz/intake/token-123");
  });

  it("uses the current loopback origin on a local stand", () => {
    expect(candidateIntakePublicUrl("/intake/token-123", undefined, "http://127.0.0.1:3000"))
      .toBe("http://127.0.0.1:3000/intake/token-123");
  });

  it("rejects configured loopback and malformed links", () => {
    expect(candidateIntakePublicUrl("/intake/token-123", "http://localhost:3000", "https://test.mmc.004.kz")).toBeNull();
    expect(candidateIntakePublicUrl("/intake/token-123", "https://test.mmc.004.kz/other", undefined)).toBeNull();
    expect(candidateIntakePublicUrl("https://evil.example/intake/token-123", "https://test.mmc.004.kz", undefined)).toBeNull();
  });
});
