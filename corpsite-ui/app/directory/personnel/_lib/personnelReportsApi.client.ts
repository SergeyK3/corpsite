import {
  apiFetchJson,
  buildHeaders,
  buildUrl,
  handleAuthFailureIfNeeded,
  readJsonSafe,
  toApiError,
} from "@/lib/api";

export type PersonnelReportGroup = { group_id: number; group_name: string };
export type PersonnelReportDepartment = { unit_id: number; unit_name: string; group_id: number };
export type PersonnelReportOptions = {
  groups: PersonnelReportGroup[];
  departments: PersonnelReportDepartment[];
};
export type PersonnelRosterItem = {
  employee_id: number;
  number: number;
  full_name: string;
  position: string;
  rate: string;
  rate_value: number | null;
};
export type PersonnelRosterSummaryItem = {
  number: number;
  group: { id: number; name: string };
  department: { id: number; name: string };
  employee_count: number;
  rate_total: number;
};
export type PersonnelRosterDepartment = {
  id: number;
  name: string;
  items: PersonnelRosterItem[];
};
export type PersonnelRosterGroup = {
  id: number;
  name: string;
  departments: PersonnelRosterDepartment[];
};
export type PersonnelRosterReport = {
  report_code: "personnel_roster";
  report_name: string;
  generated_at: string;
  filters: {
    group: { id: number; name: string } | null;
    department: { id: number; name: string } | null;
  };
  summary: PersonnelRosterSummaryItem[];
  total: number;
  total_rate: number;
  missing_rate_count: number;
  groups: PersonnelRosterGroup[];
  items: PersonnelRosterItem[];
};

export type PersonnelRosterFilters = {
  groupId?: number;
  orgUnitId?: number;
};

export type PersonnelOrdersSummaryOrder = {
  order_id: number;
  order_number: string | null;
  order_date: string | null;
  order_type_code: string;
  item_type_codes: string[];
  type_label: string;
  employee_names: string[];
  department_names: string[];
  status: string;
  status_label: string;
  category_code: string;
};

export type PersonnelOrdersSummaryCategory = {
  code: string;
  name: string;
  count: number;
  incomplete_count: number;
  orders: PersonnelOrdersSummaryOrder[];
};

export type PersonnelOrdersSummaryReport = {
  report_code: "personnel_orders_summary";
  report_name: string;
  generated_at: string;
  filters: { date_from: string | null; date_to: string | null };
  period_note: string | null;
  categories: PersonnelOrdersSummaryCategory[];
  total_count: number;
  total_incomplete_count: number;
};

export type PersonnelOrdersSummaryFilters = {
  dateFrom?: string;
  dateTo?: string;
};

function rosterPath(filters: PersonnelRosterFilters, suffix = ""): string {
  const params = new URLSearchParams();
  if (filters.groupId) params.set("group_id", String(filters.groupId));
  if (filters.orgUnitId) params.set("org_unit_id", String(filters.orgUnitId));
  const query = params.toString();
  return `/directory/personnel/reports/personnel-roster${suffix}${query ? `?${query}` : ""}`;
}

export function getPersonnelReportOptions(): Promise<PersonnelReportOptions> {
  return apiFetchJson<PersonnelReportOptions>("/directory/personnel/reports/options");
}

export function getPersonnelRoster(filters: PersonnelRosterFilters): Promise<PersonnelRosterReport> {
  return apiFetchJson<PersonnelRosterReport>(rosterPath(filters));
}

export function getPersonnelOrdersSummary(
  filters: PersonnelOrdersSummaryFilters,
): Promise<PersonnelOrdersSummaryReport> {
  const params = new URLSearchParams();
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);
  const query = params.toString();
  return apiFetchJson<PersonnelOrdersSummaryReport>(
    `/directory/personnel/reports/orders-summary${query ? `?${query}` : ""}`,
  );
}

export async function downloadPersonnelRoster(filters: PersonnelRosterFilters): Promise<void> {
  const url = buildUrl(rosterPath(filters, "/excel"));
  const response = await fetch(url, { headers: buildHeaders(), cache: "no-store" });
  if (!response.ok) {
    handleAuthFailureIfNeeded(response.status);
    throw toApiError(response.status, await readJsonSafe(response));
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const filename = encodedName ? decodeURIComponent(encodedName) : "Личный_состав.xlsx";
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
