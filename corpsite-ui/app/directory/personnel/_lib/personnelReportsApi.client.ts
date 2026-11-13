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

export type PersonnelOrdersSummaryStatus = {
  code: string;
  count: number;
  incomplete_count: number;
  by_category: Record<string, { count: number; incomplete_count: number }>;
};

export type PersonnelOrdersSummaryReport = {
  report_code: "personnel_orders_summary";
  report_name: string;
  generated_at: string;
  filters: { date_from: string | null; date_to: string | null };
  period_note: string | null;
  categories: PersonnelOrdersSummaryCategory[];
  statuses: PersonnelOrdersSummaryStatus[];
  total_count: number;
  total_incomplete_count: number;
};

export type PersonnelOrdersSummaryFilters = {
  dateFrom?: string;
  dateTo?: string;
};

export type PersonnelOrdersMonthlyType = "HIRE" | "TERMINATION" | "TRANSFER";

export type PersonnelOrdersMonthlyDashboard = {
  report_code: "personnel_orders_monthly_dashboard";
  year: number;
  as_of: string;
  order_type: PersonnelOrdersMonthlyType | null;
  months: Array<{ month: number; count: number; is_current: boolean }>;
  total: number;
};

export type PersonnelTypeHeadcountReport = {
  report_code: "personnel_type_headcount";
  groups: Array<{ code: number | null; name: string; count: number }>;
  unknown_employees: Array<{
    employee_id: number;
    full_name: string | null;
    org_unit_name: string | null;
    position_name: string | null;
  }>;
  total: number;
};

export function getPersonnelTypeHeadcountReport(): Promise<PersonnelTypeHeadcountReport> {
  return apiFetchJson<PersonnelTypeHeadcountReport>("/directory/personnel/reports/personnel-type-headcount");
}

export type PersonnelHeadcountTrend = {
  report_code: "personnel_headcount_trend";
  year: number;
  as_of: string;
  history_complete: boolean;
  months: Array<{
    month: number;
    date: string;
    count: number | null;
    source: "active_register" | "approved_employee_events" | null;
    is_current: boolean;
  }>;
};

export function getPersonnelHeadcountTrend(): Promise<PersonnelHeadcountTrend> {
  return apiFetchJson<PersonnelHeadcountTrend>("/directory/personnel/reports/headcount-trend");
}

export type PersonnelEmployeeActionType = { code: string; label: string; count: number };
export type PersonnelEmployeeOrder = {
  order_id: number;
  order_number: string | null;
  order_date: string | null;
  status: "SIGNED" | "REGISTERED";
  status_label: string;
  is_composite: boolean;
  actions: PersonnelEmployeeActionType[];
};
export type PersonnelEmployeeActionsRow = {
  employee_id: number;
  full_name: string;
  org_unit_id: number | null;
  org_unit_name: string | null;
  order_count: number;
  ordinary_order_count: number;
  composite_order_count: number;
  action_count: number;
  actions_by_type: PersonnelEmployeeActionType[];
  orders: PersonnelEmployeeOrder[];
};
export type PersonnelEmployeeActionsReport = {
  report_code: "personnel_employee_actions";
  employees: PersonnelEmployeeActionsRow[];
};

export function getPersonnelEmployeeActionsReport(): Promise<PersonnelEmployeeActionsReport> {
  return apiFetchJson<PersonnelEmployeeActionsReport>("/directory/personnel/reports/employee-actions");
}

export type StaffingReport = { data_quality: { requires_review: boolean; message: string | null }; metrics: { current_headcount: number; hired: number; terminated: number; average_headcount: number; average_formula: string; turnover_numerator: number; turnover_percent: number; turnover_reasons: Array<{ reason: string; count: number }> }; hired_items: Array<{ full_name: string; date: string; group_name?: string; unit_name?: string }>; terminated_items: Array<{ full_name: string; date: string; reason: string; group_name?: string; unit_name?: string }>; breakdown: Array<{ label: string; group_name?: string; current_headcount: number; average_headcount: number; hired: number; terminated: number; turnover_terminated: number; turnover_percent: number }> };
export type StaffingReportFilters = { dateFrom: string; dateTo: string; groupId?: number; orgUnitId?: number; breakdown: "total" | "groups" | "units" };

export function getStaffingReport(filters: StaffingReportFilters): Promise<StaffingReport> {
  const params = new URLSearchParams({ date_from: filters.dateFrom, date_to: filters.dateTo, breakdown: filters.breakdown });
  if (filters.groupId) params.set("group_id", String(filters.groupId));
  if (filters.orgUnitId) params.set("org_unit_id", String(filters.orgUnitId));
  return apiFetchJson<StaffingReport>(`/directory/personnel/reports/staffing?${params}`);
}

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

export function getPersonnelOrdersMonthlyDashboard(
  orderType?: PersonnelOrdersMonthlyType | null,
): Promise<PersonnelOrdersMonthlyDashboard> {
  const params = new URLSearchParams();
  if (orderType) params.set("order_type", orderType);
  const query = params.toString();
  return apiFetchJson<PersonnelOrdersMonthlyDashboard>(
    `/directory/personnel/reports/orders-monthly-dashboard${query ? `?${query}` : ""}`,
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
