import { describe, expect, it } from "vitest";

import {
  buildIntakePhotoArchiveFilename,
  sanitizeIntakePhotoArchivePart,
} from "./intakePhotoArchiveFilename";

describe("intakePhotoArchiveFilename", () => {
  it("keeps Cyrillic and uses personnel number when present", () => {
    expect(
      buildIntakePhotoArchiveFilename({
        lastName: "Иванов",
        firstName: "Иван",
        applicationId: 100,
        personnelNumber: "ТН-0042",
      }),
    ).toBe("Иванов_Иван_ТН-0042.jpg");
  });

  it("falls back to application_id when personnel number is missing", () => {
    expect(
      buildIntakePhotoArchiveFilename({
        lastName: "Петров",
        firstName: "Пётр",
        applicationId: 55,
        personnelNumber: "",
      }),
    ).toBe("Петров_Пётр_55.jpg");
  });

  it("distinguishes homonyms by personnel number or application id", () => {
    const a = buildIntakePhotoArchiveFilename({
      lastName: "Иванов",
      firstName: "Иван",
      applicationId: 10,
    });
    const b = buildIntakePhotoArchiveFilename({
      lastName: "Иванов",
      firstName: "Иван",
      applicationId: 11,
    });
    expect(a).toBe("Иванов_Иван_10.jpg");
    expect(b).toBe("Иванов_Иван_11.jpg");
    expect(a).not.toBe(b);
  });

  it("strips forbidden filesystem characters", () => {
    expect(sanitizeIntakePhotoArchivePart('Ива/нов:"*?<>|')).toBe("Иванов");
    expect(
      buildIntakePhotoArchiveFilename({
        lastName: "Смирнов\\Тест",
        firstName: "Алекс*",
        applicationId: 9,
        personnelNumber: "12:34",
      }),
    ).toBe("СмирновТест_Алекс_1234.jpg");
  });
});
