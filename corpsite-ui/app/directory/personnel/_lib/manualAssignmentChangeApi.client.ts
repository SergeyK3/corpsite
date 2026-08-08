import { apiFetchJson } from "@/lib/api";

export type ManualAssignmentChangeRequest = {
  expected_assignment_id: number;
  org_unit_id: number;
  position_id: number;
  start_date: string;
  idempotency_key: string;
  comment?: string;
};

export type ManualAssignmentChangeResponse = {
  result: {
    employee_id: number;
    person_id: number;
    predecessor_assignment_id: number;
    successor_assignment_id: number;
    event_id: number;
    audit_id: number;
    already_applied: boolean;
  };
};

export function changeEmployeeAssignment(
  employeeId: string | number,
  body: ManualAssignmentChangeRequest,
): Promise<ManualAssignmentChangeResponse> {
  return apiFetchJson<ManualAssignmentChangeResponse>(
    `/directory/employees/${encodeURIComponent(String(employeeId))}/assignment-change`,
    { method: "POST", body },
  );
}
