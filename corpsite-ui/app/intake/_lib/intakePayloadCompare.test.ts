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

  it("canonicalizes typed personal section with stable keys and empty defaults", () => {
    const payload = emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.personal.first_name = "Пётр";
    payload.personal.birth_date = "1990-05-20";

    const canonical = canonicalizeIntakePayloadForCompare(payload);

    expect(canonical.personal).toEqual({
      last_name: "Петров",
      first_name: "Пётр",
      middle_name: "",
      birth_date: "1990-05-20",
      birth_place: "",
      gender: "",
      citizenship: "",
      nationality: "",
    });
    expect(Object.keys(canonical.personal)).toEqual([
      "last_name",
      "first_name",
      "middle_name",
      "birth_date",
      "birth_place",
      "gender",
      "citizenship",
      "nationality",
    ]);
  });

  it("treats equivalent payloads as equal after scalar normalization", () => {
    const left = emptyIntakeDraftPayload();
    left.personal.last_name = "Петров";
    left.contacts.email = "petrov@example.com";

    const right = structuredClone(left);
    right.personal = { ...left.personal, middle_name: "" };
    right.contacts = { ...left.contacts, mobile_phone: "" };

    expect(intakePayloadsEqual(left, right)).toBe(true);
  });
});
