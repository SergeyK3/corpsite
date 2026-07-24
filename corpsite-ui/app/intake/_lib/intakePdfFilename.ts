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
  return `inline; filename="${safe}"`;
}

export function buildIntakePdfHrefByToken(token: string): string {
  return `/intake/${encodeURIComponent(token)}/pdf`;
}

export function buildIntakePdfHrefByApplicationId(applicationId: number): string {
  return `/directory/personnel-applications/${applicationId}/intake/pdf`;
}
