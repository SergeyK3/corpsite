import { describe, expect, it } from "vitest";

import { validateIntakePhotoSourceFile } from "./intakePhotoValidation";
import { INTAKE_PHOTO_SOURCE_MAX_BYTES } from "./intakePhotoTypes";

function makeFile(type: string, size: number, name = "photo.jpg"): File {
  const content = new Uint8Array(size);
  return new File([content], name, { type });
}

describe("validateIntakePhotoSourceFile", () => {
  it("accepts jpeg, png and heic within 10 MB", () => {
    expect(validateIntakePhotoSourceFile(makeFile("image/jpeg", 1024))).toBeNull();
    expect(validateIntakePhotoSourceFile(makeFile("image/png", 1024, "photo.png"))).toBeNull();
    expect(validateIntakePhotoSourceFile(makeFile("image/heic", 1024, "photo.heic"))).toBeNull();
  });

  it("rejects unsupported types", () => {
    expect(validateIntakePhotoSourceFile(makeFile("image/svg+xml", 1024, "photo.svg"))).toMatch(
      /JPEG, PNG или HEIC/i,
    );
    expect(validateIntakePhotoSourceFile(makeFile("application/pdf", 1024, "photo.pdf"))).toMatch(
      /JPEG, PNG или HEIC/i,
    );
  });

  it("rejects empty and oversized files", () => {
    expect(validateIntakePhotoSourceFile(makeFile("image/jpeg", 0))).toMatch(/пуст/i);
    expect(
      validateIntakePhotoSourceFile(makeFile("image/jpeg", INTAKE_PHOTO_SOURCE_MAX_BYTES + 1)),
    ).toMatch(/10 МБ/i);
  });
});
