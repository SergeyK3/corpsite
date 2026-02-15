// FILE: corpsite-ui/lib/tenant.ts
export type TenantInfo = { orgName: string };

let cached: TenantInfo | null = null;

export async function loadTenant(): Promise<TenantInfo> {
  if (cached) return cached;
  const r = await fetch("/tenant.json", { cache: "no-store" });
  if (!r.ok) return { orgName: "" };
  cached = (await r.json()) as TenantInfo;
  return cached ?? { orgName: "" };
}
