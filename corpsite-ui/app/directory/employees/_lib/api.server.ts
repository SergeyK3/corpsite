// corpsite-ui/app/directory/employees/_lib/api.server.ts

import { notFound } from "next/navigation";
import type { EmployeesResponse } from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "http://127.0.0.1:8000";

function qs(params: Record<string, any>) {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

export async function getEmployees(params: Record<string, any>): Promise<EmployeesResponse> {
  const res = await fetch(`${BASE}/directory/employees${qs(params)}`, { cache: "no-store" });
  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`getEmployees ${res.status}: ${t || res.statusText}`);
  }
  return res.json();
}

export async function getDepartments() {
  const res = await fetch(`${BASE}/directory/departments`, { cache: "no-store" });
  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`getDepartments ${res.status}: ${t || res.statusText}`);
  }
  return res.json();
}

export async function getPositions() {
  const res = await fetch(`${BASE}/directory/positions`, { cache: "no-store" });
  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`getPositions ${res.status}: ${t || res.statusText}`);
  }
  return res.json();
}

// NEW: карточка сотрудника
export async function getEmployeeById(employee_id: string) {
  const res = await fetch(`${BASE}/directory/employees/${encodeURIComponent(employee_id)}`, {
    cache: "no-store",
  });

  if (res.status === 404) {
    notFound();
  }

  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`getEmployeeById ${res.status}: ${t || res.statusText}`);
  }

  return res.json();
}
