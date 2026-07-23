import { describe, expect, it } from "vitest";

import { emptyIntakeDraftPayload } from "./intakeApi.client";
import { canonicalizeIntakePayloadForCompare, intakePayloadsEqual } from "./intakePayloadCompare";

describe("intakePayloadCompare", () => {
  it("detects military and employment biography differences", () => {
    const baseline = emptyIntakeDraftPayload();
    baseline.employment_biography = [
      {
        organization: "Клиника А",
        position: "Медсестра",
        year_from: "2020",
        year_to: "2024",
        reason_for_leaving: "Переезд",
      },
    ];
    baseline.military.composition = "soldiers";

    const edited = structuredClone(baseline);
    edited.employment_biography[0].organization = "Клиника Б";
    edited.military.status = "В запасе";
    edited.military.rank = "Сержант";
    edited.current_step = "review";

    expect(intakePayloadsEqual(baseline, edited)).toBe(false);
    expect(canonicalizeIntakePayloadForCompare(baseline).employment_biography[0].organization).toBe(
      "Клиника А",
    );
    expect(canonicalizeIntakePayloadForCompare(edited).military.rank).toBe("Сержант");
  });

  it("ignores current_step-only navigation changes", () => {
    const left = emptyIntakeDraftPayload();
    const right = structuredClone(left);
    left.current_step = "employment_biography";
    right.current_step = "review";
    expect(intakePayloadsEqual(left, right)).toBe(true);
  });
});
