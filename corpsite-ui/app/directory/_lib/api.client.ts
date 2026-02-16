// FILE: corpsite-ui/app/directory/_lib/api.client.ts
"use client";

import { apiFetchJson } from "../../../lib/api";

export type Department = {
  unit_id?: number;
  department_id?: number;
  id?: number;
  code?: string;
  name_ru?: string;
  name_en?: string;
  name?: string;
};

export type Employee = {
  employee_id?: number;
  user_id?: number;
  tab_no?: string;
  full_name?: string;
  department?: string;
  unit_id?: number;
  position?: string;
  rate?: number;
  date_from?: string;
  date_to?: string | null;
  is_active?: boolean;
};

export async function apiDirectoryDepartments(): Promise<Department[]> {
  // важно: именно через apiFetchJson -> будет Authorization
  const body = await apiFetchJson<any>("/directory/departments");
  return Array.isArray(body) ? (body as Department[]) : (body?.items ?? []);
}

export async function apiDirectoryEmployees(params?: {
  q?: string;
  unit_id?: number;
  position?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<Employee[]> {
  const body = await apiFetchJson<any>("/directory/employees", {
    query: {
      q: params?.q ?? undefined,
      unit_id: params?.unit_id ?? undefined,
      position: params?.position ?? undefined,
      status: params?.status ?? undefined,
      limit: params?.limit ?? 50,
      offset: params?.offset ?? 0,
    },
  });

  return Array.isArray(body) ? (body as Employee[]) : (body?.items ?? []);
}
