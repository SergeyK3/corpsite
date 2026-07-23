export type EmploymentTenureYmd = {
  years: number;
  months: number;
  days: number;
};

export type EmploymentTenureRecordResult = {
  record_id: string;
  index: number;
  label: string;
  days: number | null;
  included: boolean;
  is_open_ended: boolean;
  overlaps_other: boolean;
  warning: string | null;
};

export type EmploymentTenureRecordInput = {
  record_id: string;
  organization: string;
  position: string;
  year_from: string | null;
  year_to: string | null;
  reason_for_leaving: string;
};

export type EmploymentTenureCalculation = {
  calculation_date: string;
  records: EmploymentTenureRecordResult[];
  arithmetic_sum_days: number;
  overlap_excluded_days: number;
  total_days: number;
  total_decimal_years: number;
  total_ymd: EmploymentTenureYmd;
};

export function formatTenureDaysCount(days: number): string {
  return new Intl.NumberFormat("ru-RU").format(Math.max(0, days)).replace(/\u00a0/g, " ");
}

export function formatTenureDecimalYears(days: number): string {
  const years = Math.round((Math.max(0, days) / 365.25) * 100) / 100;
  return years.toFixed(2).replace(".", ",");
}

export function formatTenureYearsLabel(days: number): string {
  return `${formatTenureDecimalYears(days)} года`;
}

export function formatTenureDisplay(days: number): string {
  return `${formatTenureYearsLabel(days)} (${formatTenureDaysCount(days)} дней)`;
}

export function formatTenureYmd(ymd: EmploymentTenureYmd): string {
  return `${ymd.years} ${chooseYearWord(ymd.years)} ${ymd.months} ${chooseMonthWord(ymd.months)} ${ymd.days} ${chooseDayWord(ymd.days)}`;
}

function chooseYearWord(value: number): string {
  const integer = Math.floor(Math.abs(value));
  const mod100 = integer % 100;
  if (mod100 >= 11 && mod100 <= 14) return "лет";
  const mod10 = integer % 10;
  if (mod10 === 1) return "год";
  if (mod10 >= 2 && mod10 <= 4) return "года";
  return "лет";
}

function chooseMonthWord(value: number): string {
  const mod100 = value % 100;
  if (mod100 >= 11 && mod100 <= 14) return "месяцев";
  const mod10 = value % 10;
  if (mod10 === 1) return "месяц";
  if (mod10 >= 2 && mod10 <= 4) return "месяца";
  return "месяцев";
}

function chooseDayWord(value: number): string {
  const mod100 = value % 100;
  if (mod100 >= 11 && mod100 <= 14) return "дней";
  const mod10 = value % 10;
  if (mod10 === 1) return "день";
  if (mod10 >= 2 && mod10 <= 4) return "дня";
  return "дней";
}

export const EMPLOYMENT_TENURE_OVERLAP_HINT =
  "Пересекается с другим периодом — в общем стаже учитывается один раз";
