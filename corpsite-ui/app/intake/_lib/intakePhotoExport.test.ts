import { describe, expect, it } from "vitest";

import { createDefaultIntakePhotoCropState } from "./intakePhotoTypes";
import { exportIntakePhotoJpeg } from "./intakePhotoExport";

describe("exportIntakePhotoJpeg", () => {
  it("throws when image dimensions are unavailable", async () => {
    const image = {
      naturalWidth: 0,
      naturalHeight: 0,
    } as HTMLImageElement;

    await expect(
      exportIntakePhotoJpeg(image, createDefaultIntakePhotoCropState(), 300, 400),
    ).rejects.toThrow(/прочитать изображение/i);
  });
});
