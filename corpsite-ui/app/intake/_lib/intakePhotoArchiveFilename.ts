/** Human-readable archive/export filename for intake photos (Cyrillic kept). */

const FORBIDDEN_CHARS_RE = /[\\/:*?"<>|\u0000-\u001f]+/g;
const WHITESPACE_RE = /\s+/g;
const MULTI_UNDERSCORE_RE = /_+/g;

export function sanitizeIntakePhotoArchivePart(value: string | null | undefined): string {
  const text = String(value ?? "")
    .trim()
    .replace(FORBIDDEN_CHARS_RE, "")
    .replace(WHITESPACE_RE, "_")
    .replace(MULTI_UNDERSCORE_RE, "_")
    .replace(/^[._]+|[._]+$/g, "");
  return text;
}

export function buildIntakePhotoArchiveFilename(input: {
  lastName?: string | null;
  firstName?: string | null;
  applicationId: number;
  personnelNumber?: string | null;
}): string {
  const surname = sanitizeIntakePhotoArchivePart(input.lastName) || "БезФамилии";
  const name = sanitizeIntakePhotoArchivePart(input.firstName) || "БезИмени";
  const number = sanitizeIntakePhotoArchivePart(input.personnelNumber);
  const suffix = number || String(Math.trunc(input.applicationId));
  return `${surname}_${name}_${suffix}.jpg`;
}
