import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default async function MigrationStatusPage({ searchParams }: Props) {
  const incoming = await searchParams;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(incoming)) {
    if (key === "view" || key === "report" || value == null) continue;
    for (const part of Array.isArray(value) ? value : [value]) params.append(key, part);
  }
  const legacyReport = Array.isArray(incoming.report) ? incoming.report[0] : incoming.report;
  const legacyView = Array.isArray(incoming.view) ? incoming.view[0] : incoming.view;
  const categories = ["categories", "qualification-categories"].includes(legacyReport || "") || legacyView === "categories";
  if (categories) redirect("/directory/personnel/qualification-categories");
  params.set("view", "reports");
  params.set("report", "cards");
  redirect(`/directory/personnel/lk?${params.toString()}`);
}
