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
  number: number;
  full_name: string;
  position: string;
  rate: string;
};
export type PersonnelRosterReport = {
  report_code: "personnel_roster";
  report_name: string;
  generated_at: string;
  group: { id: number; name: string };
  department: { id: number; name: string };
  items: PersonnelRosterItem[];
};

export function getPersonnelReportOptions(): Promise<PersonnelReportOptions> {
  return apiFetchJson<PersonnelReportOptions>("/directory/personnel/reports/options");
}

export function getPersonnelRoster(orgUnitId: number): Promise<PersonnelRosterReport> {
  return apiFetchJson<PersonnelRosterReport>(
    `/directory/personnel/reports/personnel-roster/${orgUnitId}`,
  );
}

export async function downloadPersonnelRoster(orgUnitId: number): Promise<void> {
  const url = buildUrl(`/directory/personnel/reports/personnel-roster/${orgUnitId}/excel`);
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
