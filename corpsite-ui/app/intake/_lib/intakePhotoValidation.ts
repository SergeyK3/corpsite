import { INTAKE_PHOTO_SOURCE_MAX_BYTES } from "./intakePhotoTypes";

const ALLOWED_SOURCE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/heic",
  "image/heif",
]);

export function validateIntakePhotoSourceFile(file: File): string | null {
  const type = String(file.type || "").trim().toLowerCase();
  if (!ALLOWED_SOURCE_TYPES.has(type)) {
    return "Допустимы только JPEG, PNG или HEIC до 10 МБ.";
  }
  if (file.size <= 0) {
    return "Файл пустой.";
  }
  if (file.size > INTAKE_PHOTO_SOURCE_MAX_BYTES) {
    return "Размер файла не должен превышать 10 МБ.";
  }
  return null;
}
