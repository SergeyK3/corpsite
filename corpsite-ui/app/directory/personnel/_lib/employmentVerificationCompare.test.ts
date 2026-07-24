import { describe, expect, it } from "vitest";

import {
  buildEmploymentCompareRows,
  summarizeEmploymentRecord,
} from "./employmentVerificationCompare";
import type { EmploymentRecordSnapshot } from "./personnelVerificationApi.client";

function snapshot(
  overrides: Partial<EmploymentRecordSnapshot> = {},
): EmploymentRecordSnapshot {
  return {
    employment_id: 1,
    record_kind: "episode",
    employer_name: "Клиника А",
    department_name: "Терапия",
    position_title: "Врач",
    employment_type: null,
    started_at: "2020-01-01",
    ended_at: null,
    termination_reason: null,
    document_reference: null,
    notes: null,
    lifecycle_status: "active",
    updated_at: "2026-07-24T10:00:00+00:00",
    ...overrides,
  };
}

describe("employmentVerificationCompare", () => {
  it("summarizes employer and position for queue rows", () => {
    expect(summarizeEmploymentRecord(snapshot())).toBe("Клиника А — Врач");
  });

  it("marks only changed fields between prior and revision", () => {
    const rows = buildEmploymentCompareRows(
      snapshot(),
      snapshot({
        employment_id: 2,
        employer_name: "Клиника Б",
        position_title: "Хирург",
        department_name: "Терапия",
      }),
    );
    const byKey = Object.fromEntries(rows.map((row) => [row.key, row]));
    expect(byKey.employer_name.changed).toBe(true);
    expect(byKey.position_title.changed).toBe(true);
    expect(byKey.department_name.changed).toBe(false);
    expect(byKey.employer_name.priorValue).toBe("Клиника А");
    expect(byKey.employer_name.revisionValue).toBe("Клиника Б");
  });
});
