// FILE: corpsite-ui/lib/tenant.ts
export type TenantInfo = {
  orgName: string;
  orgId?: string;
};

let cached: TenantInfo | null = null;

function parseTenantJson(json: Record<string, unknown>): TenantInfo {
  const orgName = String(json.orgName ?? json.organization_name ?? "").trim();
  const orgIdRaw = String(json.orgId ?? json.organization_id ?? json.org_id ?? "").trim();
  return {
    orgName,
    orgId: orgIdRaw || undefined,
  };
}

export async function loadTenant(): Promise<TenantInfo> {
  if (cached) return cached;
  const r = await fetch("/tenant.json", { cache: "no-store" });
  if (!r.ok) return { orgName: "" };
  const json = (await r.json()) as Record<string, unknown>;
  cached = parseTenantJson(json);
  return cached ?? { orgName: "" };
}
