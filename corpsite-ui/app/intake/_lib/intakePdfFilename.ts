/** Sanitize applicant name for ASCII Content-Disposition filename. */
export function sanitizeIntakePdfFilenamePart(value: string): string {
  const asciiLookalikes = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[кқ]/gi, "k")
    .replace(/[аә]/gi, "a")
    .replace(/[оө]/gi, "o")
    .replace(/[уұү]/gi, "u")
    .replace(/[иі]/gi, "i")
    .replace(/[её]/gi, "e")
    .replace(/[с]/gi, "s")
    .replace(/[р]/gi, "r")
    .replace(/[т]/gi, "t")
    .replace(/[нң]/gi, "n")
    .replace(/[м]/gi, "m")
    .replace(/[п]/gi, "p")
    .replace(/[б]/gi, "b")
    .replace(/[в]/gi, "v")
    .replace(/[гғ]/gi, "g")
    .replace(/[д]/gi, "d")
    .replace(/[з]/gi, "z")
    .replace(/[й]/gi, "y")
    .replace(/[хһ]/gi, "h")
    .replace(/[ц]/gi, "c")
    .replace(/[ч]/gi, "ch")
    .replace(/[ш]/gi, "sh")
    .replace(/[щ]/gi, "sch")
    .replace(/[ы]/gi, "y")
    .replace(/[ьъ]/gi, "")
    .replace(/[э]/gi, "e")
    .replace(/[ю]/gi, "yu")
    .replace(/[я]/gi, "ya")
    .replace(/[жҗ]/gi, "zh")
    .replace(/[л]/gi, "l")
    .replace(/[ф]/gi, "f");

  return asciiLookalikes
    .replace(/[^0-9a-z._-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80);
}

export function buildIntakePdfFilename(applicationId: number, fullName: string): string {
  const namePart = sanitizeIntakePdfFilenamePart(fullName) || "anketa";
  return `anketa-${applicationId}-${namePart}.pdf`;
}

export function buildIntakePdfContentDisposition(filename: string): string {
  const safe = filename.replace(/["\r\n]/g, "_");
  if (/^[ -~]+$/.test(safe)) return `inline; filename="${safe}"`;
  const encoded = encodeURIComponent(safe).replace(/['()*]/g, (character) =>
    `%${character.charCodeAt(0).toString(16).toUpperCase()}`,
  );
  return `inline; filename="personal-card.pdf"; filename*=UTF-8''${encoded}`;
}

export function buildIntakePdfHrefByToken(token: string): string {
  return `/intake/${encodeURIComponent(token)}/pdf`;
}

export function buildIntakePdfHrefByApplicationId(applicationId: number): string {
  return `/directory/personnel-applications/${applicationId}/intake/pdf`;
}

export function filenameFromContentDisposition(value: string | null, fallback: string): string {
  if (!value) return fallback;
  const utf8 = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const quoted = value.match(/filename="([^"\\]*(?:\\.[^"\\]*)*)"/i)?.[1];
  const plain = value.match(/filename=([^;]+)/i)?.[1];
  let decoded = "";
  if (utf8) {
    try {
      decoded = decodeURIComponent(utf8);
    } catch {
      decoded = "";
    }
  }
  const candidate = decoded || (quoted ?? plain ?? "").trim();
  // A response header must not be able to choose a path or an empty browser filename.
  const safe = candidate.replace(/[\\/:*?"<>|\x00-\x1F]/g, "_").trim();
  return safe || fallback;
}
