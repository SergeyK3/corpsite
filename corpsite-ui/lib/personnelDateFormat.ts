export type PersonnelDatePrecision = "day" | "month" | "year" | "auto";

export type FormatPersonnelDateOptions = {
  precision?: PersonnelDatePrecision;
  empty?: string;
};

const ISO_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const ISO_MONTH_RE = /^(\d{4})-(\d{2})$/;
const YEAR_RE = /^\d{4}$/;
const RU_DATE_RE = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/;
const RU_MONTH_RE = /^(\d{1,2})\.(\d{4})$/;

type DateParts = { year: string; month: string; day: string };

function pad2(value: string | number): string {
  return String(value).padStart(2, "0");
}

function formatRuDay(year: string, month: string, day: string): string {
  return `${pad2(day)}.${pad2(month)}.${year}`;
}

function formatRuMonth(year: string, month: string): string {
  return `${pad2(month)}.${year}`;
}

function parsePersonnelDateParts(text: string): DateParts | null {
  if (YEAR_RE.test(text)) {
    return { year: text, month: "01", day: "01" };
  }

  const ruMonth = RU_MONTH_RE.exec(text);
  if (ruMonth) {
    return { year: ruMonth[2], month: ruMonth[1], day: "01" };
  }

  const ruDate = RU_DATE_RE.exec(text);
  if (ruDate) {
    return { year: ruDate[3], month: ruDate[2], day: ruDate[1] };
  }

  const isoMonth = ISO_MONTH_RE.exec(text);
  if (isoMonth) {
    return { year: isoMonth[1], month: isoMonth[2], day: "01" };
  }

  const isoDate = ISO_DATE_RE.exec(text);
  if (isoDate) {
    return { year: isoDate[1], month: isoDate[2], day: isoDate[3] };
  }

  return null;
}

function formatPersonnelDateParts(
  parts: DateParts,
  precision: Exclude<PersonnelDatePrecision, "auto">,
): string {
  switch (precision) {
    case "year":
      return parts.year;
    case "month":
      return formatRuMonth(parts.year, parts.month);
    case "day":
      return formatRuDay(parts.year, parts.month, parts.day);
  }
}

/** Legacy-only helper: infer display precision from stored value shape. Do not use for new UI. */
export function detectPersonnelDatePrecision(value: string): Exclude<PersonnelDatePrecision, "auto"> {
  const text = value.trim();
  if (!text) return "day";
  if (YEAR_RE.test(text)) return "year";

  const ruMonth = RU_MONTH_RE.exec(text);
  if (ruMonth) return "month";

  const ruDate = RU_DATE_RE.exec(text);
  if (ruDate) {
    if (ruDate[1] === "01" && ruDate[2] === "01") return "year";
    if (ruDate[1] === "01") return "month";
    return "day";
  }

  const isoMonth = ISO_MONTH_RE.exec(text);
  if (isoMonth) return "month";

  const isoDate = ISO_DATE_RE.exec(text);
  if (isoDate) {
    if (isoDate[2] === "01" && isoDate[3] === "01") return "year";
    if (isoDate[3] === "01") return "month";
    return "day";
  }

  return "day";
}

export function formatPersonnelDate(
  value: string | null | undefined,
  options: FormatPersonnelDateOptions = {},
): string {
  const empty = options.empty ?? "—";
  const text = String(value ?? "").trim();
  if (!text) return empty;

  const parts = parsePersonnelDateParts(text);
  if (!parts) return text;

  const precision = options.precision ?? "auto";
  const resolved =
    precision === "auto" ? detectPersonnelDatePrecision(text) : precision;

  return formatPersonnelDateParts(parts, resolved);
}

export function formatPersonnelDateRange(
  fromRaw: string | null | undefined,
  toRaw: string | null | undefined,
  options: FormatPersonnelDateOptions = {},
): string {
  const empty = options.empty ?? "—";
  const from = formatPersonnelDate(fromRaw, { ...options, empty: "" });
  const to = formatPersonnelDate(toRaw, { ...options, empty: "" });
  if (!from && !to) return empty;
  if (from && to) return `${from} — ${to}`;
  return from || to;
}

export function formatPersonnelDateTime(value: string | null | undefined): string {
  const text = String(value ?? "").trim();
  if (!text) return "—";

  const isoDateTime = /^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/.exec(text);
  if (isoDateTime) {
    const [, year, month, day, hour, minute] = isoDateTime;
    return `${formatRuDay(year, month, day)}, ${hour}:${minute}`;
  }

  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return formatPersonnelDate(text, { precision: "day", empty: "—" });
  }

  const year = String(date.getFullYear());
  const month = pad2(date.getMonth() + 1);
  const day = pad2(date.getDate());
  const hour = pad2(date.getHours());
  const minute = pad2(date.getMinutes());
  return `${formatRuDay(year, month, day)}, ${hour}:${minute}`;
}

/** Parse UI input back to canonical stored string without inventing fake full dates for year fields. */
export function parsePersonnelDateInput(
  input: string,
  precision: Exclude<PersonnelDatePrecision, "auto">,
): string {
  const text = String(input ?? "").trim();
  if (!text) return "";

  if (ISO_DATE_RE.test(text)) {
    return text;
  }

  const ruDate = RU_DATE_RE.exec(text);
  if (ruDate) {
    const year = ruDate[3];
    const month = ruDate[2];
    const day = ruDate[1];
    if (precision === "year") return year;
    if (precision === "month") return `${year}-${pad2(month)}`;
    return `${year}-${pad2(month)}-${pad2(day)}`;
  }

  const ruMonth = RU_MONTH_RE.exec(text);
  if (ruMonth) {
    if (precision === "year") return ruMonth[2];
    return `${ruMonth[2]}-${pad2(ruMonth[1])}`;
  }

  if (YEAR_RE.test(text)) return text;
  if (/^\d{1,3}$/.test(text)) return text;

  return text;
}
