import { describe, expect, it } from "vitest";

import { formatMrdEntryLabel, formatMrdRecordKindLabel } from "./mrdEntryDisplay";

describe("mrdEntryDisplay", () => {
  it("prefers full_name from payload", () => {
    expect(
      formatMrdEntryLabel({
        entry_id: 1,
        match_key: "emp:1",
        entity_scope: "emp:1",
        record_kind: "roster",
        effective_payload: { full_name: "Иванов И.И.", position_raw: "Медсестра" },
      }),
    ).toBe("Иванов И.И.");
  });

  it("falls back to match_key", () => {
    expect(
      formatMrdEntryLabel({
        entry_id: 2,
        match_key: "emp:2",
        entity_scope: "emp:2",
        record_kind: "roster",
        effective_payload: {},
      }),
    ).toBe("emp:2");
  });

  it("formats record kind labels", () => {
    expect(formatMrdRecordKindLabel("roster")).toBe("Состав");
    expect(formatMrdRecordKindLabel("education")).toBe("Образование");
  });
});
