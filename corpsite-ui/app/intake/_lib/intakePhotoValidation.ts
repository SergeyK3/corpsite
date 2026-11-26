import { INTAKE_PHOTO_SOURCE_MAX_BYTES } from "./intakePhotoTypes";

const ALLOWED_SOURCE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/heic",
  "image/heif",
]);

export function validateIntakePhotoSourceFile(file: File): string | null {
  const type = String(file.type || "").trim().toLowerCase();
  if (!ALLOWED_SOURCE_TYPES.has(type) && !(type === "" && /\.(jpe?g|png|heic|heif)$/i.test(file.name))) {
    return "Неподдерживаемый формат файла. Выберите фото JPEG, PNG или HEIC.";
  }
  if (file.size <= 0) {
    return "Файл пустой. Выберите другое фото.";
  }
  if (file.size > INTAKE_PHOTO_SOURCE_MAX_BYTES) {
    return "Файл больше 10 МБ. Выберите фото меньшего размера.";
  }
  return null;
}
