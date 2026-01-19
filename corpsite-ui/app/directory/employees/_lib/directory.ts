// corpsite-ui/app/directory/employees/_lib/directory.ts

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

function getApiBase(): string {
  const base =
    _trim(process.env.NEXT_PUBLIC_API_BASE_URL) ??
    _trim(process.env.BACKEND_URL) ??
    "http://127.0.0.1:8000";

  return base.replace(/\/+$/, "");
}

function getDevUserId(): string | undefined {
  // ВАЖНО: только прямой доступ, иначе Next.js не инлайнит в client bundle
  return _trim(process.env.NEXT_PUBLIC_DEV_X_USER_ID);
}

export async function getOrgTree(): Promise<OrgTreeResponse> {
  const base = getApiBase();
  const url = `${base}/directory/org-units/tree`;

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
