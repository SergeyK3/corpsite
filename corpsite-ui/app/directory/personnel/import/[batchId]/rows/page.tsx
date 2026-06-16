import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ batchId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function PersonnelImportRowsPage({ params, searchParams }: Props) {
  const { batchId } = await params;
  const sp = await searchParams;
  const q = new URLSearchParams();
  Object.entries(sp).forEach(([k, v]) => {
    if (typeof v === "string") q.set(k, v);
  });
  if (!q.has("mode")) {
    const scope = q.get("roster_scope");
    if (scope === "declaration") q.set("mode", "declaration");
    else if (scope === "technical") q.set("mode", "technical");
    else q.set("mode", "personnel");
    q.delete("roster_scope");
  }
  const qs = q.toString();
  redirect(`/directory/personnel/import/${batchId}/review${qs ? `?${qs}` : ""}`);
}
