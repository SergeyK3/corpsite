// corpsite-ui/app/directory/employees/_lib/directory.ts

import { resolveApiUrl } from "@/lib/apiBase";

export type OrgTreeNode = {
  unit_id: number;
  name: string;
  code?: string | null;
  parent_unit_id?: number | null;
  is_active?: boolean;
  children?: OrgTreeNode[];
};

export type OrgTreeResponse = {
  items: OrgTreeNode[];
};

function _trim(v?: string): string | undefined {
  const s = (v || "").trim();
  return s ? s : undefined;
}

function getDevUserId(): string | undefined {
  const appEnv = _trim(process.env.NEXT_PUBLIC_APP_ENV) ?? _trim(process.env.APP_ENV) ?? "dev";
  if (appEnv.toLowerCase() === "prod" || appEnv.toLowerCase() === "production") {
    return undefined;
  }
  return _trim(process.env.NEXT_PUBLIC_DEV_X_USER_ID);
}

export async function getOrgTree(): Promise<OrgTreeResponse> {
  const url = resolveApiUrl("/directory/org-units/tree");

  const headers: Record<string, string> = { Accept: "application/json" };

  const uid = getDevUserId();
  if (uid) headers["X-User-Id"] = uid;

  const res = await fetch(url, { headers, cache: "no-store" });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`OrgTree request failed (${res.status}: ${text})`);
  }

  const data = await res.json();
  return Array.isArray(data) ? { items: data } : (data as OrgTreeResponse);
}
