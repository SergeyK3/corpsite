import { describe, expect, it } from "vitest";

import {
  addCalendarMonths,
  addCalendarYears,
  calculateExpiringCertificates,
  calculateTrainingHoursLast5y,
  trainingSummaryRecordFromIntakeEntry,
  trainingWindowStart,
  type TrainingSummaryRecord,
} from "./trainingSummary";

const AS_OF = "2026-06-16";

function record(partial: Partial<TrainingSummaryRecord> = {}): TrainingSummaryRecord {
  return {
    title: "Course",
    completedAt: "2024-01-10",
    hours: 16,
    documentType: "certificate",
    lifecycleStatus: "ACTIVE",
    ...partial,
  };
}

describe("trainingSummary", () => {
  it("matches rolling five-year window boundaries", () => {
    expect(trainingWindowStart(AS_OF)).toBe("2021-06-16");
    expect(
      calculateTrainingHoursLast5y(
        [
          record({ completedAt: "2021-06-16", hours: 40 }),
          record({ completedAt: "2021-06-15", hours: 99 }),
          record({ completedAt: "2026-07-01", hours: 10 }),
          record({ completedAt: "2025-01-01", hours: null }),
          record({ lifecycleStatus: "VOIDED", completedAt: "2025-02-01", hours: 8 }),
        ],
        AS_OF,
      ),
    ).toEqual({
      asOf: AS_OF,
      windowStart: "2021-06-16",
      trainingHoursLast5y: 40,
      qualifyingRecordsCount: 1,
    });
  });

  it("derives intake records with reconciled hours", () => {
    const summaryRecord = trainingSummaryRecordFromIntakeEntry({
      institution: "Org",
      course_name: "Safety",
      year_from: "2021-03-10",
      year_to: "2021-03-12",
      document_type: "certificate",
      document_number: "",
      hours: "",
      hours_is_manual: false,
    });

    expect(summaryRecord.hours).toBe(24);
    expect(summaryRecord.completedAt).toBe("2021-03-12");
  });

  it("lists only active certificates expiring within six months", () => {
    const completedAt = addCalendarMonths(addCalendarYears(AS_OF, -5), 3);
    const expiring = calculateExpiringCertificates(
      [
        record({ title: "Soon", completedAt, documentType: "certificate" }),
        record({ title: "Witness", completedAt, documentType: "witness" }),
        record({ title: "", completedAt, documentType: "certificate" }),
      ],
      AS_OF,
    );

    expect(expiring).toHaveLength(1);
    expect(expiring[0]?.title).toBe("Soon");
    expect(expiring[0]?.expiresAt).toBe(addCalendarYears(completedAt, 5));
    expect(expiring[0]?.daysRemaining).toBeGreaterThan(0);
  });

  it("excludes expired and distant certificates and incomplete records", () => {
    const expiredCompleted = addCalendarYears(AS_OF, -6);
    const distantCompleted = addCalendarYears(addCalendarMonths(AS_OF, -7), -5);

    expect(
      calculateExpiringCertificates(
        [
          record({ title: "Expired", completedAt: expiredCompleted }),
          record({ title: "Later", completedAt: distantCompleted }),
          record({ title: "Missing date", completedAt: null }),
        ],
        AS_OF,
      ),
    ).toEqual([]);
  });

  it("returns zero hours for empty datasets", () => {
    expect(calculateTrainingHoursLast5y([], AS_OF).trainingHoursLast5y).toBe(0);
    expect(calculateExpiringCertificates([], AS_OF)).toEqual([]);
  });
});
