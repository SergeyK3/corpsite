import { redirect } from "next/navigation";
import PersonnelLkSectionPageClient from "../_components/PersonnelLkSectionPageClient";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default async function PersonnelLkWorkplacePage({ searchParams }: Props) {
  const params = await searchParams;
  const report = Array.isArray(params.report) ? params.report[0] : params.report;
  const view = Array.isArray(params.view) ? params.view[0] : params.view;
  if (["categories", "qualification-categories"].includes(report || "") || view === "categories") {
    redirect("/directory/personnel/qualification-categories");
  }
  return <PersonnelLkSectionPageClient />;
}
